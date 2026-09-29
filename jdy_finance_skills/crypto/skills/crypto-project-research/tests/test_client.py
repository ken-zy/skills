"""Observable client and snapshot contracts; synthetic, offline fixtures only."""
import json
import fcntl
import multiprocessing as mp
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest import mock
import urllib.error

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import client
import fetch

ADDRESS = "0x" + "a" * 40
OTHER = "0x" + "b" * 40
POOL = "0x" + "c" * 64  # v4 pool IDs are not ERC20 addresses


def success(data=None):
    return {"http_status": 200, "body": json.dumps({"data": []} if data is None else data).encode(), "provider_date": "Wed, 30 Sep 2026 00:00:00 GMT"}


def pool(address=ADDRESS, side="base", volume="100", reserve="200", network="bsc"):
    return {"id": network + "_" + POOL, "attributes": {"address": POOL, "base_token_price_usd": "2", "quote_token_price_usd": "1", "reserve_in_usd": reserve, "volume_usd": {"h24": volume}}, "relationships": {
        "base_token": {"data": {"id": network + "_" + (address if side == "base" else OTHER)}},
        "quote_token": {"data": {"id": network + "_" + (address if side == "quote" else OTHER)}}}}


def pace_process(directory, output):
    instance = client.Client(directory, deadline=3, cache=False)
    instance.intervals["geckoterminal"] = 0.15
    instance._pace("geckoterminal")
    output.put(time.monotonic())


def hold_rate_lock(directory, ready, release):
    with (Path(directory) / "geckoterminal.lock").open("a") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        ready.set()
        release.wait(5)
        fcntl.flock(handle, fcntl.LOCK_UN)


def wait_for_pacing(directory, waiting, output):
    instance = client.Client(directory, deadline=0.8, cache=False)
    # Initialize after process startup so a slow spawn cannot consume the wait.
    client._atomic(Path(directory) / "geckoterminal.rate.json", {"next_at": time.time() + 0.4})
    real_sleep = time.sleep

    def signal_wait(duration):
        # Signal the actual pacing wait, not a lock-contention poll.
        if duration > 0.05:
            waiting.set()
        real_sleep(duration)

    try:
        with mock.patch.object(client.time, "sleep", side_effect=signal_wait):
            instance._pace("geckoterminal")
        output.put("reserved")
    except TimeoutError:
        output.put("budget_exhausted")


class SlowResponse:
    status = 200
    headers = {}

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass

    def read(self, _):
        time.sleep(5)
        return b'{"data":[]}'


class ClientTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.directory = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def instance(self, response=None, **kwargs):
        send = mock.Mock(return_value=success() if response is None else response)
        instance = client.Client(self.directory, send=send, **kwargs)
        instance.intervals = {provider: 0 for provider in client.ROOTS}
        return instance, send

    def test_fixed_hosts_and_parameter_whitelist(self):
        path, params, url = client.build_request("geckoterminal", "token", {"network": "solana", "address": "SoLCaseAbC"})
        self.assertEqual(path, "/networks/solana/tokens/SoLCaseAbC")
        self.assertTrue(url.startswith(client.ROOTS["geckoterminal"]))
        for params in ({"network": "../eth", "address": ADDRESS}, {"network": "eth", "address": "bad\n"}, {"network": "eth", "address": ADDRESS, "api_key": "dummy"}):
            with self.assertRaises(ValueError):
                client.build_request("geckoterminal", "token", params)
        for paid in ("trading_period", "cursor", "per_page"):
            with self.assertRaises(ValueError):
                client.build_request("geckoterminal", "pool_trades", {"network": "eth", "pool": POOL, paid: "1"})
        with self.assertRaises(ValueError):
            client.build_request("geckoterminal", "pool_ohlcv", {"network": "eth", "pool": POOL, "timeframe": "day", "aggregate": "4"})
        with self.assertRaises(ValueError):
            client.build_request("coingecko-demo", "market_chart", {"id": "bitcoin", "vs_currency": "usd", "days": "366"})

    def test_header_isolation_missing_key_and_no_secret_persistence(self):
        instance, send = self.instance()
        with mock.patch.dict(os.environ, {}, clear=True):
            missing = instance.request("coingecko-demo", "global")
        self.assertEqual(missing["status"], "missing_credential")
        self.assertEqual(send.call_count, 0)
        with mock.patch.dict(os.environ, {"COINGECKO_DEMO_API_KEY": "fake-test-secret"}, clear=True):
            demo = instance.request("coingecko-demo", "global")
            self.assertEqual(send.call_args.args[1]["x-cg-demo-api-key"], "fake-test-secret")
            gt = instance.request("geckoterminal", "networks")
            self.assertNotIn("x-cg-demo-api-key", send.call_args.args[1])
        serialized = json.dumps([missing, demo, gt]) + "".join(path.read_text() for path in self.directory.iterdir() if path.is_file())
        self.assertNotIn("fake-test-secret", serialized)
        self.assertIsNone(demo["expires_at"])
        self.assertEqual(len(list(self.directory.glob("[0-9a-f]" * 64 + ".json"))), 1)

    def test_redirect_does_not_follow_and_proxy_discovery_disabled(self):
        self.assertIsNone(client.NoRedirect().redirect_request(None, None, 302, "", {}, "https://evil.example"))
        connection = mock.Mock()
        opener = mock.Mock()
        opener.open.side_effect = urllib.error.HTTPError("https://safe.example", 302, "", {}, None)
        with mock.patch.object(client.urllib.request, "build_opener", return_value=opener) as build:
            client._network_worker(connection, client.ROOTS["coingecko-demo"] + "/global", {"x-cg-demo-api-key": "fake"}, 1)
        self.assertEqual(build.call_args.args[0].proxies, {})
        self.assertIsInstance(build.call_args.args[1], client.NoRedirect)
        self.assertEqual(connection.send.call_args.args[0]["http_status"], 302)

    def test_invalid_json_provider_errors_overflow_and_body_limit(self):
        for body in (b"bad", b'{"error":"private upstream text"}', b'{"data":{"price":NaN}}', b'{"data":{"price":1e999}}', b"x" * (client.MAX_BODY + 1), b"null"):
            instance, _ = self.instance({"http_status": 200, "body": body}, cache=False)
            evidence = instance.request("geckoterminal", "networks")
            self.assertEqual(evidence["status"], "invalid_response")
            self.assertNotIn("data", evidence)
            self.assertNotIn("private upstream text", json.dumps(evidence))

    def test_cache_preserves_original_timestamp_and_expiry(self):
        instance, send = self.instance()
        first = instance.request("geckoterminal", "networks")
        second = instance.request("geckoterminal", "networks")
        self.assertTrue(second["cache_hit"])
        self.assertEqual(first["fetched_at"], second["fetched_at"])
        self.assertEqual(first["expires_at"], second["expires_at"])
        self.assertEqual(second["attempts"], 0)
        self.assertEqual(send.call_count, 1)
        for path in self.directory.glob("*.json"):
            if path.name.endswith(".rate.json"):
                continue
            saved = json.loads(path.read_text())
            saved["expires_at"] = "2000-01-01T00:00:00Z"
            path.write_text(json.dumps(saved))
        send.return_value = {"http_status": 403}
        third = instance.request("geckoterminal", "networks")
        self.assertEqual(third["status"], "http_error")
        self.assertNotIn("data", third)

    def test_cache_write_failure_does_not_lose_success(self):
        instance, _ = self.instance()
        real_atomic = client._atomic
        def write(path, data):
            if not path.name.endswith(".rate.json"):
                raise PermissionError
            real_atomic(path, data)
        with mock.patch.object(client, "_atomic", side_effect=write):
            evidence = instance.request("geckoterminal", "networks")
        self.assertEqual(evidence["status"], "ok")
        self.assertEqual(evidence["warnings"], ["cache_write_failed"])

    def test_retry_after_exceeding_deadline_and_shared_backoff(self):
        instance, send = self.instance({"http_status": 429, "retry_after": "120"}, deadline=0.5, cache=False)
        started = time.monotonic()
        evidence = instance.request("geckoterminal", "networks")
        self.assertLess(time.monotonic() - started, 0.5)
        self.assertEqual(evidence["status"], "rate_limited")
        self.assertEqual(send.call_count, 1)
        following, send2 = self.instance(deadline=0.1, cache=False)
        self.assertEqual(following.request("geckoterminal", "networks")["status"], "budget_exhausted")
        send2.assert_not_called()

    def test_retry_attempt_budget_and_no_retry_4xx(self):
        instance, send = self.instance({"http_status": 500}, max_attempts=2, cache=False)
        with mock.patch.object(client.time, "sleep"):
            evidence = instance.request("geckoterminal", "networks")
        self.assertEqual(evidence["attempts"], 2)
        self.assertEqual(instance.used, 2)
        self.assertEqual(instance.request("geckoterminal", "networks")["status"], "budget_exhausted")
        for status in (400, 401, 403, 404):
            instance, send = self.instance({"http_status": status}, cache=False)
            instance.request("geckoterminal", "networks")
            self.assertEqual(send.call_count, 1)

    def test_corrupt_pacing_state_fails_closed_even_no_cache(self):
        (self.directory / "geckoterminal.rate.json").write_text('{"next_at":"broken"}')
        instance, send = self.instance(cache=False)
        evidence = instance.request("geckoterminal", "networks")
        self.assertEqual(evidence["error"]["code"], "invalid_pacing_state")
        send.assert_not_called()

    def test_cross_process_pacing(self):
        context = mp.get_context("spawn")
        output = context.Queue()
        workers = [context.Process(target=pace_process, args=(str(self.directory), output)) for _ in range(3)]
        for worker in workers:
            worker.start()
        times = sorted(output.get(timeout=5) for _ in workers)
        for worker in workers:
            worker.join(timeout=5)
            self.assertEqual(worker.exitcode, 0)
        self.assertGreaterEqual(times[1] - times[0], 0.13)
        self.assertGreaterEqual(times[2] - times[1], 0.13)
        output.close()

    def test_lock_contention_deadline_prevents_network(self):
        context = mp.get_context("spawn")
        ready, release = context.Event(), context.Event()
        worker = context.Process(target=hold_rate_lock, args=(str(self.directory), ready, release))
        worker.start()
        try:
            self.assertTrue(ready.wait(3))
            instance, send = self.instance(deadline=0.12, cache=False)
            started = time.monotonic()
            evidence = instance.request("geckoterminal", "networks")
            self.assertEqual(evidence["status"], "budget_exhausted")
            self.assertLess(time.monotonic() - started, 0.4)
            send.assert_not_called()
        finally:
            release.set()
            worker.join(timeout=3)
            if worker.is_alive():
                worker.terminate()
                worker.join(timeout=1)
        self.assertEqual(worker.exitcode, 0)

    def test_waiting_process_observes_new_shared_backoff(self):
        context = mp.get_context("spawn")
        waiting, output = context.Event(), context.Queue()
        # The worker initially could reserve in 0.4 seconds. A concurrent 429
        # response extends that deadline while the worker is already waiting.
        worker = context.Process(target=wait_for_pacing, args=(str(self.directory), waiting, output))
        worker.start()
        try:
            self.assertTrue(waiting.wait(3))
            updater = client.Client(self.directory, cache=False, deadline=2)
            updater._pace("geckoterminal", not_before=time.time() + 1.2)
            self.assertEqual(output.get(timeout=3), "budget_exhausted")
        finally:
            worker.join(timeout=3)
            if worker.is_alive():
                worker.terminate()
                worker.join(timeout=1)
            output.close()
        self.assertEqual(worker.exitcode, 0)

    @unittest.skipUnless("fork" in mp.get_all_start_methods(), "Unix fork needed to inject blocked network operation")
    def test_actual_worker_deadline_bounds_dns_and_slow_body(self):
        context = mp.get_context("fork")
        for dns in (True, False):
            opener = mock.Mock()
            if dns:
                opener.open.side_effect = lambda *args, **kwargs: time.sleep(5)
            else:
                opener.open.return_value = SlowResponse()
            with mock.patch.object(client.mp, "get_context", return_value=context), mock.patch.object(client.urllib.request, "build_opener", return_value=opener):
                started = time.monotonic()
                result = client.transport(client.ROOTS["geckoterminal"] + "/networks", {}, 0.15)
            self.assertEqual(result["error"], "timeout")
            self.assertLess(time.monotonic() - started, 0.7)

    def test_evidence_no_overwrite(self):
        target = self.directory / "evidence.json"
        client.write_new(target, {"first": True})
        with self.assertRaises(FileExistsError):
            client.write_new(target, {"first": False})
        self.assertTrue(json.loads(target.read_text())["first"])


class SnapshotTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.directory = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def mock_client(self, token_address=ADDRESS, cg_id="test-coin", side="base"):
        instance = client.Client(self.directory / "cache", cache=False)
        instance.intervals = {provider: 0 for provider in client.ROOTS}
        def send(url, headers, timeout):
            if "/ohlcv/" in url:
                return success({"data": {"attributes": {"ohlcv_list": []}}, "meta": {"base": {"address": ADDRESS}, "quote": {"address": OTHER}}})
            if "/trades" in url:
                return success()
            if "/pools?" in url:
                return success({"data": [pool(side=side)]})
            if "/info" in url:
                return {"http_status": 404}
            return success({"data": {"id": "bsc_" + token_address, "attributes": {"address": token_address, "coingecko_coin_id": cg_id}}})
        instance.send = mock.Mock(side_effect=send)
        return instance

    def test_partial_snapshot_quote_target_and_missing_demo_key(self):
        instance = self.mock_client(side="quote")
        with mock.patch.dict(os.environ, {}, clear=True):
            manifest = fetch.snapshot(instance, "bsc", ADDRESS, self.directory / "run", "standard", "test-coin")
        self.assertEqual(manifest["reference_pool"]["target_side"], "quote")
        self.assertEqual(manifest["identity"]["identity_evidence"]["status"], "verified")
        self.assertIn("info:http_error", manifest["warnings"])
        self.assertIn("coin:missing_credential", manifest["warnings"])
        evidence = json.loads((self.directory / "run" / "trades.json").read_text())
        self.assertEqual(evidence["request"]["params"]["token"], ADDRESS)
        self.assertTrue(all(not Path(name).is_absolute() for name in manifest["envelopes"].values()))
        with self.assertRaises(FileExistsError):
            fetch.snapshot(instance, "bsc", ADDRESS, self.directory / "run")

    def test_wrong_ca_blocks_reference_and_coin_enrichment(self):
        instance = self.mock_client(token_address=OTHER)
        manifest = fetch.snapshot(instance, "bsc", ADDRESS, self.directory / "wrong", "standard", "test-coin")
        self.assertEqual(manifest["identity"]["identity_evidence"]["status"], "unverified")
        self.assertIsNone(manifest["reference_pool"]["address"])
        self.assertNotIn("coin", manifest["envelopes"])
        self.assertNotIn("ohlcv", manifest["envelopes"])

    def test_absent_coin_mapping_skips_demo(self):
        manifest = fetch.snapshot(self.mock_client(cg_id=None), "bsc", ADDRESS, self.directory / "run", coin_id="test-coin")
        self.assertFalse(manifest["identity"]["identity_evidence"]["coin_id_match"])
        self.assertNotIn("coin", manifest["envelopes"])

    def test_selection_rejects_wrong_chain_invalid_or_missing_values(self):
        rows = [pool(network="eth"), pool(volume=None), pool(reserve="0"), pool(side="quote")]
        selected = fetch.select_pool(rows, "bsc", ADDRESS)
        # Duplicate pool IDs are one observed pool; don't overwrite earlier evidence.
        self.assertIsNone(selected["address"])
        selected = fetch.select_pool([pool(side="quote")], "bsc", ADDRESS)
        self.assertEqual(selected["address"], POOL)
        self.assertEqual(selected["target_side"], "quote")
        self.assertFalse(fetch.same_address("SoLaNa", "solana"))
        self.assertTrue(fetch.same_address(ADDRESS.upper().replace("0X", "0x"), ADDRESS))

    def test_selection_rejects_extreme_numeric_values_without_crashing(self):
        for value in ("1e999999999", "1e-999999999", "9" * 1025, "NaN", "Infinity", "-1", True):
            with self.subTest(value=str(value)[:40]):
                selected = fetch.select_pool([pool(volume=value)], "bsc", ADDRESS)
                self.assertIsNone(selected["address"])
                self.assertEqual(selected["candidates"][0]["reason"], "missing_or_invalid_price_liquidity_volume")

    def test_selection_preserves_full_precision_and_lexical_ties(self):
        def candidate(suffix, volume, reserve):
            row = pool(volume=volume, reserve=reserve)
            address = "0x" + suffix * 64
            row["id"] = "bsc_" + address
            row["attributes"]["address"] = address
            return row

        low = "123456789012345678901234567890.0000000000000000000000000001"
        high = "123456789012345678901234567890.0000000000000000000000000002"
        lower_id = candidate("1", low, "100")
        greater_volume = candidate("2", high, "100")
        greater_reserve = candidate("3", high, "100.00000000000000000000000000001")
        same_metrics_later_id = candidate("4", high, "100.00000000000000000000000000001")
        selected = fetch.select_pool([lower_id, greater_volume], "bsc", ADDRESS)
        self.assertEqual(selected["id"], greater_volume["id"])
        selected = fetch.select_pool([same_metrics_later_id, lower_id, greater_volume, greater_reserve], "bsc", ADDRESS)
        self.assertEqual(selected["id"], greater_reserve["id"])


if __name__ == "__main__":
    unittest.main()
