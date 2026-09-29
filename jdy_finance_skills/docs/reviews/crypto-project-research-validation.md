# Validation evidence — crypto-project-research

Date: 2026-09-30 (Asia/Shanghai). Raw live snapshots remain outside the repository. No real credentials were read or included.

## Offline validation

- `python3 -m unittest discover -s crypto/skills/crypto-project-research/tests -v`: **43 tests PASS** (26 analysis, 17 client/snapshot).
- `git diff --check`: PASS.
- Existing repository validator: unchanged baseline **4 missing ignored `.mcp.json` errors / 4 warnings**. Skill frontmatter, command metadata and fallback checks PASS. No private configuration copied to satisfy the legacy validator.
- System skill quick validator unavailable because its external PyYAML dependency is absent in both available Python runtimes. No dependency installed; repository frontmatter checks and local links checked.

## Live public API smoke

### niulai

- Identity: `bsc` / `0xbeea1d618e533a387d941f58a7d4c9b7bd377777`; verified by returned resource ID and attributes.
- Started: 2026-09-29T17:27:49.929357Z; completed: 2026-09-29T17:28:39.937793Z.
- Network attempts: 5; endpoint statuses: `{"token": "ok", "info": "ok", "pools_page_1": "ok", "ohlcv": "ok", "trades": "ok", "coin": "missing_credential"}`.
- Selected reference pool: `0xe5ae318389b8d6d09370a675479c64862152d126` (base).
- Analysis: 167 completed candles, 1 partial; 300 valid trades, 0 rejected.
- Markdown and normalized JSON produced; coin enrichment explicitly remains missing_credential, while GT report stays available.

### pons

- Identity: `robinhood` / `0x39dbed3a2bd333467115de45665cc57f813c4571`; verified by returned resource ID and attributes.
- Started: 2026-09-29T17:28:44.052142Z; completed: 2026-09-29T17:29:52.355788Z.
- Network attempts: 5; endpoint statuses: `{"token": "ok", "info": "ok", "pools_page_1": "ok", "ohlcv": "ok", "trades": "ok", "coin": "missing_credential"}`.
- Selected reference pool: `0xf2a0be59ab76b96f957bd5e5b967f2b75e8db269` (base).
- Analysis: 167 completed candles, 1 partial; 300 valid trades, 0 rejected.
- Markdown and normalized JSON produced; coin enrichment explicitly remains missing_credential, while GT report stays available.

- BSC new-pools discovery: HTTP 200 at 2026-09-29T17:29:15.051870Z; 20 pools, 20 included tokens without CG ID. Missing mappings are not inferred.
- Comparison CLI produced side-by-side Markdown + JSON and explicitly warned that chain/contract and time windows differ; no cross-scope ratios or rankings.
- **CoinGecko Demo was not live-tested**: exact process environment key absent. Mock tests prove transport/header isolation and missing-key behavior only.
- Live success is point-in-time availability, not a provider entitlement, contract audit, or trading validation.
