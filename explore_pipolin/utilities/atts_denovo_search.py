from __future__ import annotations
import os

from typing import Tuple, Sequence

from explore_pipolin.utilities.external_tools_run import blast_for_repeats
from explore_pipolin.utilities.io import read_blastxml
from explore_pipolin.utilities.io import save_left_right_subsequences


def find_repeats(genome, gquery, repeats_dir) -> Sequence[Repeat]:
    left_window, right_window = gquery.get_left_right_windows()
    save_left_right_subsequences(genome=genome, left_window=left_window, right_window=right_window,
                                 repeats_dir=repeats_dir)
    blast_for_repeats(gquery_id=gquery.gquery_id, repeats_dir=repeats_dir)
    repeats = _extract_repeats(file=os.path.join(repeats_dir, gquery.gquery_id + '.fmt5'))
    repeats = [rep.shift(left_window[0], right_window[0]) for rep in repeats]
    return repeats


class Repeat:
    def __init__(self, left: Tuple[int, int], right: Tuple[int, int], seq: str):
        self.left = left
        self.right = right
        self.seq = seq

    def shift(self, left_shift: int, right_shift: int) -> Repeat:
        return Repeat(self._shift_range(self.left, left_shift), self._shift_range(self.right, right_shift), self.seq)

    @staticmethod
    def _shift_range(seq_range: Tuple[int, int], shift):
        return seq_range[0] + shift, seq_range[1] + shift


def _extract_repeats(file) -> Sequence[Repeat]:
    repeats_xml = read_blastxml(file)
    repeats = []
    for entry in repeats_xml:
        for hit in entry:
            repeats.append(Repeat((hit.query_start, hit.query_end), (hit.hit_start, hit.hit_end), str(hit.hit.seq)))
    return repeats

