"""Command routing, bounded orchestration and reproducible output."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import csv
from datetime import date, datetime, timezone
import io
import json
import math
from pathlib import Path
import re
import sys

METRICS = ('tvl', 'volume', 'fees', 'revenue', 'supply-side', 'holders')
DEFAULTS = dict(format='json', output=None, overwrite=False, refresh=False,
                no_cache=False, cache_dir=None, raw=False)


def parser():
    common = argparse.ArgumentParser(add_help=False)
    for flag in ('overwrite', 'refresh', 'no-cache', 'raw'):
        common.add_argument('--' + flag, action='store_true', default=argparse.SUPPRESS)
    common.add_argument('--format', choices=('json', 'csv'), default=argparse.SUPPRESS)
    common.add_argument('--output', default=argparse.SUPPRESS)
    common.add_argument('--cache-dir', default=argparse.SUPPRESS)
    p = argparse.ArgumentParser(description='Read DefiLlama free APIs with explicit data provenance.', parents=[common])
    sub = p.add_subparsers(dest='command', required=True)
    def command(name):
        return sub.add_parser(name, parents=[common])
    def windows(q):
        q.add_argument('--days', default=None, help='Comma-separated windows, default 7,30,90; maximum 3650')
        q.add_argument('--start', help='Inclusive UTC date YYYY-MM-DD')
        q.add_argument('--end', help='Inclusive UTC date YYYY-MM-DD')
    def metrics(q):
        q.add_argument('--metrics', default='tvl,volume,fees,revenue', help=','.join(METRICS))
    command('capabilities')
    q = command('search'); q.add_argument('query'); q.add_argument('--limit', type=int, default=20)
    q = command('protocol'); q.add_argument('slug'); metrics(q); windows(q)
    q = command('compare'); q.add_argument('slugs', nargs='+'); metrics(q); windows(q)
    q = command('market'); windows(q)
    q = command('chains'); q.add_argument('chain', nargs='?'); windows(q)
    q = command('stablecoins'); q.add_argument('id', nargs='?'); q.add_argument('--chain'); windows(q)
    q = command('yields'); q.add_argument('--pool'); q.add_argument('--chain'); q.add_argument('--project'); q.add_argument('--symbol')
    q.add_argument('--stablecoin', action='store_true'); q.add_argument('--min-tvl', type=float, default=0)
    q.add_argument('--limit', type=int, default=20); q.add_argument('--sort', choices=('tvl', 'apy'), default='tvl')
    q = command('prices'); q.add_argument('tokens', nargs='+'); q.add_argument('--timestamp', type=int)
    q = command('options'); q.add_argument('slug'); q.add_argument('--kind', choices=('premium', 'notional'), default='premium'); windows(q)
    q = command('open-interest'); q.add_argument('slug', nargs='?')
    return p


def validate(args):
    if args.get('raw') and args['format'] != 'json':
        raise ValueError('--raw is available only with JSON output')
    if args.get('limit') is not None and not 1 <= args['limit'] <= 100:
        raise ValueError('--limit must be between 1 and 100')
    if args.get('command') == 'compare' and (not 2 <= len(args['slugs']) <= 5 or len(set(args['slugs'])) != len(args['slugs'])):
        raise ValueError('compare requires 2-5 distinct exact slugs')
    for slug in ([args['slug']] if args.get('slug') else []) + args.get('slugs', []) + ([args['project']] if args.get('project') else []):
        if not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,119}', slug):
            raise ValueError('Use an exact lowercase canonical slug returned by search')
    if args.get('id') is not None and not re.fullmatch(r'[1-9][0-9]{0,9}', args['id']):
        raise ValueError('stablecoin ID must be a positive numeric ID')
    if args.get('pool') and not re.fullmatch(r'[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}', args['pool']):
        raise ValueError('--pool requires an exact pool UUID')
    if args.get('pool') and any(args.get(k) for k in ('chain', 'project', 'symbol', 'stablecoin', 'min_tvl')):
        raise ValueError('--pool cannot be combined with pool-list filters')
    if args.get('min_tvl') is not None and (not math.isfinite(args['min_tvl']) or args['min_tvl'] < 0):
        raise ValueError('--min-tvl must be finite and nonnegative')
    if 'metrics' in args:
        values = args['metrics'].split(',')
        if not values or any(v not in METRICS for v in values):
            raise ValueError('Unknown metric; choose ' + ','.join(METRICS))
        args['metrics'] = list(dict.fromkeys(values))
    if 'days' in args:
        if bool(args.get('start')) != bool(args.get('end')):
            raise ValueError('--start and --end are required together')
        if args.get('start') and args.get('days'):
            raise ValueError('Use --days or --start/--end, not both')
        if args.get('start'):
            for key in ('start', 'end'):
                if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', args[key]):
                    raise ValueError('Dates must use YYYY-MM-DD')
            start, end = date.fromisoformat(args['start']), date.fromisoformat(args['end'])
            if start > end or (end - start).days >= 3650 or start.year < 2009:
                raise ValueError('Date window must be ordered, start in 2009 or later and at most 3650 days')
            if end >= datetime.now(timezone.utc).date():
                raise ValueError('Explicit windows must end before the current UTC day')
            args['days'] = []
        else:
            values = (args['days'] or '7,30,90').split(',')
            if len(values) > 12 or any(not v.isdigit() or not 1 <= int(v) <= 3650 for v in values):
                raise ValueError('--days requires 1-12 comma-separated integer windows of 1-3650 days')
            args['days'] = list(dict.fromkeys(map(int, values)))
    if args.get('tokens'):
        if len(args['tokens']) > 20:
            raise ValueError('At most 20 token identifiers per request')
        for token in args['tokens']:
            if not re.fullmatch(r'[a-z0-9-]+:[A-Za-z0-9._-]+', token) or len(token) > 200:
                raise ValueError('Tokens must use chain:address or coingecko:id without URL syntax')
        if args.get('timestamp') is not None and not 1230768000 <= args['timestamp'] <= int(datetime.now(timezone.utc).timestamp()):
            raise ValueError('Price timestamp must be Unix seconds between 2009 and now')
    for k in ('query', 'symbol', 'chain'):
        if args.get(k) is not None and (not args[k].strip() or len(args[k]) > 120 or any(ord(c) < 32 for c in args[k])):
            raise ValueError(k + ' must be nonempty text of at most 120 characters')
    return args


def capabilities():
    return {
        'commands': ['search', 'protocol', 'compare', 'market', 'chains', 'stablecoins', 'yields', 'prices', 'options', 'open-interest'],
        'hosts': ['api.llama.fi', 'stablecoins.llama.fi', 'yields.llama.fi', 'coins.llama.fi'],
        'authentication': 'none', 'dependencies': 'Python 3.10+ standard library',
        'calendar_comparability': 'Only evidenced mappings qualify; see references/time-semantics.md. Other flows remain source observations.',
        'endpoint_access': 'Implemented public endpoints; offline capability listing is not a live availability check.',
        'supply_side': 'Empirical per-protocol dailySupplySideRevenue access; not universally available or a marketing-cost measure.',
        'holders': 'Holder revenue, not holder count.',
        'excluded': ['trading', 'wallet signing', 'paid MCP/API', 'complete users/retention/concentration', 'complete unlocks/ETF/raises/hacks'],
        'examples': ['search polymarket', 'protocol polymarket-international --metrics tvl,volume,fees,revenue,supply-side --days 7,30', 'prices coingecko:ethereum'],
    }


def execute(args, client=None):
    from .analysis import analyze_series, derive_metrics
    from .client import Client, FetchError
    from .providers import Provider
    generated = datetime.now(timezone.utc).isoformat()
    requested = {k:v for k,v in args.items() if k not in DEFAULTS and v is not None}
    base = {'schema_version': '1.0', 'generated_at': generated, 'command': args['command'],
            'requested_scope': requested, 'effective_scope': {}, 'sources': [], 'results': [], 'warnings': [], 'status': 'ok'}
    if args['command'] == 'capabilities':
        base['capabilities'] = capabilities()
        return base
    client = client or Client(cache_dir=args['cache_dir'], refresh=args['refresh'], no_cache=args['no_cache'])
    def fetch(command, request):
        provider = Provider(client)
        try:
            return provider.dispatch(command, request)
        except (FetchError, ValueError, KeyError, TypeError) as exc:
            bundle = getattr(provider, 'out', {})
            source_ids = [s['id'] for s in bundle.get('sources', [])]
            bundle.setdefault('records', []).append({'entity': {'slug': request.get('slug')}, 'metric': 'request', 'value': None, 'status': 'unavailable', 'reason': str(exc), 'source_ids': source_ids, 'error': exc.as_dict() if isinstance(exc, FetchError) else {'code':'schema_error','message':str(exc)}})
            bundle.setdefault('warnings', []).append(str(exc))
            return bundle
    if args['command'] == 'compare':
        with ThreadPoolExecutor(max_workers=3) as pool:
            bundles = list(pool.map(lambda slug: fetch('protocol', dict(args, slug=slug)), args['slugs']))
    else:
        bundles = [fetch(args['command'], args)]
    series, records, raw, sources = [], [], {}, {}
    listings = []
    for bundle in bundles:
        if 'count' in bundle or 'truncated' in bundle:
            listings.append({k:bundle[k] for k in ('count', 'truncated', 'empty') if k in bundle})
        series.extend(bundle.get('series', [])); records.extend(bundle.get('records', []))
        base['warnings'].extend(bundle.get('warnings', [])); raw.update(bundle.get('raw', {}))
        for source in bundle.get('sources', []):
            sources[source['id']] = source
    rows = analyze_series(series, days=None if args.get('start') else args.get('days', [7,30,90]), start=args.get('start'), end=args.get('end'), align='metric' if args['command'] == 'compare' else 'all') if series else []
    base['results'] = records + rows + derive_metrics(rows)
    base['sources'] = list(sources.values())
    if listings:
        base['listing'] = listings[0] if len(listings) == 1 else listings
    base['effective_scope'] = {'entities': list({json.dumps(r.get('entity', {}), sort_keys=True):r.get('entity', {}) for r in base['results']}.values()), 'alignment': 'same_metric' if args['command'] == 'compare' else 'all_eligible_series'}
    statuses = [r.get('status', 'ok') for r in base['results']]
    if statuses and any(s not in ('ok', 'empty') for s in statuses):
        base['status'] = 'partial' if any(s in ('ok', 'partial') for s in statuses) else 'unavailable'
    if not statuses:
        base['count'] = 0; base['empty'] = True
    if args['raw']:
        base['raw'] = raw
    return base


def safe_cell(value):
    if value is None:
        return ''
    if isinstance(value, (str, int, float, bool)):
        if isinstance(value, str) and value.lstrip().startswith(('=', '+', '-', '@')):
            return "'" + value
        return value
    return ''


def csv_text(result):
    """One scalar field per row; no nested objects hidden inside CSV cells."""
    out = io.StringIO(newline='')
    fields = ['record', 'entity', 'metric', 'kind', 'unit', 'status', 'field', 'value', 'period_start', 'period_end', 'observed_at', 'source_url', 'fetched_at']
    writer = csv.DictWriter(out, fieldnames=fields); writer.writeheader()
    sources = {s['id']:s for s in result.get('sources', [])}
    def leaves(value, path=''):
        if isinstance(value, dict):
            for key, child in value.items():
                yield from leaves(child, path + '.' + str(key) if path else str(key))
        elif isinstance(value, list):
            for i, child in enumerate(value):
                yield from leaves(child, f'{path}[{i}]')
        else:
            yield path, value
    records = result.get('results', []) or [{'metric': 'response', 'status': result['status'], 'count': 0, 'capabilities':result.get('capabilities')}]
    for index, record in enumerate(records):
        entity = record.get('entity') or {}
        name = entity.get('slug') or entity.get('name') or entity.get('id') if isinstance(entity, dict) else str(entity)
        linked = [sources.get(s, {}) for s in record.get('source_ids', [])] or [{}]
        for field, value in leaves(record):
            for source in linked:
                row = dict(record=index, entity=name, metric=record.get('metric'), kind=record.get('kind'), unit=record.get('unit'), status=record.get('status'), field=field, value=value, period_start=record.get('period_start'), period_end=record.get('period_end'), observed_at=record.get('observed_at'), source_url=source.get('url'), fetched_at=source.get('fetched_at'))
                writer.writerow({k:safe_cell(v) for k,v in row.items()})
    return out.getvalue()


def main(argv=None):
    p = parser()
    args = dict(DEFAULTS, **vars(p.parse_args(argv)))
    try:
        validate(args)
        if args['output'] and Path(args['output']).exists() and not args['overwrite']:
            raise ValueError('Output exists; choose another path or explicitly use --overwrite')
        result = execute(args)
        text = csv_text(result) if args['format'] == 'csv' else json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
        if args['output']:
            with open(args['output'], 'w' if args['overwrite'] else 'x', encoding='utf-8', newline='') as f:
                f.write(text)
        else:
            sys.stdout.write(text)
        return 0 if result['status'] == 'ok' else 1
    except (ValueError, OSError) as exc:
        print(json.dumps({'status':'unavailable', 'error':str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
