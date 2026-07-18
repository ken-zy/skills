---
name: check-ip-quality
description: Evaluate public IP address quality, reputation, proxy/VPN risk, ASN ownership, DNSBL listings, reverse DNS, and basic reachability. Use when the user asks to check an IP, compare IP quality, assess whether an IP is suitable for accounts, proxies, email, ads, registration, login, scraping, API access, or asks about current egress IP reputation.
---

# Check IP Quality

## Overview

Use this skill to evaluate whether an IP is clean, risky, or unsuitable for a specific use case. Prefer evidence from multiple public sources over one score.

For user-facing answers in this vault, report in Chinese. Keep skill-facing notes, scripts, and source comments in English.

## Workflow

1. Identify the target IP.
   - If the user says "current IP", query at least two egress sources such as `https://api.ipify.org`, `https://ifconfig.me/ip`, and `https://icanhazip.com`.
   - If the sources disagree, state that the environment may be using multiple exits and evaluate each visible IP separately.
2. Run the bundled evidence collector:

```bash
python3 /Users/jdy/Documents/skills/check-ip-quality/scripts/check_ip_quality.py <ip>
```

3. If the script cannot reach a source, continue with available evidence and say which checks were unavailable. Do not treat source failure as an IP risk signal.
4. Interpret the evidence for the user's intended use case:
   - Normal browsing / development testing: tolerate hosting and some proxy labels if no blacklist is present.
   - Account registration, login, social platforms, payments, ads: penalize hosting, VPN, proxy, shared Cloudflare/WARP exits, DNSBL hits, and inconsistent geography.
   - Email sending: require clean DNSBL, PTR/rDNS, non-proxy reputation, and preferably a dedicated mail-friendly ASN. No PTR is a meaningful negative.
5. Return a concise verdict with a score, table of key signals, and use-case recommendations.

## Evidence Sources

Prefer these checks:

- `proxycheck.io` API for `proxy`, `type`, `risk`, ASN, provider, country, and range.
- Team Cymru whois for BGP ASN and routed prefix.
- RDAP (`rdap.org` or registry RDAP) for registered holder and allocation range.
- PTR/rDNS with `dig -x`.
- Google DoH DNSBL lookups for Spamhaus, SpamCop, Barracuda, SORBS, SpamRATS, InterServer, DroneBL, PSBL, and Mailspike.
- DroneBL lookup page or DNS TXT for incident class details.
- Shodan InternetDB for exposed services when available.
- CleanTalk only as supporting evidence; ignore "Anti-Crawler" or blocked pages as inconclusive.

Avoid relying on local resolver DNSBL responses. If local `dig` returns fake-IP ranges such as `198.18.0.0/15` across many DNSBL zones, discard those results and use DNS-over-HTTPS instead.

## Scoring Heuristic

Use the script score as a starting point, then adjust with judgment:

- `85-100`: clean or low-risk IP.
- `70-84`: usable, but with tradeoffs such as hosting ASN or missing PTR.
- `50-69`: risky for account or platform use; may still work for browsing/API.
- `<50`: poor quality for trust-sensitive use.

Major negative signals:

- `proxy=yes`, `VPN`, `Proxy`, `Tor`, `Open SOCKS proxy`, `Open HTTP proxy`.
- SpamCop, DroneBL, Spamhaus, or multiple DNSBL listings.
- Cloudflare `AS13335` plus VPN/proxy labeling, often WARP/Gateway-like egress.
- Hosting/datacenter ASN when the user needs "real user" behavior.
- No PTR for mail-related use.

Do not over-penalize:

- Ping failure by itself. Many hosts and Cloudflare-like networks block ICMP.
- One unavailable website/API.
- Generic "hosting" when the user only needs server/API access.

## Report Shape

Use this structure unless the user asks for raw output:

```markdown
`<ip>` 查完了。结论：<one sentence with score and suitability>.

| 项目 | 结果 |
|---|---|
| ASN | ... |
| 归属 | ... |
| proxy/VPN | ... |
| 地理 | ... |
| DNSBL | ... |
| PTR | ... |
| Shodan | ... |
| Ping | ... |

使用建议：
- 普通浏览 / 开发测试：...
- 注册 / 登录 / 社媒 / 支付 / 广告：...
- 邮件发送：...

参考源：...
```

When comparing several IPs, normalize scores to the same rubric and call out whether differences are per-IP or inherited from the same `/24`, ASN, or provider.
