# Evidence and assessment rules

The source envelope records `status=ok|unknown|unsupported`, UTC query time, URL, parsed data and a reason. DNSBL adds `listing_status=listed|not_listed|unknown|unsupported`. Unknown fields never default to safe values. Markdown and JSON use the same assessments; no quality score is generated.

## DNSBL admission

Each enabled IPv4 zone (Spamhaus ZEN, SpamCop, DroneBL) must pass fresh same-resolver controls: `2.0.0.127.<zone>` contains the expected `127.0.0.2` with no invalid codes for Spamhaus/SpamCop. DroneBL's positive control instead requires a nonempty A set entirely within `{127.0.0.1,127.0.0.2}` (official testing/sample classes). `1.0.0.127.<zone>` is confirmed absent. Failed controls invalidate target results, including apparent positives. These internal test addresses do not relax public-target validation. The queried test address and its returned classification code are distinct.

Validate DNS Status, `TC=false`, Question name/type, answer owners/types and record structure. NXDOMAIN must have no contradictory Answer. NOERROR absence requires a relevant SOA with valid fields. CNAMEs are conservatively unknown. TXT is only supporting evidence. DNSBL response codes must match the provider map; mixed valid/invalid answers remain unknown.

SOA MNAME/RNAME and PTR use conservative ASCII DNS names: nonempty labels, at most 63 characters per label and 253 characters overall (excluding one terminal dot). Unsupported escaped names are unknown. All five SOA numeric fields must be ASCII unsigned 32-bit integers. Deprecated IPv6 site-local addresses are rejected before lookup.

- Spamhaus: SBL `.2`, CSS `.3`, XBL `.4`, DROP `.9`, PBL `.10/.11`, BCL `.30` in `127.0.0.x`. Error codes and all other answers are unknown. PBL affects direct-MX mail only.
- SpamCop: `127.0.0.2` means reported spam.
- DroneBL: use the official threat-class map in the collector. Testing/sample/uncategorized entries cannot supply negative coverage; no specific attack is invented. Experimental or possible-compromise categories retain those qualifications.

Removed old or unverified zones and automated CleanTalk scraping must not be treated as checked. IPv6 DNSBL is unsupported.

## Frozen ProxyCheck v2 policy

Only top-level `ok` or `warning` admits fields. A complete result requires proxy yes/no, a recognized type, and integer risk 0–100. Complete warnings remain usable and display a warning. Independently valid positive fields are retained on incomplete responses; they cannot supply negative coverage. Denied/error/unknown top-level statuses do not supply evidence.

Recognized v2 non-VPN proxy types include OpenVPN, Shadowsocks, SOCKS4A, SOCKS5H, Scraper and Inference Engine as well as TOR/HTTP/HTTPS/SOCKS variants. OpenVPN here means a public proxy, distinct from the generic VPN service label; it does not inherit VPN's <=73 exception. Unknown future types remain incomplete and never supply negative coverage. DroneBL A codes use exact ASCII IPv4 strings; leading zeros, Unicode digits and valid/invalid mixtures are unknown.

Browsing/direct-MX apply the vendor's conservative table:

| Detection | Risk trigger |
|---|---|
| proxy=no | risk >=67 |
| proxy=yes, type=VPN | risk >=74 |
| proxy=yes, recognized non-VPN type | any valid proxy detection |

VPN <=73 and pure Hosting (`proxy=no`, risk <=66) are tradeoffs rather than browsing risk. Account use additionally treats valid VPN/proxy/Tor/Hosting labels as platform-sensitive risk signals. Vendor risk is not a maliciousness probability. Effective abuse-list hits independently trigger observed risk; VPN baseline never cancels them.

## Coverage and verdicts

- `observed_risk`: independently valid relevant positive evidence exists, even if other checks are incomplete. Explain vendor risk, platform sensitivity, abuse category, direct-mail policy or mail configuration separately.
- `no_adverse_signal_in_checked_sources`: no relevant positive and no required gaps. Browsing/account require complete ProxyCheck plus at least one valid abuse-list result; mail requires every enabled list valid and classified, complete ProxyCheck and a successful PTR lookup with records.
- `insufficient_evidence`: no relevant positive, but a required check is missing, unknown or unsupported. Classification uncertainty also prevents a negative claim.

A confirmed missing PTR is a direct-mail configuration risk, whereas a failed lookup is unknown. Mail assessment applies to direct-to-MX sending; authenticated relay delivery depends on that relay. RDAP/ASN/Shodan are enrichment and cannot fill missing reputation coverage. All conclusions are limited to the checked datasets and do not promise platform access or deliverability.

## Transport and privacy

curl must be identifiable as >=8.4.0 before HTTP. First argument `-q` disables curlrc; no automatic or manual decompression. HTTPS-only redirects, 512 KiB transport-time body cap, per-request hard timeout and shared monotonic deadline are enforced. Failed/oversized responses are not parsed; raw stderr, webpages, RDAP personal contacts and credentials are not printed. No new packages are required.

WHOIS stdout is capped during receipt at 512 KiB, with only one extra byte read to detect overflow; stderr is discarded. Overflow or timeout terminates and reaps the process and yields unknown, even if a valid record preceded the overflow. External lone surrogate code points are replaced with U+FFFD in the shared evidence model, including diagnostic text, so JSON/Markdown UTF-8 output retains other valid evidence.

## Primary references (checked 2026-10-12)

- [ProxyCheck v2 documentation and conservative table](https://proxycheck.io/api/)
- [Spamhaus codes](https://docs.spamhaus.com/datasets/docs/source/10-data-type-documentation/datasets/040-zones.html)
- [Spamhaus controls and public-resolver limitations](https://www.spamhaus.org/faqs/dnsbl-usage/)
- [Spamhaus PBL](https://www.spamhaus.org/blocklists/policy-blocklist/)
- [SpamCop lookup](https://www.spamcop.net/fom-serve/cache/351.html)
- [DroneBL threat classes](https://dronebl.org/classes)
- [DNSBL test entries, RFC5782 §5](https://www.rfc-editor.org/rfc/rfc5782.html)
- [Google DoH JSON schema](https://developers.google.com/speed/public-dns/docs/doh/json)
- [curl transport limits](https://curl.se/docs/manpage.html)
