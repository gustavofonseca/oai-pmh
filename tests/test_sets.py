import unittest

from oaipmh import sets


class SetsRegistryTests(unittest.TestCase):
    def test_static_sets(self):
        setspec = sets.Set(setSpec='Foo', setName='My testing set spec')
        static_sets = [(setspec, lambda: 'Foo')]
        reg = sets.SetsRegistry(None, static_sets)
        self.assertEqual(list(reg.list()), [static_sets[0][0]])


class VirtualOffsetTranslationTests(unittest.TestCase):
    def test_case_1(self):
        self.assertEqual(sets.translate_virtual_offset(10, 0), 0)

    def test_case_2(self):
        self.assertEqual(sets.translate_virtual_offset(10, 0), 0)

    def test_case_3(self):
        self.assertEqual(sets.translate_virtual_offset(150, 0), 0)

    def test_case_4(self):
        self.assertEqual(sets.translate_virtual_offset(150, 101), 0)

