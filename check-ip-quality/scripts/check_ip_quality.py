#!/usr/bin/env python3
"""Collect public evidence for IP quality and reputation checks."""

from __future__ import annotations

import argparse
import datetime as dt
import html
import ipaddress
import json
import re
import subprocess
import sys
import urllib.parse
from typing import Any


DNSBL_ZONES = [
    "zen.spamhaus.org",
    "bl.spamcop.net",
    "b.barracudacentral.org",
    "dnsbl.sorbs.net",
    "all.spamrats.com",
    "rbl.interserver.net",
    "dnsbl.dronebl.org",
    "psbl.surriel.com",
    "bl.mailspike.net",
]


def run_cmd(args: list[str], timeout: int = 20) -> tuple[int, str, str]:
    try:
        proc = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return proc.returncode, proc.stdout.strip(), proc.stderr.strip()
    except subprocess.TimeoutExpired as exc:
        return 124, exc.stdout or "", f"timeout after {timeout}s"
    except FileNotFoundError:
        return 127, "", f"missing command: {args[0]}"


def curl(url: str, timeout: int = 20) -> tuple[int, str, str]:
    return run_cmd(
        ["curl", "-L", "-s", "--http1.1", "--max-time", str(timeout), url],
        timeout=timeout + 2,
    )


def parse_json(raw: str) -> Any | None:
    try:
        return json.loads(raw)
    except Exception:
        return None


def reversed_ipv4(ip: str) -> str | None:
    addr = ipaddress.ip_address(ip)
    if addr.version != 4:
        return None
    return ".".join(reversed(str(addr).split(".")))


def doh(name: str, qtype: str = "A") -> dict[str, Any] | None:
    query = urllib.parse.urlencode({"name": name, "type": qtype})
    code, out, _ = curl(f"https://dns.google/resolve?{query}", timeout=12)
    if code != 0:
        return None
    data = parse_json(out)
    return data if isinstance(data, dict) else None


def get_proxycheck(ip: str) -> dict[str, Any]:
    url = f"https://proxycheck.io/v2/{ip}?vpn=1&asn=1&risk=1"
    code, out, err = curl(url, timeout=15)
    data = parse_json(out)
    if code != 0 or not isinstance(data, dict):
        return {"available": False, "error": err or f"curl exit {code}"}
    item = data.get(ip)
    if not isinstance(item, dict):
        return {"available": False, "raw": data}
    return {"available": True, **item}


def get_cymru(ip: str) -> dict[str, str]:
    code, out, err = run_cmd(["whois", "-h", "whois.cymru.com", f" -v {ip}"], timeout=12)
    if code != 0 or not out:
        return {"available": "false", "error": err or f"whois exit {code}"}
    lines = [line for line in out.splitlines() if line.strip()]
    data_line = next((line for line in lines if re.match(r"\s*\d+\s*\|", line)), "")
    if not data_line:
        return {"available": "true", "raw": out}
    parts = [part.strip() for part in data_line.split("|")]
    labels = ["asn", "ip", "bgp_prefix", "cc", "registry", "allocated", "as_name"]
    return {"available": "true", **dict(zip(labels, parts))}


def get_rdap(ip: str) -> dict[str, Any]:
    code, out, err = curl(f"https://rdap.org/ip/{ip}", timeout=15)
    data = parse_json(out)
    if code != 0 or not isinstance(data, dict):
        return {"available": False, "error": err or f"curl exit {code}"}

    names: list[str] = []

    def walk_entities(entities: list[dict[str, Any]] | None) -> None:
        for entity in entities or []:
            vcard = entity.get("vcardArray")
            if isinstance(vcard, list) and len(vcard) > 1:
                for row in vcard[1]:
                    if isinstance(row, list) and len(row) >= 4 and row[0] in {"fn", "org"}:
                        value = row[3]
                        if isinstance(value, str) and value not in names:
                            names.append(value)
            child = entity.get("entities")
            if isinstance(child, list):
                walk_entities(child)

    walk_entities(data.get("entities") if isinstance(data.get("entities"), list) else None)
    return {
        "available": True,
        "name": data.get("name"),
        "handle": data.get("handle"),
        "type": data.get("type"),
        "start": data.get("startAddress"),
        "end": data.get("endAddress"),
        "entities": names[:8],
    }


def get_ptr(ip: str) -> list[str]:
    code, out, _ = run_cmd(["dig", "+short", "-x", ip], timeout=8)
    if code != 0 or not out:
        return []
    return [line.rstrip(".") for line in out.splitlines() if line.strip()]


def get_internetdb(ip: str) -> dict[str, Any]:
    code, out, err = curl(f"https://internetdb.shodan.io/{ip}", timeout=15)
    data = parse_json(out)
    if code != 0 or not isinstance(data, dict):
        return {"available": False, "error": err or f"curl exit {code}"}
    return data


def get_dnsbl(ip: str) -> list[dict[str, Any]]:
    rev = reversed_ipv4(ip)
    if not rev:
        return [{"zone": "dnsbl", "status": "skipped", "reason": "IPv6 DNSBL not implemented"}]
    results: list[dict[str, Any]] = []
    for zone in DNSBL_ZONES:
        qname = f"{rev}.{zone}"
        data = doh(qname, "A")
        if not data:
            results.append({"zone": zone, "status": "unknown", "answers": []})
            continue
        answers = [a.get("data") for a in data.get("Answer", []) if isinstance(a, dict)]
        listed = any(isinstance(ans, str) and ans.startswith("127.") for ans in answers)
        txt_answers: list[str] = []
        if listed:
            txt = doh(qname, "TXT")
            if txt:
                txt_answers = [
                    str(a.get("data"))
                    for a in txt.get("Answer", [])
                    if isinstance(a, dict) and a.get("data")
                ]
        results.append(
            {
                "zone": zone,
                "status": "listed" if listed else "not_listed",
                "answers": answers,
                "txt": txt_answers,
                "resolver_status": data.get("Status"),
                "comment": data.get("Comment"),
            }
        )
    return results


def get_cleantalk_summary(ip: str) -> list[str]:
    code, out, _ = curl(f"https://cleantalk.org/blacklists/{ip}", timeout=20)
    if code != 0 or not out:
        return []
    text = re.sub(r"<script.*?</script>", " ", out, flags=re.S | re.I)
    text = re.sub(r"<style.*?</style>", " ", text, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", "\n", text)
    text = html.unescape(text)
    lines = []
    for line in text.splitlines():
        line = re.sub(r"\s+", " ", line).strip()
        if not line:
            continue
        if re.search(rf"{re.escape(ip)}|blacklist|spam|abuse|attacks|listed|not in list|last seen", line, re.I):
            lines.append(line)
    return lines[:20]


def score_report(proxycheck: dict[str, Any], dnsbl: list[dict[str, Any]], ptr: list[str]) -> tuple[int, list[str]]:
    score = 100
    reasons: list[str] = []

    if proxycheck.get("available"):
        proxy = str(proxycheck.get("proxy", "")).lower()
        ip_type = str(proxycheck.get("type", "")).lower()
        provider = str(proxycheck.get("provider", "")).lower()
        try:
            risk = int(proxycheck.get("risk", 0))
        except Exception:
            risk = 0

        if proxy == "yes":
            score -= 15
            reasons.append("proxycheck marks proxy=yes")
        if risk >= 75:
            score -= 14
            reasons.append(f"proxycheck risk is high ({risk})")
        elif risk >= 50:
            score -= 10
            reasons.append(f"proxycheck risk is elevated ({risk})")
        elif risk >= 25:
            score -= 5
            reasons.append(f"proxycheck risk is non-zero ({risk})")
        if any(word in ip_type for word in ["vpn", "proxy", "tor"]):
            score -= 8
            reasons.append(f"proxycheck type is {proxycheck.get('type')}")
        if "cloudflare" in provider and proxy == "yes":
            score -= 5
            reasons.append("Cloudflare exit with VPN/proxy labeling")
    else:
        reasons.append("proxycheck unavailable")

    dnsbl_penalty = 0
    for item in dnsbl:
        if item.get("status") != "listed":
            continue
        zone = str(item.get("zone", ""))
        txt = " ".join(item.get("txt") or [])
        if "spamhaus" in zone:
            penalty = 18
        elif "spamcop" in zone:
            penalty = 12
        elif "dronebl" in zone and re.search(r"open .*proxy|socks", txt, re.I):
            penalty = 12
        elif "dronebl" in zone:
            penalty = 10
        else:
            penalty = 8
        dnsbl_penalty += penalty
        reasons.append(f"{zone} listed" + (f": {txt}" if txt else ""))
    if dnsbl_penalty:
        score -= min(dnsbl_penalty, 30)

    if not ptr:
        score -= 2
        reasons.append("no PTR/rDNS")

    return max(0, min(100, score)), reasons


def level(score: int) -> str:
    if score >= 85:
        return "clean / low risk"
    if score >= 70:
        return "usable with tradeoffs"
    if score >= 50:
        return "risky"
    return "poor for trust-sensitive use"


def md_value(value: Any) -> str:
    if value in (None, "", []):
        return "none"
    if isinstance(value, (list, tuple)):
        return ", ".join(str(v) for v in value) if value else "none"
    return str(value)


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect public IP quality evidence.")
    parser.add_argument("ip", help="Public IP address to evaluate")
    args = parser.parse_args()

    try:
        ipaddress.ip_address(args.ip)
    except ValueError:
        print(f"Invalid IP address: {args.ip}", file=sys.stderr)
        return 2

    ip = args.ip
    proxycheck = get_proxycheck(ip)
    cymru = get_cymru(ip)
    rdap = get_rdap(ip)
    ptr = get_ptr(ip)
    internetdb = get_internetdb(ip)
    dnsbl = get_dnsbl(ip)
    cleantalk = get_cleantalk_summary(ip)
    score, reasons = score_report(proxycheck, dnsbl, ptr)

    print(f"# IP Quality Evidence: {ip}")
    print()
    print(f"- checked_at_utc: {dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')}")
    print(f"- suggested_score: {score}/100 ({level(score)})")
    print(f"- scoring_reasons: {md_value(reasons)}")
    print()

    print("## Summary Signals")
    print()
    print("| Signal | Value |")
    print("|---|---|")
    if proxycheck.get("available"):
        print(f"| proxycheck proxy | {md_value(proxycheck.get('proxy'))} |")
        print(f"| proxycheck type | {md_value(proxycheck.get('type'))} |")
        print(f"| proxycheck risk | {md_value(proxycheck.get('risk'))} |")
        print(f"| provider | {md_value(proxycheck.get('provider'))} |")
        print(f"| organisation | {md_value(proxycheck.get('organisation'))} |")
        print(f"| range | {md_value(proxycheck.get('range'))} |")
        print(f"| location | {md_value([proxycheck.get('country'), proxycheck.get('region'), proxycheck.get('city')])} |")
    else:
        print(f"| proxycheck | unavailable: {md_value(proxycheck.get('error') or proxycheck.get('raw'))} |")
    print(f"| Team Cymru ASN | {md_value(cymru.get('asn'))} {md_value(cymru.get('as_name'))} |")
    print(f"| Team Cymru prefix | {md_value(cymru.get('bgp_prefix'))} |")
    print(f"| RDAP holder | {md_value(rdap.get('entities'))} |")
    print(f"| RDAP range | {md_value(rdap.get('start'))} - {md_value(rdap.get('end'))} |")
    print(f"| PTR/rDNS | {md_value(ptr)} |")
    if internetdb.get("detail"):
        print(f"| Shodan InternetDB | {internetdb.get('detail')} |")
    else:
        ports = internetdb.get("ports") if isinstance(internetdb, dict) else None
        vulns = internetdb.get("vulns") if isinstance(internetdb, dict) else None
        print(f"| Shodan InternetDB ports | {md_value(ports)} |")
        print(f"| Shodan InternetDB vulns | {md_value(vulns)} |")
    print()

    print("## DNSBL")
    print()
    print("| Zone | Status | Answers | TXT |")
    print("|---|---|---|---|")
    for item in dnsbl:
        print(
            f"| {item.get('zone')} | {item.get('status')} | "
            f"{md_value(item.get('answers'))} | {md_value(item.get('txt'))} |"
        )
    print()

    print("## CleanTalk Extract")
    print()
    if cleantalk:
        for line in cleantalk:
            print(f"- {line}")
    else:
        print("- unavailable or no parseable lines")

    print()
    print("## Raw Source Hints")
    print()
    print(f"- proxycheck: https://proxycheck.io/v2/{ip}?vpn=1&asn=1&risk=1")
    print(f"- rdap: https://rdap.org/ip/{ip}")
    print(f"- dronebl: https://dronebl.org/lookup?ip={ip}")
    print(f"- cleantalk: https://cleantalk.org/blacklists/{ip}")
    print(f"- shodan internetdb: https://internetdb.shodan.io/{ip}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
