#!/usr/bin/env python3
"""Collect bounded public IP evidence; unknown results never imply safety."""
from __future__ import annotations

import argparse
import datetime as dt
import ipaddress
import json
import os
import re
import selectors
import subprocess
import sys
import time
import urllib.parse
from typing import Any

MAX_BODY = 524288
USE_CASES = ('browsing', 'account', 'mail')
VERDICTS = {
    'observed_risk': '发现风险信号',
    'no_adverse_signal_in_checked_sources': '已查来源未发现该用途的异常信号',
    'insufficient_evidence': '证据不足，无法可靠判断',
}
LIMITATION = '仅覆盖所查数据库；不证明独享、住宅真实性、目标平台放行、邮件投递成功或未来信誉。'
ZONES = ('zen.spamhaus.org', 'bl.spamcop.net', 'dnsbl.dronebl.org')
SPAMHAUS = {
    '127.0.0.2': 'SBL', '127.0.0.3': 'CSS', '127.0.0.4': 'XBL',
    '127.0.0.9': 'DROP', '127.0.0.10': 'PBL', '127.0.0.11': 'PBL',
    '127.0.0.30': 'BCL',
}
DRONEBL = {
    1: 'testing', 2: 'sample', 3: 'irc_spam', 5: 'experimental_bottler',
    6: 'worm_or_spambot', 7: 'ddos', 8: 'open_socks_proxy',
    9: 'open_http_proxy', 10: 'proxychain', 11: 'web_proxy',
    12: 'open_dns_resolver', 13: 'dictionary_attack', 14: 'open_wingate_proxy',
    15: 'compromised_gateway', 16: 'worm', 17: 'experimental_botnet',
    18: 'possibly_compromised_dns_mx', 19: 'abused_vpn', 255: 'uncategorized',
}
DRONEBL_A = {f'127.0.0.{code}': category for code, category in DRONEBL.items()}
PROXY_TYPES = {
    'vpn', 'tor', 'proxy', 'http', 'https', 'socks', 'socks4', 'socks4a',
    'socks5', 'socks5h', 'shadowsocks', 'openvpn', 'scraper', 'inference engine',
}
TYPE_NAMES = {'business', 'residential', 'wireless', 'hosting', 'compromised server'} | PROXY_TYPES


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')


def output_safe(value: Any) -> Any:
    """Keep the shared evidence model encodable, including diagnostic strings."""
    if isinstance(value, str):
        return re.sub(r'[\ud800-\udfff]', '\ufffd', value)
    if isinstance(value, list):
        return [output_safe(v) for v in value]
    if isinstance(value, dict):
        return {output_safe(k): output_safe(v) for k, v in value.items()}
    return value


def evidence(source: str, url: str, status: str = 'unknown',
             data: dict | None = None, error: str | None = None) -> dict:
    return output_safe(dict(source=source, url=url, checked_at_utc=utc_now(), status=status,
                            data=data or {}, error=error))


def normalize_ip(value: str) -> str:
    # Scoped IPv6 is interface-local and must never reach a public lookup URL.
    if '%' in value:
        raise ValueError('不支持带接口范围的 IPv6')
    addr = ipaddress.ip_address(value.strip())
    if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped:
        addr = addr.ipv4_mapped
    if (not addr.is_global or addr.is_multicast or addr.is_reserved or addr.is_unspecified or
        (isinstance(addr, ipaddress.IPv6Address) and addr.is_site_local)):
        raise ValueError('只接受全球公网单播 IP，不接受私网、保留或回环地址')
    return str(addr)


class Client:
    """curl >=8.4 bounds unknown-length bodies; subprocess bounds wall time."""
    def __init__(self, budget: float = 90):
        self.deadline = time.monotonic() + budget
        self.http_error = None
        result = self.command(['curl', '-q', '--version'], timeout=3)
        if result['error']:
            self.http_error = result['error']
            return
        match = re.match(rb'curl (\d+)\.(\d+)\.(\d+)(?:\s|[-+])', result['stdout'])
        if not match or tuple(map(int, match.groups())) < (8, 4, 0):
            self.http_error = '无法确认 curl >=8.4.0，禁止无界 HTTP 读取'

    def remaining(self) -> float:
        return max(0.0, self.deadline - time.monotonic())

    def command(self, argv: list[str], timeout: float = 10, max_output: int | None = None) -> dict:
        remaining = self.remaining()
        if remaining <= 0.01:
            return dict(stdout=b'', error='全局查询预算已耗尽')
        try:
            if max_output is not None:
                return self.bounded_command(argv, min(timeout, remaining), max_output)
            proc = subprocess.run(argv, capture_output=True,
                                  timeout=min(timeout, remaining), check=False)
        except subprocess.TimeoutExpired:
            return dict(stdout=b'', error='查询超时')
        except FileNotFoundError:
            return dict(stdout=b'', error=f'缺少命令：{argv[0]}')
        except OSError:
            return dict(stdout=b'', error='无法启动查询命令')
        if proc.returncode:
            return dict(stdout=b'', error=f'查询命令失败（退出码 {proc.returncode}）')
        return dict(stdout=proc.stdout, error=None)

    def bounded_command(self, argv: list[str], timeout: float, max_output: int) -> dict:
        """Bound WHOIS while receiving, discard stderr, always kill/reap on failure."""
        deadline = min(self.deadline, time.monotonic() + timeout)
        proc = subprocess.Popen(argv, stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        selector = selectors.DefaultSelector()
        data = bytearray()
        try:
            selector.register(proc.stdout, selectors.EVENT_READ)
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0 or not selector.select(remaining):
                    return dict(stdout=b'', error='查询超时')
                # Read at most one byte beyond the cap to distinguish exact-size EOF.
                chunk = os.read(proc.stdout.fileno(), min(16384, max_output + 1 - len(data)))
                if not chunk:
                    break
                data.extend(chunk)
                if len(data) > max_output:
                    return dict(stdout=b'', error='响应超过体积上限')
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return dict(stdout=b'', error='查询超时')
            code = proc.wait(timeout=remaining)
            if code:
                return dict(stdout=b'', error=f'查询命令失败（退出码 {code}）')
            return dict(stdout=bytes(data), error=None)
        finally:
            selector.close()
            if proc.poll() is None:
                proc.kill()
            proc.wait()
            proc.stdout.close()

    def json(self, url: str) -> dict:
        if self.http_error:
            return dict(body=None, http_status=None, error=self.http_error)
        timeout = min(10.0, self.remaining())
        if timeout <= 0.01:
            return dict(body=None, http_status=None, error='全局查询预算已耗尽')
        result = self.command([
            'curl', '-q', '-L', '-sS', '--http1.1', '--proto', '=https',
            '--proto-redir', '=https', '--max-redirs', '3',
            '--max-time', str(timeout), '--max-filesize', str(MAX_BODY),
            '-H', 'Accept-Encoding: identity', '-w', '\n%{http_code}', url,
        ], timeout=timeout)
        if result['error']:
            return dict(body=None, http_status=None, error=result['error'])
        raw, sep, status_raw = result['stdout'].rpartition(b'\n')
        if not sep or not re.fullmatch(rb'\d{3}', status_raw):
            return dict(body=None, http_status=None, error='缺少合法 HTTP 状态')
        status = int(status_raw)
        if not 200 <= status < 300:
            return dict(body=None, http_status=status, error=f'HTTP {status}')
        if len(raw) > MAX_BODY:
            return dict(body=None, http_status=status, error='响应超过体积上限')
        try:
            body = json.loads(raw, parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
        except (ValueError, UnicodeError, RecursionError):
            return dict(body=None, http_status=status, error='响应不是合法 JSON')
        if not isinstance(body, dict):
            return dict(body=None, http_status=status, error='JSON 顶层不是对象')
        return dict(body=body, http_status=status, error=None)

    def dns(self, name: str, qtype: int = 1) -> dict:
        return self.json('https://dns.google/resolve?' + urllib.parse.urlencode(
            {'name': name, 'type': qtype}))


def short_text(value: Any, limit: int = 160) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    return re.sub(r'[\x00-\x1f\x7f]', ' ', output_safe(value.strip()))[:limit]


def valid_dns_name(value: str) -> bool:
    # Conservatively support simple ASCII DNS names; reject escaped/other forms.
    name = value[:-1] if value.endswith('.') else value
    return (1 <= len(name) <= 253 and all(
        re.fullmatch(r'[A-Za-z0-9_](?:[A-Za-z0-9_-]{0,61}[A-Za-z0-9_])?', label)
        for label in name.split('.')))


def parse_proxycheck(body: Any, ip: str) -> tuple[dict, str | None]:
    if not isinstance(body, dict) or body.get('status') not in ('ok', 'warning'):
        return {}, 'ProxyCheck 状态不是 ok/warning'
    item = body.get(ip)
    if not isinstance(item, dict):
        return {}, '缺少目标 IP 的检测对象'
    data: dict[str, Any] = {'accepted_response': True,
                            'warning': '供应商返回 warning' if body['status'] == 'warning' else None}
    missing = []
    if item.get('proxy') in ('yes', 'no'):
        data['proxy'] = item['proxy']
    else:
        missing.append('proxy')
    typ = short_text(item.get('type'))
    if typ and typ.lower() in TYPE_NAMES:
        data['type'] = typ
    else:
        missing.append('type')
    risk = item.get('risk')
    if type(risk) is int and 0 <= risk <= 100:
        data['risk'] = risk
    else:
        missing.append('risk')
    for key in ('asn', 'provider', 'organisation', 'country', 'region', 'city', 'range'):
        value = short_text(item.get(key))
        if value:
            data[key] = value
    if data.get('proxy') == 'no' and data.get('type', '').lower() in PROXY_TYPES:
        missing.append('proxy/type 相互矛盾')
    data['complete'] = not missing
    data['missing_fields'] = missing
    return data, ('缺少或无效字段：' + ', '.join(missing)) if missing else None


def get_proxycheck(client: Client, ip: str) -> dict:
    url = f'https://proxycheck.io/v2/{ip}?vpn=1&asn=1&risk=1'
    response = client.json(url)
    if response['error']:
        return evidence('ProxyCheck v2', url, error=response['error'])
    data, error = parse_proxycheck(response['body'], ip)
    return evidence('ProxyCheck v2', url, 'unknown' if error else 'ok', data, error)


def dns_records(body: Any, name: str, qtype: int) -> dict:
    """Fail closed on truncated, mismatched, aliased, or ambiguous answers."""
    def unknown(error: str) -> dict:
        return dict(state='unknown', values=[], error=error)
    norm = lambda x: x.lower().rstrip('.') if isinstance(x, str) else ''
    if not isinstance(body, dict) or type(body.get('Status')) is not int:
        return unknown('缺少合法 DNS Status')
    if body.get('TC') is not False:
        return unknown('DNS 回答截断或缺少 TC=false')
    question = body.get('Question')
    if (not isinstance(question, list) or len(question) != 1 or
        not isinstance(question[0], dict) or norm(question[0].get('name')) != norm(name) or
        type(question[0].get('type')) is not int or question[0]['type'] != qtype):
        return unknown('DNS Question 与请求不一致')
    if body['Status'] not in (0, 3):
        return unknown(f'DNS 查询失败（RCODE {body["Status"]}）')
    answers = body.get('Answer', [])
    authority = body.get('Authority', [])
    if not isinstance(answers, list) or not isinstance(authority, list):
        return unknown('DNS 记录结构无效')
    values = []
    for row in answers:
        if (not isinstance(row, dict) or type(row.get('type')) is not int or
            not isinstance(row.get('data'), str) or norm(row.get('name')) != norm(name)):
            return unknown('DNS Answer 记录无效或名称不匹配')
        if row['type'] == 5:
            return unknown('CNAME 查询未跟踪，不能确认结果')
        if row['type'] != qtype or not row['data'].strip():
            return unknown('DNS Answer 类型与请求不符')
        values.append(row['data'])
    soa = False
    for row in authority:
        if (not isinstance(row, dict) or type(row.get('type')) is not int or
            not isinstance(row.get('name'), str) or not isinstance(row.get('data'), str)):
            return unknown('DNS Authority 结构无效')
        owner = norm(row['name'])
        if row['type'] == 6 and owner and (norm(name) == owner or norm(name).endswith('.' + owner)):
            # RFC1035 SOA: MNAME RNAME plus five numeric fields.
            parts = row['data'].split()
            if (len(parts) != 7 or not all(valid_dns_name(p) for p in parts[:2]) or
                not all(re.fullmatch(r'[0-9]{1,10}', p) and int(p) <= 4294967295 for p in parts[2:])):
                return unknown('相关 SOA 内容无效')
            soa = True
    if body['Status'] == 3:
        return unknown('NXDOMAIN 与 Answer 矛盾') if answers else dict(state='absent', values=[], error=None)
    if values:
        return dict(state='present', values=values, error=None)
    if soa:
        return dict(state='absent', values=[], error=None)
    return unknown('空 DNS 回答无相关 SOA，不能确认 NODATA')


def classify_dnsbl(zone: str, values: list[str]) -> tuple[list[str], str | None]:
    categories = []
    for value in values:
        if zone == 'zen.spamhaus.org':
            category = SPAMHAUS.get(value)
        elif zone == 'bl.spamcop.net':
            category = 'reported_spam' if value == '127.0.0.2' else None
        else:
            # Exact ASCII address strings only: never normalize a malformed A code.
            category = DRONEBL_A.get(value)
        if not category:
            return [], f'不支持或错误 DNSBL 返回码：{short_text(value)}'
        if category not in categories:
            categories.append(category)
    return categories, None


def dnsbl_reply(response: dict, name: str, zone: str) -> dict:
    if response['error']:
        return dict(status='unknown', answers=[], categories=[], error=response['error'])
    parsed = dns_records(response['body'], name, 1)
    if parsed['state'] == 'unknown':
        return dict(status='unknown', answers=[], categories=[], error=parsed['error'])
    categories, error = classify_dnsbl(zone, parsed['values'])
    return dict(status='unknown' if error else ('listed' if categories else 'not_listed'),
                answers=parsed['values'], categories=categories, error=error)


def get_dnsbl(client: Client, ip: str, zone: str) -> dict:
    url = {'zen.spamhaus.org': 'https://check.spamhaus.org/',
           'bl.spamcop.net': 'https://www.spamcop.net/bl.shtml',
           'dnsbl.dronebl.org': f'https://dronebl.org/lookup?ip={ip}'}[zone]
    addr = ipaddress.ip_address(ip)
    if addr.version == 6:
        return evidence(zone, url, 'unsupported', {'listing_status': 'unsupported'},
                        '此实现未提供 IPv6 DNSBL 查询')
    positive_name, negative_name = f'2.0.0.127.{zone}', f'1.0.0.127.{zone}'
    positive = dnsbl_reply(client.dns(positive_name), positive_name, zone)
    negative = dnsbl_reply(client.dns(negative_name), negative_name, zone)
    controls = {'positive': positive, 'negative': negative, 'resolver': 'https://dns.google/resolve'}
    expected_positive = (bool(positive['answers']) and set(positive['answers']) <= {'127.0.0.1', '127.0.0.2'}
                         if zone == 'dnsbl.dronebl.org' else '127.0.0.2' in positive['answers'])
    if (positive['status'] != 'listed' or not expected_positive or
        negative['status'] != 'not_listed'):
        return evidence(zone, url, data={'listing_status': 'unknown', 'controls': controls},
                        error=('本次同路径正负控制未通过，目标结果不予采信；'
                               f'正控制={positive["status"]}/{positive["answers"]}，'
                               f'负控制={negative["status"]}/{negative["answers"]}；'
                               f'{positive["error"] or negative["error"] or "不符合预期"}'))
    name = '.'.join(reversed(ip.split('.'))) + '.' + zone
    reply = dnsbl_reply(client.dns(name), name, zone)
    data = {**reply, 'listing_status': reply['status'], 'query_name': name, 'controls': controls}
    if reply['status'] == 'listed':
        txt = client.dns(name, 16)
        parsed = dns_records(txt['body'], name, 16) if not txt['error'] else {'error': txt['error'], 'values': []}
        data['txt'] = [short_text(v, 240) for v in parsed['values'][:3]]
        data['txt_error'] = parsed['error']
    return evidence(zone, url, 'unknown' if reply['status'] == 'unknown' else 'ok', data, reply['error'])


def get_ptr(client: Client, ip: str) -> dict:
    name = ipaddress.ip_address(ip).reverse_pointer
    url = 'https://dns.google/resolve?' + urllib.parse.urlencode({'name': name, 'type': 12})
    response = client.json(url)
    if response['error']:
        return evidence('PTR/rDNS', url, error=response['error'])
    parsed = dns_records(response['body'], name, 12)
    if parsed['error']:
        return evidence('PTR/rDNS', url, error=parsed['error'])
    if any(not valid_dns_name(value) for value in parsed['values']):
        return evidence('PTR/rDNS', url, error='PTR 主机名格式无效')
    hostnames = [value[:-1] if value.endswith('.') else value for value in parsed['values']]
    return evidence('PTR/rDNS', url, 'ok', {'records': hostnames, 'record_status': parsed['state']})


def get_cymru(client: Client, ip: str) -> dict:
    url = 'https://www.team-cymru.com/ip-asn-mapping'
    # Leading space keeps macOS whois from interpreting the remote '-v' query as a local option.
    result = client.command(['whois', '-h', 'whois.cymru.com', f' -v {ip}'], max_output=MAX_BODY)
    if result['error']:
        return evidence('Team Cymru', url, error=result['error'])
    try:
        text = result['stdout'].decode('utf-8')
    except UnicodeError:
        return evidence('Team Cymru', url, error='WHOIS 编码无效')
    for line in text.splitlines():
        fields = [v.strip() for v in line.split('|')]
        if len(fields) != 7 or not fields[0].isdigit():
            continue
        try:
            if ipaddress.ip_address(fields[1]) != ipaddress.ip_address(ip):
                continue
            if ipaddress.ip_address(ip) not in ipaddress.ip_network(fields[2]):
                continue
        except ValueError:
            continue
        return evidence('Team Cymru', url, 'ok', {'asn': fields[0], 'bgp_prefix': fields[2],
                                                'registered_country': fields[3], 'as_name': short_text(fields[6])})
    return evidence('Team Cymru', url, error='未找到匹配目标的有效 ASN/prefix')


def parse_rdap(body: dict, ip: str) -> tuple[dict, str | None]:
    try:
        start, end = ipaddress.ip_address(body['startAddress']), ipaddress.ip_address(body['endAddress'])
        addr = ipaddress.ip_address(ip)
        if start.version != addr.version or end.version != addr.version or not int(start) <= int(addr) <= int(end):
            raise ValueError()
        if body.get('objectClassName') != 'ip network' or 'errorCode' in body:
            raise ValueError()
    except (KeyError, ValueError, TypeError):
        return {}, 'RDAP 缺少目标匹配的网络对象/地址范围'
    # Only organization fields on registrant entities; never FN, email, address, telephone.
    organizations = []
    for entity in body.get('entities', []) if isinstance(body.get('entities'), list) else []:
        if not isinstance(entity, dict) or not isinstance(entity.get('roles'), list) or 'registrant' not in entity['roles']:
            continue
        card = entity.get('vcardArray')
        if not isinstance(card, list) or len(card) != 2 or not isinstance(card[1], list):
            continue
        for row in card[1]:
            if isinstance(row, list) and len(row) >= 4 and row[0] == 'org':
                value = short_text(row[3])
                if value and '@' not in value and value not in organizations:
                    organizations.append(value)
    return {'name': short_text(body.get('name')), 'start': str(start), 'end': str(end),
            'registered_organizations': organizations[:5]}, None


def get_rdap(client: Client, ip: str) -> dict:
    url = f'https://rdap.org/ip/{ip}'
    response = client.json(url)
    if response['error']:
        return evidence('RDAP', url, error=response['error'])
    data, error = parse_rdap(response['body'], ip)
    return evidence('RDAP', url, 'unknown' if error else 'ok', data, error)


def get_internetdb(client: Client, ip: str) -> dict:
    url = f'https://internetdb.shodan.io/{ip}'
    response = client.json(url)
    if response['http_status'] == 404:
        return evidence('Shodan InternetDB', url, data={'record_status': 'no_data'},
                        error='HTTP 404：无扫描数据，不能解释为零暴露')
    if response['error']:
        return evidence('Shodan InternetDB', url, error=response['error'])
    body = response['body']
    try:
        if ipaddress.ip_address(body.get('ip')) != ipaddress.ip_address(ip):
            raise ValueError()
        ports, vulns = body['ports'], body['vulns']
        if (not isinstance(ports, list) or not all(type(p) is int and 0 <= p <= 65535 for p in ports) or
            not isinstance(vulns, list) or not all(isinstance(v, str) for v in vulns)):
            raise ValueError()
    except (KeyError, ValueError, TypeError):
        return evidence('Shodan InternetDB', url, error='缺少匹配目标的有效扫描字段')
    return evidence('Shodan InternetDB', url, 'ok', {'ports': ports[:100], 'vulns': [short_text(v) for v in vulns[:100]],
                                                   'note': '历史扫描辅助信息，不证明当前感染'})


def assess(sources: dict, use_case: str) -> dict:
    pc = sources['proxycheck']['data']
    risks, notes, gaps = [], [], []
    if pc.get('accepted_response'):
        proxy, typ, risk = pc.get('proxy'), pc.get('type', '').lower(), pc.get('risk')
        if proxy == 'yes' and typ and typ != 'vpn':
            risks.append('ProxyCheck 检测到非 VPN 代理（供应商判断）')
        elif risk is not None and ((proxy == 'no' and risk >= 67) or
                                  (proxy == 'yes' and typ == 'vpn' and risk >= 74)):
            risks.append(f'ProxyCheck 供应商风险判断达到保守阈值（原分 {risk}，不是恶意概率）')
        if use_case == 'account' and (proxy == 'yes' or typ in PROXY_TYPES or typ == 'hosting'):
            risks.append('代理/VPN/Tor/机房标签可能影响平台风控，属于平台敏感性信号')
        if typ in ('hosting', 'vpn'):
            notes.append(f'{pc.get("type")} 类型可用于浏览/开发，但不能据此保证平台接受或独享')
    if sources['proxycheck']['status'] != 'ok' or not pc.get('complete'):
        gaps.append('ProxyCheck 必要字段不完整或查询不可用')
    valid = 0
    for zone in ZONES:
        source, data = sources[zone], sources[zone]['data']
        if source['status'] != 'ok':
            if use_case == 'mail':
                gaps.append(f'{zone} 未获得有效结果')
            continue
        cats = set(data.get('categories', []))
        uncertain = cats & {'testing', 'sample', 'uncategorized'}
        if uncertain:
            gaps.append(f'{zone} 返回测试/样本/未分类条目，不能作为阴性覆盖')
        else:
            valid += 1
        abuse = cats - {'PBL', 'testing', 'sample', 'uncategorized'}
        if abuse:
            risks.append(f'{zone} 命中 {", ".join(sorted(abuse))}（名单类别，不证明本机感染）')
        if 'PBL' in cats:
            notes.append('PBL 限制直接向 MX 发送未认证 SMTP；不影响普通浏览或使用认证邮件中继')
            if use_case == 'mail':
                risks.append('PBL 直接发信政策限制')
    if use_case != 'mail' and valid < 1:
        gaps.append('没有有效的滥用名单覆盖（IPv6 查询也不能视为未命中）')
    if use_case == 'mail':
        ptr = sources['ptr']
        if ptr['status'] != 'ok':
            gaps.append('PTR 查询未完成')
        elif not ptr['data'].get('records'):
            risks.append('已确认无 PTR；不适合作为直接发信服务器')
        notes.append('邮件结论针对 direct-MX；认证 SMTP 中继须评估实际中继服务器，且 PTR 存在不等于配置正确')
    verdict = 'observed_risk' if risks else ('insufficient_evidence' if gaps else 'no_adverse_signal_in_checked_sources')
    return dict(verdict=verdict, label=VERDICTS[verdict], reasons=risks, gaps=gaps, notes=list(dict.fromkeys(notes)))


def collect(ip: str, use_case: str = 'overview', budget: float = 90, client: Client | None = None) -> dict:
    started = utc_now()
    client = client or Client(budget)
    sources = {'proxycheck': get_proxycheck(client, ip)}
    # Core reputation first, enrichment last so optional sources cannot exhaust core budget.
    for zone in ZONES:
        sources[zone] = get_dnsbl(client, ip, zone)
    sources['ptr'] = get_ptr(client, ip)
    sources['cymru'] = get_cymru(client, ip)
    sources['rdap'] = get_rdap(client, ip)
    sources['internetdb'] = get_internetdb(client, ip)
    cases = USE_CASES if use_case == 'overview' else (use_case,)
    return dict(schema_version=2, ip=ip, use_case=use_case, started_at_utc=started,
                checked_at_utc=utc_now(), scope='用户指定 IP 的公共数据库查询；未验证浏览器出口或目标平台',
                budget_seconds=budget, sources=sources,
                coverage={state: sum(s['status'] == state for s in sources.values()) for state in ('ok', 'unknown', 'unsupported')},
                assessments={case: assess(sources, case) for case in cases}, limitation=LIMITATION)


def md_cell(value: Any) -> str:
    if value is None:
        text = '未知/无数据'
    elif isinstance(value, (dict, list)):
        text = json.dumps(value, ensure_ascii=False)
    else:
        text = str(value)
    text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    text = text.replace('\\', '\\\\').replace('|', '\\|').replace('`', '\\`').replace('[', '\\[').replace(']', '\\]')
    return text.replace('\r', ' ').replace('\n', ' ')[:1800]


def render_markdown(report: dict) -> str:
    lines = [f'# IP 质量证据：{report["ip"]}', '']
    for case, result in report['assessments'].items():
        lines.append(f'- **{case}：{result["label"]}**（`{result["verdict"]}`）')
        for key, title in (('reasons', '依据'), ('gaps', '缺口'), ('notes', '说明')):
            if result[key]:
                lines.append(f'  - {title}：{md_cell("；".join(result[key]))}')
    lines += ['', f'查询时间（UTC）：{report["checked_at_utc"]}', f'范围：{report["scope"]}',
              f'覆盖：有效 {report["coverage"]["ok"]}；未知 {report["coverage"]["unknown"]}；不支持 {report["coverage"]["unsupported"]}',
              '', '| 来源 | 状态 | 证据 | 缺失/失败原因 |', '|---|---|---|---|']
    for source in report['sources'].values():
        data = {k: v for k, v in source['data'].items() if k != 'controls'}
        lines.append(f'| {md_cell(source["source"])} | {source["status"]} | {md_cell(data)} | {md_cell(source["error"] or "—")} |')
    lines += ['', 'ASN/RDAP 的注册国家不等于出口地理；Shodan 历史扫描不证明当前感染。',
              report['limitation'], '', '核查来源：']
    lines += [f'- [{source["source"]}]({source["url"]}) — {source["checked_at_utc"]}' for source in report['sources'].values()]
    return '\n'.join(lines) + '\n'


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='查询公网 IP 的信誉证据；未知结果不等于安全。')
    parser.add_argument('ip', help='全球公网 IPv4/IPv6')
    parser.add_argument('--use-case', choices=('overview', *USE_CASES), default='overview')
    parser.add_argument('--format', choices=('markdown', 'json'), default='markdown')
    parser.add_argument('--budget', type=float, default=90, help='全局查询预算，1–180秒（默认90）')
    args = parser.parse_args(argv)
    try:
        ip = normalize_ip(args.ip)
        if not 1 <= args.budget <= 180:
            raise ValueError('预算须在1–180秒之间')
    except ValueError as exc:
        print(f'输入无效：{exc}', file=sys.stderr)
        return 2
    report = collect(ip, args.use_case, args.budget)
    print(json.dumps(report, ensure_ascii=False, indent=2) if args.format == 'json' else render_markdown(report), end='\n' if args.format == 'json' else '')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
