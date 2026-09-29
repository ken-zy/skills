import sys
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from defillama_lib.providers import Provider, API, STABLE, YIELDS, COINS, number
from defillama_lib.client import FetchError

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

    def test_nonfinite_and_boolean_values_never_numbers(self):
        for value in (True, False, float('nan'), float('inf'), '12', None):
            self.assertIsNone(number(value))
        self.assertEqual(number(-2), -2)


if __name__ == '__main__':
    unittest.main()
