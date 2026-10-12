"""Regression cases from observed failures and the reviewed evidence contract."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import shutil
import subprocess
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'check_ip_quality.py'
spec = importlib.util.spec_from_file_location('ip_quality', SCRIPT)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
IP = '8.8.8.8'
ZONE = 'zen.spamhaus.org'
NAME = '8.8.8.8.' + ZONE


def dns(name=NAME, values=None, status=0, qtype=1, soa=False):
    body = {'Status': status, 'TC': False, 'Question': [{'name': name + '.', 'type': qtype}]}
    if values:
        body['Answer'] = [{'name': name + '.', 'type': qtype, 'TTL': 60, 'data': v} for v in values]
    if soa:
        body['Authority'] = [{'name': ZONE + '.', 'type': 6, 'data': 'ns.example.org. hostmaster.example.org. 1 60 60 60 60'}]
    return body


def response(body=None, error=None, status=200):
    return {'body': body, 'error': error, 'http_status': status}


def pc(proxy='no', typ='Business', risk=0, status='ok'):
    return {'status': status, IP: {'proxy': proxy, 'type': typ, 'risk': risk}}


def base_sources(proxy='no', typ='Business', risk=0):
    data, error = m.parse_proxycheck(pc(proxy, typ, risk), IP)
    sources = {'proxycheck': m.evidence('pc', 'https://example.org', 'ok' if not error else 'unknown', data, error),
               'ptr': m.evidence('ptr', 'https://example.org', 'ok', {'records': ['dns.google']})}
    for zone in m.ZONES:
        sources[zone] = m.evidence(zone, 'https://example.org', 'ok', {'listing_status': 'not_listed', 'categories': []})
    return sources


class FakeClient:
    def json(self, url):
        if 'proxycheck' in url:
            return response(pc())
        if 'dns.google' in url:
            query = m.urllib.parse.parse_qs(m.urllib.parse.urlparse(url).query)
            return self.dns(query['name'][0], int(query['type'][0]))
        if 'rdap' in url:
            return response({'errorCode': 500})
        return response(None, 'HTTP 404', 404)

    def dns(self, name, qtype=1):
        if name.endswith('.arpa'):
            return response(dns(name, ['dns.google.'], qtype=12))
        return response(dns(name, ['127.0.0.2']) if name.startswith('2.0.0.127.') else dns(name, status=3))

    def command(self, *args, **kwargs):
        return {'stdout': b'', 'error': 'whois unavailable'}


class InputTests(unittest.TestCase):
    def test_nonpublic_rejected(self):
        for ip in ('127.0.0.1', '10.0.0.1', '192.168.1.1', '198.18.1.1', '192.0.2.1',
                   '100.64.0.1', '0.0.0.0', '224.0.0.1', '::1', 'fe80::1', '2001:db8::1',
                   'ff02::1', 'fe80::1%en0', '::ffff:127.0.0.1'):
            with self.subTest(ip=ip), self.assertRaises(ValueError):
                m.normalize_ip(ip)

    def test_public_canonical(self):
        self.assertEqual(m.normalize_ip('::ffff:8.8.8.8'), IP)
        self.assertEqual(m.normalize_ip('2606:4700:4700:0:0:0:0:1111'), '2606:4700:4700::1111')

    def test_invalid_cli_does_not_query(self):
        with patch.object(m, 'collect') as collect, contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(m.main(['10.0.0.1']), 2)
            self.assertEqual(m.main([IP, '--budget', 'nan']), 2)
            collect.assert_not_called()


class DNSParsingTests(unittest.TestCase):
    def test_spamhaus_all_error_codes_unknown(self):
        for code in (250, 251, 252, 254, 255):
            with self.subTest(code=code):
                result = m.dnsbl_reply(response(dns(values=[f'127.255.255.{code}'])), NAME, ZONE)
                self.assertEqual(result['status'], 'unknown')

    def test_spamhaus_classes(self):
        expected = {2: 'SBL', 3: 'CSS', 4: 'XBL', 9: 'DROP', 10: 'PBL', 11: 'PBL', 30: 'BCL'}
        for code, category in expected.items():
            value = f'127.0.0.{code}'
            with self.subTest(value=value):
                result = m.dnsbl_reply(response(dns(values=[value])), NAME, ZONE)
                self.assertEqual(result['status'], 'listed')
                self.assertEqual(result['categories'], [category])

    def test_other_provider_codes(self):
        self.assertEqual(m.classify_dnsbl('bl.spamcop.net', ['127.0.0.2']), (['reported_spam'], None))
        expected = {1: 'testing', 2: 'sample', 8: 'open_socks_proxy', 9: 'open_http_proxy',
                    12: 'open_dns_resolver', 13: 'dictionary_attack', 15: 'compromised_gateway',
                    17: 'experimental_botnet', 18: 'possibly_compromised_dns_mx',
                    19: 'abused_vpn', 255: 'uncategorized'}
        for code, category in expected.items():
            self.assertEqual(m.classify_dnsbl('dnsbl.dronebl.org', [f'127.0.0.{code}']), ([category], None))

    def test_rcode_failures_unknown(self):
        for status in (1, 2, 5):
            self.assertEqual(m.dnsbl_reply(response(dns(status=status)), NAME, ZONE)['status'], 'unknown')

    def test_valid_absence(self):
        for body in (dns(status=3), dns(soa=True)):
            self.assertEqual(m.dnsbl_reply(response(body), NAME, ZONE)['status'], 'not_listed')

    def test_nodata_without_soa_unknown(self):
        self.assertEqual(m.dnsbl_reply(response(dns()), NAME, ZONE)['status'], 'unknown')

    def test_mixed_or_fake_answers_unknown(self):
        for values in (['198.18.0.1'], ['127.0.0.99'], ['127.0.0.2', '127.255.255.254'], ['8.8.8.8']):
            self.assertEqual(m.dnsbl_reply(response(dns(values=values)), NAME, ZONE)['status'], 'unknown')

    def test_truncated_or_missing_tc_unknown(self):
        for value in (True, None, 0):
            body = dns(values=['127.0.0.2'])
            body['TC'] = value
            self.assertEqual(m.dnsbl_reply(response(body), NAME, ZONE)['status'], 'unknown')

    def test_question_mismatch(self):
        for question in ([{'name': 'different.example', 'type': 1}], [{'name': NAME, 'type': 28}], [], 'invalid'):
            body = dns(values=['127.0.0.2'])
            body['Question'] = question
            self.assertEqual(m.dnsbl_reply(response(body), NAME, ZONE)['status'], 'unknown')

    def test_cname_unfinished(self):
        body = dns(values=['target.example'])
        body['Answer'][0]['type'] = 5
        self.assertEqual(m.dnsbl_reply(response(body), NAME, ZONE)['status'], 'unknown')

    def test_answer_owner_mismatch(self):
        body = dns(values=['127.0.0.2'])
        body['Answer'][0]['name'] = 'wrong.example'
        self.assertEqual(m.dnsbl_reply(response(body), NAME, ZONE)['status'], 'unknown')

    def test_nxdomain_contradictory_answer(self):
        self.assertEqual(m.dnsbl_reply(response(dns(status=3, values=['127.0.0.2'])), NAME, ZONE)['status'], 'unknown')

    def test_malformed_records(self):
        for mutation in ({'Status': False}, {'Answer': 'bad'}, {'Authority': [None]}, {'Answer': [{}]}):
            body = dns()
            body.update(mutation)
            self.assertEqual(m.dnsbl_reply(response(body), NAME, ZONE)['status'], 'unknown')

    def test_unrelated_soa_does_not_confirm_absence(self):
        body = dns(soa=True)
        body['Authority'][0]['name'] = 'different.example'
        self.assertEqual(m.dnsbl_reply(response(body), NAME, ZONE)['status'], 'unknown')


class CollectorTests(unittest.TestCase):
    def test_positive_control_nxdomain_invalidates_negative(self):
        client = FakeClient()
        client.dns = lambda name, qtype=1: response(dns(name, status=3))
        source = m.get_dnsbl(client, IP, ZONE)
        self.assertEqual(source['status'], 'unknown')

    def test_wildcard_invalidates_apparent_positive(self):
        client = FakeClient()
        client.dns = lambda name, qtype=1: response(dns(name, ['127.0.0.2']))
        self.assertEqual(m.get_dnsbl(client, IP, ZONE)['status'], 'unknown')

    def test_control_timeout_unknown(self):
        client = FakeClient()
        client.dns = lambda *args: response(error='budget exhausted')
        self.assertEqual(m.get_dnsbl(client, IP, ZONE)['status'], 'unknown')

    def test_provider_positive_controls(self):
        for zone in m.ZONES:
            source = m.get_dnsbl(FakeClient(), IP, zone)
            self.assertEqual(source['status'], 'ok')
            self.assertEqual(source['data']['listing_status'], 'not_listed')

    def test_dronebl_testing_sample_positive_controls(self):
        zone = 'dnsbl.dronebl.org'
        for values in (['127.0.0.1'], ['127.0.0.2'], ['127.0.0.1', '127.0.0.2']):
            with self.subTest(values=values):
                client = FakeClient()
                client.dns = lambda name, qtype=1: response(dns(name, values) if name.startswith('2.0.0.127.') else dns(name, status=3))
                self.assertEqual(m.get_dnsbl(client, IP, zone)['status'], 'ok')

    def test_dronebl_positive_mixed_non_test_rejected(self):
        for values in (['127.0.0.1', '127.0.0.8'], ['127.0.0.1', '127.0.0.99']):
            client = FakeClient()
            client.dns = lambda name, qtype=1: response(dns(name, values) if name.startswith('2.0.0.127.') else dns(name, status=3))
            self.assertEqual(m.get_dnsbl(client, IP, 'dnsbl.dronebl.org')['status'], 'unknown')

    def test_dronebl_testing_negative_control_rejected(self):
        client = FakeClient()
        client.dns = lambda name, qtype=1: response(dns(name, ['127.0.0.1']))
        self.assertEqual(m.get_dnsbl(client, IP, 'dnsbl.dronebl.org')['status'], 'unknown')

    def test_dronebl_target_test_not_coverage(self):
        zone = 'dnsbl.dronebl.org'
        for value in ('127.0.0.1', '127.0.0.2'):
            client = FakeClient()
            client.dns = lambda name, qtype=1: response(dns(name, status=3) if name.startswith('1.0.0.127.') else dns(name, [value]))
            sources = base_sources()
            sources[zone] = m.get_dnsbl(client, IP, zone)
            self.assertEqual(sources[zone]['status'], 'ok')
            self.assertEqual(m.assess(sources, 'browsing')['verdict'], 'insufficient_evidence')

    def test_txt_failure_does_not_cancel_positive(self):
        client = FakeClient()
        def lookup(name, qtype=1):
            if qtype == 16:
                return response(error='timeout')
            if name.startswith('1.0.0.127.'):
                return response(dns(name, status=3))
            return response(dns(name, ['127.0.0.2']))
        client.dns = lookup
        result = m.get_dnsbl(client, IP, ZONE)
        self.assertEqual(result['status'], 'ok')
        self.assertEqual(result['data']['listing_status'], 'listed')
        self.assertEqual(result['data']['txt_error'], 'timeout')

    def test_ipv6_unsupported_without_queries(self):
        client = FakeClient()
        with patch.object(client, 'dns') as query:
            self.assertEqual(m.get_dnsbl(client, '2606:4700:4700::1111', ZONE)['status'], 'unsupported')
            query.assert_not_called()

    def test_ptr_absence_and_error_differ(self):
        client = FakeClient()
        client.json = lambda url: response(dns(m.ipaddress.ip_address(IP).reverse_pointer, status=3, qtype=12))
        self.assertEqual(m.get_ptr(client, IP)['data']['record_status'], 'absent')
        client.json = lambda url: response(error='timeout')
        self.assertEqual(m.get_ptr(client, IP)['status'], 'unknown')

    def test_shodan_404_is_unknown(self):
        result = m.get_internetdb(FakeClient(), IP)
        self.assertEqual(result['status'], 'unknown')
        self.assertEqual(result['data']['record_status'], 'no_data')
        self.assertNotIn('ports', result['data'])

    def test_rdap_errors_not_success(self):
        self.assertEqual(m.get_rdap(FakeClient(), IP)['status'], 'unknown')

    def test_rdap_only_organization_not_contacts(self):
        body = {'objectClassName': 'ip network', 'startAddress': '8.8.8.0', 'endAddress': '8.8.8.255',
                'entities': [{'roles': ['registrant'], 'vcardArray': ['vcard', [
                    ['fn', {}, 'text', 'Private Person'], ['email', {}, 'text', 'private@example.org'],
                    ['tel', {}, 'text', '12345'], ['org', {}, 'text', 'Example Organization']]]}]}
        data, error = m.parse_rdap(body, IP)
        self.assertIsNone(error)
        serialized = json.dumps(data)
        self.assertIn('Example Organization', serialized)
        self.assertNotIn('Private Person', serialized)
        self.assertNotIn('private@example.org', serialized)
        self.assertNotIn('12345', serialized)

    def test_rdap_mismatched_target_unknown(self):
        self.assertIsNotNone(m.parse_rdap({'objectClassName': 'ip network', 'startAddress': '9.0.0.0', 'endAddress': '9.0.0.255'}, IP)[1])

    def test_missing_whois_unknown(self):
        self.assertEqual(m.get_cymru(FakeClient(), IP)['status'], 'unknown')

    def test_macos_whois_remote_flag_not_local_option(self):
        client = FakeClient()
        output = b'15169 | 8.8.8.8 | 8.8.8.0/24 | US | arin | 2023-12-28 | GOOGLE\n'
        with patch.object(client, 'command', return_value={'stdout': output, 'error': None}) as command:
            result = m.get_cymru(client, IP)
            self.assertEqual(result['status'], 'ok')
            self.assertEqual(result['data']['asn'], '15169')
            self.assertTrue(command.call_args.args[0][-1].startswith(' -v '))

    def test_shodan_malformed_object_unknown(self):
        client = FakeClient()
        client.json = lambda url: response({'detail': 'error'})
        self.assertEqual(m.get_internetdb(client, IP)['status'], 'unknown')


class PolicyTests(unittest.TestCase):
    def test_proxycheck_status_contract(self):
        for status in ('ok', 'warning'):
            self.assertIsNone(m.parse_proxycheck(pc(status=status), IP)[1])
        for status in ('success', 'denied', 'error', None):
            self.assertIsNotNone(m.parse_proxycheck(pc(status=status), IP)[1])

    def test_missing_warning_fields_not_complete(self):
        body = pc(status='warning')
        del body[IP]['risk']
        data, error = m.parse_proxycheck(body, IP)
        self.assertFalse(data['complete'])
        self.assertIsNotNone(error)
        self.assertIsNotNone(data['warning'])
        self.assertNotIn('risk', data)

    def test_invalid_risk_not_defaulted(self):
        for risk in (-1, 101, True, '0', None):
            data, error = m.parse_proxycheck(pc(risk=risk), IP)
            self.assertFalse(data['complete'])
            self.assertIsNotNone(error)

    def test_all_unknown_never_safe(self):
        sources = base_sources()
        for source in sources.values():
            source.update(status='unknown', data={})
        for case in m.USE_CASES:
            self.assertEqual(m.assess(sources, case)['verdict'], 'insufficient_evidence')

    def test_threshold_boundaries(self):
        for proxy, typ, risk, expected in (
            ('no', 'Business', 66, False), ('no', 'Business', 67, True),
            ('yes', 'VPN', 73, False), ('yes', 'VPN', 74, True),
            ('no', 'Hosting', 66, False), ('no', 'Hosting', 67, True),
            ('yes', 'HTTP', 0, True)):
            with self.subTest(proxy=proxy, typ=typ, risk=risk):
                self.assertEqual(m.assess(base_sources(proxy, typ, risk), 'browsing')['verdict'],
                                 'observed_risk' if expected else 'no_adverse_signal_in_checked_sources')

    def test_account_labels_are_platform_sensitive(self):
        for proxy, typ in (('yes', 'VPN'), ('no', 'Hosting')):
            result = m.assess(base_sources(proxy, typ, 0), 'account')
            self.assertEqual(result['verdict'], 'observed_risk')
            self.assertTrue(any('平台敏感性' in r for r in result['reasons']))

    def test_positive_retained_with_gaps(self):
        sources = base_sources('yes', 'VPN', 73)
        for zone in m.ZONES:
            sources[zone]['status'] = 'unknown'
        sources[ZONE] = m.evidence(ZONE, 'https://example.org', 'ok', {'categories': ['XBL'], 'listing_status': 'listed'})
        self.assertEqual(m.assess(sources, 'browsing')['verdict'], 'observed_risk')
        self.assertEqual(m.assess(sources, 'mail')['verdict'], 'observed_risk')

    def test_partial_positive_not_erased(self):
        sources = base_sources()
        body = pc(proxy='yes', typ='VPN')
        del body[IP]['risk']
        data, error = m.parse_proxycheck(body, IP)
        sources['proxycheck'] = m.evidence('pc', 'https://example.org', 'unknown', data, error)
        self.assertEqual(m.assess(sources, 'account')['verdict'], 'observed_risk')
        self.assertEqual(m.assess(sources, 'browsing')['verdict'], 'insufficient_evidence')

    def test_pbl_only_mail_policy(self):
        sources = base_sources()
        sources[ZONE]['data'] = {'categories': ['PBL'], 'listing_status': 'listed'}
        for case in ('browsing', 'account'):
            self.assertEqual(m.assess(sources, case)['verdict'], 'no_adverse_signal_in_checked_sources')
        result = m.assess(sources, 'mail')
        self.assertEqual(result['verdict'], 'observed_risk')
        self.assertTrue(any('认证 SMTP' in note for note in result['notes']))

    def test_mail_requires_all_zones(self):
        sources = base_sources()
        sources[ZONE]['status'] = 'unknown'
        self.assertEqual(m.assess(sources, 'browsing')['verdict'], 'no_adverse_signal_in_checked_sources')
        self.assertEqual(m.assess(sources, 'mail')['verdict'], 'insufficient_evidence')

    def test_ptr_missing_vs_unavailable(self):
        sources = base_sources()
        sources['ptr']['data']['records'] = []
        self.assertEqual(m.assess(sources, 'mail')['verdict'], 'observed_risk')
        sources['ptr']['status'] = 'unknown'
        self.assertEqual(m.assess(sources, 'mail')['verdict'], 'insufficient_evidence')

    def test_sample_uncategorized_not_negative_coverage(self):
        for cat in ('testing', 'sample', 'uncategorized'):
            sources = base_sources()
            sources['dnsbl.dronebl.org']['data'] = {'categories': [cat], 'listing_status': 'listed'}
            self.assertEqual(m.assess(sources, 'browsing')['verdict'], 'insufficient_evidence')

    def test_ipv6_does_not_inherit_ipv4_coverage(self):
        sources = base_sources()
        for zone in m.ZONES:
            sources[zone]['status'] = 'unsupported'
        self.assertEqual(m.assess(sources, 'browsing')['verdict'], 'insufficient_evidence')


class TransportTests(unittest.TestCase):
    def client(self, version=b'curl 8.7.1 (system)\n'):
        with patch.object(m.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, version, b'')):
            return m.Client()

    def test_version_gate(self):
        for version in (b'curl 8.3.0 (system)\n', b'not-a-version', b'curl 7.88.1 (system)'):
            client = self.client(version)
            with patch.object(m.subprocess, 'run') as run:
                self.assertIsNotNone(client.json('https://example.org')['error'])
                run.assert_not_called()
        self.assertIsNone(self.client(b'curl 8.4.0 (system)\n').http_error)

    def test_http_errors_unknown(self):
        client = self.client()
        for status in (403, 429, 500):
            with patch.object(client, 'command', return_value={'stdout': b'{"error":true}\n' + str(status).encode(), 'error': None}):
                result = client.json('https://example.org')
                self.assertEqual(result['http_status'], status)
                self.assertIsNotNone(result['error'])
                self.assertIsNone(result['body'])

    def test_malformed_or_oversized_json(self):
        client = self.client()
        for body in (b'invalid', b'[]', b'{"risk": NaN}', b'a' * (m.MAX_BODY + 1)):
            with patch.object(client, 'command', return_value={'stdout': body + b'\n200', 'error': None}):
                self.assertIsNotNone(client.json('https://example.org')['error'])

    def test_curl_error_does_not_parse_partial(self):
        client = self.client()
        with patch.object(client, 'command', return_value={'stdout': b'{"status":"ok"}\n200', 'error': 'exit 63'}):
            self.assertIsNone(client.json('https://example.org')['body'])

    def test_transport_flags(self):
        client = self.client()
        with patch.object(client, 'command', return_value={'stdout': b'{}\n200', 'error': None}) as run:
            self.assertIsNone(client.json('https://example.org')['error'])
            args = run.call_args.args[0]
            self.assertEqual(args[:2], ['curl', '-q'])
            self.assertIn('--max-filesize', args)
            self.assertIn('Accept-Encoding: identity', args)
            self.assertNotIn('--compressed', args)
            self.assertIn('=https', args)

    def test_deadline_prevents_new_query(self):
        client = self.client()
        client.deadline = time.monotonic() - 1
        with patch.object(m.subprocess, 'run') as run:
            self.assertIsNotNone(client.json('https://example.org')['error'])
            self.assertIsNotNone(client.command(['whois'])['error'])
            run.assert_not_called()

    def test_process_timeout_and_missing_command(self):
        client = self.client()
        for error in (subprocess.TimeoutExpired('curl', 1, output=b'partial'), FileNotFoundError()):
            with patch.object(m.subprocess, 'run', side_effect=error):
                self.assertEqual(client.command(['curl'])['stdout'], b'')
                self.assertIsNotNone(client.command(['curl'])['error'])

    def test_real_chunked_body_stops_before_full_buffer(self):
        if not shutil.which('curl'):
            self.fail('curl required to verify reviewed transport contract')
        client = m.Client()
        self.assertIsNone(client.http_error, 'curl >=8.4.0 required for chunked contract')
        class Handler(BaseHTTPRequestHandler):
            protocol_version = 'HTTP/1.1'
            def do_GET(self):
                self.close_connection = True
                self.send_response(200)
                self.send_header('Transfer-Encoding', 'chunked')
                self.end_headers()
                try:
                    for _ in range(128):
                        chunk = b'x' * 16384
                        self.wfile.write(b'4000\r\n' + chunk + b'\r\n')
                        self.wfile.flush()
                    self.wfile.write(b'0\r\n\r\n')
                except (BrokenPipeError, ConnectionResetError):
                    pass
            def log_message(self, *args):
                pass
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            # HTTP only for this disposable loopback fixture; production allows HTTPS only.
            proc = subprocess.run(['curl', '-q', '-sS', '--noproxy', '*', '--max-time', '5',
                                   '--max-filesize', str(m.MAX_BODY),
                                   f'http://127.0.0.1:{server.server_port}/'], capture_output=True, timeout=6)
            self.assertEqual(proc.returncode, 63)
            self.assertLessEqual(len(proc.stdout), m.MAX_BODY)
            self.assertLess(len(proc.stdout), 128 * 16384)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)


class ReportTests(unittest.TestCase):
    def test_mock_cli_integration_json_markdown_same_verdict(self):
        report = m.collect(IP, client=FakeClient())
        for format in ('json', 'markdown'):
            stream = io.StringIO()
            with patch.object(m, 'collect', return_value=report), contextlib.redirect_stdout(stream):
                self.assertEqual(m.main([IP, '--format', format]), 0)
            result = stream.getvalue()
            if format == 'json':
                self.assertEqual(json.loads(result)['assessments'], report['assessments'])
            else:
                for assessment in report['assessments'].values():
                    self.assertIn(assessment['verdict'], result)
            self.assertNotIn('suggested_score', result)
            self.assertNotIn('clean / low risk', result)

    def test_markdown_external_text_escaped(self):
        cell = m.md_cell('<script>|\n[click](https://bad.example) `code`')
        self.assertNotIn('<script>', cell)
        self.assertIn('\\|', cell)
        self.assertNotIn('\n', cell)
        self.assertIn('\\[click\\]', cell)

    def test_only_requested_use_case(self):
        report = m.collect(IP, 'account', client=FakeClient())
        self.assertEqual(set(report['assessments']), {'account'})
        self.assertEqual(sum(report['coverage'].values()), len(report['sources']))


if __name__ == '__main__':
    unittest.main()
