# Browser, Model, and Review Package Contract

Read this before assigning an external cognitive role or uploading review material.

## Fixed access surface

Use only these backends through `browser:control-in-app-browser`:

| Backend | Allowed roles | Repository access |
|---|---|---|
| ChatGPT Web | Advisor, implementation author, Reviewer, Arbiter | read-only package only |
| Grok Web | Advisor, implementation author, Reviewer, Arbiter | read-only package only |

Do not substitute Chrome, Playwright, OpenCLI, a direct API, model CLI, local subagent, Claude, or another platform.

Keep at most two task-controlled external-model tabs or conversations active. Before opening a new one, reuse or close a task-owned tab when safe. Record provider, role, visible model, reasoning setting, conversation URL/stable ID, and last known status. Recover interrupted work by recorded URL/ID instead of creating duplicates.

ChatGPT Pro Web and Grok Web are preferred cognitive backends; different backends are preferred for two reviewers, not a default hard requirement. If the built-in Browser is unavailable, preserve evidence and enter `WAITING_HUMAN`.

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
  reasoning_levels: ["Extra High", "High", "Medium"]
  availability: "available"
  visible_limit_or_recovery: ""
```

Also record `model_inventory_observed_at`. Do not reopen the menu before every role. Refresh it only when Grok or ChatGPT Pro reports a quota limit, the observation is stale, or an actual fallback is needed. On refresh, list every currently visible model/mode, availability, visible limit or recovery time, and confirmed reasoning choices.

For selection:

1. inspect and record all model names currently visible to the signed-in account;
2. record whether `Extra High` can be selected or confirmed for each candidate used;
3. select the highest-capability visible compatible model using this preference baseline:

```text
ChatGPT Pro → GPT-5.6 Sol → GPT-5.5 → GPT-5.3 → o3
```

This 2026-08-03 list is only a synthetic baseline, not a permanent inventory. `GPT-5.5` appeared as `Instant` in that observation; this UI mode is not a general reasoning level. Never infer `Extra High` support for GPT-5.3, o3, or a future model—confirm it in the current menu.

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

Backend/model fallback is allowed by default. If the user sets `exact_backend_required: true` or `exact_model_required: true`, an unavailable exact target causes `WAITING_HUMAN`. `exact_reasoning_level_required` is always true. If no ChatGPT Web model is available, can carry the frozen artifacts, or confirms `Extra High`, enter `WAITING_HUMAN`.

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
- implementation-author conversation IDs;
- repository-derived test and artifact evidence;
- failure-matrix risk focus;
- previous findings, resolution matrix, and rework diff for a re-review;
- prohibited actions and required verdict schema.

### `full.diff`

Generate the complete textual Git diff for the frozen base/head range. It may contain any number of changed paths. Record its SHA-256. Never use a shortened display, summary-only patch, or silently omitted file. Binary and symlink paths are excluded and reported rather than uploaded.

If the complete diff cannot be uploaded within the browser/provider limit:

1. do not truncate it;
2. split the task only at a coherent independently testable boundary when still consistent with the frozen contract; otherwise
3. enter `WAITING_HUMAN` with the measured limit and affected artifact.

### `review-context.txt`

Include only explicitly allowed Git-tracked text: necessary repository instructions, contract excerpts, final relevant source context not understandable from the diff, concise test/artifact evidence, and clear path separators. For re-review, previous findings and their resolution matrix may go here or in `review-request.yaml`. Do not include the Writer's desired verdict or another Reviewer's conclusions.

## Safe transfer

Transfer only explicitly selected Git-tracked text, the complete task diff, and bounded evidence excerpts. Exclude `.env`, secrets, tokens, keys, certificates, authentication headers, signed payloads, databases, real user data, unrelated logs, binaries, symlinks, and unlisted untracked files.

Apply both path denylisting and content secret scanning. If a safe complete package cannot be formed, enter `WAITING_HUMAN`.

## Package accounting

Record a SHA-256 for each file. The package digest covers all three file digests and the exact head. Increment the task-wide package counter only for a newly verified head with newly generated package contents.

The following keep the same sequence number and digest:

- sending the package to the second Reviewer;
- retrying a failed upload;
- reopening/recovering a conversation;
- sending a bounded evidence supplement that does not change the reviewed head or package inputs.

Any code change invalidates the package. Re-test, re-build artifacts, and generate the next package if the task-wide count remains below three.

## Finalize or hand off browser state

Before pausing or ending a turn, record each task conversation's URL/ID and status. Close only blank or completed tabs created by this task; never close user-owned tabs. A browser/backend failure never creates a new package version implicitly.
