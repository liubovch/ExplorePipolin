# ExplorePipolin

To extract the subsequence from a genome:
 * `get_subsequence.py`
 
 `$ get_subsequence.py genomes/NZ_JNMI01000006.1.fa 80191 82792 pi-polB.fa`
 
 `$ get_subsequence.py genomes/NZ_JNMI01000006.1.fa 64241 64373 att.fa`

the whole analysis:
 * `download_genomes_ncbi.py`
 * `identify_pipolins_roughly.py` 
 (using reference `att.fa` and `pi-polB.fa` sequences)
 * `extract_pipolin_regions.py`
 * `annotate_pipolins.py`
 * `create_shelve_with_new_atts.py` 
 (parse HMMER output for atts)
 * ...

To get the sequences from roary groups:
 * `extract_roary_groups.py`
 
ATTs:
 1. Prepared ATT sequences with `prepare_atts_for_msa.py`
 2. Built a MSA with att sequences using 
 [MAFFT](https://www.ebi.ac.uk/Tools/msa/mafft/). 
 The output format -- Pearson FASTA, otherwise some
 sequence names will be truncated.
 It looked like there were two different types of ATTs.
 3. TODO: DELETE. Clustered the ATTs using the obtained MSA: `cluster_atts.py`.
 Reverse-complement the sequences in one of the clusters and 
 save as a new FASTA file.
 4. TODO: DELETE. Built a new MSA with "unified" ATTs (MAFFT), 
 saved as Pearson FASTA file.
 5. Modified with Jalview: deleted not conserved regions 
 from both ends.
 6. Created HMM profile with `hmmbuild` and `hmmpress`.
 7. `predict_atts_with_hmmer.py`
 