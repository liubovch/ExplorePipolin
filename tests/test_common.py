import unittest

from explore_pipolin.common import Orientation, Contig, Genome, Feature, Repeat, PipolinFragment
from explore_pipolin.common import define_genome_id


class UtilitiesTestCase(unittest.TestCase):
    def test_orientation(self):
        self.assertEqual(-Orientation.FORWARD, Orientation.REVERSE)
        self.assertEqual(-Orientation.REVERSE, Orientation.FORWARD)

    def test_blast_orientation(self):
        self.assertEqual(Orientation.orientation_from_blast(1), Orientation.FORWARD)
        self.assertEqual(Orientation.orientation_from_blast(-1), Orientation.REVERSE)
        with self.assertRaises(AssertionError):
            Orientation.orientation_from_blast(0)

    def test_pm_one_encoding(self):
        self.assertEqual(Orientation.FORWARD.to_pm_one_encoding(), 1)
        self.assertEqual(Orientation.REVERSE.to_pm_one_encoding(), -1)

    def test_default_contig_orientation(self):
        self.assertEqual(Contig('foo', 100).contig_orientation, Orientation.FORWARD)

    def setUp(self) -> None:
        self.single_contig_genome = Genome(genome_id='bar', genome_file='dir/bar.fa')
        self.contig1_id = 'foo'
        self.contig1 = Contig(contig_id=self.contig1_id, contig_length=100)
        self.single_contig_genome.contigs = [self.contig1]

        self.multi_contig_genome = Genome(genome_id='car', genome_file='dir/car.fa')
        self.contig2_id = 'boo'
        self.contig2 = Contig(contig_id=self.contig2_id, contig_length=500)
        self.multi_contig_genome.contigs = [self.contig1, self.contig2]

        self.feature = Feature(start=123, end=321, strand=Orientation.REVERSE,
                               contig_id='boo', genome=self.multi_contig_genome)

        self.pipolin = PipolinFragment(contig_id='boo', genome=self.multi_contig_genome, start=300, end=400)

        self.repeat = Repeat(left=(12, 21), right=(45, 54), seq='GATTACA')
        self.left_shift = 100
        self.right_shift = 200
        self.repeat_shifted = Repeat(left=(112, 121), right=(245, 254), seq='GATTACA')

    def test_single_contig_genome(self):
        self.assertTrue(self.single_contig_genome.is_single_contig())
        self.assertEqual(self.single_contig_genome.get_complete_genome_contig_id(), 'foo')
        self.assertEqual(self.single_contig_genome.get_complete_genome_length(), 100)

    def test_multi_contig_genome(self):
        self.assertFalse(self.multi_contig_genome.is_single_contig())
        with self.assertRaises(AssertionError):
            self.multi_contig_genome.get_complete_genome_contig_id()
        with self.assertRaises(AssertionError):
            self.multi_contig_genome.get_complete_genome_length()

    def test_get_contig_by_id(self):
        self.assertEqual(self.single_contig_genome.get_contig_by_id(contig_id=self.contig1_id), self.contig1)
        with self.assertRaises(AssertionError):
            self.single_contig_genome.get_contig_by_id(contig_id=self.contig2_id)

    def test_feature_contig_property(self):
        self.assertEqual(self.feature.contig, self.contig2)

    def test_feature_start_not_greater_end(self):
        with self.assertRaises(AssertionError):
            Feature(start=321, end=123, strand=Orientation.REVERSE,
                    contig_id='boo', genome=self.multi_contig_genome)

    def test_feature_end_not_greater_contig_length(self):
        with self.assertRaises(AssertionError):
            Feature(start=123, end=321, strand=Orientation.FORWARD,
                    contig_id='foo', genome=self.multi_contig_genome)

    def test_repeat_start_not_greater_end(self):
        with self.assertRaises(AssertionError):
            Repeat(left=(123, 321), right=(654, 456), seq='ATCG')

    def test_repeat_seq_not_greater_range(self):
        with self.assertRaises(AssertionError):
            Repeat(left=(1, 3), right=(5, 7), seq='ATCG')

    def test_repeat_shift_left_greater_right(self):
        with self.assertRaises(AssertionError):
            self.repeat.shift(left_shift=250, right_shift=150)

    def test_repeat_shift(self):
        repeat_shifted = self.repeat.shift(left_shift=self.left_shift, right_shift=self.right_shift)
        self.assertEqual(repeat_shifted.left, self.repeat_shifted.left)
        self.assertEqual(repeat_shifted.right, self.repeat_shifted.right)
        self.assertEqual(repeat_shifted.seq, self.repeat_shifted.seq)

    def test_pipolin_contig_property(self):
        self.assertEqual(self.pipolin.contig, self.contig2)

    def test_pipolin_start_not_greater_end(self):
        with self.assertRaises(AssertionError):
            PipolinFragment(contig_id='boo', genome=self.multi_contig_genome, start=400, end=300)

    def test_pipolin_end_not_greater_contig_length(self):
        with self.assertRaises(AssertionError):
            PipolinFragment(contig_id='foo', genome=self.multi_contig_genome, start=300, end=400)

    def test_define_genome_id(self):
        self.assertEqual(define_genome_id('my_genome.fa'), 'my_genome')
        with self.assertRaises(AssertionError):
            define_genome_id('thisisverylongfilebasename.fa')


if __name__ == '__main__':
    unittest.main()