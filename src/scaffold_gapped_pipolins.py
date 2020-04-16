#!/usr/bin/env python3
# -*- encoding: utf-8 -*-

import os
import click
from prefect import task
from Bio.Seq import Seq
from Bio.Alphabet.IUPAC import IUPACAmbiguousDNA
from Bio.SeqFeature import SeqFeature, FeatureLocation
from Bio.SeqRecord import SeqRecord
from utilities import CONTEXT_SETTINGS, Contig
from utilities import read_seqio_records, write_genbank_records
from utilities import write_gff_records
from utilities import write_fna_records
from utilities import SeqIORecords
from utilities import PipolinFragment, GQuery

# Useful link to check feature's qualifiers: https://www.ebi.ac.uk/ena/WebFeat/
# https://github.com/biopython/biopython/issues/1755


def get_atts_from_record(record):
    atts = []
    for i_f, feature in enumerate(record.features):
        if feature.type == 'repeat_region':
            atts.append((feature.location.start, feature.location.end, i_f))
    return atts


def get_polbs_from_record(record):
    polbs = []
    for i_f, feature in enumerate(record.features):
        if 'gene' in feature.qualifiers:
            if feature.qualifiers['gene'] == ['pi-polB']:
                polbs.append((feature.location.start, feature.location.end, i_f))
    return polbs


def get_trna_end(trna_record):
    for feature in trna_record.features:
        if feature.type == 'tRNA':
            if feature.qualifiers['product'] == ['tRNA-Leu']:
                return feature.location.end




def create_assembly_gap_record(record):
    source_feature = SeqFeature(type='source', location=FeatureLocation(1, 100, strand=+1),
                                qualifiers={'mol_type': record.features[0].qualifiers['mol_type'],
                                            'organism': record.features[0].qualifiers['organism'],
                                            'strain': record.features[0].qualifiers['strain']})
    assembly_gap_seq = Seq('N' * 100, alphabet=IUPACAmbiguousDNA())
    assembly_gap_qualifiers = {'estimated_length': ['unknown'],
                               'gap_type': ['within_scaffolds'],
                               'linkage_evidence': ['pipolin_structure']}
    assembly_gap_feature = SeqFeature(type='assembly_gap',
                                      location=FeatureLocation(1, 100, strand=+1),
                                      qualifiers=assembly_gap_qualifiers)
    assembly_gap_record = SeqRecord(seq=assembly_gap_seq, id=record.id, name=record.name,
                                    description=record.description, features=[source_feature, assembly_gap_feature],
                                    annotations=record.annotations)

    return assembly_gap_record


def add_assembly_gap_to_unchangeable(record):
    assembly_gap_record = create_assembly_gap_record(record)
    atts = get_atts_from_record(record)
    polbs = get_polbs_from_record(record)

    modified_record = assembly_gap_record + record if atts[-1][2] > polbs[-1][2] else record + assembly_gap_record
    return modified_record


def get_assembly_gap_position(unchangeable_record):
    for i_f, feature in enumerate(unchangeable_record.features):
        if feature.type == 'assembly_gap':
            if 'pipolin_structure' in feature.qualifiers['linkage_evidence']:
                return i_f


def glue_unchangeable_and_att(unchangeable_record, att_record, long) -> SeqRecord:
    gap_position = get_assembly_gap_position(unchangeable_record)
    if gap_position == 1:
        att_record = cut_att_contig(att_record, 'left', long)
        glued_record = att_record + unchangeable_record
    else:
        att_record = cut_att_contig(att_record, 'right', long)
        glued_record = unchangeable_record + att_record
    return glued_record


def check_trna(att_record):
    atts = get_atts_from_record(att_record)
    for att in atts:
        left_feature = att_record.features[att[2] - 1] if att[2] - 1 >= 0 else None
        right_feature = att_record.features[att[2] + 1] if att[2] + 1 < len(att_record.features) else None
        if left_feature is not None and left_feature.type == 'tRNA':
            if 'product' in left_feature.qualifiers:
                if left_feature.qualifiers['product'] == ['tRNA-Leu']:
                    return True
        if right_feature is not None and right_feature.type == 'tRNA':
            if 'product' in right_feature.qualifiers:
                if right_feature.qualifiers['product'] == ['tRNA-Leu']:
                    return True


def cut_att_contig(att_record, direction, long):
    atts = get_atts_from_record(att_record)
    if direction == 'right':
        if long and len(atts) != 1:
            new_att_record = att_record[:atts[1][1] + 50]
        else:
            new_att_record = att_record[:atts[0][1] + 50]
    else:
        new_att_record = att_record[atts[0][0] - 50:]
    source_feature = SeqFeature(type='source', location=FeatureLocation(1, len(new_att_record), strand=+1),
                                qualifiers={'mol_type': att_record.features[0].qualifiers['mol_type'],
                                            'organism': att_record.features[0].qualifiers['organism'],
                                            'strain': att_record.features[0].qualifiers['strain']})
    new_att_record.features.insert(0, source_feature)

    return new_att_record


def cut_trna_contig(trna_record):
    trna_end = get_trna_end(trna_record)
    new_trna_record = trna_record[:trna_end + 50]
    source_feature = SeqFeature(type='source', location=FeatureLocation(1, len(new_trna_record), strand=+1),
                                qualifiers={'mol_type': trna_record.features[0].qualifiers['mol_type'],
                                            'organism': trna_record.features[0].qualifiers['organism'],
                                            'strain': trna_record.features[0].qualifiers['strain']})
    new_trna_record.features.insert(0, source_feature)

    return new_trna_record


def modify_polb_only_record(polb_contigs, record_set):
    if len(polb_contigs) != 1:
        raise NotImplementedError
    polbs = get_polbs_from_record(record_set[polb_contigs[0]])
    if len(polbs) != 1:
        raise NotImplementedError
    else:
        print(f'>>> The polB contig is {polb_contigs[0]}!')
        assembly_gap = create_assembly_gap_record(record_set[polb_contigs[0]])
        record_set[polb_contigs[0]] = assembly_gap + record_set[polb_contigs[0]] + assembly_gap


        # start, end = gquery.get_unchangeable_bounds(unchangeable_contig.contig_id)
    # else:
    #     gap_position = get_assembly_gap_position(record_set[unchangeable_contig[0]])
    #     direction = 'left' if gap_position == 1 else 'right'
    #     trna_contig = get_trna_contig(record_set, att_only_contigs)
    #     if trna_contig is None:
    #         raise NotImplementedError
    #     else:
    #         att_only_contigs.remove(trna_contig)
    #
    #         trna_record = cut_trna_contig(record_set[trna_contig])
    #         gap = create_assembly_gap_record(record_set[unchangeable_contig[0]])
    #
    #         if len(att_only_contigs) == 1:
    #             print('The single record was assembled!!!\n')
    #             if direction == 'right':
    #                 att_record = cut_att_contig(record_set[att_only_contigs[0]], 'right', long)
    #                 short_pipolin = record_set[unchangeable_contig[0]] + att_record
    #                 if long:
    #                     return short_pipolin + gap + trna_record
    #                 else:
    #                     return short_pipolin
    #             if direction == 'left':
    #                 att_record = cut_att_contig(record_set[att_only_contigs[0]], 'left', long)
    #                 short_pipolin = att_record + record_set[unchangeable_contig[0]]
    #                 if long:
    #                     return short_pipolin + gap + trna_record
    #                 else:
    #                     return short_pipolin
    #         else:
    #             raise NotImplementedError


def is_inside_fragment(feature, fragment_start, fragment_end):
    return feature.start >= fragment_start and feature.end <= fragment_end


@task
def is_scaffolding_required(gquery: GQuery):
    if gquery.is_single_contig() or gquery.is_on_the_same_contig():
        print('>>>Scaffolding is not required!')
        start, end = gquery.get_pipolin_bounds()
        pipolin = PipolinFragment(contig=gquery.polbs[0].contig, start=start, end=end)

        pipolin.atts.extend(gquery.atts)
        gquery.pipolin_fragments.append(pipolin)
    else:
        print('>>>Scaffolding is required!')
        gquery.try_creating_single_record()


# def scaffold_gapped_pipolins_(in_dir, out_dir, long):
#     gb_records = read_seqio_records(in_dir)
#     assemble_gapped_pipolins(gb_records, long)
#     new_dir = os.path.join(out_dir, 'prokka_atts_scaffolded')
#     os.makedirs(new_dir, exist_ok=True)
#     write_genbank_records(gb_records, new_dir)
#     write_gff_records(gb_records, new_dir)
#     write_fna_records(gb_records, new_dir)
#
#     return new_dir


@click.command(context_settings=CONTEXT_SETTINGS)
@click.argument('in-dir', type=click.Path(exists=True))
@click.argument('out-dir', type=click.Path())
@click.option('--long', is_flag=True, help='If long, pipolin regions are identified by leftmost and rightmost '
                                           'atts. If it is not specified, the closest atts to pi-polB will determine '
                                           'the pipolin bounds.')
def main(in_dir, out_dir, long):
    """
    The script takes IN_DIR with *.gbk files (generated after annotation and with included atts),
    detects not assembled pipolins and tries to order the contigs into one sequence,
    filling in gaps with NNs and adding the /assembly_gap feature to the *.gbk files.
    TODO: also learn how to scaffold long pipolins!
    """
    is_scaffolding_required(in_dir, out_dir, long)


if __name__ == '__main__':
    main()
