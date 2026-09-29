#!/usr/bin/env python3
"""Small, keyless DefiLlama reader. Python standard library only."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import socket
import tempfile
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

API = "https://api.llama.fi"
STABLE = "https://stablecoins.llama.fi"
CACHE = Path(tempfile.gettempdir()) / "jdy-finance-defillama-cache"
DAY = 86400


def iso(ts):
    return datetime.fromtimestamp(float(ts), timezone.utc).isoformat()


def number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def percent(current, previous):
    return (current / previous - 1) * 100 if number(current) and number(previous) and previous > 0 else None


def retry_delay(header, attempt):
    if header:
        try:
            return max(0, float(header))
        except ValueError:
            try:
                return max(0, parsedate_to_datetime(header).timestamp() - time.time())
            except (ValueError, TypeError, OverflowError):
                pass
    return 2 ** attempt


class Client:
    def __init__(self, refresh=False, cache=CACHE):
        self.refresh, self.cache = refresh, Path(cache)

    def get(self, url):
        path = self.cache / (hashlib.sha256(url.encode()).hexdigest() + ".json")
        if not self.refresh:
            try:
                saved = json.loads(path.read_text())
                if 0 <= time.time() - saved["fetched_ts"] < 300:
                    return saved["data"], dict(saved["source"], cached=True)
            except (OSError, ValueError, KeyError, TypeError):
                pass
        for attempt in range(2):
            try:
                request = Request(url, headers={"User-Agent": "jdy-finance-macro/1.0", "Accept": "application/json"})
                with urlopen(request, timeout=25) as response:
                    raw = response.read(64 * 1024 * 1024 + 1)
                    if len(raw) > 64 * 1024 * 1024:
                        raise ValueError("Response exceeds 64 MiB")
                    data = json.loads(raw)
                    now = time.time()
                    source = {"url": url, "http_status": response.status, "fetched_at": iso(now),
                              "http_date": response.headers.get("Date"), "cached": False}
                # Cache failure must not discard a valid network result.
                try:
                    self.cache.mkdir(parents=True, exist_ok=True)
                    with tempfile.NamedTemporaryFile(mode="w", dir=self.cache, delete=False) as f:
                        json.dump({"fetched_ts": now, "source": source, "data": data}, f)
                        temp_path = f.name
                    os.replace(temp_path, path)
                except OSError:
                    pass
                return data, source
            except HTTPError as error:
                if attempt or (error.code != 429 and not 500 <= error.code < 600):
                    raise
                delay = retry_delay(error.headers.get("Retry-After"), attempt)
                if delay > 30:
                    raise RuntimeError("Rate limited; Retry-After exceeds 30s. Stop and try later.") from error
                time.sleep(delay)
            except (URLError, TimeoutError, socket.timeout):
                if attempt:
                    raise
                time.sleep(1)


def series_summary(points, now=None):
    """Stock levels: exact UTC calendar-day comparisons; never fill a missing day."""
    now = time.time() if now is None else now
    if not points:
        raise ValueError("Empty time series")
    daily = {}
    for timestamp, value in sorted(points):
        if not number(timestamp) or timestamp <= 0 or timestamp > now + 300:
            raise ValueError("Invalid/future observation timestamp")
        daily[int(timestamp // DAY)] = (timestamp, value)
    latest_day = max(daily)
    timestamp, value = daily[latest_day]
    if not number(value):
        raise ValueError("Latest observation is missing or non-numeric")
    result = {"value": value, "observed_at": iso(timestamp), "unit": "USD",
              "stale_over_48h": now - timestamp > 2 * DAY, "changes": {}}
    for days in (1, 7, 30):
        previous = daily.get(latest_day - days)
        old_ts, old = previous if previous else (None, None)
        change = percent(value, old)
        result["changes"][str(days) + "d"] = {
            "previous": old if number(old) else None,
            "previous_observed_at": iso(old_ts) if old_ts is not None else None,
            "pct": change,
            "status": "ok" if change is not None else "missing_or_nonpositive_baseline",
        }
    return result


def usd_total(row):
    values = row.get("totalCirculatingUSD")
    if not isinstance(values, dict) or not values or not all(number(v) for v in values.values()):
        return None
    return sum(values.values())


def flow_summary(data):
    # The API's total24h is not necessarily the last chart bucket.
    fields = ("total24h", "total7d", "total30d", "total48hto24h", "total14dto7d", "total60dto30d")
    result = {k: data.get(k) if number(data.get(k)) else None for k in fields}
    if not any(result[k] is not None for k in fields[:3]):
        raise ValueError("No valid flow totals returned")
    result.update(unit="USD", totals_observed_at=None, period="upstream total24h/total7d/total30d; end time unspecified")
    result.update(name=data.get("name"), methodology=data.get("methodology"))
    result["period_changes_pct"] = {
        "1d_vs_previous_1d": percent(result["total24h"], result["total48hto24h"]),
        "7d_vs_previous_7d": percent(result["total7d"], result["total14dto7d"]),
        "30d_vs_previous_30d": percent(result["total30d"], result["total60dto30d"]),
    }
    chart = data.get("totalDataChart") or []
    if chart:
        ts, value = max(chart, key=lambda p: p[0])
        result["latest_chart_bucket"] = {"observed_at": iso(ts), "value": value if number(value) else None,
                                         "stale_over_48h": time.time() - float(ts) > 2 * DAY}
    return result


def run(args, client):
    results = {}

    def collect(key, url, transform):
        source = {"url": url}
        try:
            data, source = client.get(url)
            results[key] = {"status": "ok", "source": source, "data": transform(data)}
        except (OSError, ValueError, TypeError, KeyError, IndexError, AttributeError, OverflowError, RuntimeError) as error:
            results[key] = {"status": "unavailable", "source": source, "reason": str(error)}

    if args.command == "dashboard":
        collect("defi_tvl", API + "/v2/historicalChainTvl",
                lambda d: series_summary([(float(p["date"]), p.get("tvl")) for p in d]))
        collect("stablecoin_market_cap", STABLE + "/stablecoincharts/all",
                lambda d: series_summary([(float(p["date"]), usd_total(p)) for p in d]))
        collect("dex_volume", API + "/overview/dexs?excludeTotalDataChart=false&excludeTotalDataChartBreakdown=true", flow_summary)
    elif args.command == "protocol":
        def protocol(d):
            return {"name": d["name"], "parentProtocol": d.get("parentProtocol"),
                    "methodology": d.get("methodology"), "chains": d.get("chains"),
                    "tvl": series_summary([(float(p["date"]), p.get("totalLiquidityUSD")) for p in d["tvl"]])}
        collect("protocol", API + "/protocol/" + args.protocol, protocol)
    elif args.command == "search":
        def search(d):
            matches = [p for p in d if args.query.casefold() in (str(p.get("name", "")) + " " + str(p.get("slug", ""))).casefold()]
            fields = ("name", "slug", "parentProtocol", "category", "chains")
            return {"matches": [{k: p.get(k) for k in fields} for p in matches[:30]],
                    "match_count": len(matches), "truncated": len(matches) > 30}
        collect("protocol_candidates", API + "/protocols", search)
    elif args.command == "chains":
        def chains(d):
            valid = [p for p in d if number(p.get("tvl"))]
            return {"top": [{"name": p["name"], "tvl_usd": p["tvl"]} for p in sorted(valid, key=lambda p: p["tvl"], reverse=True)[:10]],
                    "missing_tvl_count": len(d) - len(valid), "observed_at": None}
        collect("chains", API + "/v2/chains", chains)
    else:
        kind = "dailyFees" if args.command == "fees" else "dailyRevenue"
        collect(args.command, API + "/summary/fees/" + args.protocol + "?dataType=" + kind, flow_summary)
    return {"generated_at": iso(time.time()), "results": results,
            "browser_supplement": ["ETF flows", "unlocks", "upgrades/airdrops", "hacks/fundraises announcements"],
            "notes": ["TVL changes are not net inflows.", "Stablecoin cap sums totalCirculatingUSD, not mixed-currency supply.",
                      "Fetch time is not observation time; flow total end times may be unknown."]}


def slug(value):
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", value):
        raise argparse.ArgumentTypeError("Use the exact lowercase protocol slug (search first).")
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true", help="Skip the 5-minute cache")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("dashboard")
    sub.add_parser("chains")
    sub.add_parser("search").add_argument("query")
    for name in ("protocol", "fees", "revenue"):
        sub.add_parser(name).add_argument("protocol", type=slug)
    args = parser.parse_args()
    result = run(args, Client(args.refresh))
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    return int(any(item["status"] != "ok" for item in result["results"].values()))


if __name__ == "__main__":
    raise SystemExit(main())
