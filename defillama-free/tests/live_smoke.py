"""Opt-in real CLI release checks. Usage: python3 tests/live_smoke.py --run.

No fixed live values; raw responses stay in a temporary output directory.
This is intentionally not discovered by unittest.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile

CLI = Path(__file__).resolve().parents[1] / 'scripts' / 'defillama.py'


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run', action='store_true', required=True)
    args = p.parse_args()
    directory = Path(tempfile.mkdtemp(prefix='defillama-live-'))
    cases = [
        ('polymarket', ['protocol','polymarket-international','--metrics','tvl,volume,fees,revenue,supply-side','--days','7','--raw']),
        ('second-protocol', ['protocol','aave-v3','--metrics','tvl','--days','7']),
        ('chains', ['chains']), ('chain-history',['chains','Polygon','--days','7']),
        ('stablecoins',['stablecoins','1','--days','7']),
        ('yields',['yields','--limit','1']), ('prices',['prices','coingecko:ethereum']),
        ('market',['market','--days','7']), ('options',['options','derive','--days','7']),
        ('open-interest',['open-interest'])]
    def run(case):
        name, words = case; target = directory/(name+'.json')
        proc = subprocess.run([sys.executable,str(CLI),*words,'--output',str(target)],capture_output=True,text=True,timeout=300)
        try:
            data = json.loads(target.read_text())
        except (OSError,ValueError):
            data = {'status':'unavailable','results':[],'sources':[]}
        return name,proc.returncode,data
    with ThreadPoolExecutor(max_workers=3) as pool:
        runs = list(pool.map(run,cases))
    all_data = {name:data for name,_,data in runs}
    pools = all_data['yields']['results']
    if pools:
        pool_id = pools[0]['entity']['id']
        runs.append(run(('yield-history',['yields','--pool',pool_id])))
    checks = []
    def check(name, condition, detail):
        checks.append({'check':name,'passed':bool(condition),'detail':detail})
    for name,code,data in runs:
        sources = data.get('sources',[])
        good = [s for s in sources if s.get('status') != 'unavailable' and not s.get('error')]
        check(name+'-http',code in (0,1) and bool(good),{'exit':code,'status':data['status'],'sources':len(good)})
    pm = all_data['polymarket']
    for metric in ('tvl','volume'):
        matches = [r for r in pm['results'] if r['metric']==metric and r.get('window_days')==7]
        check('pm-'+metric, len(matches)==1 and matches[0]['status']=='ok' and str(matches[0]['entity']['id'])=='711', 'Exact international entity and complete 7d comparison')
        if not matches or matches[0]['status']!='ok':
            continue
        row=matches[0]; raw=pm['raw'][row['source_ids'][0]]
        end=datetime.fromisoformat(row['period_end'].replace('Z','+00:00')).timestamp()
        start=end-7*86400
        if metric=='volume':
            obs={int(t):v for t,v in raw['totalDataChart']}
            cur=sum(obs[t] for t in range(int(start),int(end),86400))
            prior=sum(obs[t] for t in range(int(start)-7*86400,int(start),86400))
        else:
            def last_day(a,b):
                points=[(r['date'],r['totalLiquidityUSD']) for r in raw['tvl'] if a<=r['date']<b]
                return max(points)[1]
            cur=last_day(end-86400,end); prior=last_day(end-8*86400,end-7*86400)
        check('pm-'+metric+'-independent-math', math.isclose(cur,row['value'],rel_tol=1e-12) and math.isclose(prior,row['previous_value'],rel_tol=1e-12), {'current':cur,'previous':prior})
    for name,metric in [('second-protocol','tvl'),('stablecoins','stablecoin-cap'),('prices','price')]:
        data=all_data[name]
        check(name+'-usable',any(r.get('metric')==metric and r.get('value') is not None and r['status']=='ok' for r in data['results']), 'Required usable observation/comparison')
    histories=[d for n,_,d in runs if n=='yield-history']
    check('yield-history-usable',bool(histories) and any(r.get('value') is not None and r['status']=='ok' for r in histories[0]['results']), 'Discovered pool chart, not guessed UUID')
    check('chains-usable',any(r.get('value') is not None for r in all_data['chains']['results']), 'Actual chain TVL')
    report={'generated_at':datetime.now(timezone.utc).isoformat(),'output_directory':str(directory),'checks':checks,'passed':all(c['passed'] for c in checks),'notes':'Partial optional calendar metrics are degraded, not asserted supported; network-only failures do not prove unsupported APIs.'}
    (directory/'summary.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))
    return 0 if report['passed'] else 1

if __name__=='__main__':
    raise SystemExit(main())
