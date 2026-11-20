import unittest
from shard_identity import shard_from_title


class TestShardTitle(unittest.TestCase):
    def setUp(self):
        self.names = ['Legends', 'Lake Superior', 'Great Lakes', 'Napa Valley']

    def test_extracts_canonical(self):
        self.assertEqual(shard_from_title('Ultima Online - privateaccount (Lake Superior)', self.names), 'Lake Superior')

    def test_case_insensitive(self):
        self.assertEqual(shard_from_title('Ultima Online - something (great lakes)', self.names), 'Great Lakes')

    def test_no_suffix(self):
        self.assertIsNone(shard_from_title('Ultima Online - privateaccount', self.names))

    def test_unknown_suffix(self):
        self.assertIsNone(shard_from_title('Ultima Online - privateaccount (Test Shard)', self.names))

    def test_never_leaks_account(self):
        self.assertEqual(shard_from_title('Ultima Online - confidential value (Legends)', self.names), 'Legends')
        self.assertIsNone(shard_from_title('Ultima Online - confidential (not a shard)', self.names))

    def test_extra_suffix_position(self):
        self.assertIsNone(shard_from_title('Ultima Online - privateaccount (Legends) - extra', self.names))


if __name__ == '__main__':
    unittest.main()
