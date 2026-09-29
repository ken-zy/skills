"""Regressions found by using the skill's documented research/export workflow."""
import contextlib
import csv
import hashlib
import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from defillama_lib.cli import DEFAULTS, execute, main, parser, validate, csv_text
from defillama_lib.client import FetchError

CATALOG_URL = 'https://api.llama.fi/protocols'


def arguments(*argv):
    return validate(dict(DEFAULTS, **vars(parser().parse_args(argv))))


class CatalogClient:
    def __init__(self, rows):
        self.rows = rows
        self.urls = []

    def get(self, url):
        self.urls.append(url)
        return {'data': self.rows, 'source': {
            'id': hashlib.sha256(url.encode()).hexdigest(), 'url': url,
            'fetched_at': '2026-09-29T17:22:00Z', 'http_date': None, 'cached': False,
        }}


class ForwardRegressionTests(unittest.TestCase):
    def test_bounded_search_discloses_total_matches_and_truncation(self):
        client = CatalogClient([
            {'id': '711', 'slug': 'polymarket-international', 'name': 'Polymarket International', 'chains': ['Polygon']},
            {'id': '7656', 'slug': 'polymarket-us', 'name': 'Polymarket US', 'chains': []},
            {'id': '8223', 'slug': 'polymarket-combos', 'name': 'Polymarket Combos', 'chains': []},
        ])
        result = execute(arguments('search', 'polymarket', '--limit', '1', '--raw'), client)
        self.assertEqual('ok', result['status'])
        self.assertEqual(1, len(result['results']))
        self.assertEqual(3, result['listing']['count'])
        self.assertIs(True, result['listing']['truncated'])
        self.assertEqual([CATALOG_URL], client.urls)
        source_id = result['results'][0]['source_ids'][0]
        self.assertEqual(CATALOG_URL, result['sources'][0]['url'])
        self.assertEqual(client.rows, result['raw'][source_id])
        exported = list(csv.DictReader(io.StringIO(csv_text(result))))
        metadata = {r['field']: r['value'] for r in exported if r['record_type'] == 'metadata'}
        self.assertEqual('3', metadata['listing.count'])
        self.assertEqual('True', metadata['listing.truncated'])
        self.assertEqual('1', metadata['requested_scope.limit'])
        self.assertEqual('polymarket', metadata['requested_scope.query'])

    def test_dispatch_failure_retains_requested_url_error_and_source_link(self):
        class OfflineClient:
            def get(self, url):
                raise FetchError('network_error', 'Request failed: URLError', url)

        result = execute(arguments('search', 'polymarket', '--raw'), OfflineClient())
        self.assertEqual('unavailable', result['status'])
        self.assertEqual(1, len(result['sources']))
        source = result['sources'][0]
        self.assertEqual(CATALOG_URL, source['url'])
        self.assertEqual('unavailable', source['status'])
        self.assertIsNone(source['fetched_at'])
        self.assertTrue(source['attempted_at'])
        failure = result['results'][0]
        self.assertEqual([source['id']], failure['source_ids'])
        self.assertEqual('network_error', failure['error']['code'])
        self.assertEqual(CATALOG_URL, failure['error']['url'])
        self.assertEqual({}, result['raw'])
        exported = list(csv.DictReader(io.StringIO(csv_text(result))))
        self.assertTrue(any(r['record_type'] == 'metadata' and r['field'] == 'status' and r['value'] == 'unavailable' for r in exported))
        self.assertTrue(any(r['record_type'] == 'source' and r['source_url'] == CATALOG_URL for r in exported))

    def test_duplicate_slugs_cannot_bypass_compare_request_bound(self):
        # Historically two distinct slugs plus many repeats passed len(set(...)).
        cases = [
            ['aave-v3', 'compound-v3'] + ['aave-v3'] * 100,
            ['aave-v3', 'compound-v3', 'aave-v3'],
            ['one', 'two', 'three', 'four', 'five', 'six'],
        ]
        for slugs in cases:
            with self.subTest(count=len(slugs)):
                error = io.StringIO()
                with patch('defillama_lib.client.Client', side_effect=AssertionError('No network client should be created for invalid input')):
                    with contextlib.redirect_stderr(error):
                        status = main(['compare', *slugs, '--raw'])
                self.assertEqual(2, status)
                self.assertIn('2-5 distinct', json.loads(error.getvalue())['error'])
        valid = arguments('compare', 'aave-v3', 'compound-v3', '--raw')
        self.assertEqual(['aave-v3', 'compound-v3'], valid['slugs'])


if __name__ == '__main__':
    unittest.main()
