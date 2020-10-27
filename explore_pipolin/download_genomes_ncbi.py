import os
import click
import subprocess
from Bio import SeqIO
from io import StringIO
from explore_pipolin.common import CONTEXT_SETTINGS
from explore_pipolin.utilities.external_tools import subprocess_with_retries


def read_metadata_file(metadata_file):
    with open(metadata_file) as inf:
        inf.readline()   # skip header line
        lines = [line.strip() for line in inf]
    return lines


def get_strain_names_and_gb_ids(metadata_file_lines):
    strain_names = ['_'.join(line.split('\t')[2].split(' ')) for line in metadata_file_lines]
    gb_ids = [line.split('\t')[3] for line in metadata_file_lines]
    return strain_names, gb_ids


def download_genome_seqs(gb_ids):
    seqs = []
    seqs_batch_request = subprocess_with_retries(['epost', '-id', gb_ids, '-db', 'nucleotide'],
                                                 input='', stdout=subprocess.PIPE)
    seqs_batch_fetched = subprocess_with_retries(['efetch', '-format', 'fasta'], input=seqs_batch_request.stdout,
                                                 stdout=subprocess.PIPE)
    seqs.extend(SeqIO.parse(StringIO(seqs_batch_fetched.stdout.decode(encoding='UTF8')), format='fasta'))

    if len(gb_ids.split(sep=',')) != len(seqs):
        raise AssertionError('The number of downloaded sequences (contigs) is wrong!!!')

    return seqs


@click.command(context_settings=CONTEXT_SETTINGS)
@click.argument('metadata-file', type=click.Path(exists=True))
@click.argument('out-dir', type=click.Path())
def download_genomes_ncbi(metadata_file, out_dir):
    """
    Given METADATA_FILE, generated by download_metadata_ncbi, the genome sequences in
    FASTA format will be downloaded from NCBI to the OUT_DIR.
    NOTE: requires "ncbi-entrez-direct" package!
    """
    os.makedirs(out_dir, exist_ok=True)
    metadata_file_lines = read_metadata_file(metadata_file=metadata_file)
    strains, gb_ids = get_strain_names_and_gb_ids(metadata_file_lines=metadata_file_lines)

    for strain, gb in zip(strains, gb_ids):
        print(f'>>> Downloading sequences for the strain {strain}')
        seqs = download_genome_seqs(gb_ids=gb)
        with open(os.path.join(out_dir, strain + '.fa'), 'w') as ouf:
            SeqIO.write(seqs, ouf, format='fasta')


if __name__ == '__main__':
    download_genomes_ncbi()
