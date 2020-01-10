#!/usr/bin/env python3
# -*- encoding: utf-8 -*-

import click
from utilities import CONTEXT_SETTINGS, GenBankRecords
from utilities import read_genbank_records, write_genbank_records

red = '255 0 0'   # Primer-independent DNA polymerase PolB
brick_red = '139 58 58'   # Tyrosine recombinase XerC
yellow = '255 255 0'   # Type I site-specific deoxyribonuclease (hsdR)
# Type I restriction modification enzyme
# Type I restriction modification system methyltransferase (hsdM)
magenta = '255 0 255'   # metallohydrolase
purple = '178 58 238'   # excisionase
cyan = '0 255 255'   # Uracil-DNA glycosylase
green = '0 255 0'   # tRNA-Leu
blue = '0 0 255'   # repeat_region
floral_white = '255 250 240'   # others
black = '0 0 0'   # pipolin_structure
pink = '255 200 200'   # paired-ends

products_to_colours = {'Primer-independent DNA polymerase PolB': red,
                       'Tyrosine recombinase XerC': brick_red,
                       'Type I site-specific deoxyribonuclease (hsdR)': yellow,
                       'Type I restriction modification enzyme': yellow,
                       'Type I restriction modification system methyltransferase (hsdM)': yellow,
                       'metallohydrolase': magenta, 'excisionase': purple,
                       'Uracil-DNA glycosylase': cyan, 'tRNA-Leu': green,
                       'repeat_region': blue, 'pipolin_structure': black,
                       'paired-ends': pink, 'other': floral_white}


def colour_feature(qualifiers):
    if 'product' in qualifiers:
        for product in qualifiers['product']:
            if product in products_to_colours:
                qualifiers['colour'] = [products_to_colours[product]]
            else:
                qualifiers['colour'] = [products_to_colours['other']]
    if 'linkage_evidence' in qualifiers:
        for evidence in qualifiers['linkage_evidence']:
            if evidence in products_to_colours:
                qualifiers['colour'] = [products_to_colours[evidence]]
            else:
                qualifiers['colour'] = [products_to_colours['other']]


def add_colours(gb_records: GenBankRecords):
    for record_set in gb_records.values():
        for record in record_set.values():
            for feature in record.features:
                if feature.type in products_to_colours:
                    feature.qualifiers['colour'] = products_to_colours[feature.type]
                else:
                    colour_feature(feature.qualifiers)


@click.command(context_settings=CONTEXT_SETTINGS)
@click.argument('in-dir', type=click.Path(exists=True))
def easyfig_add_colours(in_dir):
    """
    IN_DIR contains *.gbk files to modify.
    """
    gb_records = read_genbank_records(in_dir)
    add_colours(gb_records)
    write_genbank_records(gb_records, in_dir)


if __name__ == '__main__':
    easyfig_add_colours()