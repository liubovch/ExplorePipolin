import logging
import os
import subprocess
from typing import List

from Bio import SeqIO

import explore_pipolin.settings as settings


def check_external_dependencies():
    check_blast()
    check_aragorn()
    check_prokka()
    check_prodigal()
    check_hmmsearch()


def check_blast():
    command_args = ['blastn', '-version']
    _try_command_except_fatal(command_args, 'blastn')


def check_aragorn():
    command_args = ['aragorn', '-h']
    _try_command_except_fatal(command_args, 'aragorn')


def check_prokka():
    command_args = ['prokka', '--version']
    _try_command_except_fatal(command_args, 'prokka')


def check_prodigal():
    command_args = ['prodigal', '-h']
    _try_command_except_fatal(command_args, 'prodigal')


def check_hmmsearch():
    command_args = ['hmmsearch', '-h']
    _try_command_except_fatal(command_args, 'hmmsearch')


def _try_command_except_fatal(command_args: List[str], exec_name: str):
    p = subprocess.Popen(command_args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    std_out, std_err = p.communicate()
    if p.returncode != 0:
        print(std_err.decode()) if std_err != b'' else print(std_out.decode())
        logging.fatal(f'Cannot check {exec_name} executable!')
        exit(1)


def run_prodigal(genome_file: str, output_file: str):
    mode = 'single' if _is_long_enough(genome_file) else 'meta'
    command = ['prodigal', '-c', '-m', '-q', '-p', mode, '-a', output_file, '-i', genome_file]
    p = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    std_out, std_err = p.communicate()
    if p.returncode != 0:
        print(std_err.decode()) if std_err != b'' else print(std_out.decode())
        raise subprocess.CalledProcessError(p.returncode, ' '.join(command))


def _is_long_enough(genome_file) -> bool:
    records = SeqIO.parse(handle=genome_file, format='fasta')
    length = 0
    for record in records:
        length += len(record.seq)
    return length >= 100000


def run_hmmsearch(proteins_file: str, output_file: str):
    profile = settings.get_instance().pipolb_hmm_profile
    command = ['hmmsearch', '--tblout', output_file, '-E', '1e-50', profile, proteins_file]
    p = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    std_out, std_err = p.communicate()
    if p.returncode != 0:
        print(std_err.decode()) if std_err != b'' else print(std_out.decode())
        raise subprocess.CalledProcessError(p.returncode, ' '.join(command))


def blastn_against_ref_att(genome_file, output_file):
    ref_att = settings.get_instance().ref_att
    with open(output_file, 'w') as ouf:
        command = ['blastn', '-query', ref_att, '-subject', genome_file, '-evalue', '0.1', '-outfmt', '5']
        p = subprocess.Popen(command, stdout=ouf, stderr=subprocess.PIPE)
        _, std_err = p.communicate()
        if p.returncode != 0:
            if std_err != b'':
                print(std_err.decode())
            raise subprocess.CalledProcessError(p.returncode, ' '.join(command))


def blast_for_repeats(genome_id: str, repeats_dir: str):
    dir_content = os.listdir(repeats_dir)
    left_sorted = sorted([f for f in dir_content if f.startswith(genome_id) and f.endswith('.left')])
    right_sorted = sorted([f for f in dir_content if f.startswith(genome_id) and f.endswith('.right')])
    if len(left_sorted) != len(right_sorted):
        raise AssertionError('Number of .left files is not equal to the number of .right files!')

    percent_of_identity = settings.get_instance().percent_identity

    for lr, rr in zip(left_sorted, right_sorted):
        l_rep_index = _extract_index_from_filename(lr)
        r_rep_index = _extract_index_from_filename(rr)
        if l_rep_index != r_rep_index:
            raise AssertionError(f'Wrong pair for file {lr}: {rr}')

        with open(os.path.join(repeats_dir, genome_id + f'_{l_rep_index}.fmt5'), 'w') as ouf:
            command = ['blastn', '-query', os.path.join(repeats_dir, lr),
                       '-subject', os.path.join(repeats_dir, rr),
                       '-outfmt', '5', '-perc_identity', str(percent_of_identity),
                       '-word_size', '6', '-strand', 'plus']
            p = subprocess.Popen(command, stdout=ouf, stderr=subprocess.PIPE)
            _, std_err = p.communicate()
            if p.returncode != 0:
                if std_err != b'':
                    print(std_err)
                raise subprocess.CalledProcessError(p.returncode, ' '.join(command))


def _extract_index_from_filename(filename: str) -> int:
    return int(os.path.splitext(filename)[0].split(sep='_')[-1])


def run_aragorn(genome_file, output_file):
    with open(output_file, 'w') as ouf:
        p = subprocess.run(['aragorn', '-l', '-w', genome_file], stdout=ouf, stderr=subprocess.PIPE)
        # If no file, still returns 0 exitcode. Therefore, checking for the message.
        if b'Could not open ' in p.stderr:
            raise FileNotFoundError(genome_file)


def run_prokka(input_file, prokka_results_dir):
    hmm_profile = settings.get_instance().pipolb_hmm_profile
    proteins = settings.get_instance().proteins
    cpus = settings.get_instance().prokka_cpus
    prefix = os.path.splitext(os.path.basename(input_file))[0]
    command = ['prokka', '--outdir', prokka_results_dir, '--prefix', prefix,
               '--rawproduct', '--cdsrnaolap', '--cpus', str(cpus), '--hmms', hmm_profile,
               '--rfam', '--proteins', proteins, '--force', input_file]
    p = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    std_out, std_err = p.communicate()
    if p.returncode != 0:
        print(std_err.decode()) if std_err != b'' else print(std_out.decode())
        raise subprocess.CalledProcessError(p.returncode, ' '.join(command))
