from __future__ import annotations

from collections import defaultdict
from typing import MutableSequence, Optional, Tuple, Sequence, Mapping, MutableMapping, List

from explore_pipolin.common import Orientation, Contig, Genome, Feature, FeatureType, RepeatPair


class GQuery:
    def __init__(self, genome: Genome):
        self.genome = genome
        self.pipolbs: MutableSequence[Feature] = []
        self.atts: MutableSequence[Feature] = []
        self.trnas: MutableSequence[Feature] = []
        self.target_trnas: MutableSequence[Feature] = []
        self.denovo_atts: MutableSequence[Feature] = []
        self.target_trnas_denovo: MutableSequence[Feature] = []

    @staticmethod
    def _dict_by_contig_normalized(features: Sequence[Feature]) -> Mapping[str, Sequence[Feature]]:
        result: MutableMapping[str, List[Feature]] = defaultdict(list)
        for feature in features:
            result[feature.contig_id].append(feature)
        for _, features in result.items():
            features.sort(key=lambda p: p.start)
        return result

    def get_features_dict_by_contig_normalized(self, feature_type: FeatureType) -> Mapping[str, Sequence[Feature]]:
        return self._dict_by_contig_normalized(self.get_features_by_type(feature_type))

    def get_features_of_contig_normalized(self, contig_id: str, feature_type: FeatureType) -> Sequence[Feature]:
        features_dict = self.get_features_dict_by_contig_normalized(feature_type=feature_type)
        return features_dict[contig_id]

    def get_features_by_type(self, feature_type: FeatureType) -> MutableSequence[Feature]:
        if feature_type is FeatureType.PIPOLB:
            return self.pipolbs
        elif feature_type is FeatureType.ATT:
            return self.atts
        elif feature_type is FeatureType.TARGET_TRNA:
            return self.target_trnas
        elif feature_type is FeatureType.TRNA:
            return self.trnas
        else:
            raise AssertionError(f'Feature must be one of: {list(FeatureType)}, not {feature_type}')

    # `add_features_from_aragorn` and `add_features_atts_denovo`
    def find_target_trna(self, att: Feature) -> Optional[Feature]:
        trna_dict = self.get_features_dict_by_contig_normalized(FeatureType.TRNA)

        if att.contig_id in trna_dict:
            trnas = trna_dict[att.contig_id]
            for trna in trnas:
                if self._is_overlapping(range1=(att.start, att.end), range2=(trna.start, trna.end)):
                    return trna

    def is_on_the_same_contig(self) -> bool:
        target_contigs = []
        target_contigs.extend(f.contig_id for f in self.pipolbs)
        target_contigs.extend(f.contig_id for f in self.atts)
        target_contigs.extend(f.contig_id for f in self.target_trnas)
        return len(set(target_contigs)) == 1

    # `find_atts_denovo` and `scaffold_pipolins`
    def get_left_right_windows(self) -> Tuple[Tuple[int, int], Tuple[int, int]]:
        pipolbs = sorted((i for i in self.pipolbs), key=lambda p: p.start)

        if pipolbs[-1].start - pipolbs[0].start > 10000:   # TODO: is it small/big enough?
            raise AssertionError(f'You have several piPolBs per genome and they are too far from each other: '
                                 f'within the region ({pipolbs[0].start}, {pipolbs[-1].end}). It might be, '
                                 f'that you have two or more pipolins per genome, but we are expecting only one.')

        length = self.genome.get_complete_genome_length()
        left_edge = pipolbs[0].start - 100000
        left_window = (left_edge if left_edge >= 0 else 0, pipolbs[0].start)
        right_edge = pipolbs[-1].end + 100000
        right_window = (pipolbs[-1].end, right_edge if right_edge <= length else length)

        return left_window, right_window

    def is_att_denovo(self, repeat_pair: RepeatPair) -> bool:
        if self._is_overlapping_att(left_repeat=repeat_pair.left):
            return False
        return self._is_overlapping_trna(repeat_pair)

    def _is_overlapping_att(self, left_repeat: Feature):
        for att in self.atts:
            if self._is_overlapping((left_repeat.start, left_repeat.end), (att.start, att.end)):
                return True
        return False

    def _is_overlapping_trna(self, repeat_pair: RepeatPair):
        for trna in self.trnas:
            trna_range = (trna.start, trna.end)
            is_overlapping_left = self._is_overlapping((repeat_pair.left.start, repeat_pair.left.end), trna_range)
            is_overlapping_right = self._is_overlapping((repeat_pair.right.start, repeat_pair.right.end), trna_range)
            if is_overlapping_left or is_overlapping_right:
                return True
        return False

    @staticmethod
    def _is_overlapping(range1, range2):
        max_start = max(range1[0], range2[0])
        min_end = min(range1[1], range2[1])
        return max_start <= min_end

    # `analyse_pipolin_orientation`
    def is_single_target_trna_per_contig(self):
        # TODO: don't like this
        # there was one case with two target trnas per genome, although usually only one
        targeted_contigs = [trna.contig_id for trna in self.target_trnas]
        if len(self.target_trnas) != len(targeted_contigs):
            raise AssertionError("We are expecting a single tRNA to overlap with a single att per contig!")

    # `analyse_pipolin_orientation`
    def get_contig_orientation(self, contig: Contig) -> Orientation:
        target_trnas = self.get_features_of_contig_normalized(contig_id=contig.contig_id,
                                                              feature_type=FeatureType.TARGET_TRNA)
        atts = self.get_features_of_contig_normalized(contig_id=contig.contig_id, feature_type=FeatureType.ATT)
        atts_strands = [att.strand for att in atts]
        polbs = self.get_features_of_contig_normalized(contig_id=contig.contig_id, feature_type=FeatureType.PIPOLB)
        polbs_strands = [polb.strand for polb in polbs]

        if len(target_trnas) != 0:
            if len(set(atts_strands)) != 1:
                raise AssertionError('ATTs are expected to be in the same frame, as they are direct repeats!')
            if set(atts_strands).pop() == target_trnas[0].strand:
                raise AssertionError('ATT and tRNA are expected to be on the different strands!')
            return - target_trnas[0].strand

        elif len(atts) != 0:
            if len(set(atts_strands)) != 1:
                raise AssertionError('ATTs are expected to be in the same frame, as they are direct repeats!')
            return atts[0].strand

        if len(polbs) != 0:
            if len(set(polbs_strands)) != 1:  # an ambiguous case
                return contig.contig_orientation
            return polbs[0].strand


def join_it(iterable, delimiter):
    it = iter(iterable)
    yield next(it)
    for x in it:
        yield delimiter
        yield x


def create_fragment_record(fragment, genome_dict):
    fragment_record = genome_dict[fragment.contig.contig_id][fragment.start:fragment.end]
    if fragment.contig.contig_orientation == Orientation.REVERSE:
        fragment_record = fragment_record.reverse_complement()
    return fragment_record


def feature_from_blasthit(hit, contig_id: str, genome: Genome) -> Feature:
    return Feature(start=hit.hit_start, end=hit.hit_end,
                   strand=Orientation.orientation_from_blast(hit.hit_strand),
                   contig_id=contig_id, genome=genome)
