"""Fixed-host, bounded, evidence-preserving public/Demo REST client (stdlib)."""
from __future__ import annotations

import datetime as dt
import email.utils
import fcntl
import hashlib
import json
import math
import multiprocessing as mp
import os
from pathlib import Path
import re
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

ROOTS = {"geckoterminal": "https://api.geckoterminal.com/api/v2",
         "coingecko-demo": "https://api.coingecko.com/api/v3"}
MAX_BODY = 8 * 1024 * 1024

# Rule strings are also exposed by `capabilities`; unknown parameters fail closed.
GT = {
    "networks": ("/networks", {"page": "page"}),
    "dexes": ("/networks/{network}/dexes", {"page": "page"}),
    "search_pools": ("/search/pools", {"query": "text", "network": "id", "include": "include", "page": "page"}),
    "token": ("/networks/{network}/tokens/{address}", {"include": "include"}),
    "token_info": ("/networks/{network}/tokens/{address}/info", {}),
    "token_pools": ("/networks/{network}/tokens/{address}/pools", {"include": "include", "page": "page", "sort": "enum:h24_volume_usd_desc,h24_tx_count_desc,h24_volume_usd_liquidity_desc"}),
    "pool": ("/networks/{network}/pools/{pool}", {"include": "include"}),
    "pool_ohlcv": ("/networks/{network}/pools/{pool}/ohlcv/{timeframe}", {"aggregate": "aggregate", "before_timestamp": "timestamp", "limit": "limit1000", "currency": "enum:usd,token", "token": "perspective", "include_empty_intervals": "bool"}),
    "pool_trades": ("/networks/{network}/pools/{pool}/trades", {"trade_volume_in_usd_greater_than": "nonnegative", "token": "perspective"}),
    "trending_pools": ("/networks/{network}/trending_pools", {"include": "include", "page": "page", "duration": "enum:5m,1h,6h,24h"}),
    "new_pools": ("/networks/{network}/new_pools", {"include": "include", "page": "page"}),
}
CG = {
    "search": ("/search", {"query": "text"}),
    "coin": ("/coins/{id}", {"localization": "bool", "tickers": "bool", "market_data": "bool", "community_data": "bool", "developer_data": "bool", "sparkline": "bool"}),
    "markets": ("/coins/markets", {"vs_currency": "id", "ids": "ids", "category": "id", "order": "enum:market_cap_asc,market_cap_desc,volume_asc,volume_desc,id_asc,id_desc", "per_page": "limit250", "page": "page", "sparkline": "bool", "price_change_percentage": "enumlist:1h,24h,7d,14d,30d,200d,1y"}),
    "tickers": ("/coins/{id}/tickers", {"page": "page", "order": "enum:trust_score_desc,trust_score_asc,volume_desc,volume_asc", "depth": "bool"}),
    "market_chart": ("/coins/{id}/market_chart", {"vs_currency": "id", "days": "days"}),
    "global": ("/global", {}),
    "categories": ("/coins/categories", {"order": "enum:market_cap_desc,market_cap_asc,name_desc,name_asc,market_cap_change_24h_desc,market_cap_change_24h_asc"}),
    "trending": ("/search/trending", {}),
}
CATALOG = {"geckoterminal": GT, "coingecko-demo": CG}


def finite_float(value):
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("nonfinite JSON number")
    return number


def decode_json(value):
    return json.loads(value, parse_float=finite_float,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError("invalid JSON number")))


def utc(timestamp=None):
    return dt.datetime.fromtimestamp(time.time() if timestamp is None else timestamp, dt.timezone.utc).isoformat().replace("+00:00", "Z")


def clean(value, rule):
    value = str(value)
    if not value or len(value) > 512 or any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise ValueError("invalid parameter value")
    if rule == "text":
        valid = len(value) <= 100
    elif rule in ("id", "address", "pool"):
        valid = bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}", value))
    elif rule == "perspective":
        return clean(value, "address")
    elif rule == "timeframe":
        valid = value in ("minute", "hour", "day")
    elif rule.startswith("enum:"):
        valid = value in rule[5:].split(",")
    elif rule.startswith("enumlist:"):
        valid = all(x in rule[9:].split(",") for x in value.split(","))
    elif rule == "include":
        valid = all(x in ("base_token", "quote_token", "dex", "top_pools") for x in value.split(","))
    elif rule == "ids":
        valid = len(value.split(",")) <= 50 and all(re.fullmatch(r"[A-Za-z0-9_-]+", x) for x in value.split(","))
    elif rule == "bool":
        valid = value in ("true", "false")
    elif rule == "nonnegative":
        try:
            number = float(value)
            valid = math.isfinite(number) and 0 <= number <= 1e15
        except ValueError:
            valid = False
    else:
        bounds = {"page": (1, 10), "limit1000": (1, 1000), "limit250": (1, 250), "days": (1, 365), "aggregate": (1, 15), "timestamp": (1230768000, int(time.time()) + 86400)}
        low, high = bounds[rule]
        valid = value.isascii() and value.isdigit() and low <= int(value) <= high
    if not valid:
        raise ValueError("invalid parameter value")
    return value


def build_request(provider, endpoint, params):
    if provider not in CATALOG or endpoint not in CATALOG[provider]:
        raise ValueError("unknown provider or endpoint")
    template, rules = CATALOG[provider][endpoint]
    path_keys = re.findall(r"\{(\w+)\}", template)
    if set(params) - (set(rules) | set(path_keys)):
        raise ValueError("unknown or unsupported parameter")
    if any(key not in params for key in path_keys):
        raise ValueError("missing path parameter")
    required = {"search_pools": ["query"], "search": ["query"], "markets": ["vs_currency"], "market_chart": ["vs_currency", "days"]}.get(endpoint, [])
    if any(key not in params for key in required):
        raise ValueError("missing query parameter")
    parts = {key: clean(params[key], "timeframe" if key == "timeframe" else "id") for key in path_keys}
    query = {key: clean(value, rules[key]) for key, value in params.items() if key not in path_keys}
    if endpoint == "pool_ohlcv":
        aggregate = query.get("aggregate", "1")
        if aggregate not in {"minute": ("1", "5", "15"), "hour": ("1", "4", "12"), "day": ("1",)}[parts["timeframe"]]:
            raise ValueError("unsupported OHLCV aggregate")
    if "include" in query:
        allowed = {"top_pools"} if endpoint == "token" else {"base_token", "quote_token", "dex"}
        if not set(query["include"].split(",")) <= allowed:
            raise ValueError("unsupported include")
    path = template.format(**{key: urllib.parse.quote(value, safe="") for key, value in parts.items()})
    url = ROOTS[provider] + path
    if query:
        url += "?" + urllib.parse.urlencode(sorted(query.items()))
    return path, query, url


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _network_worker(connection, url, headers, timeout):
    """Only child does DNS/read; parent enforces a wall-clock process deadline."""
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
        try:
            response = opener.open(urllib.request.Request(url, headers=headers), timeout=timeout)
        except urllib.error.HTTPError as exc:
            try:
                connection.send({"http_status": exc.code, "retry_after": exc.headers.get("Retry-After"), "provider_date": exc.headers.get("Date")})
            finally:
                exc.close()
            return
        with response:
            body = response.read(MAX_BODY + 1)
            if len(body) > MAX_BODY:
                connection.send({"error": "body_too_large"})
                return
            connection.send({"http_status": response.status, "provider_date": response.headers.get("Date"), "body": body})
    except (TimeoutError, OSError, urllib.error.URLError):
        connection.send({"error": "transport_error"})
    except Exception:
        connection.send({"error": "invalid_response"})
    finally:
        connection.close()


def transport(url, headers, timeout):
    context = mp.get_context("spawn")
    receiver, sender = context.Pipe(duplex=False)
    worker = context.Process(target=_network_worker, args=(sender, url, headers, timeout), daemon=True)
    started = time.monotonic()
    worker.start()
    sender.close()
    try:
        if receiver.poll(max(0, timeout - (time.monotonic() - started))):
            try:
                return receiver.recv()
            except EOFError:
                return {"error": "transport_error"}
        return {"error": "timeout"}
    finally:
        receiver.close()
        if worker.is_alive():
            worker.terminate()
        worker.join(timeout=0.2)
        if worker.is_alive():
            worker.kill()
            worker.join(timeout=0.2)


def write_new(path, data):
    """Exclusive creation ensures evidence is never overwritten."""
    with Path(path).open("x", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write("\n")


def _atomic(path, data):
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix=".state-")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(data, handle, allow_nan=False)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


class Client:
    def __init__(self, cache_dir=None, *, cache=True, deadline=180, max_attempts=12, gt_per_minute=5, demo_per_minute=30, send=None):
        if not 0 < deadline <= 180 or not 1 <= max_attempts <= 12:
            raise ValueError("invalid run budget")
        if not 0 < gt_per_minute <= 5 or not 0 < demo_per_minute <= 30:
            raise ValueError("invalid pacing budget")
        self.cache_dir = Path(cache_dir or Path.home() / ".cache" / "crypto-project-research")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache = cache
        self.started = time.monotonic()
        self.deadline = self.started + deadline
        self.max_attempts = max_attempts
        self.used = 0
        self.intervals = {"geckoterminal": 60 / gt_per_minute, "coingecko-demo": 60 / demo_per_minute}
        self.send = send or transport

    def remaining(self):
        return max(0, self.deadline - time.monotonic())

    def _pace(self, provider, not_before=None):
        """Reserve under lock; sleep unlocked so concurrent 429s can extend it."""
        lock_path = self.cache_dir / (provider + ".lock")
        state_path = self.cache_dir / (provider + ".rate.json")
        with lock_path.open("a") as handle:
            while True:
                if self.remaining() <= 0:
                    raise TimeoutError
                try:
                    fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    time.sleep(min(0.05, self.remaining()))
                    continue
                try:
                    next_at = 0.0
                    if state_path.exists():
                        state = decode_json(state_path.read_text())
                        next_at = state["next_at"]
                        if isinstance(next_at, bool) or not isinstance(next_at, (float, int)) or not math.isfinite(next_at) or next_at < 0:
                            raise ValueError("invalid pacing state")
                    if not_before is not None:
                        _atomic(state_path, {"next_at": max(next_at, not_before)})
                        return
                    wait = max(0, next_at - time.time())
                    if wait >= self.remaining():
                        raise TimeoutError
                    if not wait:
                        _atomic(state_path, {"next_at": time.time() + self.intervals[provider]})
                        return
                finally:
                    fcntl.flock(handle, fcntl.LOCK_UN)
                time.sleep(wait)
                # A different process may have extended next_at while asleep.
                # Reacquire and reread it before granting a request reservation.

    def request(self, provider, endpoint, **params):
        path, query, url = build_request(provider, endpoint, params)
        envelope = {"schema_version": 1, "request_id": str(uuid.uuid4()), "provider": provider, "endpoint": endpoint,
                    "request": {"path": path, "params": query}, "source_url": url, "fetched_at": utc(), "provider_date": None,
                    "cache_hit": False, "expires_at": None, "status": "budget_exhausted", "http_status": None, "attempts": 0}
        headers = {"Accept": "application/json;version=20230203" if provider == "geckoterminal" else "application/json", "User-Agent": "crypto-project-research/1"}
        if provider == "coingecko-demo":
            key = os.environ.get("COINGECKO_DEMO_API_KEY")
            if not key:
                envelope.update(status="missing_credential", error={"code": "missing_demo_env"})
                return envelope
            headers["x-cg-demo-api-key"] = key
        fingerprint = hashlib.sha256(json.dumps([1, provider, path, sorted(query.items())]).encode()).hexdigest()
        cache_path = self.cache_dir / (fingerprint + ".json")
        cacheable = self.cache and provider == "geckoterminal"
        if cacheable and cache_path.exists():
            try:
                saved = decode_json(cache_path.read_text())
                expiry = dt.datetime.fromisoformat(saved["expires_at"].replace("Z", "+00:00")).timestamp()
                if saved.get("status") == "ok" and saved.get("source_url") == url and expiry > time.time():
                    saved.update(cache_hit=True, attempts=0, request_id=envelope["request_id"])
                    return saved
            except (ValueError, TypeError, KeyError, OSError):
                pass
        for attempt in range(3):
            if self.used >= self.max_attempts or self.remaining() <= 0:
                envelope.update(status="budget_exhausted", error={"code": "run_budget"})
                break
            try:
                self._pace(provider)
            except TimeoutError:
                envelope.update(status="budget_exhausted", error={"code": "pacing_deadline"})
                break
            except (OSError, ValueError, KeyError, TypeError):
                envelope.update(status="invalid_response", error={"code": "invalid_pacing_state"})
                break
            self.used += 1
            envelope["attempts"] += 1
            try:
                result = self.send(url, headers, min(20, self.remaining()))
            except (OSError, RuntimeError):
                result = {"error": "transport_error"}
            envelope.update(fetched_at=utc(), provider_date=result.get("provider_date"), http_status=result.get("http_status"))
            code = result.get("http_status")
            transient = False
            if "error" in result:
                transient = result["error"] in ("timeout", "transport_error")
                envelope.update(status="timeout" if transient else "invalid_response", error={"code": result["error"]})
            elif code == 200:
                try:
                    body = result.get("body", b"")
                    if len(body) > MAX_BODY:
                        raise ValueError
                    data = decode_json(body)
                    if not isinstance(data, (dict, list)) or (isinstance(data, dict) and ("error" in data or "errors" in data or (isinstance(data.get("status"), dict) and data["status"].get("error_code")))):
                        raise ValueError
                    if provider == "geckoterminal" and (not isinstance(data, dict) or "data" not in data):
                        raise ValueError
                except (ValueError, TypeError, UnicodeError):
                    envelope.update(status="invalid_response", error={"code": "json_or_provider_error"})
                    break
                ttl = 3600 if endpoint in ("networks", "dexes") else 60
                envelope.update(status="ok", data=data, expires_at=utc(time.time() + ttl) if cacheable else None)
                envelope.pop("error", None)
                if cacheable:
                    try:
                        _atomic(cache_path, envelope)
                    except OSError:
                        envelope["warnings"] = ["cache_write_failed"]
                break
            else:
                transient = code == 429 or (isinstance(code, int) and 500 <= code <= 599)
                envelope.update(status="rate_limited" if code == 429 else "http_error", error={"code": "http_status"})
            if not transient:
                break
            wait = 2 ** attempt
            retry_after = result.get("retry_after")
            if retry_after:
                try:
                    wait = float(retry_after)
                except (ValueError, TypeError):
                    try:
                        wait = email.utils.parsedate_to_datetime(retry_after).timestamp() - time.time()
                    except (ValueError, TypeError, OverflowError):
                        wait = 2 ** attempt
                if not math.isfinite(wait):
                    wait = self.remaining()
                wait = max(0, wait)
                envelope["error"]["retry_after_seconds"] = min(wait, 86400)
            if code == 429:
                try:
                    self._pace(provider, not_before=time.time() + wait)
                except (OSError, ValueError, KeyError, TypeError, TimeoutError):
                    envelope["error"]["pacing_state"] = "could_not_persist_backoff"
                    # Stop this client after a failed shared-state update.
                    self.deadline = time.monotonic()
                    break
            if attempt == 2 or self.used >= self.max_attempts or wait >= self.remaining():
                break
            time.sleep(wait)
        return envelope
