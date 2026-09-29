"""Offline transport invariants, including actual HTTPResponse stream behavior."""

import hashlib
import http.client
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from email.utils import format_datetime
from unittest.mock import patch
from urllib.error import HTTPError, URLError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from defillama_lib.client import Client, FetchError, MAX_BYTES

URL = "https://api.llama.fi/protocol/polymarket-international"
NOW = 1790640000.0


class Socket:
    def __init__(self, wire):
        self.wire = wire

    def makefile(self, mode):
        return io.BytesIO(self.wire)


def response(body=b'{"value":0}', status=200, headers=None):
    fields = {"Date": "Tue, 29 Sep 2026 00:00:00 GMT", **(headers or {})}
    wire = ("HTTP/1.1 " + str(status) + " Test\r\n" + "".join(k + ": " + str(v) + "\r\n" for k, v in fields.items()) + "\r\n").encode() + body
    result = http.client.HTTPResponse(Socket(wire))
    result.begin()
    return result


class Opener:
    def __init__(self, *items):
        self.items = list(items)
        self.requests = []

    def open(self, request, timeout):
        self.requests.append((request.full_url, request.get_method(), timeout))
        item = self.items.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class ClientTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.sleeps = []

    def client(self, *items, **kwargs):
        opener = Opener(*items)
        result = Client(cache_dir=self.directory.name, clock=lambda: NOW, sleep=self.sleeps.append, opener=opener, **kwargs)
        return result, opener

    def assert_error(self, code, client, url=URL):
        with self.assertRaises(FetchError) as raised:
            client.get(url)
        self.assertEqual(code, raised.exception.code)
        self.assertEqual(code, raised.exception.as_dict()["code"])
        return raised.exception

    def test_valid_json_provenance_and_cache_preserve_original_fetch_time(self):
        client, opener = self.client(response())
        first = client.get(URL)
        client.clock = lambda: NOW + 200
        second = client.get(URL)
        self.assertEqual({"value": 0}, first["data"])
        self.assertEqual(first["source"]["fetched_at"], second["source"]["fetched_at"])
        self.assertFalse(first["source"]["cached"])
        self.assertTrue(second["source"]["cached"])
        self.assertEqual([(URL, "GET", 25)], opener.requests)
        self.assertEqual(hashlib.sha256(URL.encode()).hexdigest(), first["source"]["id"])

    def test_expired_cache_never_masks_fresh_request_failure(self):
        client, opener = self.client(response(), URLError("offline"), URLError("offline"))
        client.get(URL)
        client.clock = lambda: NOW + 300
        self.assert_error("network_error", client)
        self.assertEqual(3, len(opener.requests))
        self.assertEqual([1.0], self.sleeps)

    def test_refresh_and_no_cache_bypass_stored_data(self):
        client, _ = self.client(response())
        client.get(URL)
        refreshed, _ = self.client(response(b'{"value":2}'), refresh=True)
        self.assertEqual(2, refreshed.get(URL)["data"]["value"])
        uncached, _ = self.client(response(b'{"value":3}'), no_cache=True)
        self.assertEqual(3, uncached.get(URL)["data"]["value"])
        reader, _ = self.client()
        self.assertEqual(2, reader.get(URL)["data"]["value"])

    def test_corrupt_wrong_url_future_and_wrong_shape_cache_are_ignored(self):
        path = Path(self.directory.name) / (hashlib.sha256(URL.encode()).hexdigest() + ".json")
        for mutation in ("corrupt", "wrong_url", "future", "bad_shape", "nonfinite"):
            with self.subTest(mutation=mutation):
                client, _ = self.client(response())
                client.refresh = True
                result = client.get(URL)
                if mutation == "corrupt":
                    path.write_text("{")
                else:
                    if mutation == "wrong_url":
                        result["source"]["url"] += "?unexpected=1"
                    elif mutation == "future":
                        result["source"]["fetched_at"] = "2099-01-01T00:00:00Z"
                    elif mutation == "bad_shape":
                        result = {"data": 1, "source": []}
                    else:
                        result["data"] = float("nan")
                    path.write_text(json.dumps(result))
                reader, opener = self.client(response(b'{"fresh":true}'))
                self.assertEqual({"fresh": True}, reader.get(URL)["data"])
                self.assertEqual(1, len(opener.requests))

    def test_cache_write_failure_does_not_lose_success(self):
        client, _ = self.client(response())
        with patch("defillama_lib.client.os.replace", side_effect=OSError("read only")):
            self.assertEqual({"value": 0}, client.get(URL)["data"])
        self.assertEqual([], list(Path(self.directory.name).iterdir()))

    def test_host_scheme_credentials_and_port_validation_precede_io(self):
        bad = ["http://api.llama.fi/protocols", "https://api.llama.fi.evil.test/x", "https://evil.test/", "https://x:secret@api.llama.fi/x", "https://api.llama.fi:80/x", "https://api.llama.fi/x#fragment", "https://api.llama.fi/\nfoo", "https://api.llama.fi\\@evil.test/"]
        for url in bad:
            client, opener = self.client()
            self.assert_error("invalid_url", client, url)
            self.assertFalse(opener.requests)

    def test_redirect_follows_allowlisted_hosts_keeps_requested_provenance(self):
        client, opener = self.client(response(status=302, headers={"Location": "https://coins.llama.fi/prices/current/coingecko:ethereum"}), response())
        result = client.get(URL)
        self.assertEqual(URL, result["source"]["url"])
        self.assertEqual("https://coins.llama.fi/prices/current/coingecko:ethereum", opener.requests[1][0])

    def test_redirect_rejects_external_host_without_fetching_it(self):
        client, opener = self.client(response(status=302, headers={"Location": "https://evil.test/x"}))
        self.assert_error("invalid_url", client)
        self.assertEqual(1, len(opener.requests))

    def test_five_redirects_allowed_but_sixth_and_loop_fail(self):
        client, opener = self.client(*(response(status=302, headers={"Location": "/next"}) for _ in range(5)), response())
        self.assertEqual({"value": 0}, client.get(URL)["data"])
        self.assertEqual(6, len(opener.requests))
        client, opener = self.client(*(response(status=302, headers={"Location": URL}) for _ in range(6)), no_cache=True)
        self.assert_error("redirect_error", client)
        self.assertEqual(6, len(opener.requests))

    def test_http_error_object_can_be_followed_and_is_closed(self):
        body = io.BytesIO(b"redirect")
        error = HTTPError(URL, 302, "redirect", {"Location": "/next"}, body)
        client, _ = self.client(error, response())
        client.get(URL)
        self.assertTrue(body.closed)

    def test_429_retry_after_seconds_and_date(self):
        for retry_after in ("3", format_datetime(datetime.fromtimestamp(NOW + 3, timezone.utc), usegmt=True)):
            with self.subTest(retry_after=retry_after):
                client, opener = self.client(response(status=429, headers={"Retry-After": retry_after}), response(), no_cache=True)
                self.assertEqual({"value": 0}, client.get(URL)["data"])
                self.assertEqual(2, len(opener.requests))
                self.assertEqual(3, self.sleeps[-1])

    def test_retry_after_over_limit_does_not_sleep_or_retry(self):
        client, opener = self.client(response(status=429, headers={"Retry-After": "31"}))
        self.assert_error("rate_limited", client)
        self.assertEqual([], self.sleeps)
        self.assertEqual(1, len(opener.requests))

    def test_network_and_5xx_retry_only_twice(self):
        for failure in (lambda: URLError("temporary"), lambda: response(status=503)):
            client, opener = self.client(failure(), failure(), no_cache=True)
            with self.assertRaises(FetchError):
                client.get(URL)
            self.assertEqual(2, len(opener.requests))

    def test_404_and_invalid_json_never_retry(self):
        for item, code in ((response(status=404), "http_error"), (response(b"not json"), "invalid_json"), (response(b'{"n":NaN}'), "invalid_json"), (response(b'{"n":1e999}'), "invalid_json")):
            client, opener = self.client(item, no_cache=True)
            self.assert_error(code, client)
            self.assertEqual(1, len(opener.requests))

    def test_oversize_actual_stream_is_bounded_without_content_length(self):
        stream = response(b" " * (MAX_BYTES + 1))
        client, opener = self.client(stream)
        self.assert_error("response_too_large", client)
        self.assertTrue(stream.isclosed())
        self.assertEqual(1, len(opener.requests))

    def test_truncated_actual_httpresponse_does_not_become_valid_json(self):
        # Body is valid JSON but shorter than the server's promised response.
        client, opener = self.client(response(b"{}", headers={"Content-Length": "20"}), response(b"{}", headers={"Content-Length": "20"}))
        self.assert_error("truncated_response", client)
        self.assertEqual(2, len(opener.requests))

    def test_truncated_chunked_stream_is_network_failure(self):
        client, opener = self.client(response(b"9\r\n{}", headers={"Transfer-Encoding": "chunked"}), response(b"9\r\n{}", headers={"Transfer-Encoding": "chunked"}))
        self.assert_error("network_error", client)
        self.assertEqual(2, len(opener.requests))

    def test_slow_continuous_chunks_cannot_evade_elapsed_deadline(self):
        clock = [0.0]

        class SlowStream:
            headers = {}
            closed = False
            def getcode(self):
                return 200
            def read1(self, size):
                clock[0] += 20
                return b" "  # Always receives data before a 25-second socket timeout.
            def close(self):
                self.closed = True

        streams = [SlowStream(), SlowStream()]
        client, opener = self.client(*streams, monotonic=lambda: clock[0])
        self.assert_error("read_timeout", client)
        self.assertEqual(120, clock[0])
        self.assertTrue(all(stream.closed for stream in streams))
        self.assertEqual(2, len(opener.requests))


if __name__ == "__main__":
    unittest.main()
