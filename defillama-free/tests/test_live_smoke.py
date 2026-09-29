"""Offline proofs that release checks require fresh, usable endpoint evidence."""
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

SPEC = importlib.util.spec_from_file_location('defillama_live_smoke', Path(__file__).with_name('live_smoke.py'))
smoke = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(smoke)
POOL = '11111111-2222-3333-4444-555555555555'
START = '2026-09-29T17:00:00+00:00'
FETCHED = '2026-09-29T17:00:05+00:00'
END = '2026-09-29T17:00:10+00:00'


def fixtures():
    runs = []
    for name, _ in smoke.CASES + [('yield-history', [])]:
        sid = name + '-source'
        source = {'id': sid, 'url': 'https://api.llama.fi/' + name, 'cached': False, 'fetched_at': FETCHED}
        row = {'metric': 'tvl', 'value': 1, 'status': 'ok', 'source_ids': [sid], 'entity': {}}
        run = {'name': name, 'exit': 0, 'started_at': START, 'finished_at': END,
               'data': {'sources': [source], 'results': [row], 'status': 'ok', 'raw': {}}}
        if name == 'second-protocol':
            row['entity'] = {'slug': 'aave-v3', 'id': 'fixture-aave'}
        elif name == 'stablecoins':
            row['metric'] = 'stablecoin-cap'
        elif name == 'prices':
            row['metric'] = 'price'
        elif name in ('yields', 'yield-history'):
            row['metric'], row['entity'] = 'tvlUsd', {'id': POOL}
        elif name == 'polymarket':
            end = int(datetime(2026, 9, 29, tzinfo=timezone.utc).timestamp())
            base = {'status': 'ok', 'source_ids': [sid], 'entity': {'id': '711', 'slug': 'polymarket-international'},
                    'window_days': 7, 'period_end': '2026-09-29T00:00:00Z'}
            run['data']['results'] = [
                {**base, 'metric': 'volume', 'time_semantics': 'utc_calendar_day', 'value': 7, 'previous_value': 7, 'change_pct': 0},
                {**base, 'metric': 'tvl', 'value': 10, 'previous_value': 5, 'change_pct': 100},
            ] + [{**base, 'metric': metric, 'status': 'unavailable', 'value': None, 'source_observations': [[end - 86400, 1]]}
                 for metric in ('fees', 'revenue', 'supply-side')]
            run['data']['raw'][sid] = {'totalDataChart': [[stamp, 1] for stamp in range(end - 14 * 86400, end, 86400)],
                                     'tvl': [{'date': end - 86400, 'totalLiquidityUSD': 10}, {'date': end - 8 * 86400, 'totalLiquidityUSD': 5}]}
        runs.append(run)
    return runs


def named(runs, name):
    return next(run for run in runs if run['name'] == name)


def checks(runs):
    return {item['check']: item for item in smoke.evaluate_runs(runs)}


class LiveSmokeGateTests(unittest.TestCase):
    def test_complete_fresh_evidence_passes_including_unknown_optional_flows(self):
        result = checks(fixtures())
        self.assertTrue(all(item['passed'] for item in result.values()))
        self.assertEqual('verified_degraded', result['pm-fees-observations']['classification'])

    def test_cached_response_cannot_pass_live_gate(self):
        runs = fixtures()
        for run in runs:
            for source in run['data']['sources']:
                source['cached'] = True
        result = checks(runs)
        self.assertFalse(any(item['passed'] for key, item in result.items() if key.endswith('-fresh-http')))
        self.assertFalse(result['pm-volume']['passed'])
        self.assertFalse(result['yields-list-usable']['passed'])

    def test_stale_future_missing_and_naive_fetch_times_fail(self):
        for fetched in ('2026-09-29T16:59:59Z', '2026-09-29T17:00:11Z', None, '2026-09-29T17:00:05'):
            with self.subTest(fetched=fetched):
                runs = fixtures()
                named(runs, 'prices')['data']['sources'][0]['fetched_at'] = fetched
                result = checks(runs)
                self.assertFalse(result['prices-fresh-http']['passed'])
                self.assertFalse(result['prices-usable']['passed'])

    def test_http_success_with_unusable_yields_list_is_not_sufficient(self):
        runs = fixtures()
        named(runs, 'yields')['data']['results'][0]['value'] = None
        result = checks(runs)
        self.assertTrue(result['yields-fresh-http']['passed'])
        self.assertFalse(result['yields-list-usable']['passed'])
        self.assertFalse(result['yield-history-usable']['passed'])

    def test_second_protocol_cannot_be_another_protocol_tvl(self):
        runs = fixtures()
        named(runs, 'second-protocol')['data']['results'][0]['entity'] = {'id': '711', 'slug': 'polymarket-international'}
        self.assertFalse(checks(runs)['second-protocol-usable']['passed'])

    def test_catalogue_success_cannot_mask_optional_endpoint_network_failure(self):
        runs = fixtures()
        run = named(runs, 'options')
        # Its good source represents only a catalogue. The metric refers to a failed source.
        run['data']['sources'].append({'id': 'failed', 'status': 'unavailable', 'cached': False, 'fetched_at': None})
        run['data']['results'] = [{'metric': 'options', 'value': None, 'status': 'unavailable', 'source_ids': ['failed']}]
        run['data']['status'] = 'unavailable'
        result = checks(runs)
        self.assertTrue(result['options-fresh-http']['passed'])
        self.assertFalse(result['options-observations']['passed'])
        self.assertEqual('unverified', result['options-observations']['classification'])

    def test_optional_retained_observations_can_verify_degraded_coverage(self):
        runs = fixtures()
        run = named(runs, 'options')
        run['data']['status'] = 'unavailable'
        row = run['data']['results'][0]
        row.update(status='unavailable', value=None, source_observations=[[100, 12]])
        result = checks(runs)['options-observations']
        self.assertTrue(result['passed'])
        self.assertEqual('verified_degraded', result['classification'])

    def test_missing_mismatched_pool_history_and_missing_raw_math_fail(self):
        runs = fixtures()
        named(runs, 'yield-history')['data']['results'][0]['entity']['id'] = 'different-pool'
        named(runs, 'polymarket')['data']['raw'] = {}
        result = checks(runs)
        self.assertFalse(result['yield-history-usable']['passed'])
        self.assertFalse(result['pm-volume-independent-math']['passed'])

    def test_every_command_forces_no_cache_including_discovered_history(self):
        with tempfile.TemporaryDirectory() as directory:
            for name, words in smoke.CASES + [('yield-history', ['yields', '--pool', POOL])]:
                def fake_runner(command, **kwargs):
                    self.assertIn('--no-cache', command)
                    self.assertEqual(1, command.count('--no-cache'))
                    target = Path(command[command.index('--output') + 1])
                    target.write_text(json.dumps({'status': 'ok', 'sources': [], 'results': []}))
                    return Mock(returncode=0, stderr='')
                clock = iter([datetime.fromisoformat(START), datetime.fromisoformat(END)])
                run = smoke.run_case((name, words), Path(directory), runner=fake_runner, clock=lambda: next(clock))
                self.assertEqual(START, run['started_at'])
                self.assertEqual(END, run['finished_at'])


if __name__ == '__main__':
    unittest.main()
