Pipolins constitute a new group of self-synthesizing or self-replicating 
mobile genetic elements (MGEs). They are widespread among diverse bacterial 
phyla and mitochondria.

> [**Redrejo-Rodríguez, M., *et al.*** Primer-independent DNA synthesis 
>by a family B DNA polymerase from self-replicating Mobile genetic elements. 
>*Cell reports*, 2017](https://doi.org/10.1016/j.celrep.2017.10.039)
>
>[**Flament-Simon, S.C., de Toro, M., Chuprikova, L., *et al.*** High diversity 
>and variability of pipolins among a wide range of pathogenic *Escherichia 
>coli* strains. *bioRxiv*, 2020](https://www.biorxiv.org/content/10.1101/2020.04.24.059261v1)

 **ExplorePipolin** is a search tool that identifies and analyses
 pipolins within bacterial genome.

# Table of contents

* [Requirements](#requirements)
* [Installation](#installation)
    * [Install from source](#install-from-source)
    * [Install using Bioconda](#install-using-bioconda)
* [Quick usage](#quick-usage)
    * [Test run](#test-run)
    * [Output files](#output-files)
    * [Additional scripts](#additional-scripts)
* [Running with Docker](#running-with-docker)

# Requirements

 * pip
 * [Entrez Direct](https://www.ncbi.nlm.nih.gov/books/NBK179288/) 
 (not required to run the main script)
 * [BLAST+](https://www.ncbi.nlm.nih.gov/books/NBK279690/)
 * [ARAGORN](https://github.com/TheSEED/aragorn)
 * [Prokka](https://github.com/tseemann/prokka)

# Installation
### Install from source

 1. Install the requirements (see above).
 1. Click green button on the right "Clone or Download" => "Download zip"
 1. `unzip ExplorePipolin-master.zip && cd ExplorePipolin-master`
 1. `pip install .` (install in user site-package) or
 `sudo pip install .` (requires superuser privileges)
 
**How to uninstall:**

`(sudo) pip uninstall ExplorePipolin`

### Install using Bioconda

**Not user steps (TODO: remove this later)** 

 * Build the package:

`conda-build ./conda -c bioconda -c conda-forge`

 * The package can be found in 
 $HOME/miniconda3/conda-bld/noarch/explore-pipolin-0.0.1-py_0.tar.bz2.
 TODO: either upload it to Anaconda, or store somewhere on GitHub!
 
 * Create a dummy environment. This steps could be done by user, 
 but it takes too long to solve the dependencies. 

`conda create -n dummy explore-pipolin -c local -c bioconda -c conda-forge`

Export the environment:

`conda env export -n dummy > explore_pipolin-0.0.1.yml`

 * Delete `local` channel, name, prefix and `explore_pipolin` dependency from 
 the explore_pipolin-0.0.1.yml. Upload the file to GitHub!
 
 **User steps**
 
 * Before installing ExplorePipolin, make sure you'are running the latest 
 version of Conda:
 
 `conda update conda`
 
 `conda install wget`
 
 * Create a new environment that is specific for ExplorePipolin. You can 
 choose whatever name you'd like for the environment.
 
 `wget github//explore_pipolin-0.0.1.yml`
 
 `conda env create -n ExplorePipolin-0.0.1 --file explore_pipolin-0.0.1.yml`
 
 * Download and install ExplorePipolin into the created environment (This 
 step will be part of the previous step when we upload the package to Anaconda):
 
 `wget github//explore-pipolin-0.0.1-py_0.tar.bz2`
 
 `conda install -n ExplorePipolin-0.0.1 explore-pipolin-0.0.1-py_0.tar.bz2`
 
 Clean up (optional):
 
 `rm explore_pipolin-0.0.1.yml explore-pipolin-0.0.1-py_0.tar.bz2`
 
 * Activate the environment and test the installation:
 
 `conda activate ExplorePipolin-0.0.1`
 
 `explore_pipolin -h`

# Quick usage

### Test run
As input, **ExplorePipolin** takes FASTA file(s) with genome sequence(s). 
A genome sequence can be either a single complete chromosome (preferred) 
or contigs (in a single multiFASTA file).

```bash
--> explore_pipolin -h
Usage: explore_pipolin [OPTIONS] GENOMES...

  ExplorePipolin is a search tool that identifies and analyses
  pipolin elements  within bacterial genome(s).

Options:
  --out-dir PATH  [required]
  -h, --help      Show this message and exit.
```

TODO: test run.

### Output files

The output directory will contain several folders:
 
 | Folder | Content description |
 |--------|---------------------|
 | `polb_blast` | BLAST results of searching for the "reference" piPolB |
 | `att_blast` | BLAST results of searching for the "reference" att |
 | `atts_denovo` | Results of *de novo* search of atts |
 | `aragorn_results` | Results of searching for tRNAs/tmRNAs using ARAGORN |
 | `pipolin_sequences` | extracted pipolin sequences in FASTA format |
 | `prokka` | Prokka's annotation pipeline output (check files description [here](https://github.com/tseemann/prokka/blob/master/README.md#output-files))|
 | `prokka_atts` | Since Prokka doesn't find atts, att features are added separately to the annotation files (.gbk and .gff) |

### Additional scripts

TODO: install as console scripts

 * `download_metadata_ncbi.py` -- downloads the metadata for the analysed 
 genomes, such as accessions, organism and strain names
 * `download_genomes_ncbi.py` -- downloads genome (chromosome) sequences 
 given NCBI assembly accession (i.e. for a non-complete genome, it 
 downloads all its contigs)

# Running with Docker

See https://docs.docker.com/install/ to install Docker.

**NOTE:** superuser privileges and around 3GB of disk space are required
to build image and run the analysis.

 1. Click green button on the right "Clone or Download" => "Download zip"
 1. `unzip ExplorePipolin-master.zip && cd ExplorePipolin-master/docker`
 1. `sudo docker build -t explore_pipolin .`
 1. `sudo docker run --rm explore_pipolin --help` (test)
 1. `sudo docker run --rm -v $(pwd):/output -w /output explore_pipolin 
 --out-dir output ./input_genomes/*.fa` (example run)


<!---
Prediction of ATTs:

 1. Prepared ATT sequences with `prepare_atts_for_msa.py`
 ```
The total number of atts is 198
> Maximum att length is 132
> Minimum att length is 121
```
 1. Built a MSA with att sequences using MAFFT, MUSCLE
 and T-Coffee (https://www.ebi.ac.uk/Tools/msa). 
 The output format -- Pearson FASTA, otherwise long
 sequence names might be truncated.
 1. Compared the alignments. Modified them, using 
 Jalview: deleted not conserved regions from both ends.
 1. Created HMM profile with `hmmbuild` and `hmmpress`.


To extract the subsequence from a genome:
 * `get_subsequence.py`
 
 `$ get_subsequence.py genomes/NZ_JNMI01000006.1.fa 80191 82792 pi-polB.fa`
 
 `$ get_subsequence.py genomes/NZ_JNMI01000006.1.fa 64241 64373 attL.fa`

 `$ get_subsequence.py genome/NZ_JNMI010000006.1.fa 90094 90008 tRNA.fa`

 For Saskia's strains: 
 * `edit_contig_names.sh <in-dir>` -- to shorten the long contig names

To get the sequences from roary groups:
 * `extract_roary_groups.py`
-->