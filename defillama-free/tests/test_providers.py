import http.client
import io
import json
import sys
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from defillama_lib.providers import Provider, API, STABLE, YIELDS, COINS, number
from defillama_lib.client import Client, FetchError
from defillama_lib import cli

CANONICAL = {'id': '711', 'slug': 'polymarket-international', 'name': 'Polymarket International',
             'parentProtocol': 'parent#polymarket', 'chains': ['Polygon'], 'category': 'Prediction Market'}


class FakeClient:
    def __init__(self, responses):
        self.responses = responses
        self.urls = []

    def get(self, url):
        self.urls.append(url)
        parsed = urlsplit(url)
        key = parsed.netloc + parsed.path
        payload = self.responses[key]
        if isinstance(payload, Exception):
            raise payload
        return {'data': payload, 'source': {'id': url, 'url': url, 'fetched_at': '2026-01-01T00:00:00Z',
                                          'http_date': None, 'cached': False}}


class ResponseSocket:
    def __init__(self, wire):
        self.wire = wire

    def makefile(self, mode):
        return io.BytesIO(self.wire)


class JSONOpener:
    """Inject only HTTP bytes; exercise real Client decoding, Provider and CLI."""
    def __init__(self, responses):
        self.responses = responses
        self.urls = []

    def open(self, request, timeout):
        self.urls.append(request.full_url)
        parsed = urlsplit(request.full_url)
        key = parsed.netloc + parsed.path
        data_type = parse_qs(parsed.query).get('dataType', [None])[0]
        data = self.responses[(key, data_type)] if (key, data_type) in self.responses else self.responses[key]
        body = json.dumps(data, allow_nan=False).encode()
        wire = ('HTTP/1.1 200 OK\r\nContent-Length: ' + str(len(body)) + '\r\n\r\n').encode() + body
        response = http.client.HTTPResponse(ResponseSocket(wire))
        response.begin()
        return response


class ProvidersTests(unittest.TestCase):
    def protocol_client(self, **overrides):
        data = {'api.llama.fi/protocols': [CANONICAL],
                'api.llama.fi/protocol/polymarket-international': {**CANONICAL, 'tvl': [{'date': 1767225600, 'totalLiquidityUSD': 0}]},
                'api.llama.fi/summary/dexs/polymarket-international': {**CANONICAL, 'totalDataChart': [[1767225600, 20]], 'total24h': 25},
                'api.llama.fi/summary/fees/polymarket-international': {**CANONICAL, 'totalDataChart': [[1767225600, -2]]}}
        data.update(overrides)
        return FakeClient(data)

    def test_identity_mismatch_does_not_suppress_other_metric(self):
        client = self.protocol_client(**{'api.llama.fi/summary/dexs/polymarket-international':
                                        {**CANONICAL, 'id': 'parent#polymarket', 'totalDataChart': [[1767225600, 20]]}})
        output = Provider(client).dispatch('protocol', {'slug': CANONICAL['slug'], 'metrics': ['tvl', 'volume']})
        self.assertEqual([s['status'] for s in output['series']], ['ok', 'unavailable'])
        self.assertEqual(output['series'][0]['points'][0][1], 0)
        self.assertIn('ID mismatch', output['series'][1]['reason'])

    def test_no_name_similarity_identity(self):
        client = self.protocol_client(**{'api.llama.fi/summary/dexs/polymarket-international':
                                        {'name': CANONICAL['name'], 'totalDataChart': [[1767225600, 20]]}})
        output = Provider(client).dispatch('protocol', {'slug': CANONICAL['slug'], 'metrics': ['volume']})
        self.assertEqual(output['series'][0]['status'], 'unavailable')

    def test_scope_preserves_source_chain_and_version(self):
        changed = {**CANONICAL, 'chains': ['Ethereum'], 'version': 'v3', 'totalDataChart': [[1767225600, -2]]}
        client = self.protocol_client(**{'api.llama.fi/summary/fees/polymarket-international': changed})
        output = Provider(client).dispatch('protocol', {'slug': CANONICAL['slug'], 'metrics': ['volume', 'revenue']})
        self.assertEqual(output['series'][0]['scope']['chains'], ['Polygon'])
        self.assertEqual(output['series'][1]['scope']['chains'], ['Ethereum'])
        self.assertEqual(output['series'][1]['scope']['version'], 'v3')
        self.assertEqual(output['series'][1]['points'][0][1], -2)

    def test_utc_mapping_is_narrow_and_history_explicit(self):
        client = self.protocol_client()
        output = Provider(client).dispatch('protocol', {'slug': CANONICAL['slug'], 'metrics': ['volume', 'fees']})
        self.assertEqual(output['series'][0]['time_semantics'], 'utc_calendar_day')
        self.assertEqual(output['series'][1]['time_semantics'], 'unknown')
        self.assertIsNone(output['records'][0]['interval_end'])
        for url in client.urls:
            if '/summary/' in url:
                self.assertEqual(parse_qs(urlsplit(url).query)['excludeTotalDataChart'], ['false'])
        self.assertEqual(output['series'][1]['points'][0][1], -2)

    def test_stablecoins_use_usd_valuation_and_keep_missing(self):
        client = FakeClient({'stablecoins.llama.fi/stablecoincharts/all': [
            {'date': '1767225600', 'totalCirculating': {'peggedUSD': 2, 'peggedEUR': 3},
             'totalCirculatingUSD': {'peggedUSD': 2, 'peggedEUR': 3.3}},
            {'date': '1767312000', 'totalCirculatingUSD': {'peggedUSD': 2, 'peggedEUR': None}}]})
        output = Provider(client).dispatch('stablecoins', {})
        self.assertEqual(output['series'][0]['points'], [[1767225600, 5.3], [1767312000, None]])

    def test_missing_price_is_retained_and_observation_not_fetch_time(self):
        client = FakeClient({'coins.llama.fi/prices/current/coingecko:ethereum,ethereum:0x123':
                             {'coins': {'coingecko:ethereum': {'price': 0, 'timestamp': 1767225600, 'confidence': .99}}}})
        output = Provider(client).dispatch('prices', {'tokens': ['coingecko:ethereum', 'ethereum:0x123']})
        self.assertEqual(len(output['records']), 2)
        self.assertEqual(output['records'][0]['value'], 0)
        self.assertEqual(output['records'][1]['status'], 'unavailable')
        self.assertIsNone(output['records'][1]['observed_at'])

    def test_yields_null_apy_and_zero_tvl(self):
        client = FakeClient({'yields.llama.fi/pools': {'data': [
            {'pool': '1', 'symbol': 'A', 'project': 'a', 'chain': 'Polygon', 'tvlUsd': 0, 'apy': None, 'apyBase': 0, 'apyReward': None},
            {'pool': '2', 'symbol': 'B', 'project': 'b', 'chain': 'Polygon', 'tvlUsd': 10, 'apy': 2}]}})
        output = Provider(client).dispatch('yields', {'limit': 1})
        self.assertTrue(output['truncated'])
        self.assertEqual(output['records'][0]['entity']['id'], '2')
        output = Provider(client).dispatch('yields', {'project': 'a'})
        self.assertEqual(output['records'][0]['value'], 0)
        self.assertIsNone(output['records'][1]['value'])
        self.assertEqual(output['records'][2]['value'], 0)

    def test_open_interest_does_not_sum_rolling_fields(self):
        client = FakeClient({'api.llama.fi/overview/open-interest': {'protocols': [
            {'slug': 'a', 'id': '1', 'total24h': 12, 'total7d': 200, 'total30d': 999}]}})
        output = Provider(client).dispatch('open-interest', {})
        self.assertEqual(output['records'][0]['value'], 12)
        self.assertEqual(output['records'][0]['kind'], 'stock')
        self.assertIsNone(output['records'][0]['observed_at'])
        self.assertEqual(output['series'], [])

    def test_empty_search_and_offline_capabilities(self):
        output = Provider(self.protocol_client()).dispatch('search', {'query': 'does-not-exist'})
        self.assertTrue(output['empty'])
        self.assertEqual(output['count'], 0)
        output = Provider(FakeClient({})).dispatch('capabilities', {})
        self.assertEqual(output['sources'], [])

    def test_fetch_failure_has_exact_source_url(self):
        client = self.protocol_client(**{'api.llama.fi/summary/dexs/polymarket-international':
                                        FetchError('network', 'offline', 'ignored')})
        output = Provider(client).dispatch('protocol', {'slug': CANONICAL['slug'], 'metrics': ['volume']})
        failed = [s for s in output['sources'] if s.get('status') == 'unavailable']
        self.assertEqual(len(failed), 1)
        self.assertIn('/summary/dexs/polymarket-international?', failed[0]['url'])
        self.assertEqual(output['series'][0]['source_ids'], [failed[0]['id']])
        self.assertIsNone(failed[0]['fetched_at'])

    def test_response_datatype_mismatch_and_health_preserved(self):
        mismatch = {**CANONICAL, 'totalDataChart': [[1767225600, 5]], 'dataType': 'dailyRevenue'}
        client = self.protocol_client(**{'api.llama.fi/summary/fees/polymarket-international': mismatch})
        output = Provider(client).dispatch('protocol', {'slug': CANONICAL['slug'], 'metrics': ['fees']})
        self.assertEqual(output['series'][0]['status'], 'unavailable')
        mismatch['dataType'] = 'dailyFees'
        mismatch['latestFetchIsOk'] = False
        output = Provider(client).dispatch('protocol', {'slug': CANONICAL['slug'], 'metrics': ['fees']})
        self.assertEqual(output['series'][0]['status'], 'ok')
        self.assertFalse(output['series'][0]['upstream_health']['latestFetchIsOk'])

    def test_changed_chain_does_not_inherit_utc_mapping(self):
        changed = {**CANONICAL, 'chains': ['Ethereum'], 'totalDataChart': [[1767225600, 5]]}
        client = self.protocol_client(**{'api.llama.fi/summary/dexs/polymarket-international': changed})
        output = Provider(client).dispatch('protocol', {'slug': CANONICAL['slug'], 'metrics': ['volume']})
        self.assertEqual(output['series'][0]['time_semantics'], 'unknown')

    def test_options_parent_dashboard_has_own_authoritative_identity(self):
        client = FakeClient({'api.llama.fi/summary/options/derive': {
            'slug': 'derive', 'id': 'parent#lyra', 'defillamaId': 'parent#lyra',
            'chains': ['Derive Chain'], 'totalDataChart': [[1767225600, 12]]}})
        output = Provider(client).dispatch('options', {'slug': 'derive', 'kind': 'notional'})
        self.assertEqual(output['series'][0]['status'], 'ok')
        self.assertEqual(output['series'][0]['metric'], 'options-notional')
        self.assertEqual(output['series'][0]['entity']['id'], 'parent#lyra')
        self.assertEqual(output['series'][0]['time_semantics'], 'unknown')
        client.responses['api.llama.fi/summary/options/derive']['slug'] = 'derive-parent'
        output = Provider(client).dispatch('options', {'slug': 'derive', 'kind': 'notional'})
        self.assertEqual(output['series'][0]['status'], 'unavailable')

    def test_stablecoin_metadata_bounds_chain_distribution_to_latest(self):
        client = FakeClient({
            'stablecoins.llama.fi/stablecoins': {'peggedAssets': [{'id': '1'}]},
            'stablecoins.llama.fi/stablecoin/1': {'id': '1', 'name': 'Tether', 'chainBalances': {
                'Ethereum': {'tokens': [{'date': '1767225600', 'circulating': {'peggedUSD': 1}},
                                        {'date': '1767312000', 'circulating': {'peggedUSD': 2}}]}}},
            'stablecoins.llama.fi/stablecoincharts/all': []})
        output = Provider(client).dispatch('stablecoins', {'id': '1'})
        metadata = output['records'][0]['metadata']
        self.assertEqual(metadata['currentChainSupply']['Ethereum']['circulating']['peggedUSD'], 2)
        self.assertNotIn('chainBalances', metadata)

    def execute(self, words, responses):
        args = cli.validate(dict(cli.DEFAULTS, **vars(cli.parser().parse_args(words))))
        result = cli.execute(args, client=FakeClient(responses))
        json.dumps(result, allow_nan=False)
        return result

    def test_malformed_list_rows_preserve_good_records_through_cli(self):
        pool = {'pool': 'good', 'symbol': 'USDC', 'project': 'good', 'chain': 'Polygon',
                'tvlUsd': 12, 'apy': 2, 'apyBase': 2, 'apyReward': 0}
        cases = [
            (['chains'], {'api.llama.fi/v2/chains': [None, 'bad', {'name': None}, {'name': 'Polygon', 'tvl': 12}]}),
            (['open-interest'], {'api.llama.fi/overview/open-interest': {'protocols': [None, 'bad', {'slug': 'good', 'total24h': 12}]}}),
            (['yields'], {'yields.llama.fi/pools': {'data': [None, 'bad', {**pool, 'chain': []}, pool]}}),
        ]
        for words, responses in cases:
            with self.subTest(words=words):
                result = self.execute(words, responses)
                self.assertEqual(result['status'], 'partial')
                self.assertTrue(any(r['value'] == 12 for r in result['results']))
                bad = [r for r in result['results'] if r['status'] == 'unavailable']
                self.assertTrue(bad)
                self.assertTrue(all(r['value'] is None and r['source_ids'] and r['reason'] for r in bad))
                self.assertTrue(all(s['url'].startswith('https://') for s in result['sources']))

    def test_primitive_payloads_become_structured_cli_failures(self):
        cases = [(['chains'], 'api.llama.fi/v2/chains'),
                 (['yields'], 'yields.llama.fi/pools'),
                 (['open-interest'], 'api.llama.fi/overview/open-interest'),
                 (['stablecoins'], 'stablecoins.llama.fi/stablecoincharts/all')]
        for words, key in cases:
            for malformed in (None, 'bad', 12):
                with self.subTest(words=words, malformed=malformed):
                    result = self.execute(words, {key: malformed})
                    self.assertEqual(result['status'], 'unavailable')
                    self.assertTrue(result['sources'][0]['url'].startswith('https://'))
                    self.assertTrue(all(r.get('value') is None for r in result['results']))

    def test_stablecoin_nested_damage_preserves_history_and_metadata(self):
        responses = {
            'stablecoins.llama.fi/stablecoins': {'peggedAssets': [None, {'id': '1'}]},
            'stablecoins.llama.fi/stablecoin/1': {'id': '1', 'name': 'Tether', 'chainBalances': {
                'Broken': [], 'Ethereum': {'tokens': [None, {'date': None},
                    {'date': '1767225600', 'circulating': {'peggedUSD': 12}}]}}},
            'stablecoins.llama.fi/stablecoincharts/all': [None, {'date': {}},
                {'date': '1767225600', 'totalCirculatingUSD': {'peggedUSD': 12}}]}
        result = self.execute(['stablecoins', '1', '--start', '2026-01-01', '--end', '2026-01-01'], responses)
        self.assertEqual(result['status'], 'partial')
        metadata = next(r for r in result['results'] if r['metric'] == 'stablecoin-metadata')
        self.assertEqual(metadata['metadata']['currentChainSupply']['Ethereum']['circulating']['peggedUSD'], 12)
        self.assertTrue(any(r.get('value') == 12 for r in result['results']))
        self.assertTrue(all(r['source_ids'] for r in result['results']))

    def test_pool_history_skips_bad_rows_without_discarding_good_observations(self):
        pool = '747c1d2a-c668-4682-b9f9-296708a3dd90'
        client = FakeClient({'yields.llama.fi/chart/' + pool: {'data': [None, 'bad',
            {'timestamp': 'bad'}, {'timestamp': '2026-01-01T00:00:00Z', 'tvlUsd': 12, 'apy': 0}]}})
        result = Provider(client).dispatch('yields', {'pool': pool})
        self.assertEqual(result['series'][0]['points'], [[1767225600, 12]])
        self.assertEqual(len(result['records']), 3)
        self.assertTrue(all(r['status'] == 'unavailable' for r in result['records']))

    def test_pool_iso_fractional_seconds_normalize_without_accepting_numeric_fractions(self):
        pool = '747c1d2a-c668-4682-b9f9-296708a3dd90'
        client = FakeClient({'yields.llama.fi/chart/' + pool: {'data': [
            {'timestamp': '2022-09-05T23:00:30.679Z', 'tvlUsd': 12},
            {'timestamp': '2026-01-01T08:00:30.175+08:00', 'tvlUsd': 15},
            {'timestamp': 1767225630.175, 'tvlUsd': 99},
            {'timestamp': '2026-01-01T08:00:30.175', 'tvlUsd': 99}]}})
        result = Provider(client).dispatch('yields', {'pool': pool})
        self.assertEqual(result['series'][0]['points'], [[1662418830, 12], [1767225630, 15]])
        self.assertEqual(len(result['records']), 2)
        self.assertTrue(all(r['status'] == 'unavailable' for r in result['records']))

    def test_huge_integer_and_aggregate_overflow_are_missing_not_crashes(self):
        self.assertIsNone(number(10 ** 400))
        self.assertIsNone(Provider._usd_total({'a': 1e308, 'b': 1e308}))
        result = self.execute(['chains'], {'api.llama.fi/v2/chains': [
            {'name': 'Good', 'tvl': 12}, {'name': 'Huge', 'tvl': 10 ** 400}]})
        self.assertEqual(result['status'], 'partial')
        self.assertEqual(result['results'][0]['value'], 12)
        self.assertIsNone(result['results'][1]['value'])

    def test_chain_aggregate_echo_conflict_rejects_only_affected_metric(self):
        responses = {
            'api.llama.fi/v2/chains': [{'name': 'Polygon', 'chainId': 137, 'tvl': 13}],
            'api.llama.fi/v2/historicalChainTvl/Polygon': [
                {'date': 1709078400, 'tvl': 12}, {'date': 1709164800, 'tvl': 13}],
            'api.llama.fi/overview/dexs/Polygon': {'dataType': 'dailyVolume', 'totalDataChart': [[1709164800, 88]]},
            ('api.llama.fi/overview/fees/Polygon', 'dailyFees'): {'dataType': 'dailyFees', 'totalDataChart': [[1709164800, 900]]},
            ('api.llama.fi/overview/fees/Polygon', 'dailyRevenue'): {'dataType': 'dailyRevenue', 'totalDataChart': [[1709164800, 777]]}}
        args = cli.validate(dict(cli.DEFAULTS, **vars(cli.parser().parse_args([
            'chains', 'Polygon', '--start', '2024-02-29', '--end', '2024-02-29', '--raw']))))
        for echoed_type in ('dailyRevenue', 'dailyFees'):
            with self.subTest(echoed_type=echoed_type):
                responses[('api.llama.fi/overview/fees/Polygon', 'dailyRevenue')]['dataType'] = echoed_type
                result = cli.execute(args, client=Client(no_cache=True, opener=JSONOpener(responses)))
                json.dumps(result, allow_nan=False)
                self.assertIn('Chain fees/revenue are the API dashboard aggregate', cli.csv_text(result))
                revenue = next(row for row in result['results'] if row['metric'] == 'revenue')
                tvl = next(row for row in result['results'] if row['metric'] == 'tvl')
                fees = next(row for row in result['results'] if row['metric'] == 'fees')
                self.assertEqual(tvl['value'], 13)
                self.assertEqual(fees['source_observations'], [[1709164800, 900]])
                source = next(row for row in result['sources'] if row['id'] in revenue['source_ids'])
                self.assertIn('dataType=dailyRevenue', source['url'])
                self.assertEqual(result['raw'][source['id']]['dataType'], echoed_type)
                if echoed_type == 'dailyRevenue':
                    self.assertEqual(revenue['source_observations'], [[1709164800, 777]])
                else:
                    self.assertEqual(revenue['status'], 'unavailable')
                    self.assertEqual(revenue['source_observations'], [])
                    self.assertIn('dataType differs', revenue['reason'])
                    self.assertIsNone(revenue['value'])

    def test_real_client_json_damage_preserves_good_cli_records(self):
        args = cli.validate(dict(cli.DEFAULTS, **vars(cli.parser().parse_args(['chains']))))
        responses = {'api.llama.fi/v2/chains': [None, 'bad',
            {'name': 'Good', 'tvl': 12}, {'name': 'Huge', 'tvl': 10 ** 400}]}
        result = cli.execute(args, client=Client(no_cache=True, opener=JSONOpener(responses)))
        json.dumps(result, allow_nan=False)
        self.assertEqual(result['status'], 'partial')
        self.assertTrue(any(row['value'] == 12 for row in result['results']))
        bad = [row for row in result['results'] if row['status'] == 'unavailable']
        self.assertEqual(len(bad), 3)
        self.assertTrue(all(row['value'] is None and row['reason'] and row['source_ids'] for row in bad))
        self.assertEqual(result['sources'][0]['url'], 'https://api.llama.fi/v2/chains')

    def test_real_client_null_yield_row_returns_structured_unavailable(self):
        args = cli.validate(dict(cli.DEFAULTS, **vars(cli.parser().parse_args(['yields']))))
        result = cli.execute(args, client=Client(no_cache=True, opener=JSONOpener({
            'yields.llama.fi/pools': {'data': [None]}})))
        json.dumps(result, allow_nan=False)
        self.assertEqual(result['status'], 'unavailable')
        self.assertEqual(len(result['results']), 1)
        self.assertIsNone(result['results'][0]['value'])
        self.assertIn('expected object', result['results'][0]['reason'])
        self.assertEqual(result['results'][0]['source_ids'], [result['sources'][0]['id']])
        self.assertEqual(result['sources'][0]['url'], 'https://yields.llama.fi/pools')

    def test_real_client_huge_fee_does_not_stop_later_volume_fetch(self):
        args = cli.validate(dict(cli.DEFAULTS, **vars(cli.parser().parse_args([
            'protocol', CANONICAL['slug'], '--metrics', 'tvl,fees,volume',
            '--start', '2026-01-01', '--end', '2026-01-01']))))
        responses = {
            'api.llama.fi/protocols': [CANONICAL],
            'api.llama.fi/protocol/polymarket-international': {**CANONICAL, 'tvl': [
                {'date': 1767139200, 'totalLiquidityUSD': 10}, {'date': 1767225600, 'totalLiquidityUSD': 20}]},
            'api.llama.fi/summary/fees/polymarket-international': {**CANONICAL,
                'dataType': 'dailyFees', 'totalDataChart': [[1767225600, 10 ** 400]]},
            'api.llama.fi/summary/dexs/polymarket-international': {**CANONICAL,
                'dataType': 'dailyVolume', 'totalDataChart': [[1767139200, 10], [1767225600, 20]]}}
        opener = JSONOpener(responses)
        result = cli.execute(args, client=Client(no_cache=True, opener=opener))
        json.dumps(result, allow_nan=False)
        self.assertEqual(result['status'], 'partial')
        for metric in ('tvl', 'volume'):
            row = next(row for row in result['results'] if row['metric'] == metric)
            self.assertEqual(row['status'], 'ok')
            self.assertEqual(row['value'], 20)
        fees = next(row for row in result['results'] if row['metric'] == 'fees')
        self.assertIsNone(fees['value'])
        self.assertEqual(fees['source_observations'], [[1767225600, None]])
        self.assertEqual([urlsplit(url).path for url in opener.urls], [
            '/protocols', '/protocol/polymarket-international',
            '/summary/fees/polymarket-international', '/summary/dexs/polymarket-international'])

    def test_nonfinite_and_boolean_values_never_numbers(self):
        for value in (True, False, float('nan'), float('inf'), '12', None):
            self.assertIsNone(number(value))
        self.assertEqual(number(-2), -2)


if __name__ == '__main__':
    unittest.main()
