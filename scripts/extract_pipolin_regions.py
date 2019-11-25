#!/usr/bin/env python3
# -*- encoding: utf-8 -*-

import os
import click
import shelve
from Bio import SeqIO
from Bio.SeqRecord import SeqRecord
from utilities import CONTEXT_SETTINGS
from utilities import Feature, Pipolin
from utilities import check_dir


@click.command(context_settings=CONTEXT_SETTINGS)
@click.argument('shelve-file', type=click.Path(exists=True))
@click.argument('genomes-dir', type=click.Path(exists=True))
@click.argument('out-dir')
def extract_pipolin_regions(shelve_file, genomes_dir, out_dir):
    """
    This script retrieves the information about pipolins from SHELVE_FILE
    and creates FASTA files with pipolin regions for their further annotation.
    """
    shelve_db = shelve.open(os.path.splitext(shelve_file)[0])
    pipolins = shelve_db['pipolins']
    shelve_db.close()

    # TODO: the code below is a mess, simplify it!
    genomes = {}
    for file in os.listdir(genomes_dir):
        genomes[file[:-3]] = SeqIO.to_dict(SeqIO.parse(os.path.join(genomes_dir, file), 'fasta'))

    check_dir(out_dir)
    for pipolin in pipolins:
        if pipolin.is_complete_genome():
            bounds = pipolin.get_pipolin_bounds()
            records = SeqRecord(seq=genomes[pipolin.strain_id][pipolin.strain_id].seq[bounds[0] - 50:bounds[1] + 50],
                                id=pipolin.strain_id, description='')
        else:
            # TODO: restrict contig length if it is too long!
            contings_bounds = pipolin.get_contigs_with_bounds()
            print(contings_bounds)
        #     records = [genomes[pipolin.strain_id][contig] for contig in contings]
        # with open(os.path.join(out_dir, f'{pipolin.strain_id}-pipolin.fa'), 'w') as ouf:
        #     SeqIO.write(records, ouf, 'fasta')


if __name__ == '__main__':
    extract_pipolin_regions()
