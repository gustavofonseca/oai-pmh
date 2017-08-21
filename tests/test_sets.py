import unittest

from oaipmh import sets


class SetsRegistryTests(unittest.TestCase):
    def test_static_sets(self):
        setspec = sets.Set(setSpec='Foo', setName='My testing set spec')
        static_sets = [(setspec, lambda: 'Foo')]
        reg = sets.SetsRegistry(None, static_sets)
        self.assertEqual(list(reg.list()), [static_sets[0][0]])

