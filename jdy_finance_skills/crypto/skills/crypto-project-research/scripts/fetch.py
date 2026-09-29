#!/usr/bin/env python3
"""Read free endpoint evidence; never execute provider metadata or overwrite runs."""
from __future__ import annotations

import argparse
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
import re
import sys

from client import CATALOG, Client, clean, utc, write_new


def same_address(left, right):
    if not isinstance(left, str) or not isinstance(right, str):
        return False
    evm = r"0x[0-9a-fA-F]{40}"
    if re.fullmatch(evm, left) and re.fullmatch(evm, right):
        return left.lower() == right.lower()
    return left == right


def resource_matches(resource_id, network, address):
    prefix = network + "_"
    return isinstance(resource_id, str) and resource_id.startswith(prefix) and same_address(resource_id[len(prefix):], address)


def numeric(value, positive=False):
    if value is None or isinstance(value, bool):
        return None
    try:
        number = Decimal(str(value))
    except (ValueError, InvalidOperation):
        return None
    if not number.is_finite() or (number <= 0 if positive else number < 0):
        return None
    return number


def select_pool(rows, network, address):
    candidates, eligible, seen = [], [], set()
    for row in rows:
        if not isinstance(row, dict):
            candidates.append({"reason": "invalid_pool_record"})
            continue
        rid = row.get("id")
        if not isinstance(rid, str) or rid in seen:
            continue
        seen.add(rid)
        attrs = row.get("attributes") or {}
        relations = row.get("relationships") or {}
        if not isinstance(attrs, dict) or not isinstance(relations, dict):
            candidates.append({"id": rid, "reason": "invalid_pool_shape"})
            continue
        pool_address = attrs.get("address")
        try:
            clean(pool_address, "pool")
        except ValueError:
            candidates.append({"id": rid, "reason": "invalid_pool_address"})
            continue
        if not resource_matches(rid, network, pool_address):
            candidates.append({"id": rid, "reason": "wrong_network_or_pool_id"})
            continue
        pair = {}
        for side in ("base", "quote"):
            relation = relations.get(side + "_token")
            value = relation.get("data") if isinstance(relation, dict) else None
            pair[side] = value.get("id") if isinstance(value, dict) else None
        sides = [side for side, value in pair.items() if resource_matches(value, network, address)]
        if len(sides) != 1 or not all(isinstance(value, str) and value.startswith(network + "_") for value in pair.values()):
            candidates.append({"id": rid, "reason": "target_or_pair_unverified"})
            continue
        side = sides[0]
        price = numeric(attrs.get(side + "_token_price_usd"), positive=True)
        reserve = numeric(attrs.get("reserve_in_usd"), positive=True)
        volume_data = attrs.get("volume_usd")
        volume = numeric(volume_data.get("h24")) if isinstance(volume_data, dict) else None
        if price is None or reserve is None or volume is None:
            candidates.append({"id": rid, "reason": "missing_or_invalid_price_liquidity_volume"})
            continue
        candidate = {"id": rid, "address": pool_address, "target_side": side,
                     "volume_h24_usd": str(volume), "reserve_in_usd": str(reserve), "reason": "eligible"}
        candidates.append(candidate)
        eligible.append((volume, reserve, rid, candidate))
    if not eligible:
        return {"address": None, "target_side": None, "selection": "no_eligible_pool", "candidates": candidates}
    # Stable lexical ID tie-break, descending volume then reserve.
    chosen = sorted(eligible, key=lambda item: (-item[0], -item[1], item[2]))[0][3]
    return {"address": chosen["address"], "target_side": chosen["target_side"],
            "id": chosen["id"], "selection": "h24_volume_desc_then_reserve_desc_then_id",
            "reasons": ["target_relationship_verified", "positive_price_and_reserve", "bounded_pool_discovery"], "candidates": candidates}


def snapshot(client, network, address, output, mode="quick", coin_id=None, pool_pages=1):
    clean(network, "id")
    clean(address, "address")
    if coin_id is not None:
        clean(coin_id, "id")
    if mode not in ("quick", "standard") or pool_pages not in (1, 2):
        raise ValueError("invalid snapshot mode or pool page count")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    manifest = {"schema_version": 1, "identity": {"network": network, "address": address, "coin_id": coin_id,
        "identity_evidence": {"status": "unverified", "source": "token", "network": network, "address": address, "coin_id_match": False}},
        "started_at": utc(), "completed_at": None, "mode": mode, "reference_pool": None, "envelopes": {},
        "coverage": {"pool_pages": 0, "partial": True, "trades_sample": True, "candles": "unavailable"},
        "budget": {"requested_attempts": client.max_attempts, "requested_seconds": client.deadline - client.started, "used_attempts": 0}, "warnings": []}

    def record(name, endpoint, **params):
        provider = "coingecko-demo" if name == "coin" else "geckoterminal"
        evidence = client.request(provider, endpoint, **params)
        filename = name + ".json"
        write_new(output / filename, evidence)
        manifest["envelopes"][name] = filename
        if evidence["status"] != "ok":
            manifest["warnings"].append(name + ":" + evidence["status"])
        return evidence

    token = record("token", "token", network=network, address=address)
    data = token.get("data", {}).get("data") if isinstance(token.get("data"), dict) else None
    attrs = data.get("attributes") if isinstance(data, dict) else None
    verified = isinstance(attrs, dict) and same_address(attrs.get("address"), address) and resource_matches(data.get("id"), network, address)
    if verified:
        manifest["identity"]["identity_evidence"]["status"] = "verified"
    else:
        manifest["warnings"].append("token_identity_unverified:token_conclusions_blocked")
    record("info", "token_info", network=network, address=address)
    pool_rows = []
    for page in range(1, pool_pages + 1):
        pools = record("pools_page_" + str(page), "token_pools", network=network, address=address, page=page, include="base_token,quote_token,dex")
        rows = pools.get("data", {}).get("data") if isinstance(pools.get("data"), dict) else None
        if pools["status"] != "ok" or not isinstance(rows, list):
            break
        pool_rows.extend(rows)
        manifest["coverage"]["pool_pages"] += 1
        if not rows:
            break
    manifest["reference_pool"] = select_pool(pool_rows, network, address) if verified else {"address": None, "target_side": None, "selection": "token_identity_unverified", "candidates": []}
    reference = manifest["reference_pool"]
    if mode == "standard" and reference["address"]:
        candles = record("ohlcv", "pool_ohlcv", network=network, pool=reference["address"], timeframe="hour", aggregate=1, limit=168, currency="usd", token=address)
        manifest["coverage"]["candles"] = "sampled_hourly_max_168" if candles["status"] == "ok" else "unavailable"
        record("trades", "pool_trades", network=network, pool=reference["address"], token=address)
    elif mode == "standard":
        manifest["warnings"].append("standard_pool_evidence_unavailable")
    if coin_id:
        mapped = verified and attrs.get("coingecko_coin_id") == coin_id
        manifest["identity"]["identity_evidence"]["coin_id_match"] = bool(mapped)
        if mapped:
            coin = record("coin", "coin", id=coin_id, localization="false", tickers="false", market_data="true", community_data="false", developer_data="false", sparkline="false")
            if coin["status"] == "ok" and (not isinstance(coin.get("data"), dict) or coin["data"].get("id") != coin_id):
                manifest["identity"]["identity_evidence"]["coin_id_match"] = False
                manifest["warnings"].append("coin_response_id_mismatch:no_combined_statistics")
        else:
            manifest["warnings"].append("coin_id_mapping_unverified:enrichment_skipped")
    manifest["completed_at"] = utc()
    manifest["budget"]["used_attempts"] = client.used
    write_new(output / "manifest.json", manifest)
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("capabilities")
    query = commands.add_parser("query")
    query.add_argument("--provider", choices=CATALOG, required=True)
    query.add_argument("--endpoint", required=True)
    query.add_argument("--param", action="append", default=[], metavar="KEY=VALUE")
    query.add_argument("--out", required=True)
    snap = commands.add_parser("snapshot")
    snap.add_argument("--network", required=True)
    snap.add_argument("--address", required=True)
    snap.add_argument("--mode", choices=("quick", "standard"), default="quick")
    snap.add_argument("--coin-id")
    snap.add_argument("--pool-pages", type=int, choices=(1, 2), default=1)
    snap.add_argument("--out-dir", required=True)
    for command in (query, snap):
        command.add_argument("--cache-dir", type=Path)
        command.add_argument("--no-cache", action="store_true")
        command.add_argument("--deadline", type=float, default=180)
        command.add_argument("--max-attempts", type=int, default=12)
    args = parser.parse_args(argv)
    if args.command == "capabilities":
        print(json.dumps({"schema_version": 1, "providers": {provider: {"auth": "none" if provider == "geckoterminal" else "COINGECKO_DEMO_API_KEY header only", "endpoints": {name: {"path": spec[0], "query_params": spec[1]} for name, spec in endpoints.items()}} for provider, endpoints in CATALOG.items()}}, indent=2))
        return 0
    try:
        if args.command == "query" and Path(args.out).exists():
            raise FileExistsError
        client = Client(args.cache_dir, cache=not args.no_cache, deadline=args.deadline, max_attempts=args.max_attempts)
        if args.command == "snapshot":
            result = snapshot(client, args.network, args.address, args.out_dir, args.mode, args.coin_id, args.pool_pages)
            print(json.dumps({"status": "partial", "identity": result["identity"]["identity_evidence"]["status"], "envelopes": len(result["envelopes"]), "used_attempts": client.used}))
            return 0 if result["identity"]["identity_evidence"]["status"] == "verified" else 2
        params = {}
        for item in args.param:
            if "=" not in item:
                raise ValueError("expected KEY=VALUE")
            key, value = item.split("=", 1)
            if key in params:
                raise ValueError("duplicate parameter")
            params[key] = value
        evidence = client.request(args.provider, args.endpoint, **params)
        write_new(args.out, evidence)
        print(json.dumps({"status": evidence["status"], "attempts": evidence["attempts"]}))
        return 0 if evidence["status"] == "ok" else 2
    except (ValueError, OSError):
        print(json.dumps({"status": "error", "error": "invalid_arguments_or_unavailable_output"}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
