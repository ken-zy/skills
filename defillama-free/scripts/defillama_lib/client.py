"""Bounded, unauthenticated access to DefiLlama's public JSON APIs."""

from __future__ import annotations

import hashlib
import http.client
import json
import math
import os
from pathlib import Path
import tempfile
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

ALLOWED_HOSTS = frozenset({"api.llama.fi", "stablecoins.llama.fi", "yields.llama.fi", "coins.llama.fi"})
MAX_BYTES = 32 * 1024 * 1024
SOCKET_TIMEOUT = 25
READ_DEADLINE = 60
MAX_REDIRECTS = 5
CACHE_SECONDS = 300
CHUNK_BYTES = 64 * 1024


class FetchError(Exception):
    """A transport failure safe to include in a per-source result."""

    def __init__(self, code: str, message: str, url: str):
        super().__init__(message)
        self.code, self.message, self.url = code, message, url

    def as_dict(self) -> dict:
        return {"code": self.code, "message": self.message, "url": self.url}


class _Retryable(FetchError):
    def __init__(self, code, message, url, delay=1.0):
        super().__init__(code, message, url)
        self.delay = delay


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _validate_url(url: str) -> None:
    try:
        parsed = urlsplit(url)
        valid = (
            isinstance(url, str)
            and not any(ord(c) <= 32 or ord(c) == 127 for c in url)
            and parsed.scheme == "https"
            and parsed.hostname in ALLOWED_HOSTS
            and parsed.port in (None, 443)
            and parsed.username is None
            and parsed.password is None
            and not parsed.fragment
            and "\\" not in url
        )
    except (ValueError, TypeError, AttributeError):
        valid = False
    if not valid:
        raise FetchError("invalid_url", "Only HTTPS URLs on the four public DefiLlama API hosts are allowed", str(url))


def _reject_constant(value):
    raise ValueError("Non-finite JSON constant: " + value)


def _finite_float(value):
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("Non-finite JSON number")
    return number


def _load_json(body):
    return json.loads(body, parse_constant=_reject_constant, parse_float=_finite_float)


def _iso_time(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, timezone.utc).isoformat().replace("+00:00", "Z")


class Client:
    """GET-only client. Socket timeout is not an absolute DNS/process deadline.

    ``opener``, clocks, and sleep are dependency-injection hooks for offline tests.
    A read deadline is checked between read1 chunks, including after each read.
    """

    def __init__(self, cache_dir=None, refresh=False, no_cache=False, *,
                 opener=None, clock=None, monotonic=None, sleep=None):
        uid = str(os.getuid()) if hasattr(os, "getuid") else "user"
        self.cache_dir = Path(cache_dir) if cache_dir is not None else Path(tempfile.gettempdir()) / ("defillama-free-" + uid) / "cache"
        self.refresh, self.no_cache = refresh, no_cache
        self.opener = opener if opener is not None else build_opener(_NoRedirect())
        self.clock = clock if clock is not None else time.time
        self.monotonic = monotonic if monotonic is not None else time.monotonic
        self.sleep = sleep if sleep is not None else time.sleep

    def get(self, url: str) -> dict:
        _validate_url(url)
        source_id = hashlib.sha256(url.encode("utf-8")).hexdigest()
        if not self.no_cache and not self.refresh:
            cached = self._read_cache(url, source_id)
            if cached is not None:
                return cached
        for attempt in range(2):
            try:
                data, http_date = self._fetch(url)
                result = {"data": data, "source": {
                    "id": source_id, "url": url, "fetched_at": _iso_time(self.clock()),
                    "http_date": http_date, "cached": False,
                }}
                if not self.no_cache:
                    self._write_cache(source_id, result)
                return result
            except _Retryable as exc:
                if attempt == 1:
                    raise FetchError(exc.code, exc.message, exc.url) from exc
                self.sleep(exc.delay)
        raise AssertionError("unreachable")

    def _retry_delay(self, header, url, status):
        if header is None:
            return 1.0
        try:
            delay = float(header)
            if not math.isfinite(delay):
                raise ValueError("nonfinite Retry-After")
        except (TypeError, ValueError):
            try:
                date = parsedate_to_datetime(header)
                if date.tzinfo is None:
                    raise ValueError("ambiguous HTTP date")
                delay = date.timestamp() - self.clock()
            except (TypeError, ValueError, OverflowError):
                return 1.0
        if delay > 30:
            raise FetchError("rate_limited" if status == 429 else "retry_wait_exceeded",
                             "Retry-After exceeds the 30-second wait limit", url)
        return max(0.0, delay)

    def _fetch(self, original_url):
        current_url = original_url
        for redirects in range(MAX_REDIRECTS + 1):
            _validate_url(current_url)
            response = None
            try:
                request = Request(current_url, headers={"Accept": "application/json", "User-Agent": "defillama-free/1"}, method="GET")
                try:
                    response = self.opener.open(request, timeout=SOCKET_TIMEOUT)
                except HTTPError as exc:
                    response = exc
                status = response.getcode()
                if status in (301, 302, 303, 307, 308):
                    location = response.headers.get("Location")
                    if not location or redirects == MAX_REDIRECTS:
                        raise FetchError("redirect_error", "Missing redirect location or maximum of five redirects exceeded", original_url)
                    current_url = urljoin(current_url, location)
                    _validate_url(current_url)
                    continue
                if status == 429 or 500 <= status <= 599:
                    delay = self._retry_delay(response.headers.get("Retry-After"), original_url, status)
                    raise _Retryable("rate_limited" if status == 429 else "http_error", "HTTP " + str(status), original_url, delay)
                if not 200 <= status < 300:
                    raise FetchError("http_error", "HTTP " + str(status), original_url)
                body = self._read_body(response, original_url)
                try:
                    payload = _load_json(body)
                except (ValueError, UnicodeError, RecursionError) as exc:
                    raise FetchError("invalid_json", "Response is not valid finite JSON", original_url) from exc
                return payload, response.headers.get("Date")
            except (URLError, OSError, http.client.HTTPException) as exc:
                raise _Retryable("network_error", "Request failed: " + type(exc).__name__, original_url) from exc
            finally:
                if response is not None:
                    response.close()
        raise AssertionError("unreachable")

    def _read_body(self, response, url):
        started = self.monotonic()
        parts, total = [], 0
        while True:
            if self.monotonic() - started >= READ_DEADLINE:
                raise _Retryable("read_timeout", "Response reading exceeded the 60-second deadline", url)
            chunk = response.read1(min(CHUNK_BYTES, MAX_BYTES - total + 1))
            if self.monotonic() - started >= READ_DEADLINE:
                raise _Retryable("read_timeout", "Response reading exceeded the 60-second deadline", url)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_BYTES:
                raise FetchError("response_too_large", "Response exceeds the 32 MiB byte limit", url)
            parts.append(chunk)
        length = response.headers.get("Content-Length")
        # HTTPResponse.read1 may finish without raising IncompleteRead, unlike read().
        if length is not None and not response.headers.get("Transfer-Encoding"):
            try:
                declared = int(length)
            except (ValueError, TypeError):
                declared = -1
            if declared >= 0 and total < declared:
                raise _Retryable("truncated_response", "Response ended before its declared Content-Length", url)
        return b"".join(parts)

    def _read_cache(self, url, source_id):
        try:
            path = self.cache_dir / (source_id + ".json")
            with path.open("rb") as handle:
                raw = handle.read(MAX_BYTES * 2 + 1)
            if len(raw) > MAX_BYTES * 2:
                return None
            item = _load_json(raw)
            source = item["source"]
            if (set(item) != {"data", "source"} or source["id"] != source_id
                    or source["url"] != url or source["cached"] is not False
                    or not isinstance(source["fetched_at"], str)
                    or not (source["http_date"] is None or isinstance(source["http_date"], str))):
                return None
            fetched = datetime.fromisoformat(source["fetched_at"].replace("Z", "+00:00"))
            if fetched.tzinfo is None or fetched.utcoffset().total_seconds() != 0:
                return None
            if not 0 <= self.clock() - fetched.timestamp() < CACHE_SECONDS:
                return None
            source["cached"] = True
            return item
        except (OSError, ValueError, TypeError, KeyError, AttributeError, OverflowError, RecursionError):
            return None

    def _write_cache(self, source_id, result):
        temporary = None
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.cache_dir, prefix=".fetch-", delete=False) as handle:
                temporary = Path(handle.name)
                json.dump(result, handle, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
            os.replace(temporary, self.cache_dir / (source_id + ".json"))
        except (OSError, ValueError, TypeError, RecursionError):
            pass
        finally:
            if temporary is not None:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    pass
