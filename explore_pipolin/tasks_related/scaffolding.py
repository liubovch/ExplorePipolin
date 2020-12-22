from enum import Enum, auto
from typing import Sequence, MutableSequence, Optional, Set

from explore_pipolin.common import PipolinFragment, FeatureType, Contig, Feature, Orientation, Pipolin, Genome
from explore_pipolin.tasks_related.misc import get_windows


class Direction(Enum):
    LEFT = auto()
    RIGHT = auto()


class Scaffolder:
    def __init__(self, genome: Genome):
        self.genome = genome
        self.polbs_dict = genome.features.get_features_dict_by_contig_normalized(FeatureType.PIPOLB)
        self.atts_dict = genome.features.get_features_dict_by_contig_normalized(FeatureType.ATT)
        self.target_trnas_dict = genome.features.get_features_dict_by_contig_normalized(FeatureType.TARGET_TRNA)

    def scaffold(self) -> Pipolin:
        unchangeable_contigs = self._get_unchangeable_contigs()

        if len(unchangeable_contigs) == 1:
            unchangeable_contig = unchangeable_contigs[0]
            print(f'The unchangeable contig is {unchangeable_contig.contig_id}!')

            att_only_contigs = self._order_att_only_contigs()
            if len(att_only_contigs) == 1:
                direction = self._get_direction_of_unchangeable(unchangeable_contig.contig_id)

                orphan_atts = self.atts_dict[att_only_contigs[0].contig_id]

                if direction is None:
                    contig_length = unchangeable_contig.contig_length
                    left_edge = self.atts_dict[unchangeable_contig.contig_id][0].coords.start - 50
                    right_edge = self.atts_dict[unchangeable_contig.contig_id][-1].coords.end + 50
                    pipolin = PipolinFragment(contig_id=unchangeable_contig.contig_id, genome=self.genome,
                                              start=left_edge if left_edge >= 0 else 0,
                                              end=right_edge if right_edge <= contig_length else contig_length)
                    pipolin.atts.extend(self.atts_dict[unchangeable_contig.contig_id])
                    return Pipolin(pipolin)
                    # TODO: if att_only_contig has a target_trna, it could be added on the right
                if direction.RIGHT:
                    left_fragment = self._create_unchangeable_fragment(unchangeable_contig, direction)
                    right_fragment = self._create_att_contig_fragment(contig_atts=orphan_atts, direction=direction)
                    return Pipolin(left_fragment, right_fragment)
                else:
                    left_fragment = self._create_att_contig_fragment(contig_atts=orphan_atts, direction=direction)
                    right_fragment = self._create_unchangeable_fragment(unchangeable_contig, direction)
                    return Pipolin(left_fragment, right_fragment)
            elif len(att_only_contigs) == 2:
                # TODO: the order can be also [middle_fragment, left_fragment, right_fragment]
                middle_fragment = PipolinFragment(contig_id=unchangeable_contig.contig_id, genome=self.genome,
                                                  start=0, end=unchangeable_contig.contig_length)
                middle_fragment.atts.extend(self.atts_dict[unchangeable_contig.contig_id])

                left_atts = self.atts_dict[att_only_contigs[0].contig_id]
                left_fragment = self._create_att_contig_fragment(contig_atts=left_atts, direction=Direction.LEFT)

                right_atts = self.atts_dict[att_only_contigs[1].contig_id]
                right_fragment = self._create_att_contig_fragment(contig_atts=right_atts, direction=Direction.RIGHT)

                return Pipolin(left_fragment, middle_fragment, right_fragment)
            else:
                raise NotImplementedError
        elif len(unchangeable_contigs) == 2:
            target_trnas_contig0 = self.target_trnas_dict[unchangeable_contigs[0].contig_id]
            target_trnas_contig1 = self.target_trnas_dict[unchangeable_contigs[1].contig_id]

            if len(target_trnas_contig0) != 0:
                right_contig = unchangeable_contigs[0]
                left_contig = unchangeable_contigs[1]
            elif len(target_trnas_contig1) != 0:
                right_contig = unchangeable_contigs[1]
                left_contig = unchangeable_contigs[0]
            else:
                raise NotImplementedError

            left_direction = self._get_direction_of_unchangeable(left_contig.contig_id)
            left_fragment = self._create_unchangeable_fragment(left_contig, left_direction)

            right_direction = self._get_direction_of_unchangeable(right_contig.contig_id)
            right_fragment = self._create_unchangeable_fragment(right_contig, right_direction)

            return Pipolin(left_fragment, right_fragment)
        elif len(unchangeable_contigs) > 2:
            raise NotImplementedError
        else:
            return self._try_finish_separate()

    def _create_unchangeable_fragment(self, contig: Contig, direction: Direction) -> PipolinFragment:
        if direction is Direction.RIGHT:
            if contig.contig_orientation == Orientation.FORWARD:
                edge = self.atts_dict[contig.contig_id][0].coords.start - 50
                fragment = PipolinFragment(contig_id=contig.contig_id, genome=self.genome,
                                           start=edge if edge >= 0 else 0, end=contig.contig_length)
            else:
                edge = self.atts_dict[contig.contig_id][-1].coords.end + 50
                fragment = PipolinFragment(contig_id=contig.contig_id, start=0, genome=self.genome,
                                           end=edge if edge <= contig.contig_length else contig.contig_length)
        else:
            if contig.contig_orientation == Orientation.FORWARD:
                edge = self.atts_dict[contig.contig_id][-1].coords.end + 50
                fragment = PipolinFragment(contig_id=contig.contig_id, start=0, genome=self.genome,
                                           end=edge if edge <= contig.contig_length else contig.contig_length)
            else:
                edge = self.atts_dict[contig.contig_id][0].coords.start - 50
                fragment = PipolinFragment(contig_id=contig.contig_id, genome=self.genome,
                                           start=edge if edge >= 0 else 0, end=contig.contig_length)

        fragment.atts.extend(self.atts_dict[contig.contig_id])
        return fragment

    def _try_finish_separate(self) -> Pipolin:
        polbs_fragments = self._create_polbs_fragments()

        if len(self.genome.features.get_features(FeatureType.TARGET_TRNA)) != 1:
            raise NotImplementedError('At the moment I can only handle one target tRNA')

        the_target_trna, = self.genome.features.get_features(FeatureType.TARGET_TRNA)

        right_fragment = self._create_att_contig_fragment(contig_atts=self.atts_dict[the_target_trna.contig_id],
                                                          direction=Direction.RIGHT)

        atts_contigs = set([i.contig for i in self.genome.features.get_features(FeatureType.ATT)])
        if len(atts_contigs) == 2:
            print('The single record can be created!!!\n')

            atts_contigs = list(atts_contigs)
            if atts_contigs[0].contig_id == the_target_trna.contig_id:
                left_contig = atts_contigs[1]
            else:
                left_contig = atts_contigs[0]

            left_fragment = self._create_att_contig_fragment(contig_atts=self.atts_dict[left_contig.contig_id],
                                                             direction=Direction.LEFT)
        else:
            raise NotImplementedError

        return Pipolin(left_fragment, *polbs_fragments, right_fragment)

    def _create_polbs_fragments(self) -> Sequence[PipolinFragment]:
        polbs_contigs = set([i.contig for i in self.genome.features.get_features(FeatureType.PIPOLB)])
        if len(polbs_contigs) == 2:
            print('Two "polb only contigs" were found!')
            polbs_contigs = list(polbs_contigs)
            if polbs_contigs[0].contig_length + polbs_contigs[1].contig_length < 15000:
                polb0_fragment = PipolinFragment(contig_id=polbs_contigs[0].contig_id, start=0, genome=self.genome,
                                                 end=polbs_contigs[0].contig_length)
                polb1_fragment = PipolinFragment(contig_id=polbs_contigs[1].contig_id, start=0, genome=self.genome,
                                                 end=polbs_contigs[1].contig_length)

                contig_features = self.genome.features.get_features_of_contig_normalized(
                    contig_id=polbs_contigs[0].contig_id, feature_type=FeatureType.PIPOLB)
                polb0_length = sum((i.coords.end - i.coords.start) for i in contig_features)
                contig_features = self.genome.features.get_features_of_contig_normalized(
                    contig_id=polbs_contigs[1].contig_id, feature_type=FeatureType.PIPOLB)
                polb1_length = sum((i.coords.end - i.coords.start) for i in contig_features)
                # TODO: comparing just by length is an unreliable way! REWRITE if possible!
                if polb0_length < polb1_length:
                    return [polb0_fragment, polb1_fragment]
                else:
                    return [polb1_fragment, polb0_fragment]
            else:
                raise NotImplementedError

        elif len(polbs_contigs) == 1:
            the_polb_contig, = polbs_contigs
            return [PipolinFragment(contig_id=the_polb_contig.contig_id, genome=self.genome,
                                    start=0, end=the_polb_contig.contig_length)]

        raise NotImplementedError

    def _get_unchangeable_contigs(self) -> MutableSequence[Contig]:
        polbs_contigs = set([i.contig for i in self.genome.features.get_features(FeatureType.PIPOLB)])

        contigs_to_return = []
        for contig in polbs_contigs:
            atts_next_polbs = self.genome.features.get_features_of_contig_normalized(contig_id=contig.contig_id,
                                                                                     feature_type=FeatureType.ATT)
            if len(atts_next_polbs) != 0:
                contigs_to_return.append(contig)

        return contigs_to_return

    def _create_att_contig_fragment(self, contig_atts: Sequence[Feature],
                                    direction: Direction) -> PipolinFragment:
        contig = contig_atts[0].contig
        contig_length = contig.contig_length
        if direction is Direction.RIGHT:
            if contig.contig_orientation == Orientation.FORWARD:
                left_edge = 0
                right_edge = contig_atts[-1].coords.end + 50
            else:
                left_edge = contig_atts[0].coords.start - 50
                right_edge = contig_length
        else:
            if contig.contig_orientation == Orientation.FORWARD:
                left_edge = contig_atts[0].coords.start - 50
                right_edge = contig_length
            else:
                left_edge = 0
                right_edge = contig_atts[-1].coords.end + 50

        fragment = PipolinFragment(contig_id=contig.contig_id, genome=self.genome,
                                   start=left_edge if left_edge >= 0 else 0,
                                   end=right_edge if right_edge <= contig_length else contig_length)
        fragment.atts.extend(contig_atts)
        return fragment

    def _order_att_only_contigs(self) -> MutableSequence[Contig]:
        att_only_contigs = list(self._get_att_only_contigs())
        if len(att_only_contigs) == 1:
            print('The single record can be created!!!\n')
            return att_only_contigs
        elif len(att_only_contigs) == 2:
            if self._contig_has_feature_type(att_only_contigs[0].contig_id, FeatureType.TARGET_TRNA):
                # TODO: here sometimes fails for LREC241: KeyError: 'NODE_38'
                print('The single record can be created!!!\n')
                return [att_only_contigs[1], att_only_contigs[0]]
            elif self._contig_has_feature_type(att_only_contigs[1].contig_id, FeatureType.TARGET_TRNA):
                print('The single record can be created!!!\n')
                return [att_only_contigs[0], att_only_contigs[1]]
            else:
                raise NotImplementedError
        else:
            raise NotImplementedError

    def _get_att_only_contigs(self) -> Set[Contig]:
        att_only_contigs = set()
        for att in self.genome.features.get_features(FeatureType.ATT):
            polbs_next_att = self.genome.features.get_features_of_contig_normalized(contig_id=att.contig_id,
                                                                                    feature_type=FeatureType.PIPOLB)
            if len(polbs_next_att) == 0:
                att_only_contigs.add(att.contig)

        return att_only_contigs

    def _get_direction_of_unchangeable(self, contig_id: str) -> Optional[Direction]:
        polbs_sorted = self.polbs_dict[contig_id]
        atts_sorted = self.atts_dict[contig_id]
        if polbs_sorted[0].coords.start > atts_sorted[-1].coords.end:
            if polbs_sorted[0].contig.contig_orientation == Orientation.FORWARD:
                return Direction.RIGHT
            else:
                return Direction.LEFT
        elif polbs_sorted[-1].coords.end < atts_sorted[0].coords.start:
            if polbs_sorted[-1].contig.contig_orientation == Orientation.FORWARD:
                return Direction.LEFT
            else:
                return Direction.RIGHT
        else:
            return None

    def _contig_has_feature_type(self, contig_id: str, feature_type: FeatureType) -> bool:
        feature_dict = self.genome.features.get_features_dict_by_contig_normalized(feature_type)
        return len(feature_dict[contig_id]) != 0


def create_pipolin_fragments_single_contig(genome: Genome) -> Pipolin:
    if len(genome.features.get_features_dict_by_contig_normalized(FeatureType.ATT)) != 0:
        start, end = _get_pipolin_bounds(genome)
        pipolin = PipolinFragment(contig_id=genome.features.get_features(FeatureType.PIPOLB)[0].contig.contig_id,
                                  genome=genome, start=start, end=end)

        pipolin.atts.extend(genome.features.get_features(FeatureType.ATT))
        return Pipolin(pipolin)
    else:
        left_window, right_window = get_windows(genome)
        pipolin = PipolinFragment(contig_id=genome.features.get_features(FeatureType.PIPOLB)[0].contig.contig_id,
                                  genome=genome, start=left_window.start, end=right_window.end)
        return Pipolin(pipolin)


def _get_pipolin_bounds(genome: Genome):
    pipolbs = sorted((i for i in genome.features.get_features(FeatureType.PIPOLB)), key=lambda p: p.start)
    atts = sorted((i for i in genome.features.get_features(FeatureType.ATT)), key=lambda p: p.start)

    length = pipolbs[0].contig.contig_length
    left_edge = atts[0].coords.start - 50 if atts[0].coords.start < pipolbs[0].coords.start \
        else pipolbs[0].coords.start - 50
    right_edge = atts[-1].coords.end + 50 if atts[-1].coords.end > pipolbs[-1].coords.end \
        else pipolbs[-1].coords.end + 50
    return left_edge if left_edge >= 0 else 0, right_edge if right_edge <= length else length
