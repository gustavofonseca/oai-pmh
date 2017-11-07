import unittest

from oaipmh import (
        entities,
        )


class ResumptionTokenInterfaceTest:
    def test_responds_to_encode(self):
        self.assertTrue(hasattr(self.object, 'encode'))

    def test_responds_to_decode(self):
        self.assertTrue(hasattr(self.object, 'decode'))

    def test_responds_to_next(self):
        self.assertTrue(hasattr(self.object, 'next'))

    def test_responds_to_new_from_request(self):
        self.assertTrue(hasattr(self.object, 'new_from_request'))

    def test_responds_to_query_offset(self):
        self.assertTrue(hasattr(self.object, 'query_offset'))

    def test_responds_to_query_from(self):
        self.assertTrue(hasattr(self.object, 'query_from'))

    def test_responds_to_query_until(self):
        self.assertTrue(hasattr(self.object, 'query_until'))

    def test_responds_to_query_count(self):
        self.assertTrue(hasattr(self.object, 'query_count'))

    def test_responds_to_is_first_page(self):
        self.assertTrue(hasattr(self.object, 'is_first_page'))


class ResumptionTokenTests(ResumptionTokenInterfaceTest, unittest.TestCase):

    def setUp(self):
        self.object = entities.ResumptionToken()

    def test_token_is_encoded_correctly(self):
        token = entities.ResumptionToken(set='', from_='1998-01-01',
                until='1998-12-31', offset='1998-01-01(0)', count='1000',
                metadataPrefix='oai_dc')
        self.assertEqual(token.encode(),
                ':1998-01-01:1998-12-31:1998-01-01(0):1000:oai_dc')

    def test_encode_ommit_empty_strings(self):
        token = entities.ResumptionToken(set='', from_='', until='',
                offset='1998-01-01(0)', count='1000', metadataPrefix='oai_dc')
        self.assertEqual(token.encode(),
                ':::1998-01-01(0):1000:oai_dc')

    def test_encode_turns_integer_to_string(self):
        token = entities.ResumptionToken(set='', from_='1998-01-01',
                until='1998-12-31', offset='1998-01-01(0)', count=1000,
                metadataPrefix='oai_dc')
        self.assertEqual(token.encode(),
                ':1998-01-01:1998-12-31:1998-01-01(0):1000:oai_dc')

    def test_encode_treats_none_as_empty_strings(self):
        token = entities.ResumptionToken(set='', from_='1998-01-01',
                until='1998-12-31', offset='1998-01-01(0)', count=None,
                metadataPrefix='oai_dc')
        self.assertEqual(token.encode(),
                ':1998-01-01:1998-12-31:1998-01-01(0)::oai_dc')

    def test_token_is_decoded_correctly(self):
        token = 'foo:1998-01-01:1998-12-31:1998-01-01(0):1000:oai_dc'
        self.assertEqual(entities.ResumptionToken.decode(token),
                entities.ResumptionToken(set='foo', from_='1998-01-01',
                    until='1998-12-31', offset='1998-01-01(0)', count='1000',
                    metadataPrefix='oai_dc'))

    def test_decodes_empty_values_to_empty_strings(self):
        token = ':::1998-01-01(0):1000:oai_dc'
        self.assertEqual(entities.ResumptionToken.decode(token),
                entities.ResumptionToken(set='', from_='', until='',
                    offset='1998-01-01(0)', count='1000',
                    metadataPrefix='oai_dc'))

    def test_first_page_detection(self):
        token = entities.ResumptionToken(set='', from_='1998-01-01',
                until='1998-12-31', offset='1998-01-01(0)', count='1000',
                metadataPrefix='oai_dc')
        self.assertTrue(token.is_first_page())


    def test_non_first_page_detection(self):
        token = entities.ResumptionToken(set='', from_='1998-01-01',
                until='1998-12-31', offset='1998-01-01(100)', count='1000',
                metadataPrefix='oai_dc')
        self.assertFalse(token.is_first_page())

    def test_non_first_page_detection_on_different_from_year(self):
        token = entities.ResumptionToken(set='', from_='1998-01-01',
                until='1999-12-31', offset='1999-01-01(0)', count='1000',
                metadataPrefix='oai_dc')
        self.assertFalse(token.is_first_page())


class ResumptionTokenPrivateMethodTests(unittest.TestCase):
    def test_increments_offset_size(self):
        token = entities.ResumptionToken(set='', from_='1998-01-01',
                until='1998-12-31', offset='1998-01-01(0)', count='1000',
                metadataPrefix='oai_dc')
        self.assertEqual(token._incr_offset_size(),
                entities.ResumptionToken(set='', from_='1998-01-01',
                until='1998-12-31', offset='1998-01-01(1000)', count='1000',
                metadataPrefix='oai_dc'))

    def test_increments_offset_from(self):
        token = entities.ResumptionToken(set='', from_='1998-01-01',
                until='1998-12-31', offset='1998-12-31(1001)', count='1000',
                metadataPrefix='oai_dc')
        self.assertEqual(token._incr_offset_from(),
                entities.ResumptionToken(set='', from_='1998-01-01',
                until='1998-12-31', offset='1999-01-01(0)', count='1000',
                metadataPrefix='oai_dc'))

