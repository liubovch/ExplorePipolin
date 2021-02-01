import unittest

from explore_pipolin.tasks.create_genome import define_genome_id


class TestOthers(unittest.TestCase):
    def test_define_genome_id(self):
        self.assertEqual(define_genome_id('my_genome.fa'), 'my_genome')
        self.assertEqual(define_genome_id('../dir1/dir2/genome.1234.fa'), 'genome.1234')

    def test_too_long_genome_id(self):
        with self.assertRaises(AssertionError):
            define_genome_id('thisisverylongfilename.fa')


if __name__ == '__main__':
    unittest.main()
