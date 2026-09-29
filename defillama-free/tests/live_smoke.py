"""Opt-in real CLI release checks: python3 tests/live_smoke.py --run.

Every command bypasses caches. Raw responses stay in a temporary directory.
No network runs during unittest discovery; evaluate_runs is an offline gate.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re
import subprocess
import sys
import tempfile

CLI = Path(__file__).resolve().parents[1] / 'scripts' / 'defillama.py'
CASES = [
    ('polymarket', ['protocol', 'polymarket-international', '--metrics', 'tvl,volume,fees,revenue,supply-side', '--days', '7', '--raw']),
    ('second-protocol', ['protocol', 'aave-v3', '--metrics', 'tvl', '--days', '7']),
    ('chains', ['chains']), ('chain-history', ['chains', 'Polygon', '--days', '7']),
    ('stablecoins', ['stablecoins', '1', '--days', '7']),
    ('yields', ['yields', '--limit', '1']), ('prices', ['prices', 'coingecko:ethereum']),
    ('market', ['market', '--days', '7']), ('options', ['options', 'derive', '--days', '7']),
    ('open-interest', ['open-interest']),
]
UUID = re.compile(r'[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}')


def utcnow():
    return datetime.now(timezone.utc)


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def timestamp(text):
    try:
        value = datetime.fromisoformat(text.replace('Z', '+00:00'))
        return value if value.tzinfo is not None else None
    except (TypeError, AttributeError, ValueError):
        return None


def run_case(case, directory, runner=None, clock=None):
    runner, clock = runner or subprocess.run, clock or utcnow
    name, words = case
    target = directory / (name + '.json')
    started = clock()
    try:
        proc = runner([sys.executable, str(CLI), *words, '--no-cache', '--output', str(target)],
                      capture_output=True, text=True, timeout=300)
        code, error = proc.returncode, proc.stderr[:2000]
    except (OSError, subprocess.TimeoutExpired) as exc:
        code, error = 2, type(exc).__name__
    finished = clock()
    try:
        data = json.loads(target.read_text())
        if not isinstance(data, dict):
            raise ValueError('Expected CLI object')
    except (OSError, ValueError):
        data = {'status': 'unavailable', 'results': [], 'sources': []}
    return {'name': name, 'exit': code, 'data': data, 'started_at': started.isoformat(),
            'finished_at': finished.isoformat(), 'stderr': error}


def fresh_source(source, run):
    fetched, started, finished = (timestamp(value) for value in
                                 (source.get('fetched_at'), run.get('started_at'), run.get('finished_at')))
    return (source.get('cached') is False and source.get('status') != 'unavailable'
            and not source.get('error') and fetched is not None and started is not None
            and finished is not None and started <= fetched <= finished)


def linked_fresh(row, run):
    sources = {s.get('id'): s for s in run['data'].get('sources', [])}
    ids = row.get('source_ids', [])
    return bool(ids) and all(sid in sources and fresh_source(sources[sid], run) for sid in ids)


def usable(row, run, metric=None):
    return (row.get('status') == 'ok' and finite(row.get('value'))
            and (metric is None or row.get('metric') == metric) and linked_fresh(row, run))


def has_observation(row, run):
    if not linked_fresh(row, run):
        return False
    return finite(row.get('value')) or any(
        isinstance(point, (list, tuple)) and len(point) == 2 and finite(point[1])
        for point in row.get('source_observations', []))


def discover_pool(run):
    for row in run['data'].get('results', []):
        pool = (row.get('entity') or {}).get('id')
        if usable(row, run, 'tvlUsd') and isinstance(pool, str) and UUID.fullmatch(pool):
            return pool
    return None


def evaluate_runs(runs):
    by_name = {run['name']: run for run in runs}
    checks = []

    def check(name, condition, detail, classification=None):
        item = {'check': name, 'passed': bool(condition), 'detail': detail}
        if classification:
            item['classification'] = classification
        checks.append(item)

    def get(name):
        return by_name.get(name, {'name': name, 'data': {'results': [], 'sources': []}, 'exit': 2})

    for name, _ in CASES + [('yield-history', [])]:
        run = get(name)
        sources = run['data'].get('sources', [])
        successful = [s for s in sources if s.get('status') != 'unavailable' and not s.get('error')]
        fresh = run['exit'] in (0, 1) and bool(successful) and all(fresh_source(s, run) for s in successful)
        check(name + '-fresh-http', fresh,
              {'exit': run['exit'], 'status': run['data'].get('status'), 'successful_sources': len(successful),
               'fresh_sources': sum(fresh_source(s, run) for s in successful), 'stderr': run.get('stderr', '')},
              'verified_fresh' if fresh else 'unverified')

    pm = get('polymarket')
    for metric in ('tvl', 'volume'):
        matches = [r for r in pm['data'].get('results', []) if r.get('metric') == metric and r.get('window_days') == 7]
        valid = (len(matches) == 1 and usable(matches[0], pm, metric)
                 and str(matches[0].get('entity', {}).get('id')) == '711'
                 and matches[0].get('entity', {}).get('slug') == 'polymarket-international'
                 and (metric != 'volume' or matches[0].get('time_semantics') == 'utc_calendar_day'))
        check('pm-' + metric, valid, 'Exact international entity; complete 7d comparison from fresh sources')
        try:
            if not valid:
                raise ValueError('Required comparable row missing')
            row = matches[0]
            raw = pm['data']['raw'][row['source_ids'][0]]
            end = timestamp(row['period_end']).timestamp()
            start = end - 7 * 86400
            if metric == 'volume':
                obs = {int(t): value for t, value in raw['totalDataChart']}
                current = sum(obs[t] for t in range(int(start), int(end), 86400))
                prior = sum(obs[t] for t in range(int(start) - 7 * 86400, int(start), 86400))
            else:
                def last_day(a, b):
                    points = [(r['date'], r['totalLiquidityUSD']) for r in raw['tvl'] if a <= r['date'] < b]
                    return max(points)[1]
                current = last_day(end - 86400, end)
                prior = last_day(end - 8 * 86400, end - 7 * 86400)
            correct = (finite(current) and finite(prior) and math.isclose(current, row['value'], rel_tol=1e-12)
                       and math.isclose(prior, row['previous_value'], rel_tol=1e-12))
            if prior > 0:
                correct = correct and finite(row.get('change_pct')) and math.isclose((current - prior) / prior * 100, row['change_pct'], rel_tol=1e-12, abs_tol=1e-12)
            check('pm-' + metric + '-independent-math', correct, {'current': current, 'previous': prior})
        except (KeyError, TypeError, ValueError, AttributeError, OverflowError) as exc:
            check('pm-' + metric + '-independent-math', False, str(exc))

    second = get('second-protocol')
    check('second-protocol-usable', any(
        usable(r, second, 'tvl') and r.get('entity', {}).get('slug') == 'aave-v3'
        and r.get('entity', {}).get('id') is not None
        for r in second['data'].get('results', [])), 'Exact aave-v3 identity and usable TVL')
    for name, metric in [('stablecoins', 'stablecoin-cap'), ('prices', 'price'), ('chains', 'tvl')]:
        run = get(name)
        check(name + '-usable', any(usable(r, run, metric) for r in run['data'].get('results', [])), 'Required usable observation/comparison')
    pool = discover_pool(get('yields'))
    check('yields-list-usable', pool is not None, 'Usable pool TVL and actual UUID from the fresh list')
    history = get('yield-history')
    check('yield-history-usable', pool is not None and any(
        usable(r, history) and r.get('entity', {}).get('id') == pool
        for r in history['data'].get('results', [])), 'Usable chart for the same discovered pool')

    # Optional statistical comparability may be unavailable, but a successful
    # catalogue lookup alone does not verify the requested metric endpoint.
    for name in ('chain-history', 'market', 'options', 'open-interest'):
        run = get(name)
        observed = any(has_observation(row, run) for row in run['data'].get('results', []))
        classification = ('verified_supported' if run['data'].get('status') == 'ok' else 'verified_degraded') if observed else 'unverified'
        check(name + '-observations', observed, 'Fresh linked values or retained upstream observations; network failure is unverified', classification)
    for metric in ('fees', 'revenue', 'supply-side'):
        rows = [r for r in pm['data'].get('results', []) if r.get('metric', '').split(':')[0] == metric]
        observed = any(has_observation(row, pm) for row in rows)
        comparable = any(usable(row, pm, metric) for row in rows)
        check('pm-' + metric + '-observations', observed, 'Optional calendar comparison can degrade; actual upstream observations remain required',
              'verified_supported' if comparable else 'verified_degraded' if observed else 'unverified')
    return checks


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run', action='store_true', required=True)
    p.parse_args(argv)
    directory = Path(tempfile.mkdtemp(prefix='defillama-live-'))
    with ThreadPoolExecutor(max_workers=3) as pool:
        runs = list(pool.map(lambda case: run_case(case, directory), CASES))
    pool_id = discover_pool(next(run for run in runs if run['name'] == 'yields'))
    if pool_id:
        runs.append(run_case(('yield-history', ['yields', '--pool', pool_id]), directory))
    checks = evaluate_runs(runs)
    report = {'generated_at': utcnow().isoformat(), 'output_directory': str(directory), 'checks': checks,
              'runs': [{k: v for k, v in run.items() if k != 'data'} for run in runs],
              'passed': all(check['passed'] for check in checks),
              'notes': 'Every command uses --no-cache. Freshness is verified per subprocess. Optional calendar degradation requires actual linked observations; network-only failures stay unverified.'}
    (directory / 'summary.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
