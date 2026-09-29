import contextlib
import csv
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from defillama_lib import cli


class CliTests(unittest.TestCase):
    def parse(self, words):
        return cli.validate(dict(cli.DEFAULTS, **vars(cli.parser().parse_args(words))))

    def test_global_flags_before_and_after_subcommand(self):
        a = self.parse(['--no-cache', '--format', 'csv', 'search', 'poly', '--limit', '5'])
        self.assertEqual((a['format'], a['no_cache'], a['limit']), ('csv', True, 5))
        self.assertEqual(self.parse(['search', 'poly', '--format', 'csv'])['format'], 'csv')

    def test_invalid_requests_fail_before_fetch(self):
        cases = [['prices', 'coingecko:btc?foo=x'], ['protocol', '../bad'],
                 ['protocol', 'aave-v3', '--start', '2026-01-01'],
                 ['protocol', 'aave-v3', '--days', '0'], ['protocol', 'aave-v3', '--metrics', 'users'],
                 ['compare', 'aave-v3', 'aave-v3'], ['yields', '--min-tvl', 'nan'],
                 ['search', 'a', '--limit', '101'], ['prices', 'coingecko:btc', '--raw', '--format', 'csv']]
        for case in cases:
            with self.subTest(case=case), self.assertRaises(ValueError):
                self.parse(case)

    def test_capabilities_offline_and_cli_entrypoint(self):
        with patch('defillama_lib.client.Client.get', side_effect=AssertionError('network')):
            result = cli.execute(self.parse(['capabilities']))
        self.assertEqual(result['status'], 'ok')
        proc = subprocess.run([sys.executable, str(Path(__file__).resolve().parents[1] / 'scripts/defillama.py'), '--help'], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0)
        self.assertIn('stablecoins', proc.stdout)

    def test_output_refuses_existing_before_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory)/'result.json'; p.write_text('keep')
            with contextlib.redirect_stderr(io.StringIO()), patch.object(cli, 'execute', side_effect=AssertionError('must not run')):
                self.assertEqual(cli.main(['capabilities', '--output', str(p)]), 2)
            self.assertEqual(p.read_text(), 'keep')
            self.assertEqual(cli.main(['capabilities', '--output', str(p), '--overwrite']), 0)
            self.assertEqual(json.loads(p.read_text())['status'], 'ok')

    def test_custom_dates_reach_analysis_without_days_conflict(self):
        bundle = {'series':[{'entity':{'id':'x'},'metric':'tvl','kind':'stock','unit':'USD','points':[[1767139200,10],[1767225600,20]],'source_ids':[],'time_semantics':'snapshot','timestamp_role':'sample_time','status':'ok'}]}
        with patch('defillama_lib.providers.Provider.dispatch', return_value=bundle):
            result = cli.execute(self.parse(['protocol','aave-v3','--metrics','tvl','--start','2026-01-01','--end','2026-01-01']))
        self.assertEqual(result['results'][0]['value'], 20)
        self.assertEqual(result['results'][0]['previous_value'], 10)

    def test_csv_retains_missing_provenance_and_escapes_formula(self):
        result = {'status':'partial','sources':[{'id':'s','url':'https://api.llama.fi/protocol/x','fetched_at':'2026-01-01T00:00:00Z'}], 'results':[{'entity':{'name':' =BAD()'},'metric':'fees','value':None,'status':'unavailable','reason':'missing','source_ids':['s']}]}
        records = list(csv.DictReader(io.StringIO(cli.csv_text(result))))
        self.assertTrue(any(r['field']=='value' and r['value']=='' for r in records))
        self.assertTrue(all(r['source_url'].startswith('https://') for r in records))
        self.assertTrue(all(r['entity'].startswith("'") for r in records))

    def test_listing_truncation_and_partial_status_retained(self):
        bundle = {'records':[{'entity':{'id':'x'},'metric':'tvl','value':0,'status':'ok'}, {'metric':'apy','value':None,'status':'unavailable'}], 'count':500,'truncated':True}
        with patch('defillama_lib.providers.Provider.dispatch', return_value=bundle):
            result = cli.execute(self.parse(['yields']))
        self.assertEqual(result['status'], 'partial')
        self.assertEqual(result['listing']['count'], 500)
        self.assertTrue(result['listing']['truncated'])

if __name__ == '__main__':
    unittest.main()
