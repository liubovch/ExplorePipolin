import os
from copy import deepcopy
from typing import MutableSequence, Tuple, Sequence

from Bio.SeqFeature import SeqFeature, FeatureLocation
from Bio.SeqRecord import SeqRecord
from prefect import task

from explore_pipolin.common import Strand, Pipolin, FeatureType, ContigID, Genome, PipolinVariants, AttFeature, \
    get_rec_id_by_contig_id, Range
from explore_pipolin.tasks.easyfig_coloring import easyfig_add_colours
from explore_pipolin.utilities.io import SeqIORecords, create_seqio_records_dict, write_seqio_records, \
    read_gff_records, write_gff_records, read_colours, PRODUCTS_TO_COLOUR
from explore_pipolin.utilities.logging import genome_specific_logging
import explore_pipolin.settings as settings


@task()
@genome_specific_logging
def generate_results(genome: Genome, prokka_dir, pipolins: Sequence[PipolinVariants]):
    results_dir = os.path.join(os.path.dirname(prokka_dir), 'pipolins')
    os.makedirs(results_dir, exist_ok=True)

    for prokka_file in os.listdir(prokka_dir):

        if prokka_file.startswith(genome.id) and (prokka_file.endswith('.gbk') or prokka_file.endswith('.gff')):
            # genome_NvN.type.ext
            nvn = os.path.splitext(os.path.splitext(prokka_file)[0])[0].split(sep='_')[-1]
            index, variant = nvn.split(sep='v')

            cur_pipolin = pipolins[int(index)].variants[int(variant)]

            if prokka_file.endswith('.gbk'):
                gb_records = create_seqio_records_dict(file=os.path.join(prokka_dir, prokka_file),
                                                       file_format='genbank')

                include_atts_into_gb(gb_records=gb_records, pipolin=cur_pipolin)
                mark_integration_sites(records=gb_records, pipolin=cur_pipolin)
                accver = os.path.splitext(prokka_file)[0]
                add_acc_version(records=gb_records, accver=accver)
                if settings.get_instance().skip_colours is False:
                    easyfig_add_colours(gb_records=gb_records, pipolin=cur_pipolin)

                single_record = create_single_gb_record(gb_records=gb_records, pipolin=cur_pipolin, accver=accver)
                output_file_single_record = os.path.join(
                    results_dir, os.path.splitext(prokka_file)[0] + '.single_record.gbk'
                )
                write_seqio_records(single_record, output_file_single_record, 'genbank')

                output_file = os.path.join(results_dir, prokka_file)
                write_seqio_records(gb_records, output_file, 'genbank')

            if prokka_file.endswith('.gff'):
                gff_records = read_gff_records(file=os.path.join(prokka_dir, prokka_file))
                include_atts_into_gff(gff_records=gff_records, pipolin=cur_pipolin)
                mark_integration_sites(records=gff_records, pipolin=cur_pipolin)

                output_file = os.path.join(results_dir, prokka_file)
                write_gff_records(gff_records=gff_records, output_file=output_file)

    return results_dir


def create_single_gb_record(gb_records: SeqIORecords, pipolin: Pipolin, accver: str) -> SeqIORecords:
    record = deepcopy(gb_records[get_rec_id_by_contig_id(gb_records, pipolin.fragments[0].contig_id)])
    record = revcompl_if_reverse(record, pipolin.fragments[0].orientation)
    if len(pipolin.fragments) > 1:
        for fragment in pipolin.fragments[1:]:
            # insert assembly gap from the reconstruction step
            record += SeqRecord(seq='N' * 100)
            record.features.insert(len(record.features), create_reconstruction_gap_feature(record))
            # delete fragment's source feature
            del gb_records[get_rec_id_by_contig_id(gb_records, fragment.contig_id)].features[0]
            record += revcompl_if_reverse(
                gb_records[get_rec_id_by_contig_id(gb_records, fragment.contig_id)],
                fragment.orientation
            )

    old_source = record.features[0]
    new_source = SeqFeature(FeatureLocation(0, len(record), 1), type=old_source.type,
                            location_operator=old_source.location_operator, strand=old_source.strand,
                            id=old_source.id, qualifiers=old_source.qualifiers,
                            ref=old_source.ref, ref_db=old_source.ref_db)
    del record.features[0]
    record.features.insert(0, new_source)

    record.name = 'PIPOLIN_RECORD'
    record.id = accver
    return {pipolin.fragments[0].genome.id: record}


def create_reconstruction_gap_feature(record: SeqRecord) -> SeqFeature:
    record_length = len(record)
    qualifiers = {'estimated_length': ['unknown'],
                  'gap_type': ['between scaffolds'],
                  'linkage_evidence': ['pipolin_structure'],
                  'inference': ['ExplorePipolin']}
    if settings.get_instance().skip_colours is False:
        colours = settings.get_instance().colours
        read_colours(colours)
        if 'pipolin_structure' in PRODUCTS_TO_COLOUR:
            qualifiers['colour'] = PRODUCTS_TO_COLOUR['pipolin_structure']
    return SeqFeature(FeatureLocation(start=record_length - 100, end=record_length),
                      type='assembly_gap', qualifiers=qualifiers)


def revcompl_if_reverse(gb_record: SeqRecord, orientation: Strand) -> SeqRecord:
    if orientation == Strand.REVERSE:
        return gb_record.reverse_complement(id=True, name=True, description=True, annotations=True)
    return gb_record


def include_atts_into_gb(gb_records: SeqIORecords, pipolin: Pipolin):
    att_seq_features = _generate_att_seq_features(record_format='gb', pipolin=pipolin)
    for att in att_seq_features:
        _add_att_seq_feature(
            att_seq_feature=att[0],
            seq_record=gb_records[get_rec_id_by_contig_id(gb_records, att[1])]
        )


def include_atts_into_gff(gff_records: SeqIORecords, pipolin: Pipolin):
    att_seq_features = _generate_att_seq_features(record_format='gff', pipolin=pipolin)
    for att in att_seq_features:
        _add_att_seq_feature(
            att_seq_feature=att[0],
            seq_record=gff_records[get_rec_id_by_contig_id(gff_records, att[1])]
                             )


def _generate_att_seq_features(record_format: str, pipolin: Pipolin):
    att_seq_features: MutableSequence[Tuple[SeqFeature, ContigID]] = []

    for fragment in pipolin.fragments:
        fragment_shift = fragment.start

        for i, att in enumerate([f for f in fragment.features if f.ftype == FeatureType.ATT]):
            att: AttFeature
            att_start, att_end = (att.start - fragment_shift), (att.end - fragment_shift)
            locus_tag = f'{att.contig_id}_{"0" * (5 - len(str(i)))}{i}'   # always 5 digits, starting from zeros
            if record_format == 'gb':
                att_feature = _create_gb_att_seq_feature(start=att_start, end=att_end, strand=att.strand,
                                                         att_locus_tag=locus_tag,
                                                         note=att.att_type.to_string())
            elif record_format == 'gff':
                att_feature = _create_gff_att_seq_feature(start=att_start, end=att_end, strand=att.strand,
                                                          att_locus_tag=locus_tag,
                                                          note=att.att_type.to_string())
            else:
                raise AssertionError

            att_seq_features.append((att_feature, fragment.contig_id))

    return att_seq_features


def _create_gb_att_seq_feature(start: int, end: int, strand: Strand, att_locus_tag: str, note: str) -> SeqFeature:
    gb_qualifiers = {'inference': ['BLAST search'], 'locus_tag': [att_locus_tag],
                     'rpt_family': ['Att'], 'rpt_type': ['direct'], 'note': [note]}
    att_seq_feature = SeqFeature(type='repeat_region',
                                 location=FeatureLocation(start=start, end=end, strand=strand.to_pm_one_encoding()),
                                 qualifiers=gb_qualifiers)
    return att_seq_feature


def _create_gff_att_seq_feature(start: int, end: int, strand: Strand, att_locus_tag: str, note: str) -> SeqFeature:
    gff_qualifiers = {'phase': ['.'], 'source': ['BLAST search'],
                      'ID': [att_locus_tag], 'inference': ['BLAST search'],
                      'locus_tag': [att_locus_tag],
                      'rpt_family': ['Att'], 'rpt_type': ['direct'], 'note': [note]}
    att_seq_feature = SeqFeature(type='repeat_region',
                                 location=FeatureLocation(start=start, end=end, strand=strand.to_pm_one_encoding()),
                                 qualifiers=gff_qualifiers)
    return att_seq_feature


def _add_att_seq_feature(att_seq_feature: SeqFeature, seq_record: SeqRecord):
    seq_record.features.append(att_seq_feature)
    seq_record.features.sort(key=lambda x: x.location.start)


def mark_integration_sites(records: SeqIORecords, pipolin: Pipolin) -> None:
    for fragment in pipolin.fragments:
        fragment_shift = fragment.start

        for ttrna in [f for f in fragment.features if f.ftype == FeatureType.TARGET_TRNA]:
            ttrna_start, ttrna_end = (ttrna.start - fragment_shift), (ttrna.end - fragment_shift)
            ttrna_range = Range(start=ttrna_start, end=ttrna_end)

            for feature in records[get_rec_id_by_contig_id(records, fragment.contig_id)].features:
                feature_range = Range(start=feature.location.start, end=feature.location.end)
                if feature.type == 'tRNA' and feature_range.is_overlapping(ttrna_range):
                    feature.qualifiers['note'] = ['integration site']


def add_acc_version(records: SeqIORecords, accver: str) -> None:
    for record in records.values():
        record.id = accver
        record.description = ''
