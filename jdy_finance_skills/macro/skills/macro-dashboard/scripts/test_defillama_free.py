"""Offline regression checks for financial semantics and network failures."""
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

import defillama_free as dl


class Response(io.BytesIO):
    status = 200
    headers = {"Date": "Wed, 30 Sep 2026 00:00:00 GMT"}


class DataTests(unittest.TestCase):
    def test_calendar_baselines_and_missing_days(self):
        day = 20000 * dl.DAY
        points = [(day - 30 * dl.DAY, 50), (day - 7 * dl.DAY, 100), (day, 110)]
        result = dl.series_summary(points, now=day + 60)
        self.assertAlmostEqual(result["changes"]["7d"]["pct"], 10)
        self.assertAlmostEqual(result["changes"]["30d"]["pct"], 120)
        self.assertIsNone(result["changes"]["1d"]["pct"])
        self.assertEqual(result["value"], 110)  # not summed across dates

    def test_missing_latest_does_not_become_old_value(self):
        with self.assertRaises(ValueError):
            dl.series_summary([(100000, 123), (200000, None)], now=200001)
        self.assertIsNone(dl.percent(123, 0))
        self.assertEqual(dl.percent(0, 123), -100)

    def test_stablecoins_use_usd_not_mixed_units(self):
        row = {"totalCirculating": {"peggedUSD": 100, "peggedJPY": 15000},
               "totalCirculatingUSD": {"peggedUSD": 99, "peggedJPY": 100}}
        self.assertEqual(dl.usd_total(row), 199)
        self.assertIsNone(dl.usd_total({"totalCirculating": {"peggedUSD": 100}}))
        self.assertIsNone(dl.usd_total({"totalCirculatingUSD": {"peggedUSD": None}}))

    def test_flow_total_is_separate_from_chart_and_missing_baseline(self):
        result = dl.flow_summary({"total24h": 80, "total7d": 700,
                                  "total14dto7d": 350, "totalDataChart": [[200000, 95]]})
        self.assertEqual(result["total24h"], 80)
        self.assertEqual(result["latest_chart_bucket"]["value"], 95)
        self.assertIsNone(result["totals_observed_at"])
        self.assertEqual(result["period_changes_pct"]["7d_vs_previous_7d"], 100)
        self.assertIsNone(result["period_changes_pct"]["1d_vs_previous_1d"])

    def test_stale_and_future_observations(self):
        self.assertTrue(dl.series_summary([(200000, 10)], now=500000)["stale_over_48h"])
        with self.assertRaises(ValueError):
            dl.series_summary([(500000, 10)], now=200000)

    def test_partial_failure_preserves_other_results(self):
        class FakeClient:
            def get(self, url):
                if "stablecoins" in url:
                    raise URLError("unavailable")
                if "historical" in url:
                    return [{"date": 1700000000, "tvl": 100}], {"url": url}
                return {"total24h": 80}, {"url": url}
        result = dl.run(SimpleNamespace(command="dashboard"), FakeClient())["results"]
        self.assertEqual(result["defi_tvl"]["status"], "ok")
        self.assertEqual(result["stablecoin_market_cap"]["status"], "unavailable")
        self.assertEqual(result["dex_volume"]["status"], "ok")

    def test_wrong_response_shape_is_unavailable(self):
        class FakeClient:
            def get(self, url):
                return [], {"url": url}
        result = dl.run(SimpleNamespace(command="fees", protocol="aave"), FakeClient())
        self.assertEqual(result["results"]["fees"]["status"], "unavailable")


class ClientTests(unittest.TestCase):
    def test_cache_preserves_fetch_time(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(dl, "urlopen", return_value=Response(b'{"value": 1}')) as net:
            client = dl.Client(cache=tmp)
            _, first = client.get(dl.API + "/test")
            _, second = client.get(dl.API + "/test")
            self.assertEqual(net.call_count, 1)
            self.assertEqual(first["fetched_at"], second["fetched_at"])
            self.assertTrue(second["cached"])

    def test_expired_cache_cannot_hide_network_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            client = dl.Client(cache=tmp)
            with patch.object(dl, "urlopen", return_value=Response(b'{"value": 1}')):
                client.get(dl.API + "/test")
            path = next(Path(tmp).glob("*.json"))
            cached = json.loads(path.read_text()); cached["fetched_ts"] -= 301
            path.write_text(json.dumps(cached))
            with patch.object(dl, "urlopen", side_effect=URLError("offline")) as net, patch.object(dl.time, "sleep"):
                with self.assertRaises(URLError):
                    client.get(dl.API + "/test")
                self.assertEqual(net.call_count, 2)

    def test_rate_limit_retry_is_bounded(self):
        error = HTTPError(dl.API, 429, "rate limited", {"Retry-After": "2"}, None)
        with tempfile.TemporaryDirectory() as tmp, patch.object(dl, "urlopen", side_effect=[error, Response(b'[]')]) as net, patch.object(dl.time, "sleep") as sleep:
            dl.Client(cache=tmp).get(dl.API + "/test")
            self.assertEqual(net.call_count, 2)
            sleep.assert_called_once_with(2)

    def test_long_retry_after_stops(self):
        error = HTTPError(dl.API, 429, "rate limited", {"Retry-After": "120"}, None)
        with tempfile.TemporaryDirectory() as tmp, patch.object(dl, "urlopen", side_effect=error) as net, patch.object(dl.time, "sleep") as sleep:
            with self.assertRaises(RuntimeError):
                dl.Client(cache=tmp).get(dl.API + "/test")
            self.assertEqual(net.call_count, 1)
            sleep.assert_not_called()

    def test_not_found_and_invalid_json_do_not_retry(self):
        for response in [HTTPError(dl.API, 404, "missing", {}, None), Response(b'<html>unavailable</html>')]:
            with tempfile.TemporaryDirectory() as tmp, patch.object(dl, "urlopen") as net:
                if isinstance(response, Exception):
                    net.side_effect = response
                else:
                    net.return_value = response
                with self.assertRaises((HTTPError, ValueError)):
                    dl.Client(cache=tmp).get(dl.API + "/test")
                self.assertEqual(net.call_count, 1)


if __name__ == "__main__":
    unittest.main()
