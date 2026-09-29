#!/usr/bin/env python3
"""Analyze immutable free-API evidence without network access or credentials."""
import argparse
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, localcontext
from email.utils import parsedate_to_datetime
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit, parse_qsl

MAX_FILE = 8 * 1024 * 1024
MAX_ENVELOPES = 24
EVM = re.compile(r"0x[0-9a-fA-F]{40}\Z")


class EvidenceError(ValueError):
    pass


def address_equal(a, b):
    if not isinstance(a, str) or not isinstance(b, str):
        return False
    return a.lower() == b.lower() if EVM.fullmatch(a) and EVM.fullmatch(b) else a == b


def quantity(value, positive=False):
    if isinstance(value, bool) or value is None or not isinstance(value, (str, int, float, Decimal)):
        return None
    text = str(value)
    if len(text) > 1024:
        return None
    try:
        number = Decimal(text)
        if not number.is_finite() or number < 0 or abs(number.as_tuple().exponent) > 1024:
            return None
        if positive and number <= 0:
            return None
        return number
    except InvalidOperation:
        return None


def number_text(value):
    return None if value is None else format(value, 'f')


def timestamp(value):
    try:
        if isinstance(value, bool):
            return None
        if isinstance(value, (int, float, Decimal)) or (isinstance(value, str) and value.isdigit()):
            result = float(value)
        else:
            dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
            if dt.tzinfo is None:
                return None
            result = dt.timestamp()
        # Static bounds keep analysis reproducible; no analyzer-clock inference.
        return result if 1230768000 <= result <= 4102444800 else None
    except (ValueError, TypeError, OverflowError, AttributeError):
        return None


def iso(value):
    return datetime.fromtimestamp(value, timezone.utc).isoformat().replace('+00:00', 'Z') if value is not None else None


def read_json(path):
    try:
        if not path.is_file() or path.stat().st_size > MAX_FILE:
            raise EvidenceError('证据文件缺失或超过大小上限')
        with path.open(encoding='utf-8') as stream:
            result = json.load(stream, parse_float=str, parse_constant=lambda _: None)
        if not isinstance(result, dict):
            raise EvidenceError('证据必须是 JSON 对象')
        return result
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise EvidenceError('证据文件不可读取或 JSON 无效') from exc


def load_run(directory):
    root = Path(directory).resolve()
    manifest_path = (root / 'manifest.json').resolve()
    if not manifest_path.is_relative_to(root):
        raise EvidenceError('manifest 路径越界')
    manifest = read_json(manifest_path)
    refs = manifest.get('envelopes')
    if manifest.get('schema_version') != 1 or not isinstance(refs, dict) or len(refs) > MAX_ENVELOPES:
        raise EvidenceError('不支持的 manifest 结构或证据数量')
    envelopes = {}
    for name, relative in refs.items():
        if not isinstance(name, str) or not re.fullmatch(r'[a-z][a-z0-9_]{0,63}', name):
            raise EvidenceError('证据名称无效')
        if not isinstance(relative, str) or Path(relative).is_absolute() or '..' in Path(relative).parts:
            raise EvidenceError('证据路径必须位于运行目录内')
        path = (root / relative).resolve()
        if not path.is_relative_to(root):
            raise EvidenceError('证据路径越界')
        envelope = read_json(path)
        if envelope.get('schema_version') != 1:
            raise EvidenceError('不支持的证据版本')
        envelopes[name] = envelope
    return manifest, envelopes


def obj(value):
    return value if isinstance(value, dict) else {}


def attributes(envelope):
    data = envelope.get('data', {}) if envelope and envelope.get('status') == 'ok' else {}
    record = data.get('data', {}) if isinstance(data, dict) else {}
    attrs = record.get('attributes', {}) if isinstance(record, dict) else {}
    return attrs if isinstance(attrs, dict) else {}


def token_identity(envelope, identity):
    attrs = attributes(envelope)
    payload = (envelope or {}).get('data', {})
    data = payload.get('data', {}) if isinstance(payload, dict) else {}
    if not isinstance(data, dict):
        return False
    expected = identity.get('network', '') + '_'
    rid = data.get('id', '')
    return (isinstance(rid, str) and rid.startswith(expected)
            and address_equal(rid[len(expected):], identity.get('address'))
            and address_equal(attrs.get('address'), identity.get('address')))


def safe_source(value):
    if not isinstance(value, str) or len(value) > 4096 or any(c in value for c in '\r\n<>'):
        return None
    try:
        parts = urlsplit(value)
        if parts.scheme != 'https' or parts.username or parts.password or parts.fragment or parts.port not in (None, 443):
            return None
        if parts.hostname not in ('api.geckoterminal.com', 'api.coingecko.com'):
            return None
        if any(re.search(r'key|token|secret|auth', key, re.I) and key != 'token' for key, _ in parse_qsl(parts.query)):
            return None
        return value
    except ValueError:
        return None


def metric(value, name, field, envelopes, scope='token', unit='USD', data_time=None, coverage='provider_reported', **extra):
    env = envelopes.get(name, {})
    return dict(value=value, source_envelope=name, source_field=field, scope=scope,
                currency='USD' if unit == 'USD' else None, unit=unit,
                fetched_at=env.get('fetched_at'), data_time=data_time,
                coverage=coverage, **extra)


def supply_metrics(attrs, name, envelopes, warnings, cg=False):
    results = {}
    if cg:
        for key in ('circulating_supply', 'total_supply', 'max_supply'):
            val = quantity(attrs.get(key))
            results['cg_' + key] = metric(number_text(val), name, 'market_data.' + key, envelopes,
                                         'coin', 'whole_tokens', supply_type=key,
                                         aggregation_scope='coin_aggregate')
        return results
    raw = quantity(attrs.get('total_supply'))
    if raw is not None and raw != raw.to_integral_value():
        raw = None
    normalized = quantity(attrs.get('normalized_total_supply'))
    decimals = attrs.get('decimals')
    valid_decimals = isinstance(decimals, int) and not isinstance(decimals, bool) and 0 <= decimals <= 255
    derived = None
    if raw is not None and valid_decimals:
        parts = raw.as_tuple()
        derived = Decimal((parts.sign, parts.digits, parts.exponent - decimals))
    if normalized is not None and derived is not None and normalized != derived:
        warnings.append('GT 原始与标准化总供应量不一致；保留两者，未据此重算估值。')
    if raw is not None and not valid_decimals:
        warnings.append('GT decimals 缺失或无效，原始供应量不能转换为整枚代币。')
    results['gt_raw_total_supply'] = metric(number_text(raw), name, 'data.attributes.total_supply', envelopes,
                                          unit='smallest_units', supply_type='total_supply', aggregation_scope='chain_contract')
    results['gt_normalized_total_supply'] = metric(number_text(normalized), name, 'data.attributes.normalized_total_supply', envelopes,
                                                 unit='whole_tokens', supply_type='total_supply', aggregation_scope='chain_contract')
    results['gt_total_supply'] = metric(number_text(normalized if normalized is not None else derived), name,
                                      'data.attributes.normalized_total_supply' if normalized is not None else 'data.attributes.total_supply / 10**decimals', envelopes,
                                      unit='whole_tokens', supply_type='total_supply', aggregation_scope='chain_contract',
                                      derived=normalized is None, decimals=decimals if valid_decimals else None)
    return results


def pool_pair(record, network):
    try:
        rel = record['relationships']
        result = []
        for side in ('base_token', 'quote_token'):
            rid = rel[side]['data']['id']
            prefix = network + '_'
            if not isinstance(rid, str) or not rid.startswith(prefix):
                return None
            result.append(rid[len(prefix):])
        return result
    except (KeyError, TypeError):
        return None


def analyze_candles(env, identity, pair, envelopes, warnings):
    missing = {'status': 'unavailable'}
    if not env or env.get('status') != 'ok' or not pair:
        return missing
    payload = obj(env.get('data'))
    meta = payload.get('meta', {})
    if not isinstance(meta, dict):
        return missing
    if not all(isinstance(meta.get(side), dict) and address_equal(meta[side].get('address'), pair[i]) for i, side in enumerate(('base', 'quote'))):
        warnings.append('OHLCV 代币元数据与参考池不一致，未计算价格窗口。')
        return missing
    req = obj(env.get('request'))
    params = obj(req.get('params'))
    requested = params.get('token', 'base')
    perspective = pair[0] if requested == 'base' else pair[1] if requested == 'quote' else requested
    if not address_equal(perspective, identity['address']) or params.get('currency', 'usd') != 'usd':
        warnings.append('OHLCV 计价或目标代币视角不匹配。')
        return missing
    timeframe = params.get('timeframe') or str(req.get('path', '')).rsplit('/', 1)[-1]
    aggregate = quantity(params.get('aggregate', 1), positive=True)
    if timeframe not in ('minute', 'hour', 'day') or aggregate not in ({'minute': (1,5,15), 'hour': (1,4,12), 'day': (1,)}[timeframe]):
        warnings.append('OHLCV 时间粒度无效。')
        return missing
    interval = {'minute': 60, 'hour': 3600, 'day': 86400}[timeframe] * int(aggregate)
    cutoff = timestamp(env.get('fetched_at'))
    if cutoff is None:
        warnings.append('OHLCV 缺少有效原始抓取时间；无法确认完成的蜡烛。')
        return missing
    provider_time = timestamp(env.get('provider_date'))
    if provider_time is None and isinstance(env.get('provider_date'), str):
        try:
            provider_time = timestamp(parsedate_to_datetime(env['provider_date']).isoformat())
        except (ValueError, TypeError, OverflowError):
            pass
    if provider_time is not None:
        cutoff = min(cutoff, provider_time)
    rows = attributes(env).get('ohlcv_list', [])
    if not isinstance(rows, list):
        return missing
    accepted = {}; duplicates = invalid = partial = 0
    for row in rows:
        if not isinstance(row, list) or len(row) != 6:
            invalid += 1; continue
        ts = timestamp(row[0]); nums = [quantity(v, positive=i < 4) for i, v in enumerate(row[1:])]
        if ts is None or ts != int(ts) or any(n is None for n in nums):
            invalid += 1; continue
        op, high, low, close, vol = nums
        if not low <= min(op, close) <= max(op, close) <= high or ts > cutoff:
            invalid += 1; continue
        if ts in accepted:
            duplicates += 1
            if accepted[ts] != nums:
                warnings.append('OHLCV 存在同时间戳冲突；保留第一条，不视为完整覆盖。')
            continue
        accepted[ts] = nums
    completed = []
    for ts, vals in sorted(accepted.items()):
        if ts + interval <= cutoff:
            completed.append((ts, vals))
        else:
            partial += 1
    gaps = sum(b[0] - a[0] != interval for a, b in zip(completed, completed[1:]))
    result = dict(status='ok', completed_count=len(completed), partial_count=partial,
                  duplicate_count=duplicates, invalid_count=invalid, gap_count=gaps,
                  interval_seconds=interval, completion_cutoff=iso(cutoff),
                  start=iso(completed[0][0]) if completed else None,
                  end=iso(completed[-1][0] + interval) if completed else None,
                  coverage='sampled_completed_candles', metrics={})
    if completed:
        with localcontext() as ctx:
            ctx.prec = 100
            ret = (completed[-1][1][3] / completed[0][1][0] - 1) * 100
            peak = completed[0][1][3]; drawdown = Decimal(0)
            for _, vals in completed:
                peak = max(peak, vals[3]); drawdown = max(drawdown, (peak - vals[3]) / peak * 100)
        for key, val, unit in (('period_return_pct',ret,'percent'), ('sample_high',max(r[1][1] for r in completed),'USD'), ('sample_low',min(r[1][2] for r in completed),'USD'), ('close_max_drawdown_pct',drawdown,'percent')):
            result['metrics'][key] = metric(number_text(val), 'ohlcv', 'data.attributes.ohlcv_list', envelopes, 'pool', unit, coverage=result['coverage'], derived=True)
    if gaps or invalid or partial or duplicates:
        warnings.append('OHLCV 为有边界的样本；缺口、重复、无效或未完成蜡烛已单独计数，不命名为固定 7/30/90 日收益。')
    return result


def analyze_trades(env, identity, pair, envelopes):
    if not env or env.get('status') != 'ok' or not pair:
        return {'status': 'unavailable'}
    rows = obj(env.get('data')).get('data')
    if not isinstance(rows, list):
        return {'status': 'unavailable'}
    cutoff = timestamp(env.get('fetched_at'))
    seen = set(); invalid = duplicate = 0; times = []; buys = []; sells = []
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get('id'), str) or not row['id']:
            invalid += 1; continue
        rid = row['id']
        if rid in seen:
            duplicate += 1; continue
        seen.add(rid)
        attrs = row.get('attributes', {})
        if not isinstance(attrs, dict):
            invalid += 1; continue
        frm, to = attrs.get('from_token_address'), attrs.get('to_token_address')
        is_pair = ((address_equal(frm,pair[0]) and address_equal(to,pair[1])) or
                   (address_equal(frm,pair[1]) and address_equal(to,pair[0]))) and not address_equal(frm,to)
        amount = quantity(attrs.get('volume_in_usd'))
        ts = timestamp(attrs.get('block_timestamp'))
        if not is_pair or amount is None or ts is None or cutoff is None or ts > cutoff:
            invalid += 1; continue
        # Provider kind refers to its requested perspective; token addresses establish target direction.
        (buys if address_equal(to,identity['address']) else sells).append(amount)
        times.append(ts)
    def exact_sum(values):
        with localcontext() as ctx:
            ctx.prec = max(100, sum(len(v.as_tuple().digits) + abs(v.as_tuple().exponent) for v in values) + 10)
            return sum(values, Decimal(0))
    buy = exact_sum(buys); sell = exact_sum(sells)
    with localcontext() as ctx:
        ctx.prec = max(100,len(buy.as_tuple().digits)+len(sell.as_tuple().digits)+abs(buy.as_tuple().exponent)+abs(sell.as_tuple().exponent)+10)
        difference = buy - sell
    result = dict(status='ok', count=len(times), buy_count=len(buys), sell_count=len(sells),
                  duplicate_count=duplicate, invalid_count=invalid,
                  start=iso(min(times)) if times else None, end=iso(max(times)) if times else None,
                  coverage='bounded_pool_trade_sample', metrics={})
    for key, val in (('buy_turnover_usd',buy), ('sell_turnover_usd',sell), ('buy_minus_sell_turnover_usd',difference)):
        # An empty valid response has zero observed trades, never zero asset price.
        result['metrics'][key] = metric(number_text(val) if times or not rows else None, 'trades', 'data[].attributes.volume_in_usd', envelopes, 'pool', coverage=result['coverage'], derived=True)
    return result


def analyze_run(directory):
    manifest, envs = load_run(directory)
    identity = manifest.get('identity', {})
    if not isinstance(identity, dict):
        identity = {}
    identity = {key: identity.get(key) for key in ('network','address','coin_id')}
    warnings = []; gaps = []
    result = dict(schema_version=1, status='blocked', identity=identity,
                  started_at=manifest.get('started_at'), completed_at=manifest.get('completed_at'),
                  metrics={}, pools=[], candles={'status':'unavailable'}, trades={'status':'unavailable'},
                  coverage={'pool_discovery':'partial', 'trades':'bounded_sample'}, warnings=warnings, gaps=gaps, sources={})
    for name, env in envs.items():
        result['sources'][name] = {k:env.get(k) for k in ('provider','endpoint','status','fetched_at','provider_date','cache_hit','expires_at')}
        result['sources'][name]['url'] = safe_source(env.get('source_url'))
        if env.get('status') != 'ok':
            gaps.append(name + ': ' + str(env.get('status','unknown')))
    if not all(isinstance(identity.get(k), str) and identity[k] for k in ('network','address')) or not token_identity(envs.get('token'),identity):
        warnings.append('必需的链与合约身份/代币证据未核实，停止生成该代币的市场结论。')
        return result
    result['status'] = 'partial' if gaps else 'ok'
    attrs = attributes(envs['token'])
    result['display'] = {key: attrs.get(key)[:256] if isinstance(attrs.get(key), str) else None for key in ('name','symbol')}
    mapped_coin_id = obj(manifest.get('identity', {}).get('identity_evidence')).get('coin_id_match') is True and bool(identity.get('coin_id')) and identity.get('coin_id') == attrs.get('coingecko_coin_id')
    result['identity']['coin_id_mapping_verified'] = mapped_coin_id
    for key, field in (('price_usd','price_usd'),('reported_fdv_usd','fdv_usd'),('reported_market_cap_usd','market_cap_usd'),('token_reserve_usd','total_reserve_in_usd')):
        val = quantity(attrs.get(field))
        result['metrics'][key] = metric(number_text(val),'token','data.attributes.'+field,envs,
                                        aggregation_scope='reported_aggregation_unknown' if 'cap' in key or 'fdv' in key else 'provider_token_aggregate')
    volume = attrs.get('volume_usd', {})
    result['metrics']['token_volume_h24_usd'] = metric(number_text(quantity(volume.get('h24') if isinstance(volume,dict) else None)), 'token','data.attributes.volume_usd.h24',envs,coverage='provider_h24_window')
    result['metrics'].update(supply_metrics(attrs,'token',envs,warnings))
    if token_identity(envs.get('info'), identity):
        info = attributes(envs['info']); holders = info.get('holders', {})
        if isinstance(holders, dict):
            result['metrics']['holders_count'] = metric(number_text(quantity(holders.get('count'))),'info','data.attributes.holders.count',envs,unit='addresses',data_time=holders.get('last_updated'),coverage='provider_optional_beta')
            dist = holders.get('distribution_percentage', {})
            if isinstance(dist, dict):
                for key in ('top_10','11_30','31_50','rest'):
                    val = quantity(dist.get(key))
                    result['metrics']['holders_'+key+'_pct'] = metric(number_text(val) if val is not None and val<=100 else None,'info','data.attributes.holders.distribution_percentage.'+key,envs,unit='percent',data_time=holders.get('last_updated'),coverage='provider_optional_beta')
        result['metrics']['is_honeypot'] = metric(info.get('is_honeypot') if isinstance(info.get('is_honeypot'),bool) else None,'info','data.attributes.is_honeypot',envs,unit='boolean',coverage='provider_signal_not_audit')
        score = quantity(info.get('gt_score'))
        result['metrics']['gt_score'] = metric(number_text(score) if score is not None and score<=100 else None,'info','data.attributes.gt_score',envs,unit='score',coverage='provider_signal_not_audit')
    elif 'info' in envs:
        warnings.append('附加 token info 身份不匹配或不可用，已排除集中度及安全信号。')
    seen_pools = set(); reference = manifest.get('reference_pool') or {}; selected_pair = None
    if not isinstance(reference, dict):
        reference = {}
    for name, env in envs.items():
        if not name.startswith('pools_page_') or env.get('status') != 'ok':
            continue
        records = obj(env.get('data')).get('data',[])
        if not isinstance(records,list):
            continue
        for record in records:
            if not isinstance(record,dict):
                continue
            pa = record.get('attributes',{}); pair = pool_pair(record,identity['network'])
            if not isinstance(pa,dict) or not pair or not any(address_equal(v,identity['address']) for v in pair):
                warnings.append('发现身份或交易对不匹配的池，已排除。'); continue
            address = pa.get('address'); rid = record.get('id')
            prefix = identity['network'] + '_'
            if (not isinstance(address, str) or not isinstance(rid, str)
                    or not rid.startswith(prefix)
                    or not address_equal(rid[len(prefix):], address)):
                continue
            # Only valid EVM addresses are case-insensitive. Network IDs and
            # other pool identifiers (including non-EVM IDs) retain their case.
            pool_key = (identity['network'], address.lower() if EVM.fullmatch(address) else address)
            if pool_key in seen_pools:
                continue
            seen_pools.add(pool_key)
            side = 'base' if address_equal(pair[0],identity['address']) else 'quote'
            entry = {'address':address,'target_side':side,'pair':pair,'metrics':{}}
            vol = pa.get('volume_usd',{})
            for key, val, field in (('reserve_usd',pa.get('reserve_in_usd'),'reserve_in_usd'),('volume_h24_usd',vol.get('h24') if isinstance(vol,dict) else None,'volume_usd.h24'),('target_price_usd',pa.get(side+'_token_price_usd'),side+'_token_price_usd')):
                entry['metrics'][key] = metric(number_text(quantity(val)),name,'data[].attributes.'+field,envs,'pool',coverage='discovered_pool_sample')
            result['pools'].append(entry)
            if address_equal(address,reference.get('address')) and side == reference.get('target_side'):
                selected_pair = pair
    result['reference_pool'] = {key:reference.get(key) for key in ('address','target_side','selection')}
    candidates = reference.get('candidates', [])
    if not isinstance(candidates, list):
        candidates = []
    rejected = {}
    for candidate in candidates:
        reason = obj(candidate).get('reason')
        if isinstance(reason, str) and reason != 'eligible':
            rejected[reason] = rejected.get(reason, 0) + 1
    result['reference_pool']['candidate_count'] = len(candidates)
    result['reference_pool']['rejection_counts'] = rejected
    pool_path = '/networks/' + identity['network'] + '/pools/' + str(reference.get('address', ''))
    for name in ('ohlcv', 'trades'):
        env = envs.get(name)
        path = obj(env.get('request')).get('path', '') if env else ''
        if not isinstance(path, str):
            path = ''
        suffix = '/ohlcv/' if name == 'ohlcv' else '/trades'
        bound = path.startswith(pool_path + suffix) if name == 'ohlcv' else path == pool_path + suffix
        if env and not bound:
            warnings.append(name + ' 请求并非所选参考池，已排除。')
            env = None
        if name == 'ohlcv':
            result['candles'] = analyze_candles(env,identity,selected_pair,envs,warnings)
        else:
            result['trades'] = analyze_trades(env,identity,selected_pair,envs)
    coin = envs.get('coin',{})
    if coin.get('status') == 'ok':
        data = coin.get('data',{})
        requested = identity.get('coin_id')
        mapped = attrs.get('coingecko_coin_id')
        identity_evidence = obj(manifest.get('identity', {}).get('identity_evidence'))
        if requested and mapped == requested and isinstance(data, dict) and data.get('id') == requested and identity_evidence.get('coin_id_match') is True:
            market = data.get('market_data',{})
            if isinstance(market,dict):
                result['metrics'].update(supply_metrics(market,'coin',envs,warnings,cg=True))
                for key, field in (('cg_price_usd','current_price'),('cg_reported_market_cap_usd','market_cap'),('cg_reported_fdv_usd','fully_diluted_valuation'),('cg_volume_usd','total_volume')):
                    value = market.get(field,{})
                    result['metrics'][key] = metric(number_text(quantity(value.get('usd') if isinstance(value,dict) else None)),'coin','market_data.'+field+'.usd',envs,'coin',data_time=data.get('last_updated'),aggregation_scope='coin_aggregate')
        else:
            warnings.append('CoinGecko ID 与合约映射未同时确认，已排除 CoinGecko 指标。')
    warnings.extend(['GeckoTerminal 与 CoinGecko 属于同一数据体系，不能视为独立交叉验证。',
                     '池储备估值不是可执行深度；持仓分布和安全信号不是审计，也不识别真实钱包归属。',
                     '供应量仅按原有类型与范围展示；未做价格乘供应量估值、跨链供应差额或 DEX/CEX 占比。',
                     '项目收入、解锁计划、团队、审计、合约权限及卖出可执行性未由本次免费 API 证据核实。'])
    if warnings or any(v['value'] is None for v in result['metrics'].values()):
        result['status'] = 'partial'
    return result


def compare_runs(left, right):
    checks = []
    same_identity = left.get('identity',{}).get('network') == right.get('identity',{}).get('network') and address_equal(left.get('identity',{}).get('address'),right.get('identity',{}).get('address'))
    if not same_identity:
        checks.append('两份证据的链/合约不同，只能并排阅读。')
    for section in ('candles','trades'):
        a,b = left.get(section,{}),right.get(section,{})
        if (a.get('start'),a.get('end'),a.get('coverage')) != (b.get('start'),b.get('end'),b.get('coverage')):
            checks.append(section+' 时间窗口或覆盖范围不同。')
    if left.get('completed_at') != right.get('completed_at'):
        checks.append('两次抓取时间不同，不能解释为同时报价。')
    checks.append('不计算跨范围供应差额、比率或排名；保留原始单位、供应类型及聚合范围。')
    return {'schema_version':1,'mode':'comparison','left':left,'right':right,'warnings':checks,'derived_comparisons':[]}


def escape(value):
    if value is None:
        return '未知/缺失'
    text = str(value)[:2048]
    return text.replace('&','&amp;').replace('<','&lt;').replace('>','&gt;').replace('|','\\|').replace('\n',' ').replace('\r',' ').replace('`','\\`').replace('[','\\[').replace(']','\\]')


def render_report(result):
    if result.get('mode') == 'comparison':
        lines = ['# 代币证据并排比较','','不生成跨范围比率或排名。',''] + ['- '+escape(v) for v in result['warnings']]
        lines += ['', '| 指标 | 左侧 | 右侧 |','|---|---|---|']
        for key in sorted(set(result['left'].get('metrics',{})) | set(result['right'].get('metrics',{}))):
            a=result['left'].get('metrics',{}).get(key,{}); b=result['right'].get('metrics',{}).get(key,{})
            lines.append('| '+escape(key)+' | '+escape(a.get('value'))+' '+escape(a.get('unit'))+' | '+escape(b.get('value'))+' '+escape(b.get('unit'))+' |')
        lines += ['','## 左侧完整证据','',render_report(result['left']),'','## 右侧完整证据','',render_report(result['right'])]
        return '\n'.join(lines)
    ident=result['identity']
    lines=['# 代币免费 API 证据报告','', '结论：'+('核心身份或代币证据未通过验证，不能生成市场结论。' if result['status']=='blocked' else '已整理所核实链与合约的有限样本；覆盖缺口及可用性见下方，不构成买卖建议。'),'',
           f"- 名称 / 符号：{escape(result.get('display',{}).get('name'))} / {escape(result.get('display',{}).get('symbol'))}", f"- 链：{escape(ident.get('network'))}",f"- 合约：{escape(ident.get('address'))}", f"- CoinGecko ID：{escape(ident.get('coin_id'))}；映射验证：{escape(ident.get('coin_id_mapping_verified',False))}",f"- 抓取开始：{escape(result.get('started_at'))}",f"- 抓取结束：{escape(result.get('completed_at'))}",'- 池覆盖：有限发现结果；成交：有限池内样本。', '', '| 指标 | 值 | 单位 / 范围 | 证据字段 | 数据更新时间 |','|---|---|---|---|---|']
    for key,m in result['metrics'].items():
        lines.append('| '+escape(key)+' | '+escape(m['value'])+' | '+escape(m['unit'])+' / '+escape(m.get('aggregation_scope',m['scope']))+' | '+escape(m['source_envelope']+': '+m['source_field'])+' | '+escape(m.get('data_time'))+' |')
    reference = result.get('reference_pool', {})
    lines += ['', '## 参考池', '', '- 地址：'+escape(reference.get('address')), '- 目标视角：'+escape(reference.get('target_side')), '- 选择规则：'+escape(reference.get('selection')), '- 候选数量：'+escape(reference.get('candidate_count'))]
    for reason, count in reference.get('rejection_counts', {}).items():
        lines.append('- 排除 '+escape(reason)+'：'+escape(count))
    lines += ['','## 已发现池','', '| 池 | 目标视角 | 目标价格 USD | 储备估值 USD | 24h 成交 USD |','|---|---|---|---|---|']
    for p in result['pools']:
        lines.append('| '+escape(p['address'])+' | '+p['target_side']+' | '+escape(p['metrics']['target_price_usd']['value'])+' | '+escape(p['metrics']['reserve_usd']['value'])+' | '+escape(p['metrics']['volume_h24_usd']['value'])+' |')
    for name,label in (('candles','价格蜡烛样本'),('trades','池内成交样本')):
        section=result[name]
        lines += ['', '## '+label,'',f"状态：{escape(section.get('status'))}；实际区间：{escape(section.get('start'))} 至 {escape(section.get('end'))}。"]
        for key,val in section.items():
            if key.endswith('_count') or key=='count':
                lines.append('- '+escape(key)+'：'+escape(val))
        for key,m in section.get('metrics',{}).items():
            title='样本池买入减卖出成交额（不代表净资金流）' if key=='buy_minus_sell_turnover_usd' else key
            lines.append('- '+escape(title)+'：'+escape(m['value'])+' '+escape(m['unit']))
    lines += ['','## 缺口与口径','']+['- '+escape(w) for w in result['warnings']+result['gaps']]
    lines += ['','## 原始 API 来源','']
    for name,source in result['sources'].items():
        url=source.get('url'); link=f'[{escape(name)}](<{url}>)' if url else escape(name)
        lines.append('- '+link+'；状态 '+escape(source.get('status'))+'；抓取 '+escape(source.get('fetched_at'))+'；缓存 '+escape(source.get('cache_hit'))+'。')
    return '\n'.join(lines)+'\n'


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run_dir',nargs='?')
    parser.add_argument('--compare',nargs=2,metavar=('LEFT','RIGHT'))
    parser.add_argument('--out',required=True,type=Path)
    args=parser.parse_args(argv)
    if bool(args.run_dir)==bool(args.compare):
        parser.error('provide RUN_DIR or --compare LEFT RIGHT')
    output=args.out; normalized=output.with_suffix('.json')
    try:
        if output==normalized or output.exists() or normalized.exists():
            raise EvidenceError('输出路径已存在或 Markdown/JSON 路径冲突')
        result=compare_runs(*(analyze_run(p) for p in args.compare)) if args.compare else analyze_run(args.run_dir)
        text=render_report(result)
        encoded=json.dumps(result,ensure_ascii=False,indent=2)+'\n'
        # Exclusive creation prevents overwriting another analysis, even during races.
        with normalized.open('x',encoding='utf-8') as stream:
            stream.write(encoded)
        with output.open('x',encoding='utf-8') as stream:
            stream.write(text)
        print(json.dumps({'status':result.get('status',result.get('mode')),'outputs':['markdown','normalized_json']},ensure_ascii=False))
        return 0
    except (EvidenceError,OSError,TypeError,ValueError) as exc:
        print(json.dumps({'status':'analysis_error','error':str(exc) if isinstance(exc,EvidenceError) else '证据结构或输出无效'},ensure_ascii=False),file=sys.stderr)
        return 2


if __name__=='__main__':
    raise SystemExit(main())
