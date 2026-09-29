"""Public endpoint normalization. Missing values and unverified time scopes survive."""
from __future__ import annotations

import hashlib
import math
import re
from datetime import datetime, timezone
from urllib.parse import quote, urlencode

from .client import FetchError

PROVIDER_ERRORS = (FetchError, ValueError, TypeError, KeyError)

API = 'https://api.llama.fi'
STABLE = 'https://stablecoins.llama.fi'
YIELDS = 'https://yields.llama.fi'
COINS = 'https://coins.llama.fi'
CHART = {'excludeTotalDataChart': 'false', 'excludeTotalDataChartBreakdown': 'true'}
DATA_TYPES = {'fees': 'dailyFees', 'revenue': 'dailyRevenue',
              'supply-side': 'dailySupplySideRevenue', 'holders': 'dailyHoldersRevenue'}
ADAPTER_REVISION = '5cbd343e7b562fdc40a6c013ff4814f3b8dc02ca'
PM_VOLUME_EVIDENCE = {
    'adapter': f'https://github.com/DefiLlama/dimension-adapters/blob/{ADAPTER_REVISION}/dexs/polymarket/index.ts',
    'framework': 'https://docs.llama.fi/list-your-project/other-dashboards',
    'basis': 'version 1 fixed UTC day; SQL explicitly filters startTimestamp <= event time < endTimestamp',
    'entity_id': '711', 'slug': 'polymarket-international', 'metric': 'volume',
}


def number(value):
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None
    try:
        return value if math.isfinite(value) else None
    except OverflowError:
        return None


def component(value):
    value = str(value)
    if not value or any(x in value for x in '/?#\\') or any(ord(x) < 32 for x in value):
        raise ValueError('Invalid endpoint identifier')
    return quote(value, safe='')


def endpoint(host, path, params=None):
    return host + path + ('?' + urlencode(params) if params else '')


def entity(row):
    return {key: row.get(key) for key in ('id', 'slug', 'name', 'parentProtocol', 'chains', 'category')}


def points(rows, timestamp='date', value='totalLiquidityUSD'):
    if not isinstance(rows, list):
        raise ValueError('Expected history list')
    out = []
    for row in rows:
        if isinstance(row, dict):
            ts = row.get(timestamp)
            val = row.get(value)
        elif isinstance(row, (list, tuple)) and len(row) == 2:
            ts, val = row
        else:
            raise ValueError('Malformed history observation')
        if isinstance(ts, str) and ts.isdigit():
            ts = int(ts)
        out.append([ts, number(val)])
    return out


def scope(row):
    # Never fill a source's unknown chain/child coverage from another source.
    chains = row.get('chains')
    return {'identity': str(row.get('id')) if row.get('id') is not None else row.get('slug'),
            'version': row.get('version'), 'children': row.get('childProtocols'),
            'chains': sorted(chains) if isinstance(chains, list) and all(isinstance(x, str) for x in chains) else None,
            'category': row.get('category')}


class Provider:
    def __init__(self, client):
        self.client = client
        self._protocols = None

    @staticmethod
    def capabilities():
        return {'commands': ['search', 'protocol', 'compare', 'market', 'chains', 'stablecoins',
                             'yields', 'prices', 'options', 'open-interest', 'capabilities'],
                'hosts': [API, STABLE, YIELDS, COINS],
                'empirical': ['dailySupplySideRevenue: availability varies by protocol'],
                'calendar_comparability': {'verified': ['polymarket-international:volume'],
                                           'others': 'unknown until adapter and aggregation semantics are evidenced'},
                'excluded': ['paid APIs', 'user retention', 'complete fundraising/hacks/unlocks/ETF data'],
                'notes': ['holders means holder revenue', 'OI is a stock', 'prices may derive from CoinGecko']}

    def dispatch(self, command, args):
        self.out = {'series': [], 'records': [], 'sources': [], 'warnings': [], 'raw': {}}
        self._failed_source = None
        if command == 'capabilities':
            self.out['records'].append({'metric': 'capabilities', 'status': 'ok', **self.capabilities()})
        elif command == 'compare':
            for slug in args['slugs']:
                self._protocol({**args, 'slug': slug})
        else:
            method = getattr(self, '_' + command.replace('-', '_'), None)
            if method is None:
                raise ValueError('Unknown command')
            method(args)
        return self.out

    def _get(self, url):
        self._failed_source = None
        try:
            response = self.client.get(url)
        except FetchError as exc:
            sid = hashlib.sha256(url.encode()).hexdigest()
            source = {'id': sid, 'url': url, 'fetched_at': None, 'http_date': None,
                      'cached': False, 'status': 'unavailable', 'reason': str(exc),
                      'attempted_at': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')}
            if not any(s['id'] == sid for s in self.out['sources']):
                self.out['sources'].append(source)
            self._failed_source = sid
            raise
        data, source = response['data'], dict(response['source'])
        if isinstance(data, dict):
            for key in ('methodology', 'methodologyURL', 'latestFetchIsOk', 'disabled'):
                if key in data:
                    source[key] = data[key]
        if not any(s['id'] == source['id'] for s in self.out['sources']):
            self.out['sources'].append(source)
        self.out['raw'][source['id']] = data
        return data, source['id']

    def _bad_row(self, sid, metric, index, reason):
        self._record({'row_index': index}, metric, source_ids=[sid], status='unavailable',
                     reason=reason)

    def _objects(self, rows, sid, metric, text_fields=()):
        if not isinstance(rows, list):
            raise ValueError('Expected list for ' + metric)
        valid = []
        for index, row in enumerate(rows):
            if not isinstance(row, dict):
                self._bad_row(sid, metric, index, 'Malformed row: expected object')
            elif any(not isinstance(row.get(key), str) or not row[key] for key in text_fields):
                self._bad_row(sid, metric, index, 'Malformed row: invalid identity text field')
            else:
                valid.append(row)
        return valid

    @staticmethod
    def _epoch(value):
        if isinstance(value, str):
            if not value.isdigit() or len(value) > 12:
                return None
            value = int(value)
        numeric = number(value)
        if numeric is None or numeric <= 0 or int(numeric) != numeric:
            return None
        if numeric > datetime.now(timezone.utc).timestamp() + 600:
            return None
        return int(numeric)

    def _record(self, ent, metric, value=None, source_ids=None, status='ok', **extra):
        row = {'entity': ent, 'metric': metric, 'value': value, 'source_ids': source_ids or [],
               'status': status, 'observed_at': None, **extra}
        if status == 'unavailable':
            row.setdefault('reason', 'Missing or invalid metric value')
        stamp = row.get('observed_at')
        if stamp is not None and (number(stamp) is None or stamp <= 0 or int(stamp) != stamp
                                  or stamp > datetime.now(timezone.utc).timestamp() + 600):
            row['observed_at'] = None
            row.setdefault('warnings', []).append('Invalid upstream observation timestamp; time remains unknown')
        self.out['records'].append(row)
        return row

    def _series(self, ent, metric, kind, values, source_id, original=None, unit='USD'):
        original = original or ent
        semantic = 'snapshot' if kind in ('stock', 'rate') else 'unknown'
        evidence = None
        if (metric == 'volume' and str(ent.get('id')) == '711'
                and ent.get('slug') == 'polymarket-international'
                and original.get('chains') == ['Polygon']):
            semantic, evidence = 'utc_calendar_day', PM_VOLUME_EVIDENCE
        warning = []
        if original.get('latestFetchIsOk') is False or original.get('disabled'):
            warning.append('Upstream collection health is degraded; returned history may still be independently usable')
        row = {'entity': ent, 'metric': metric, 'kind': kind, 'unit': unit, 'points': values,
               'source_ids': [source_id], 'time_semantics': semantic,
               'timestamp_role': 'sample_time' if kind in ('stock', 'rate') else ('interval_start' if evidence else 'unknown'),
               'semantic_evidence': evidence, 'scope': scope(original),
               'upstream_health': {key: original[key] for key in ('latestFetchIsOk', 'disabled') if key in original},
               'status': 'ok' if values else 'unavailable', 'warnings': warning}
        if not values:
            row['reason'] = 'No history returned'
        self.out['series'].append(row)
        return row

    def _failure(self, ent, metric, exc, kind='flow', source_ids=None):
        self.out['series'].append({'entity': ent, 'metric': metric, 'kind': kind, 'unit': 'USD',
                                  'points': [], 'source_ids': source_ids or ([self._failed_source] if self._failed_source else []), 'status': 'unavailable',
                                  'reason': str(exc), 'scope': scope(ent), 'warnings': [],
                                  'time_semantics': 'unknown', 'timestamp_role': 'unknown', 'semantic_evidence': None})

    def _catalog(self):
        if self._protocols is None:
            rows, sid = self._get(API + '/protocols')
            if not isinstance(rows, list):
                raise ValueError('Invalid protocol catalogue')
            self._protocols = (rows, sid, self.out['sources'][-1], rows)
        rows, sid, source, raw = self._protocols
        if not any(s['id'] == sid for s in self.out['sources']):
            self.out['sources'].append(source)
            self.out['raw'][sid] = raw
        return self._objects(rows, sid, 'protocol-catalogue', ('slug', 'name')), sid

    def _resolve(self, slug):
        component(slug)
        rows, sid = self._catalog()
        matches = [row for row in rows if isinstance(row, dict) and row.get('slug') == slug]
        if len(matches) != 1:
            raise ValueError('Exact protocol slug not found or ambiguous; use search')
        return entity(matches[0]), sid

    @staticmethod
    def _identity(data, canonical):
        if not isinstance(data, dict):
            raise ValueError('Expected protocol object')
        ids = [str(data[key]) for key in ('id', 'defillamaId') if data.get(key) is not None]
        wanted = str(canonical.get('id'))
        if ids and any(value != wanted for value in ids):
            raise ValueError('Protocol ID mismatch; parent/child substitution rejected')
        if data.get('slug') is not None and data['slug'] != canonical['slug']:
            raise ValueError('Protocol slug mismatch')
        if not ids and data.get('slug') != canonical['slug']:
            raise ValueError('Protocol identity unverified')
        if data.get('parentProtocol') is not None and data['parentProtocol'] != canonical.get('parentProtocol'):
            raise ValueError('Protocol parent mismatch')
        result = dict(data)
        result['id'] = canonical['id']
        result['slug'] = canonical['slug']
        result.setdefault('category', canonical.get('category'))
        return result

    def _search(self, args):
        rows, sid = self._catalog()
        query = args['query'].casefold()
        matches = [row for row in rows if isinstance(row, dict) and
                   any(query in str(row.get(k, '')).casefold() for k in ('name', 'slug'))]
        limit = args.get('limit', 20)
        for row in matches[:limit]:
            self._record(entity(row), 'protocol', source_ids=[sid])
        self.out['count'] = len(matches)
        self.out['truncated'] = len(matches) > limit
        if not matches:
            self.out['empty'] = True

    def _protocol(self, args):
        metrics = args.get('metrics', ['tvl', 'volume', 'fees', 'revenue'])
        ent = {'slug': args['slug']}
        try:
            ent, _ = self._resolve(args['slug'])
        except PROVIDER_ERRORS as exc:
            for metric in metrics:
                self._failure(ent, metric, exc, 'stock' if metric == 'tvl' else 'flow')
            return
        for metric in metrics:
            sid = None
            try:
                slug = component(args['slug'])
                if metric == 'tvl':
                    url = API + '/protocol/' + slug
                elif metric == 'volume':
                    url = endpoint(API, '/summary/dexs/' + slug, CHART)
                elif metric in DATA_TYPES:
                    url = endpoint(API, '/summary/fees/' + slug, {**CHART, 'dataType': DATA_TYPES[metric]})
                else:
                    raise ValueError('Unsupported metric')
                data, sid = self._get(url)
                identified = self._identity(data, ent)
                expected_type = 'dailyVolume' if metric == 'volume' else DATA_TYPES.get(metric)
                if expected_type and data.get('dataType') not in (None, expected_type):
                    raise ValueError('Response dataType differs from requested metric')
                values = points(data.get('tvl' if metric == 'tvl' else 'totalDataChart'))
                row = self._series(entity(identified), metric, 'stock' if metric == 'tvl' else 'flow', values, sid, identified)
                if metric == 'supply-side':
                    row['warnings'].append('Empirical dataType; adapter-defined supply-side revenue is not universal marketing expense')
                for key in ('total24h', 'total7d', 'total30d'):
                    if key in data:
                        self._record(entity(identified), metric + ':' + key, number(data[key]), [sid],
                                     kind='flow', unit='USD', time_semantics='rolling_window', interval_end=None,
                                     status='ok' if number(data[key]) is not None else 'unavailable')
            except PROVIDER_ERRORS as exc:
                self._failure(ent, metric, exc, 'stock' if metric == 'tvl' else 'flow', [sid] if sid else [])

    def _aggregate(self, ent, metric, host, path, params=None, stable=False):
        sid = None
        try:
            data, sid = self._get(endpoint(host, path, params))
            if metric == 'tvl':
                values = points(data, value='tvl')
            elif stable:
                if not isinstance(data, list):
                    raise ValueError('Expected stablecoin USD history list')
                values = []
                for index, row in enumerate(self._objects(data, sid, 'stablecoin-cap')):
                    stamp = self._epoch(row.get('date'))
                    if stamp is None:
                        self._bad_row(sid, 'stablecoin-cap', index, 'Invalid history timestamp')
                        continue
                    values.append([stamp, self._usd_total(row.get('totalCirculatingUSD'))])
            else:
                if not isinstance(data, dict):
                    raise ValueError('Expected aggregate chart object')
                expected_type = 'dailyVolume' if metric == 'volume' else DATA_TYPES.get(metric)
                if expected_type and data.get('dataType') not in (None, expected_type):
                    raise ValueError('Response dataType differs from requested aggregate metric')
                values = points(data.get('totalDataChart'))
            self._series(ent, metric, 'stock' if metric in ('tvl', 'stablecoin-cap') else 'flow', values, sid,
                         data if isinstance(data, dict) else ent)
        except PROVIDER_ERRORS as exc:
            self._failure(ent, metric, exc, 'stock' if metric in ('tvl', 'stablecoin-cap') else 'flow', [sid] if sid else [])

    @staticmethod
    def _usd_total(mapping):
        if not isinstance(mapping, dict) or not mapping:
            return None
        values = [number(x) for x in mapping.values()]
        return number(sum(values)) if all(x is not None for x in values) else None

    def _market(self, args):
        ent = {'id': 'global', 'name': 'Global'}
        self._aggregate(ent, 'tvl', API, '/v2/historicalChainTvl')
        self._aggregate(ent, 'volume', API, '/overview/dexs', CHART)
        self._aggregate(ent, 'stablecoin-cap', STABLE, '/stablecoincharts/all', stable=True)

    def _chain(self, requested):
        rows, sid = self._get(API + '/v2/chains')
        if not isinstance(rows, list):
            raise ValueError('Invalid chain list')
        rows = self._objects(rows, sid, 'chain-catalogue', ('name',))
        matches = [r for r in rows if r['name'].casefold() == requested.casefold()]
        if len(matches) != 1:
            raise ValueError('Exact chain name not found or ambiguous')
        return matches[0], sid

    def _chains(self, args):
        if not args.get('chain'):
            data, sid = self._get(API + '/v2/chains')
            if not isinstance(data, list):
                raise ValueError('Invalid chain list')
            for row in self._objects(data, sid, 'tvl', ('name',)):
                val = number(row.get('tvl'))
                self._record({'id': row.get('chainId'), 'name': row.get('name')}, 'tvl', val, [sid],
                             status='ok' if val is not None else 'unavailable', kind='stock', unit='USD')
            self.out['empty'] = not data
            return
        row, _ = self._chain(args['chain'])
        chain = component(row['name'])
        ent = {'id': row.get('chainId'), 'name': row['name'], 'chains': [row['name']]}
        self._aggregate(ent, 'tvl', API, '/v2/historicalChainTvl/' + chain)
        self._aggregate(ent, 'volume', API, '/overview/dexs/' + chain, CHART)
        for metric in ('fees', 'revenue'):
            self._aggregate(ent, metric, API, '/overview/fees/' + chain, {**CHART, 'dataType': DATA_TYPES[metric]})
        self.out['warnings'].append('Chain fees/revenue are the API dashboard aggregate; not assumed to be chain gas fees')

    def _stablecoins(self, args):
        coin_id = args.get('id')
        chain = args.get('chain')
        if chain:
            row, _ = self._chain(chain)
            chain = row['name']
        params = None
        ent = {'id': 'stablecoins', 'name': 'Stablecoins', 'chains': [chain] if chain else None}
        if coin_id is not None:
            coin_id = str(coin_id)
            if not coin_id.isdigit():
                raise ValueError('Stablecoin ID must be numeric')
            listed, list_sid = self._get(STABLE + '/stablecoins?includePrices=true')
            if not isinstance(listed, dict) or not isinstance(listed.get('peggedAssets'), list):
                raise ValueError('Invalid stablecoin catalogue')
            found = [r for r in self._objects(listed['peggedAssets'], list_sid, 'stablecoin-catalogue')
                     if str(r.get('id')) == coin_id]
            if len(found) != 1:
                raise ValueError('Stablecoin ID not found')
            data, sid = self._get(STABLE + '/stablecoin/' + component(coin_id))
            if not isinstance(data, dict) or str(data.get('id')) != coin_id:
                raise ValueError('Stablecoin identity mismatch')
            ent = {'id': coin_id, 'name': data.get('name'), 'chains': [chain] if chain else data.get('chains')}
            distribution = {}
            balances = data.get('chainBalances', {})
            if not isinstance(balances, dict):
                self._bad_row(sid, 'stablecoin-chain-supply', None, 'Invalid chainBalances object')
            else:
                for name, balance in balances.items():
                    if chain and name.casefold() != chain.casefold():
                        continue
                    history = balance.get('tokens') if isinstance(balance, dict) else None
                    if not isinstance(history, list):
                        self._bad_row(sid, 'stablecoin-chain-supply', name, 'Invalid chain token history')
                        continue
                    dated = []
                    for index, row in enumerate(self._objects(history, sid, 'stablecoin-chain-supply')):
                        stamp = self._epoch(row.get('date'))
                        if stamp is None:
                            self._bad_row(sid, 'stablecoin-chain-supply', index, 'Invalid chain supply timestamp')
                        else:
                            dated.append((stamp, row))
                    if dated:
                        stamp, latest = max(dated, key=lambda pair: pair[0])
                        circulating = latest.get('circulating')
                        supply = ({key: number(value) for key, value in circulating.items()}
                                  if isinstance(circulating, dict) else None)
                        if supply is None:
                            self._bad_row(sid, 'stablecoin-chain-supply', name, 'Invalid circulating supply object')
                        distribution[name] = {'date': stamp, 'circulating': supply}
            self._record(ent, 'stablecoin-metadata', source_ids=[sid], metadata={
                **{k: data.get(k) for k in ('symbol', 'pegType', 'pegMechanism', 'price')},
                'currentChainSupply': distribution, 'supplyUnit': 'native peg units; not USD valuation'})
            params = {'stablecoin': coin_id}
        self._aggregate(ent, 'stablecoin-cap', STABLE, '/stablecoincharts/' + (component(chain) if chain else 'all'), params, stable=True)

    def _yields(self, args):
        if args.get('pool'):
            pool = args['pool']
            if not re.fullmatch(r'[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}', pool):
                raise ValueError('Pool must be UUID')
            payload, sid = self._get(YIELDS + '/chart/' + component(pool))
            data = payload.get('data') if isinstance(payload, dict) else None
            if not isinstance(data, list):
                raise ValueError('Invalid pool chart')
            ent = {'id': pool, 'name': pool}
            observations = []
            for index, row in enumerate(self._objects(data, sid, 'pool-history')):
                stamp = row.get('timestamp')
                if isinstance(stamp, str):
                    try:
                        dt = datetime.fromisoformat(stamp.replace('Z', '+00:00'))
                        stamp = int(dt.timestamp()) if dt.tzinfo is not None else None
                    except (ValueError, OverflowError):
                        stamp = None
                stamp = self._epoch(stamp)
                if stamp is None:
                    self._bad_row(sid, 'pool-history', index, 'Invalid or timezone-less pool timestamp')
                    continue
                observations.append((stamp, row))
            for metric, kind, unit in [('tvlUsd', 'stock', 'USD'), ('apy', 'rate', '%'), ('apyBase', 'rate', '%'), ('apyReward', 'rate', '%')]:
                values = [[stamp, number(row.get(metric))] for stamp, row in observations]
                self._series(ent, metric, kind, values, sid, unit=unit)
            return
        payload, sid = self._get(YIELDS + '/pools')
        data = payload.get('data') if isinstance(payload, dict) else None
        if not isinstance(data, list):
            raise ValueError('Invalid pools list')
        chosen = []
        for row in self._objects(data, sid, 'yield-pool', ('pool', 'symbol', 'project', 'chain')):
            if args.get('chain') and str(row.get('chain')).casefold() != args['chain'].casefold():
                continue
            if args.get('project') and row.get('project') != args['project']:
                continue
            if args.get('symbol') and args['symbol'].casefold() not in str(row.get('symbol', '')).casefold():
                continue
            if args.get('stablecoin') and row.get('stablecoin') is not True:
                continue
            tvl = number(row.get('tvlUsd'))
            if args.get('min_tvl', 0) > 0 and (tvl is None or tvl < args['min_tvl']):
                continue
            chosen.append(row)
        field = 'apy' if args.get('sort') == 'apy' else 'tvlUsd'
        chosen.sort(key=lambda r: number(r.get(field)) if number(r.get(field)) is not None else -math.inf, reverse=True)
        limit = args.get('limit', 20)
        for row in chosen[:limit]:
            ent = {'id': row.get('pool'), 'name': row.get('symbol'), 'slug': row.get('project'), 'chains': [row.get('chain')]}
            for metric in ('tvlUsd', 'apy', 'apyBase', 'apyReward'):
                value = number(row.get(metric))
                self._record(ent, metric, value, [sid], status='ok' if value is not None else 'unavailable',
                             kind='stock' if metric == 'tvlUsd' else 'rate', unit='USD' if metric == 'tvlUsd' else '%')
        self.out['count'] = len(chosen)
        self.out['truncated'] = len(chosen) > limit
        self.out['empty'] = not chosen

    def _prices(self, args):
        tokens = list(dict.fromkeys(args['tokens']))
        if not 1 <= len(tokens) <= 20 or any(not re.fullmatch(r'[A-Za-z0-9_-]+:[A-Za-z0-9._-]+', t) for t in tokens):
            raise ValueError('Supply 1-20 chain:address or coingecko:id tokens')
        timestamp = args.get('timestamp')
        if timestamp is not None and (not isinstance(timestamp, int) or isinstance(timestamp, bool) or timestamp <= 0):
            raise ValueError('Timestamp must be positive epoch seconds')
        path = '/prices/current/' if timestamp is None else '/prices/historical/' + str(timestamp) + '/'
        data, sid = self._get(COINS + path + ','.join(quote(t, safe=':') for t in tokens))
        if not isinstance(data, dict) or not isinstance(data.get('coins'), dict):
            raise ValueError('Invalid coin price response')
        for token in tokens:
            row = data['coins'].get(token, {})
            val = number(row.get('price')) if isinstance(row, dict) else None
            self._record({'id': token, 'name': token}, 'price', val, [sid], status='ok' if val is not None else 'unavailable',
                         kind='stock', unit='USD', observed_at=row.get('timestamp') if isinstance(row, dict) else None,
                         confidence=number(row.get('confidence')) if isinstance(row, dict) else None)

    def _options(self, args):
        ent = {'slug': args['slug']}
        kind = args.get('kind', 'premium')
        if kind not in ('premium', 'notional'):
            raise ValueError('Unknown options kind')
        metric = 'options-' + kind
        sid = None
        try:
            data, sid = self._get(endpoint(API, '/summary/options/' + component(args['slug']),
                                           {**CHART, 'dataType': 'dailyPremiumVolume' if kind == 'premium' else 'dailyNotionalVolume'}))
            # Options dashboards can aggregate a parent absent from the TVL list.
            # Their own exact echoed slug and stable ID are authoritative for this command.
            if not isinstance(data, dict) or data.get('slug') != args['slug'] or data.get('id') is None:
                raise ValueError('Options dashboard identity unverified')
            ent = entity(data)
            identified = self._identity(data, ent)
            expected_type = 'dailyPremiumVolume' if kind == 'premium' else 'dailyNotionalVolume'
            if data.get('dataType') not in (None, expected_type):
                raise ValueError('Response dataType differs from requested options metric')
            self._series(entity(identified), metric, 'flow', points(data.get('totalDataChart')), sid, identified)
        except PROVIDER_ERRORS as exc:
            self._failure(ent, metric, exc, source_ids=[sid] if sid else [])

    def _open_interest(self, args):
        data, sid = self._get(endpoint(API, '/overview/open-interest',
                                      {'excludeTotalDataChart': 'true', 'excludeTotalDataChartBreakdown': 'true'}))
        if not isinstance(data, dict) or not isinstance(data.get('protocols'), list):
            raise ValueError('Invalid OI overview')
        rows = self._objects(data['protocols'], sid, 'open-interest', ('slug',))
        if args.get('slug'):
            rows = [r for r in rows if r.get('slug') == args['slug']]
            if len(rows) != 1:
                self._record({'slug': args['slug']}, 'open-interest', source_ids=[sid], status='unavailable', reason='Exact OI slug not found')
                return
        for row in rows:
            val = number(row.get('total24h'))
            self._record(entity(row), 'open-interest', val, [sid], status='ok' if val is not None else 'unavailable',
                         kind='stock', unit='USD', time_semantics='snapshot',
                         warning='API total24h is the latest reported OI stock, observation time unknown; never sum')
        self.out['empty'] = not rows
