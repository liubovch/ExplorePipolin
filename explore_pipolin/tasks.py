"""
All the tasks should be defined in this file!
"""
import os
from prefect import task
from prefect import context
from prefect.engine import signals

from Bio.SeqRecord import SeqRecord
from Bio import SeqIO
from typing import Any, Optional

from explore_pipolin.utilities.easyfig_coloring import add_colours
from explore_pipolin.common import Feature, Orientation, FeatureType
from explore_pipolin.utilities.logging import log_genome_id
from explore_pipolin.utilities.misc import GQuery, feature_from_blasthit
from explore_pipolin.utilities.io import read_blastxml, write_repeats, write_atts_denovo
from explore_pipolin.utilities.io import read_seqio_records
from explore_pipolin.utilities.io import read_aragorn_batch
from explore_pipolin.utilities.atts_denovo_search import find_repeats
from explore_pipolin.utilities.external_tools import tblastn_against_ref_pipolb, blastn_against_ref_att
from explore_pipolin.utilities.external_tools import run_prokka, run_aragorn
from explore_pipolin.utilities.misc import create_fragment_record
from explore_pipolin.utilities.io import read_gff_records
from explore_pipolin.utilities.including_atts_into_annotation import include_atts_into_gb
from explore_pipolin.utilities.including_atts_into_annotation import include_atts_into_gff
from explore_pipolin.utilities.io import write_genbank_records
from explore_pipolin.utilities.io import write_gff_records
from explore_pipolin.utilities.io import create_genome_from_file
from explore_pipolin.utilities.scaffolding import Scaffolder, create_pipolin_fragments_single_contig


@task
def create_gquery(genome_file) -> GQuery:
    return GQuery(genome=create_genome_from_file(genome_file))


@task()
@log_genome_id
def run_blast_against_pipolb(gquery, ref_pipolb, out_dir):
    blast_results_dir = os.path.join(out_dir, 'polb_blast')
    os.makedirs(blast_results_dir, exist_ok=True)
    tblastn_against_ref_pipolb(genome=gquery.genome.genome_file, ref_pipolb=ref_pipolb, out_dir=blast_results_dir)
    return blast_results_dir


@task()
@log_genome_id
def run_blast_against_att(gquery, ref_att, out_dir):
    blast_results_dir = os.path.join(out_dir, 'att_blast')
    os.makedirs(blast_results_dir, exist_ok=True)
    blastn_against_ref_att(genome=gquery.genome.genome_file, ref_att=ref_att, out_dir=blast_results_dir)
    return blast_results_dir


@task()
@log_genome_id
def add_features_from_blast(gquery: GQuery, blast_dir, feature_type: FeatureType) -> GQuery:
    entries = read_blastxml(blast_xml=os.path.join(blast_dir, f'{gquery.genome.genome_id}.fmt5'))
    for entry in entries:
        for hit in entry:
            feature = feature_from_blasthit(hit=hit, contig_id=entry.id, genome=gquery.genome)
            gquery.get_features_by_type(feature_type).append(feature)

    return gquery


@task()
@log_genome_id
def detect_trnas_with_aragorn(gquery, out_dir):
    aragorn_results_dir = os.path.join(out_dir, 'aragorn_results')
    os.makedirs(aragorn_results_dir, exist_ok=True)
    run_aragorn(genome=gquery.genome.genome_file, aragorn_results_dir=aragorn_results_dir)
    return aragorn_results_dir


@task()
@log_genome_id
def add_features_from_aragorn(gquery: GQuery, aragorn_results_dir) -> GQuery:
    entries = read_aragorn_batch(aragorn_batch=os.path.join(aragorn_results_dir, f'{gquery.genome.genome_id}.batch'))
    for contig_id, hits in entries.items():
        for hit in hits:
            feature = Feature(start=hit[0], end=hit[1], strand=hit[2], contig_id=contig_id, genome=gquery.genome)
            gquery.trnas.append(feature)
    for att in gquery.atts:
        target_trna = gquery.find_target_trna(att)
        if target_trna is not None:
            gquery.target_trnas.append(target_trna)

    return gquery


@task()
@log_genome_id
def are_pipolbs_present(gquery: GQuery):
    logger = context.get('logger')

    if len(gquery.pipolbs) == 0:
        logger.warning('No piPolBs were found!')
        return False

    return True


@task
def return_result_if_true_else_none(result_to_filter: Any, filter_by: bool) -> Optional[Any]:
    if filter_by:
        return result_to_filter

    return None


@task()
@log_genome_id
def find_atts_denovo(gquery: GQuery, out_dir):
    logger = context.get('logger')

    if not gquery.genome.is_single_contig():
        logger.warning('This step is only for complete genomes. Pass...')
        raise signals.SKIP()

    atts_denovo_dir = os.path.join(out_dir, 'atts_denovo')
    os.makedirs(atts_denovo_dir, exist_ok=True)

    repeats = find_repeats(gquery, atts_denovo_dir)
    write_repeats(gquery, repeats, atts_denovo_dir)

    atts_denovo = [(rep.left, rep.right) for rep in repeats if gquery.is_att_denovo(rep.left, rep.right)]
    write_atts_denovo(atts_denovo, gquery, atts_denovo_dir)

    return atts_denovo_dir


@task()
@log_genome_id
def add_features_atts_denovo(gquery: GQuery, atts_denovo_dir):
    with open(os.path.join(atts_denovo_dir, gquery.genome.genome_id + '.atts')) as inf:
        _ = inf.readline()
        for line in inf:
            att_pair = [int(i) for i in line.strip().split(sep='\t')]
            gquery.denovo_atts.append(Feature(start=att_pair[0], end=att_pair[1],
                                              strand=Orientation.FORWARD,
                                              contig_id=gquery.genome.get_complete_genome_contig_id(),
                                              genome=gquery.genome))
            gquery.denovo_atts.append(Feature(start=att_pair[2], end=att_pair[3],
                                              strand=Orientation.FORWARD,
                                              contig_id=gquery.genome.get_complete_genome_contig_id(),
                                              genome=gquery.genome))

    for att in gquery.denovo_atts:
        target_trna = gquery.find_target_trna(att)
        if target_trna is not None:
            gquery.target_trnas_denovo.append(target_trna)


@task(skip_on_upstream_skip=False)
@log_genome_id
def are_atts_present(gquery: GQuery):
    logger = context.get('logger')

    if len(gquery.atts) == 0 and len(gquery.denovo_atts) == 0:
        logger.warning('\n\n>>>There is piPolB, but no atts were found! Not able to define pipolin bounds!\n')
        # TODO: probably, it makes sense to output piPolB(s) alone
        # raise signals.SKIP() # let's try cutting from both sides and proceed with annotation

    elif len(gquery.atts) == 0:
        logger.warning(f'\n\n>>>No "usual" atts were found, but some atts were found by denovo search!'
                       f'For more details, check the {gquery.genome.genome_id}.atts file '
                       f'in the atts_denovo directory!\n')
        # TODO: check that it's only one repeat! Although, this shouldn't be a problem.
        atts_frames = [att.strand for att in gquery.denovo_atts]
        if len(set(atts_frames)) != 1:
            raise AssertionError('ATTs are expected to be in the same frame, as they are direct repeats!')
        if set(atts_frames).pop() == gquery.target_trnas_denovo[0].strand:
            reverse_denovo_atts = []
            for att in gquery.denovo_atts:
                reverse_denovo_atts.append(Feature(start=att.start, end=att.end, strand=-att.strand,
                                                   contig_id=att.contig, genome=gquery.genome))
            gquery.atts.extend(reverse_denovo_atts)
        else:
            gquery.atts.extend(gquery.denovo_atts)
        gquery.target_trnas.extend(gquery.target_trnas_denovo)

    elif len(gquery.denovo_atts) != 0:
        logger.warning(f'\n\n>>>Some atts were found by denovo search, but we are not going to use them!'
                       f'For more details, check the {gquery.genome.genome_id}.atts file '
                       f'in the atts_denovo directory!\n')

    return gquery


@task()
@log_genome_id
def analyse_pipolin_orientation(gquery: GQuery):
    gquery.is_single_target_trna_per_contig()
    for contig in gquery.genome.contigs:
        contig.contig_orientation = gquery.get_contig_orientation(contig)

    return gquery


@task()
@log_genome_id
def scaffold_pipolins(gquery: GQuery):
    # Useful link to check feature's qualifiers: https://www.ebi.ac.uk/ena/WebFeat/
    # https://github.com/biopython/biopython/issues/1755
    logger = context.get('logger')

    if gquery.genome.is_single_contig() or gquery.is_on_the_same_contig():
        logger.warning('>>> Scaffolding is not required!')
        gquery.pipolin_fragments = create_pipolin_fragments_single_contig(gquery)
    else:
        logger.warning('>>> Scaffolding is required!')
        scaffolder = Scaffolder(gquery=gquery)
        gquery.pipolin_fragments = scaffolder.try_creating_single_record()

    return gquery


@task()
@log_genome_id
def extract_pipolin_regions(gquery: GQuery, out_dir):
    if gquery.pipolin_fragments is None:
        raise AssertionError('No pipolin fragments, but should be!!!')
    genome_dict = read_seqio_records(file=gquery.genome.genome_file, file_format='fasta')

    pipolins_dir = os.path.join(out_dir, 'pipolin_sequences')
    os.makedirs(pipolins_dir, exist_ok=True)

    logger = context.get('logger')

    with open(os.path.join(pipolins_dir, gquery.genome.genome_id + '.fa'), 'w') as ouf:
        record = SeqRecord(seq='')
        sep_record = SeqRecord(seq='N' * 100)

        for fragment in gquery.pipolin_fragments[:-1]:
            fragment_record = create_fragment_record(fragment=fragment, genome_dict=genome_dict)
            logger.info(f'@fragment length {len(fragment_record)} from {fragment.contig.contig_id}')
            record += fragment_record
            record += sep_record

        last_record = create_fragment_record(fragment=gquery.pipolin_fragments[-1], genome_dict=genome_dict)
        logger.info(f'@fragment length {len(last_record)} from {gquery.pipolin_fragments[-1].contig.contig_id}')
        record += last_record

        logger.info(f'@@@ total record length {len(record)}')

        record.id = gquery.genome.genome_id
        record.name = gquery.genome.genome_id
        record.description = gquery.genome.genome_id
        SeqIO.write(sequences=record, handle=ouf, format='fasta')

    return pipolins_dir


@task()
@log_genome_id
def annotate_pipolins(gquery, pipolins_dir, proteins, out_dir):
    prokka_results_dir = os.path.join(out_dir, 'prokka')
    os.makedirs(prokka_results_dir, exist_ok=True)
    run_prokka(genome_id=gquery.genome.genome_id, pipolins_dir=pipolins_dir,
               proteins=proteins, prokka_results_dir=prokka_results_dir)
    return prokka_results_dir


@task()
@log_genome_id
def include_atts_into_annotation(gquery, prokka_dir, out_dir):
    gb_records = read_seqio_records(file=os.path.join(prokka_dir, gquery.genome.genome_id + '.gbk'),
                                    file_format='genbank')
    gff_records = read_gff_records(file=os.path.join(prokka_dir, gquery.genome.genome_id + '.gff'))

    include_atts_into_gb(gb_records=gb_records, gquery=gquery)
    include_atts_into_gff(gff_records=gff_records, gquery=gquery)

    prokka_atts_dir = os.path.join(out_dir, 'prokka_atts')
    os.makedirs(prokka_atts_dir, exist_ok=True)

    write_genbank_records(gb_records=gb_records, out_dir=prokka_atts_dir, genome=gquery.genome)
    write_gff_records(gff_records=gff_records, out_dir=prokka_atts_dir, genome=gquery.genome)

    return prokka_atts_dir


@task()
@log_genome_id
def easyfig_add_colours(gquery: GQuery, in_dir):
    gb_records = read_seqio_records(file=os.path.join(in_dir, gquery.genome.genome_id + '.gbk'), file_format='genbank')
    add_colours(gb_records[gquery.genome.genome_id])
    write_genbank_records(gb_records=gb_records, out_dir=in_dir, genome=gquery.genome)
