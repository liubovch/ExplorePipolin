import logging
import os
import shutil
import click

from explore_pipolin.flow import get_flow
import explore_pipolin.settings as settings
from explore_pipolin.settings import GlobalSettings, _DEFAULT_OUT_DIR_PREFIX, _NO_BORDER_INFLATE
from explore_pipolin.tasks.prepare_for_the_analysis import define_genome_id

from explore_pipolin.utilities.external_tools import check_external_dependencies
from explore_pipolin.common import CONTEXT_SETTINGS


def check_file_names(genomes):
    if len(genomes) > 1:
        if len(genomes) != len(set(os.path.basename(i) for i in genomes)):
            logging.fatal('GENOMES should have different names!')
            exit(1)


@click.command(context_settings=CONTEXT_SETTINGS)
@click.argument('genomes', type=click.Path(exists=True), nargs=-1, required=True)
@click.option('--out-dir-prefix', type=str,
              help=f'Use this prefix for the output directory, '
                   f'instead of the default "{_DEFAULT_OUT_DIR_PREFIX}" prefix.')
@click.option('--out-dir', type=click.Path(),
              help='Use this output directory instead.')
@click.option('--pipolb-hmm-profile', type=click.Path(exists=True),
              help="piPolB's HMM profile to use as 1st priority."
                   'If not provided, the default profile will be used instead.')
@click.option('--only-find-pipolbs', is_flag=True,
              help='Only find piPolB genes.')
@click.option('--ref-att', type=click.Path(exists=True),
              help='ATT sequence in FASTA file to use as 1st priority. '
                   'If not provided, the default ATT will be used instead.')
@click.option('--percent-identity', type=int, default=85, show_default=True,
              help='Minimum percent identity for direct repeats search')
@click.option('--max-inflate', type=int, default=_NO_BORDER_INFLATE, show_default=True,
              help='If no borders of pipolin are found (no ATTs), '
                   'inflate the analysed region from both sides of piPolB by this length.')
@click.option('--skip-annotation', is_flag=True,
              help='Do not run the annotation step (i.e. Prokka).')
@click.option('--proteins', type=click.Path(exists=True),
              help='Prokka param: FASTA or GBK file to use as 1st priority. '
                   'If not provided, the default file will be used instead.')
@click.option('--colours', type=click.Path(exists=True),
              help='A TSV file describing features to colour. Please, refer to '
                   'https://github.com/pipolinlab/ExplorePipolin '
                   'for more information about the file structure.')
@click.option('--skip-colours', is_flag=True,
              help='Do not add an Easyfig-compatible colouring scheme to the final Genbank files.')
@click.option('--cpus', default=8, type=int, show_default=True,
              help='Prokka param: Number of CPUs to use [0=all]')
@click.option('--keep-tmp', is_flag=True,
              help='Preserve intermediate files produced during the run (it might be useful for debugging).')
@click.option('--keep-going', is_flag=True,
              help='Do not stop analysis if an error is raised for one of the genomes.')
def main(
        genomes,
        out_dir_prefix,
        out_dir,
        pipolb_hmm_profile,
        only_find_pipolbs,
        ref_att,
        percent_identity,
        max_inflate,
        skip_annotation,
        proteins,
        colours,
        skip_colours,
        cpus,
        keep_tmp,
        keep_going,
):
    """
    ExplorePipolin is a search tool for prediction and analysis of pipolins, bacterial mobile genetic elements.
    """

    # from graphviz import Digraph
    # graph: Digraph = get_flow().visualize(filename='/Users/liubov/Documents/ExplorePipolin_data/testtest')
    # graph.node_attr.update(fontsize='18', fontname='DejaVuSansMono')
    # graph.render('/Users/liubov/Documents/ExplorePipolin_data/test')
    # # modify test in text editor
    # # dot -Tpdf test > test.pdf
    # # check the result

    check_file_names(genomes)

    check_external_dependencies()

    settings.set_instance(GlobalSettings.create_instance(
        out_dir_prefix, out_dir, pipolb_hmm_profile, ref_att, percent_identity, max_inflate,
        proteins, cpus, colours, skip_colours
    ))
    os.makedirs(settings.get_instance().out_dir, exist_ok=True)

    for genome in genomes:
        try:
            state = get_flow().run(
                genome_file=[genome],
                only_find_pipolbs=only_find_pipolbs,
                skip_annotation=skip_annotation,
            )
            if state.is_failed() and keep_going:
                continue
            else:
                assert state.is_successful()
        finally:
            dirs_to_delete = ['pipolbs', 'atts', 'atts_denovo', 'trnas', 'prokka']
            if not keep_tmp:
                genome_id = define_genome_id(genome)
                for item in dirs_to_delete:
                    path = os.path.join(settings.get_instance().out_dir, genome_id, item)
                    if os.path.exists(path):
                        shutil.rmtree(path)

                fasta = os.path.join(settings.get_instance().out_dir, genome_id, genome_id+'.fa')
                if os.path.exists(fasta):
                    os.remove(fasta)


if __name__ == '__main__':
    main(prog_name='explore_pipolin')
