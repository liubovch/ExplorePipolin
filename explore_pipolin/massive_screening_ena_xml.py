import gzip
import os
import shutil
import subprocess
import asyncio
import tempfile

import urllib.request
from typing import Tuple, Iterator
from urllib.error import URLError
import xml.etree.ElementTree as ElementTree

import click

from explore_pipolin.common import CONTEXT_SETTINGS


def yield_acc_and_url(ena_xml: str) -> Iterator[Tuple[str, str]]:
    for event, elem in ElementTree.iterparse(ena_xml, events=('start',)):
        asmbl_acc, asmbl_url = None, None
        if event == 'start' and elem.tag == 'ASSEMBLY':
            asmbl_acc = elem.attrib['accession']

            for link in elem.findall('ASSEMBLY_LINKS/ASSEMBLY_LINK/URL_LINK[LABEL="WGS_SET_FASTA"]/URL'):
                asmbl_url = link.text

            if (asmbl_acc is not None) and (asmbl_url is not None):
                yield asmbl_acc, asmbl_url


def unzip_genome(genome_zip: str, new_genome: str) -> None:
    with gzip.open(genome_zip, 'rb') as inf, open(new_genome, 'wb') as ouf:
        shutil.copyfileobj(inf, ouf)


def _is_analysed(acc: str, out_dir) -> bool:
    try:
        with open(os.path.join(out_dir, 'analysed.txt')) as inf:
            for line in inf:
                if line.strip() == acc:
                    return True
        return False
    except FileNotFoundError:
        return False


def _update_checked(acc: str, out_dir: str) -> None:
    with open(os.path.join(out_dir, 'checked.txt'), 'a') as ouf:
        print(acc, file=ouf)


def _is_found(acc: str, out_dir: str) -> bool:
    log_path = os.path.join(out_dir, 'logs', acc + '.log')
    if not os.path.exists(log_path):
        raise AssertionError('Log should exist!')
    with open(log_path) as inf:
        return 'No piPolBs were found!' not in inf.read()


def _update_found_pipolins(acc: str, out_dir:str) -> None:
    with open(os.path.join(out_dir, 'found_pipolins.txt'), 'a') as ouf:
        print(acc, file=ouf)


def _clean_all(acc: str, out_dir: str) -> None:
    os.remove(os.path.join(out_dir, 'pipolbs', acc + '.faa'))
    os.remove(os.path.join(out_dir, 'pipolbs', acc + '.tbl'))
    os.remove(os.path.join(out_dir, 'logs', acc + '.log'))


async def analyse_genome(genome: str, out_dir: str) -> None:
    proc = await asyncio.subprocess.create_subprocess_shell(
        f'explore_pipolin --out-dir {out_dir} --no-annotation {genome}',
        stdout=subprocess.DEVNULL)
    await proc.wait()


async def download_and_analyse(acc: str, url: str, out_dir: str, sem: asyncio.BoundedSemaphore) -> None:
    try:
        if _is_analysed(acc, out_dir):
            return
        await do_download_and_analyse(acc, url, out_dir)
    except URLError:
        print(f'Broken URL for {acc}. Skip.')
        _update_checked(acc, out_dir)
    finally:
        sem.release()


async def do_download_and_analyse(acc: str, url: str, out_dir: str) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        genome = os.path.join(tmp, acc + '.fasta')
        download_genome(url, genome)
        await analyse_genome(genome, out_dir)
        print(f'Finished analysis for {acc}')

    if _is_found(acc, out_dir):
        _update_found_pipolins(acc, out_dir)
    else:
        _clean_all(acc, out_dir)

    _update_checked(acc, out_dir)


def download_genome(url: str, genome: str) -> None:
    with tempfile.NamedTemporaryFile() as genome_zip:
        download_genome_to_path(url, genome_zip.name)
        unzip_genome(genome_zip.name, genome)


def download_genome_to_path(url: str, genome_path: str) -> None:
    urllib.request.urlretrieve(url, genome_path)


async def download_and_analyse_all(ena_xml: str, out_dir: str, p: int) -> None:
    sem = asyncio.BoundedSemaphore(p)
    tasks = []
    for acc, url in yield_acc_and_url(ena_xml):

        await sem.acquire()

        print(acc, url)
        tasks.append(asyncio.create_task(download_and_analyse(acc, url, out_dir, sem)))
        tasks = [task for task in tasks if not task.done()]

    await asyncio.gather(*tasks)


@click.command(context_settings=CONTEXT_SETTINGS)
@click.argument('ena-xml', type=click.Path(exists=True))
@click.argument('out-dir', type=click.Path())
@click.option('-p', type=int, default=1, show_default=True, help='Number of processes to run.')
def massive_screening(ena_xml, out_dir, p):
    """
    ENA_XML is a file downloaded from ENA database after a search of genome assemblies
    for an organism of interest.
    An accession of each analysed genome assembly will be written to the analysed.txt file.
    When the process is interrupted and rerun again, these accessions will be skipped.
    Accessions of pipolin-harboring genomes will be written to the found_pipolins.txt file.
    """
    os.makedirs(out_dir, exist_ok=True)

    asyncio.run(download_and_analyse_all(ena_xml, out_dir, p))


if __name__ == '__main__':
    massive_screening()