# DefiLlama Free validation receipt

Validated on 2026-09-30 Asia/Shanghai (2026-09-29 UTC), Python 3.14.6. Runtime uses Python 3.10+ standard-library syntax and APIs; Python 3.10 itself was not executed in this environment.

## Offline

- `python3 -m unittest discover -s defillama-free/tests`: 88 tests passed.
- CLI `--help`, offline `capabilities`, invalid input/overwrite handling and JSON/CSV exports checked.
- Official skill-creator `quick_validate.py`: Skill is valid.
- `git diff --check`: clean.

The external validator required PyYAML absent from both installed Python runtimes. Validation-only PyYAML 6.0.2 source was fetched from official PyPI, release date 2024-08-06, and verified against PyPI SHA256 `d584d9ec91ad65861cc08d42e834324ef890a082e591037abe114850ff7bbc3e`. Only its Python library was placed in a temporary directory; no setup/build script ran and no project/global dependency was installed. It is not needed by the delivered skill.

## Real API checks

`python3 defillama-free/tests/live_smoke.py --run`: all 28 checks passed at 2026-09-29T17:56:54Z. Every CLI subprocess used `--no-cache`; successful linked sources were checked for `cached=false` and `fetched_at` within that subprocess’s start/end interval. Required endpoints need usable data, and Polymarket values and changes were independently recomputed from raw responses. No fixed-price assertions.

This supersedes the initial 20-check run at 17:25:49Z: its harness allowed cache hits and did not prove fresh network access for every required endpoint. The strengthened harness has nine offline regression tests, including rejected cached/empty/failed required results. Its first fresh run correctly rejected a fractional-ISO timestamp parsing regression in yield history; after the parser fix and a dedicated test, all 28 checks passed.

- Polymarket International id711: TVL and volume complete 7-day comparisons; fees/revenue/supply-side retrieved but strict calendar calculations deliberately unavailable because aggregation semantics remain unknown.
- Independent recomputation matched TVL current349465540/prior356194007 USD and volume current483004381/prior537918572 USD. These are dated verification observations, not current-value promises. Volume window `[2026-09-22T00:00:00Z,2026-09-29T00:00:00Z)`.
- Aave V3 identity and TVL, chain TVLs, Polygon history, Tether USD chart, current Ethereum price, yield list and a discovered pool's history yielded usable results.
- Global/chain/options flow history was retrieved but retains unknown time semantics; optional calendar summaries degrade explicitly. Yield optional APY components and some OI rows remain missing rather than zero. OI present rows remain stock observations.
- End-to-end independent subagent exercise checked PM JSON/CSV versus raw data and invalid CLI scenarios. Its three findings (truncation disclosure, failure provenance, duplicate-slug request bound) were fixed and covered by separate regression tests.

No mandatory live check is environment-blocked. Historical API values can change; raw responses and full generated exports were kept only in temporary local validation directories, not committed. The checked-in opt-in smoke script allows future reruns. Offline capabilities do not imply a live uptime guarantee.

After the aggregate dataType fix, an additional uncached `chains Polygon --days 7` call returned fresh linked TVL and volume/fees/revenue observations. Calendar flow rows remain deliberately unavailable where time semantics are unknown. All 88 offline tests and the official format validator passed after the final code fix.
