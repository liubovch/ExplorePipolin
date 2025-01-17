import unittest

from explore_pipolin.common import Strand, Contig, Genome, Feature, PipolinFragment, Range, \
    FeaturesContainer, FeatureType, ContigID


class TestOrientation(unittest.TestCase):
    def test_from_pm_one_encoding(self):
        self.assertEqual(Strand.from_pm_one_encoding(1), Strand.FORWARD)
        self.assertEqual(Strand.from_pm_one_encoding(-1), Strand.REVERSE)
        with self.assertRaises(AssertionError):
            Strand.from_pm_one_encoding(0)

    def test_to_pm_one_encoding(self):
        self.assertEqual(Strand.FORWARD.to_pm_one_encoding(), 1)
        self.assertEqual(Strand.REVERSE.to_pm_one_encoding(), -1)

    def test_negation(self):
        self.assertEqual(-Strand.FORWARD, Strand.REVERSE)
        self.assertEqual(-Strand.REVERSE, Strand.FORWARD)


class SetUpGenome(unittest.TestCase):
    def setUp(self) -> None:
        self.short_contig_id = ContigID('foo')
        self.short_contig = Contig(contig_id=self.short_contig_id, contig_length=100)

        self.long_contig_id = ContigID('boo')
        self.long_contig = Contig(contig_id=self.long_contig_id, contig_length=500)

        self.single_contig_genome = Genome(genome_id='bar', genome_file='dir/bar.fa',
                                           contigs=[self.short_contig])

        self.multi_contig_genome = Genome(genome_id='car', genome_file='dir/car.fa',
                                          contigs=[self.short_contig, self.long_contig])

        self.long_contig_feature1_pipolb = Feature(Range(123, 231), Strand.REVERSE, FeatureType.PIPOLB,
                                                   contig_id=self.long_contig_id, genome=self.multi_contig_genome)
        self.long_contig_feature1_trna = Feature(Range(123, 231), Strand.REVERSE, FeatureType.TRNA,
                                                 contig_id=self.long_contig_id, genome=self.multi_contig_genome)
        self.long_contig_feature2_pipolb = Feature(Range(213, 234), Strand.REVERSE, FeatureType.PIPOLB,
                                                   contig_id=self.long_contig_id, genome=self.multi_contig_genome)
        self.long_contig_feature2_trna = Feature(Range(213, 234), Strand.REVERSE, FeatureType.TRNA,
                                                 contig_id=self.long_contig_id, genome=self.multi_contig_genome)
        self.long_contig_feature3_pipolb = Feature(Range(321, 432), Strand.FORWARD, FeatureType.PIPOLB,
                                                   contig_id=self.long_contig_id, genome=self.multi_contig_genome)
        self.long_contig_feature3_trna = Feature(Range(321, 432), Strand.FORWARD, FeatureType.TRNA,
                                                 contig_id=self.long_contig_id, genome=self.multi_contig_genome)
        self.short_contig_feature = Feature(Range(10, 60), Strand.FORWARD, FeatureType.PIPOLB,
                                            contig_id=self.short_contig_id, genome=self.multi_contig_genome)
        self.features = FeaturesContainer()

        self.pipolin = PipolinFragment(location=Range(start=300, end=400), contig_id=ContigID('boo'),
                                       genome=self.multi_contig_genome)

        self.repeat_f1 = Range(start=10, end=15)
        self.repeat_f2 = Range(start=60, end=65)
        self.repeat_f3 = Range(start=65, end=85)


class TestGenome(SetUpGenome):
    def test_is_single_contig(self):
        self.assertTrue(self.single_contig_genome.is_single_contig())
        self.assertFalse(self.multi_contig_genome.is_single_contig())

    def test_get_contig_by_id(self):
        self.assertEqual(self.single_contig_genome.get_contig_by_id(contig_id=self.short_contig_id), self.short_contig)
        with self.assertRaises(AssertionError):
            self.single_contig_genome.get_contig_by_id(contig_id=self.long_contig_id)


class TestRange(SetUpGenome):
    def test_start_greater_than_end(self):
        with self.assertRaises(AssertionError):
            Range(start=20, end=10)

    def test_start_less_than_zero(self):
        with self.assertRaises(AssertionError):
            Range(start=-1, end=10)

    def test_shift(self):
        size = 5
        self.assertEqual(self.repeat_f1.shift(size),
                         Range(self.repeat_f1.start + size, self.repeat_f1.end + size))

    def test_inflate_within_contig(self):
        size = 5
        self.assertEqual(self.repeat_f1.inflate_within_contig(size),
                         Range(self.repeat_f1.start - size, self.repeat_f1.end + size))

    def test_inflate_beyond_zero(self):
        size = 20
        self.assertEqual(self.repeat_f1.inflate_within_contig(size).start, 0)

    def test_is_overlapping(self):
        self.assertFalse(self.repeat_f1.is_overlapping(self.repeat_f2))
        self.assertTrue(self.repeat_f2.is_overlapping(self.repeat_f3))


class TestFeatureClasses(SetUpGenome):
    def test_feature_contig_property(self):
        self.assertEqual(self.long_contig_feature1_pipolb.contig, self.long_contig)

    def test_feature_end_not_greater_contig_length(self):
        with self.assertRaises(AssertionError):
            Feature(Range(start=123, end=321), Strand.FORWARD, FeatureType.PIPOLB,
                    contig_id=self.short_contig.id, genome=self.multi_contig_genome)

    def test_add_get_feature(self):
        self.features.add_features(self.long_contig_feature1_pipolb)
        self.assertEqual(self.features.get_features(FeatureType.PIPOLB).first, self.long_contig_feature1_pipolb)

    def test_get_features_by_contig_sorted(self):
        feature_type = FeatureType.TRNA
        self.features.add_features(self.long_contig_feature2_trna)
        self.features.add_features(self.long_contig_feature3_trna)
        self.features.add_features(self.long_contig_feature1_trna)

        features_dict = self.features.get_features(feature_type).get_dict_by_contig_sorted()
        features_list = self.features.get_features(feature_type).get_list_of_contig_sorted(self.long_contig_id)
        self.assertEqual(features_dict[self.long_contig_id], features_list)

    def test_get_overlapping_with_feature(self):
        self.features.add_features(self.long_contig_feature1_trna)
        self.features.add_features(self.long_contig_feature3_pipolb)

        ofeature_present = self.features.get_features(FeatureType.TRNA).get_overlapping(self.long_contig_feature2_trna)
        self.assertEqual(ofeature_present, self.long_contig_feature1_trna)

        ofeature_absent = self.features.get_features(FeatureType.PIPOLB).get_overlapping(
            self.long_contig_feature2_pipolb
        )
        self.assertIsNone(ofeature_absent)

    def test_is_on_the_same_contig(self):
        self.features.add_features(self.long_contig_feature1_trna)
        self.features.add_features(self.long_contig_feature2_pipolb)
        self.assertTrue(self.features.is_on_the_same_contig(FeatureType.TRNA, FeatureType.PIPOLB))

        self.features.add_features(self.short_contig_feature)
        self.assertFalse(self.features.is_on_the_same_contig(FeatureType.TRNA, FeatureType.PIPOLB))


if __name__ == '__main__':
    unittest.main()
