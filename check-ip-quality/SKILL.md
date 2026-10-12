---
name: check-ip-quality
description: "检查或比较公网 IP 的信誉、归属和代理风险时使用。"
---

# Check IP Quality

Evaluate a public IP using traceable evidence and the intended use. Report in Chinese. Read [evidence rules](references/evidence-rules.md) when interpreting DNSBL categories, coverage, or vendor risk thresholds.

## Workflow

1. Identify the target and use case: browsing/development, account/platform, or direct email sending. If unspecified, report all three. For “current IP”, query at least two HTTPS egress sources (for example `https://api.ipify.org` and `https://ifconfig.me/ip`). Label the queried environment: terminal egress does not prove browser egress. If exits differ, report each separately; never choose one silently.
2. Resolve this skill's real directory (it may be symlinked). Run from that directory:

   ```bash
   python3 scripts/check_ip_quality.py <ip>
   python3 scripts/check_ip_quality.py <ip> --use-case account --format json
   ```

   Python standard library, curl >=8.4.0, and optional whois are used. Do not install or upgrade dependencies as part of a lookup. Default total query budget is 90 seconds; `--budget 30` can shorten it. Non-global IPs are rejected. IPv4-mapped IPv6 is normalized to IPv4; IPv6 DNSBL checks are explicitly unsupported.
3. Inspect source status, fields, gaps, DNSBL controls, and the use-case assessment. A failed/unavailable source remains unknown; it is neither a blacklist hit nor a clean result. The script has no synthetic 0–100 quality score. ProxyCheck's original risk score is vendor evidence, not a probability.
4. Return a conclusion first, followed by useful evidence, missing checks, use-case advice, timestamps, and source links. Distinguish observed risk, no adverse signal in the checked sources, and insufficient evidence. Keep positive findings visible even with missing checks. Never turn a limited negative result into a blanket “clean IP” claim.

## Interpretation boundaries

- Hosting/VPN can be acceptable for browsing and development. Account use is sensitive to hosting/proxy/VPN/Tor labels, but this does not prove maliciousness or predict platform acceptance.
- Spamhaus PBL is a direct-to-MX email policy listing. It does not imply poor browsing/account reputation or inability to use an authenticated SMTP relay.
- DNSBL positives require this run's same-path positive and negative controls to pass. Provider error codes, wildcard answers, failed controls, incomplete CNAMEs, and unsupported answers remain unknown. Google DoH cannot bypass a provider's public-resolver restrictions. If restricted, cite the official checker as an uncompleted manual check; do not read keys or configure accounts.
- ASN/RDAP registration country is not an egress geolocation measurement. Shodan is historical supporting evidence; no data does not mean no exposure. PTR lookup failure differs from confirmed missing PTR; PTR presence alone does not establish correct mail configuration.
- CleanTalk is optional manual supporting evidence. Blocked/anti-crawler pages are inconclusive. Ping is not collected and must not be invented.
- Do not infer dedicated ownership, genuine residential use, target-platform access, current infection, or future reputation from these databases. Website/API lookup failure is not an IP risk signal.

When comparing IPs, use identical use cases and coverage rules. An IP with fewer completed checks is not cleaner. Keep classification labels separate from confirmed abuse categories and describe the scope of each source.

## Verification after changes

```bash
python3 -B -m unittest discover -s tests -v
```

The suite includes offline response fixtures and a loopback chunked-body limit check using the existing curl. Live checks are separate evidence and must not be claimed from fixtures.
