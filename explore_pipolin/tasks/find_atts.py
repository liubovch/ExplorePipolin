import os
from collections import defaultdict
from itertools import chain
from typing import List, Mapping, Sequence

from Bio import SeqIO
from prefect import task, context
from prefect.utilities.logging import get_logger

from explore_pipolin.common import Genome, FeatureType, Range, PairedLocation, Strand, AttFeature, ContigID, \
    MultiLocation, Feature, AttType
from explore_pipolin.utilities.external_tools import blastn_against_ref_att, blast_for_repeats
from explore_pipolin.utilities.io import read_blastxml, create_seqio_records_dict
from explore_pipolin.utilities.logging import genome_specific_logging


_SEARCH_AROUND_REGION = 100_000


@task()
@genome_specific_logging
def find_atts(genome: Genome) -> Genome:
    atts_dir = os.path.join(os.path.dirname(genome.file), 'atts')
    os.makedirs(atts_dir, exist_ok=True)

    finder = AttFinder(genome=genome, output_dir=atts_dir)
    finder.find_atts()

    return genome


class AttFinder:
    def __init__(self, genome: Genome, output_dir: str):
        self.genome = genome
        self.output_dir = output_dir

    def find_atts(self):
        output_file = os.path.join(self.output_dir, self.genome.id + '.fmt5')
        blastn_against_ref_att(genome_file=self.genome.file, output_file=output_file)
        entries = read_blastxml(blast_xml=output_file)

        self._add_att_features(entries)

        self._add_target_trnas_features()

    def _add_att_features(self, entries):
        att_id = self.genome.features.get_features(FeatureType.ATT).get_next_att_id()
        for entry in entries:
            att_features = self._create_att_features(entry, att_id)
            self.genome.features.add_features(*att_features)

    def _create_att_features(self, entry, att_id) -> Sequence[AttFeature]:
        att_features = []
        evalues = []
        for hit in entry:
            evalues.append(hit.evalue)
            att_features.append(AttFeature(location=Range(start=hit.hit_start, end=hit.hit_end),
                                           strand=Strand.from_pm_one_encoding(hit.hit_strand),
                                           ftype=FeatureType.ATT, contig_id=entry.id,
                                           genome=self.genome, att_id=att_id, att_type=AttType.CONSERVED))

        while len(set(f.strand for f in att_features)) != 1:
            # delete hit with the lowest e-value
            del att_features[evalues.index(min(evalues))]

        return att_features
        # NOTE: Should the found known atts be of a similar length? Be careful when the att is at the contig edge!
        # max_length_att = max(abs(f.location.start - f.location.end) for f in att_features)
        # return [f for f in att_features if (max_length_att - abs(f.location.start - f.location.end)) <= 10]

    def _add_target_trnas_features(self):
        for att in self.genome.features.get_features(FeatureType.ATT):
            trna = self.genome.features.get_features(FeatureType.TRNA).get_overlapping(att)
            if trna is not None:
                if self._is_3prime_ttrna(trna, att):
                    target_trna = Feature(location=trna.location, strand=trna.strand,
                                          ftype=FeatureType.TARGET_TRNA,
                                          contig_id=trna.contig_id, genome=trna.genome)
                    self.genome.features.add_features(target_trna)

    @staticmethod
    def _is_3prime_ttrna(trna: Feature, att: AttFeature) -> bool:
        if trna.strand == att.strand:
            return False
        else:
            is_3prime_f = (trna.strand == Strand.FORWARD) and (trna.start < att.start)
            is_3prime_r = (trna.strand == Strand.REVERSE) and (trna.end > att.end)
            return is_3prime_f or is_3prime_r


@task()
@genome_specific_logging
def find_atts_denovo(genome: Genome) -> Genome:
    atts_denovo_dir = os.path.join(os.path.dirname(genome.file), 'atts_denovo')
    os.makedirs(atts_denovo_dir, exist_ok=True)

    finder = AttDenovoFinder(genome=genome, output_dir=atts_denovo_dir)
    finder.find_atts_denovo()

    return genome


class AttDenovoFinder:
    def __init__(self, genome: Genome, output_dir: str):
        self.genome = genome
        self.output_dir = output_dir

    def find_atts_denovo(self):
        # If known ATTs already present (at least 2), they are of higher priority.
        #   In this case, just skip this step:
        if len(self.genome.features.get_features(FeatureType.ATT)) >= 2:
            logger = get_logger(name='find_atts_denovo')
            logger.warning('Direct repeat sequences similar to the known reference ATT detected. '
                           'No more direct repeats surrounding the piPolB gene will be searched.')
        else:
            repeats: List[MultiLocation] = self._find_repeats()
            self._write_repeats(repeats)

            atts_denovo: List[MultiLocation] = [rep for rep in repeats if self._is_att_denovo(rep)]
            self._write_atts_denovo(atts_denovo)

            self._extend_att_features(atts_denovo)
            self._extend_target_trna_features()

    def _find_repeats(self) -> List[MultiLocation]:
        ranges_around_pipolbs = self._get_ranges_around_pipolbs()
        self._save_seqs_around_pipolbs(ranges_around_pipolbs)
        blast_for_repeats(genome_id=self.genome.id, repeats_dir=self.output_dir)
        paired_repeats: List[PairedLocation] = self._extract_repeats(ranges_around_pipolbs)
        return self._regroup_paired_repeats(paired_repeats)

    def _write_repeats(self, repeats: List[MultiLocation]):
        with open(os.path.join(self.output_dir, self.genome.id + '.repeats'), 'w') as ouf:
            for loc in repeats:
                ranges = [f'({i.start},{i.end})' for i in loc.ranges]
                print(loc.contig_id, ' '.join(ranges), sep='\t', file=ouf)

    def _is_att_denovo(self, repeat: MultiLocation) -> bool:
        atts_of_contig = self.genome.features.atts_dict()[repeat.contig_id]
        for att in atts_of_contig:
            if repeat.ranges[0].is_overlapping(att):
                return False

        trnas_of_contig = self.genome.features.trnas_dict()[repeat.contig_id]
        num_trnas_overlapping = 0
        for r in repeat.ranges:
            for trna in trnas_of_contig:
                if r.is_overlapping(trna.location):
                    # should be either 3'- or 5'-overlapping (not one range within the other)
                    if r.not_within(trna.location) and trna.location.not_within(r):
                        num_trnas_overlapping += 1
        # if we have att(t)---att(t), then it probably just the tRNA duplication,
        # therefore we'd like to have a single repeat range overlapping tRNA
        if num_trnas_overlapping == 1:
            return True

        return False

    def _write_atts_denovo(self, atts_denovo: List[MultiLocation]):
        with open(os.path.join(self.output_dir, self.genome.id + '.atts_denovo'), 'w') as ouf:
            for att in atts_denovo:
                ranges = [f'({i.start},{i.end})' for i in att.ranges]
                print(att.contig_id, ' '.join(ranges), sep='\t', file=ouf)

    def _extend_att_features(self, atts_denovo: List[MultiLocation]):
        atts_dict = self.genome.features.get_features(FeatureType.ATT).get_atts_dict_by_att_id()
        for att in atts_denovo:
            new_att_id = None
            for r in att.ranges:
                for att_id, atts in atts_dict.items():
                    if r.is_overlapping_any(atts):
                        new_att_id = att_id

            if new_att_id is None:
                new_att_id = self.genome.features.get_features(FeatureType.ATT).get_next_att_id()

            for r in att.ranges:
                if new_att_id in atts_dict:
                    if not r.is_overlapping_any(atts_dict[new_att_id]):
                        new_att = AttFeature(r, Strand.FORWARD, FeatureType.ATT, att.contig_id, self.genome,
                                             new_att_id, att_type=AttType.DENOVO)
                        self.genome.features.add_features(new_att)
                else:
                    new_att = AttFeature(r, Strand.FORWARD, FeatureType.ATT, att.contig_id, self.genome,
                                         new_att_id, att_type=AttType.DENOVO)
                    self.genome.features.add_features(new_att)

    def _extend_target_trna_features(self):
        target_trnas_dict = self.genome.features.target_trnas_dict()
        for att in self.genome.features.get_features(FeatureType.ATT):
            trna = self.genome.features.get_features(FeatureType.TRNA).get_overlapping(att)
            if trna is not None and self._is_3prime_ttrna(trna, att):
                if trna not in target_trnas_dict[trna.contig_id]:
                    target_trna = Feature(location=trna.location, strand=trna.strand,
                                          ftype=FeatureType.TARGET_TRNA,
                                          contig_id=trna.contig_id, genome=trna.genome)
                    self.genome.features.add_features(target_trna)

    @staticmethod
    def _is_3prime_ttrna(trna: Feature, att: AttFeature) -> bool:
        is_3prime_f = (trna.strand == Strand.FORWARD) and (trna.start < att.start)
        is_3prime_r = (trna.strand == Strand.REVERSE) and (trna.end > att.end)
        return is_3prime_f or is_3prime_r

    def _get_ranges_around_pipolbs(self) -> List[PairedLocation]:
        pipolbs_dict_by_contig = self.genome.features.pipolbs_dict()

        range_pairs = []
        for contig_id, pipolbs in pipolbs_dict_by_contig.items():
            contig_length = self.genome.get_contig_by_id(contig_id=contig_id).length

            for pipolb in pipolbs:
                search_range = pipolb.location.inflate_within_contig(
                    _SEARCH_AROUND_REGION, _contig_length=contig_length
                )
                range_pairs.append(PairedLocation(Range(search_range.start, pipolb.start),
                                                  Range(pipolb.end, search_range.end), ContigID(contig_id)))
        return range_pairs

    def _save_seqs_around_pipolbs(self, ranges_around_pipolbs: List[PairedLocation]):
        genome_dict = create_seqio_records_dict(file=self.genome.file, file_format='fasta')

        for i, range_pair in enumerate(ranges_around_pipolbs):
            left_seq = genome_dict[range_pair.contig_id][range_pair.left_range.start:range_pair.left_range.end]
            right_seq = genome_dict[range_pair.contig_id][range_pair.right_range.start:range_pair.right_range.end]
            SeqIO.write(sequences=left_seq, format='fasta',
                        handle=os.path.join(self.output_dir, self.genome.id + f'_{i}.left'))
            SeqIO.write(sequences=right_seq, format='fasta',
                        handle=os.path.join(self.output_dir, self.genome.id + f'_{i}.right'))

    def _extract_repeats(self, ranges_around_pipolbs: List[PairedLocation]):
        repeats: List[PairedLocation] = []
        for i, range_pair in enumerate(ranges_around_pipolbs):
            repeats_xml = read_blastxml(os.path.join(self.output_dir, self.genome.id + f'_{i}.fmt5'))
            for entry in repeats_xml:
                for hit in entry:
                    if abs(hit.query_start - hit.query_end) > 500:   # too long for att repeat
                        continue
                    left_repeat = Range(start=hit.query_start, end=hit.query_end).shift(range_pair.left_range.start)
                    right_repeat = Range(start=hit.hit_start, end=hit.hit_end).shift(range_pair.right_range.start)
                    repeat_pair = PairedLocation(left_repeat, right_repeat, range_pair.contig_id)
                    repeats.append(repeat_pair)
        return repeats

    @staticmethod
    def _regroup_paired_repeats(paired_repeats: List[PairedLocation]) -> List[MultiLocation]:
        result: Mapping[ContigID, List[MultiLocation]] = defaultdict(list)
        for repeat in paired_repeats:
            for rs in result[repeat.contig_id]:
                if repeat.left_range.is_overlapping_any(rs.ranges) and \
                        not repeat.right_range.is_overlapping_any(rs.ranges):
                    rs.ranges.append(repeat.right_range)
                    break
                elif repeat.right_range.is_overlapping_any(rs.ranges) and \
                        not repeat.left_range.is_overlapping_any(rs.ranges):
                    rs.ranges.append(repeat.left_range)
                    break
                elif repeat.left_range.is_overlapping_any(rs.ranges) and \
                        repeat.right_range.is_overlapping_any(rs.ranges):
                    break
            else:
                result[repeat.contig_id].append(MultiLocation(
                    ranges=[repeat.right_range, repeat.left_range], contig_id=repeat.contig_id))
        return list(chain(*result.values()))


@task()
@genome_specific_logging
def are_atts_present(genome: Genome) -> Genome:
    logger = context.get('logger')

    num_atts = len(genome.features.get_features(FeatureType.ATT))
    if num_atts == 0:
        logger.warning('\n\n>>>No atts were found! Not able to define pipolin borders!\n')
    return genome
