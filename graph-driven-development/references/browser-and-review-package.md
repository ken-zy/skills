# Browser, Model, and Review Package Contract

Read this before assigning an external cognitive role or uploading review material.

## Contents

- Fixed access surface
- Model versus reasoning
- Reviewer independence
- Exactly three uploaded files
- Safe transfer
- Package accounting
- Finalize or hand off browser state

## Fixed access surface

Use only these canonical backend IDs through `browser:control-in-app-browser`:

| Backend ID | Access surface | Allowed roles | Repository access |
|---|---|---|---|
| `chatgpt-web` | Authenticated ChatGPT website | Advisor, implementation author, Reviewer, Arbiter | read-only package only |
| `grok-web` | Authenticated Grok website | Advisor, implementation author, Reviewer, Arbiter | read-only package only |

Do not substitute Chrome, Playwright, OpenCLI, a direct API, model CLI, local subagent, Claude, or another platform.

Keep at most two task-controlled external-model tabs or conversations active. Before opening a new one, reuse or close a task-owned tab when safe. Record provider, role, visible model, reasoning setting, conversation URL/stable ID, and last known status. Recover interrupted work by recorded URL/ID instead of creating duplicates.

The ChatGPT account plan, backend, visible model, and reasoning level are separate facts. Record a visible `Pro` account plan as `account_plan: "Pro"`; never encode it as a third backend such as `chatgpt-pro-web`. ChatGPT Web and Grok Web are the only cognitive backends. Different backends are preferred for two reviewers, not a default hard requirement. If the built-in Browser is unavailable, preserve evidence and enter `WAITING_HUMAN`.

## Model versus reasoning

These are separate fields:

```yaml
model: "visible model name"
selected_reasoning_level: "Extra High"
```

`Extra High`, `High`, and `Medium` are reasoning settings, not models. Use exactly `Extra High`. A model's quota is independent of this setting; never lower reasoning as quota mitigation.

During cognitive-backend preflight, inspect the ChatGPT Web menu once and record every visible entry as structured inventory:

```yaml
- model: "GPT-5.6 Sol"
  mode: ""
  preference_rank: 1
  reasoning_levels: ["Extra High", "High", "Medium"]
  availability: "available"
  visible_limit_or_recovery: ""
```

Also record `model_inventory_observed_at`. Do not reopen the menu before every role. Refresh it only when Grok or ChatGPT Pro reports a quota limit, the observation is stale, or an actual fallback is needed. On refresh, list every currently visible model/mode, availability, visible limit or recovery time, and confirmed reasoning choices.

Use only `available`, `quota_exhausted`, `unavailable`, or `reasoning_unsupported` for machine-validated inventory availability. A lower-ranked selected model requires a non-empty `model_fallback_reason` tied to the observed higher-model condition; an ambiguous condition pauses instead of being encoded as a made-up availability value.

For selection:

1. inspect and record all model names currently visible to the signed-in account;
2. record whether `Extra High` can be selected or confirmed for each candidate used;
3. assign consecutive zero-based `preference_rank` values in the policy order below for visible known entries;
4. select the available Extra High-capable entry with the lowest rank:

```text
ChatGPT Pro → GPT-5.6 Sol → GPT-5.5 → GPT-5.3 → o3
```

This 2026-08-03 list is only a synthetic baseline, not a permanent inventory. `GPT-5.5` appeared as `Instant` in that observation; this UI mode is not a general reasoning level. Never infer `Extra High` support for GPT-5.3, o3, or a future model—confirm it in the current menu. If the menu exposes an unknown model whose priority relative to the baseline cannot be justified from visible first-party UI evidence, record the ambiguity and enter `WAITING_HUMAN` rather than inventing a rank.

When Grok or ChatGPT Pro is quota-limited, unavailable, or stale, refresh once and choose the highest-capability currently available ChatGPT Web model that confirms `Extra High`. When both preferred backends are quota-limited, the default fallback is still inside the same authenticated ChatGPT website; two required Reviewers may continue in two fresh independent ChatGPT conversations using compatible available model(s). Do not move to another platform.

For Grok Web, record the visible model and reasoning control. Use it only when the required fixed reasoning setting can be confirmed. Otherwise apply the permitted ChatGPT Web fallback unless `exact_backend_required: true`; do not guess.

Always persist:

```yaml
selected_cognitive_model: ""
required_reasoning_level: "Extra High"
selected_reasoning_level: "Extra High"
model_fallback_reason: ""
reasoning_level_selection_reason: "fixed_skill_policy"
exact_backend_required: false
exact_model_required: false
exact_reasoning_level_required: true
```

Backend/model fallback is allowed by default. Both `selected_backend` and any non-null `required_backend` must still be `chatgpt-web` or `grok-web`; an exact flag cannot legalize another platform. If the user sets `exact_backend_required: true` or `exact_model_required: true`, an unavailable exact target causes `WAITING_HUMAN`. `exact_reasoning_level_required` is always true. If no available ChatGPT Web model can carry the frozen artifacts and confirm `Extra High`, enter `WAITING_HUMAN`.

## Reviewer independence

High-risk work uses two fresh read-only review conversations; other contracts may also require two. A valid Reviewer:

- did not author the candidate in that conversation;
- cannot edit the repository;
- receives the same package digest and exact head as the other Reviewer;
- does not see the other Reviewer's verdict before submitting its own;
- returns the schema in `review-contract.md`.

Codex reconciles findings only after every contract-required verdict arrives. If fallback cannot preserve the required number and independence, enter `WAITING_HUMAN`.

Model fallback does not weaken conversation independence. The two conversations may use the same provider/model but must remain fresh, separate, read-only, non-authoring, and bound to the identical package.

## Exactly three uploaded files

Build one immutable directory for each newly verified review head:

```text
review-package/
├── review-request.yaml
├── full.diff
└── review-context.txt
```

Each Reviewer receives these same three files. This upload limit does not limit how many source files may change.

### `review-request.yaml`

Include:

- objective, scope, acceptance criteria, and risk class;
- base SHA, head SHA, package sequence number, and package digest;
- digest algorithm ID plus the diff and context SHA-256 values;
- implementation-author conversation IDs;
- repository-derived test and artifact evidence;
- failure-matrix risk focus;
- previous findings, resolution matrix, and rework diff for a re-review;
- prohibited actions and required verdict schema.

### `full.diff`

Generate the exact diff bytes with this deterministic command shape:

```bash
git -c core.quotePath=true -c diff.mnemonicPrefix=false -c diff.noprefix=false \
  -c diff.ignoreSubmodules=none -c diff.orderFile=/dev/null \
  -c diff.suppressBlankEmpty=false \
  diff --binary --full-index --no-ext-diff --no-textconv --no-color \
  --no-renames --no-relative --src-prefix=a/ --dst-prefix=b/ --line-prefix= \
  --diff-algorithm=myers --no-indent-heuristic --unified=3 \
  --inter-hunk-context=0 --submodule=short --ignore-submodules=none \
  <base>..<head>
```

The diff may contain any number of changed paths. Record its SHA-256. Never use a shortened display, summary-only patch, or silently omitted file. Validate the saved bytes before upload:

```bash
python3 scripts/validate_review_diff.py \
  --repo <repository-root> --base <base> --head <head> --diff-file <full.diff>
```

The validator overrides repository/user submodule-ignore configuration, reads the base/head tree change records independently, parses paths back out of the supplied patch, and requires both path sequences to match exactly. It also inspects every old/new regular-file blob directly, so `.gitattributes`, textconv, or diff-driver settings cannot disguise a binary blob as reviewable text. Symlink and gitlink target/mode changes stay in `full.diff`. Any binary changed path fails package creation before upload because a safe textual review package cannot claim completeness while omitting or blindly transferring it. Split at a coherent boundary or enter `WAITING_HUMAN`; do not produce a review package marked complete.

If the complete diff cannot be uploaded within the browser/provider limit:

1. do not truncate it;
2. split the task only at a coherent independently testable boundary when still consistent with the frozen contract; otherwise
3. enter `WAITING_HUMAN` with the measured limit and affected artifact.

### `review-context.txt`

Include only explicitly allowed Git-tracked text: necessary repository instructions, contract excerpts, final relevant source context not understandable from the diff, concise test/artifact evidence, and clear path separators. For re-review, previous findings and their resolution matrix may go here or in `review-request.yaml`. Do not include the Writer's desired verdict or another Reviewer's conclusions.

## Safe transfer

Transfer only explicitly selected Git-tracked text, the complete validated task diff, and bounded evidence excerpts. Exclude `.env`, secrets, tokens, keys, certificates, authentication headers, signed payloads, databases, real user data, unrelated logs, binary file bodies, directly dereferenced symlink contents, and unlisted untracked files. A textual Git diff may include a symlink's tracked target and mode change after the normal path and content scans.

Apply both path denylisting and content secret scanning. If a safe complete package cannot be formed, enter `WAITING_HUMAN`.

## Package accounting

Use the versioned algorithm ID `graph-review-package-v1`. Encode `review-request.yaml` as UTF-8 without BOM, with LF line endings and a final newline. It must contain exactly one scalar in this form:

```yaml
  package_digest: "sha256:<64 lowercase hex>"
```

For canonical request hashing, replace only those 64 hex characters with 64 ASCII zeroes while preserving every other byte. Hash those canonical bytes as `review_request_canonical_sha256`. Hash the exact `full.diff` and `review-context.txt` bytes normally.

Build these exact UTF-8 manifest bytes with LF endings, including the final LF:

```text
graph-review-package-v1
head_sha=<exact lowercase Git head>
review_request_canonical_sha256=<64 lowercase hex>
full_diff_sha256=<64 lowercase hex>
review_context_sha256=<64 lowercase hex>
```

The package digest is `sha256:` plus the SHA-256 of those manifest bytes. Use the read-only reference implementation:

```bash
python3 scripts/compute_review_package_digest.py \
  --head <head> --request review-request.yaml \
  --diff full.diff --context review-context.txt
```

First run it with the all-zero placeholder, insert the returned package digest, then run it with `--verify-embedded`. Do not write either the actual request SHA or canonical request SHA inside `review-request.yaml`, because either would create another self-reference. Record both outside that file in run state and Browser transfer evidence. The actual file hash is transport evidence; the canonical request hash is the request component bound into the package digest.

Increment the task-wide package counter only for a newly verified head with newly generated package contents.

The following keep the same sequence number and digest:

- sending the package to the second Reviewer;
- retrying a failed upload;
- reopening/recovering a conversation;
- sending a bounded evidence supplement that does not change the reviewed head or package inputs.

Any code change invalidates the package. Re-test, re-build artifacts, and generate the next package if the task-wide count remains below three.

## Finalize or hand off browser state

Before pausing or ending a turn, record each task conversation's URL/ID and status. Close only blank or completed tabs created by this task; never close user-owned tabs. A browser/backend failure never creates a new package version implicitly.
