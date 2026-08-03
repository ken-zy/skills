# Browser, Model, and Review Package Contract

Read this before assigning an external cognitive role or uploading review material.

## Fixed access surface

Use only these backends through the Codex built-in Browser:

| Backend | Website | Allowed roles | Repository access |
|---|---|---|---|
| `chatgpt-web` | authenticated ChatGPT Web | Advisor, implementation author, Reviewer, Arbiter | selected read-only inputs |
| `grok-web` | authenticated Grok Web | Advisor, implementation author, Reviewer, Arbiter | selected read-only inputs |

Do not substitute Chrome, Playwright, OpenCLI, a direct API, model CLI, local subagent, Claude, or another platform. If the built-in Browser is unavailable, preserve evidence and enter `WAITING_HUMAN`.

Keep at most two task-controlled model conversations active. Record backend, role, account plan when visible, visible model, exact selection label, separately exposed reasoning setting or `null`, Browser evidence reference, conversation URL/ID, and status. Recover by URL/ID instead of creating unnecessary duplicates.

## Model and reasoning policy

Account plan, backend, visible model, UI selection, and separately exposed reasoning setting are different facts. Record each fact without inferring an unavailable combination.

Use the latest available model version exposed by the authenticated provider website under one of these approved formal profiles. The model values below are observations from 2026-08-03, not version locks:

| Backend | Exact UI selection | Current visible model | Separate reasoning setting | Policy |
|---|---|---|---|---|
| `chatgpt-web` | `Pro` | `GPT-5.6 Sol Pro` | `null` | primary |
| `chatgpt-web` | `Extra High` | `GPT-5.6 Sol` | `Extra High` | fallback when Pro is unavailable or quota-limited |
| `grok-web` | `Expert` | `Grok 4.5` | `null` | highest available under the current subscription |

`Pro` and `Extra High` are alternative ChatGPT Web selections. Never claim `Pro + Extra High`. `Expert` is a Grok product mode, not an OpenAI reasoning level; never invent an `Extra High` equivalence for Grok.

Do not use ChatGPT `High`, `Medium`, `Instant`, or a silent mini fallback for a formal cognitive role. Do not use Grok `Auto`, `Fast`, or `Build`; do not require `Heavy` while the current subscription cannot execute it. Lowering a reasoning setting does not repair a model quota.

When a backend is first needed, inspect the live menu and record the visible model, exact selection label, separately exposed reasoning setting or `null`, and Browser evidence reference. If the provider has upgraded the visible model but the approved selection semantics remain intact, use the newer version and record it. Pause when selection semantics or role quality have materially changed and cannot be established from current first-party UI evidence.

When ChatGPT Pro is unavailable, use ChatGPT `Extra High`. When Grok `Expert` is unavailable, a fresh ChatGPT conversation may fill that review slot only if the frozen contract does not require Grok exactly. Two required Reviewers may use the same approved ChatGPT profile in separate fresh conversations as long as independence is preserved. If no approved profile remains, enter `WAITING_HUMAN`.

Do not hard-code model versions or rankings in `validate_run_state.py`. Model/profile policy belongs here; run state records the exact observed selection and evidence.

## Reviewer independence

A valid Reviewer conversation:

- did not author the candidate;
- is read-only and cannot edit the repository;
- receives the same exact head and Package v2 ID as every other current Reviewer;
- does not see another Reviewer's verdict before returning its own;
- returns the schema in [review-contract.md](review-contract.md).

High-risk work needs two fresh conversations; normal Graph work needs at least one. Different backends are preferred, not required unless frozen as exact. The same provider/model is acceptable when conversations remain separate and non-authoring.

## Review Package v2: exactly three files

Create one immutable directory for each newly verified candidate:

```text
review-package/
├── review-request.json
├── full.diff
└── review-context.txt
```

This is an upload-count rule, not a source-file limit. `full.diff` may cover any number of changed paths.

### `review-request.json`

Use valid UTF-8 JSON with no duplicate keys and one top-level `review_request` object. Include at least:

```json
{
  "review_request": {
    "package_version": "graph-review-package-v2",
    "package_sequence": 1,
    "base_commit": "<exact base sha>",
    "head_commit": "<exact verified head sha>",
    "full_diff_sha256": "<sha256 of exact full.diff bytes>",
    "review_context_sha256": "<sha256 of exact review-context.txt bytes>",
    "task": {
      "objective": "",
      "in_scope": [],
      "out_of_scope": [],
      "acceptance_criteria": [],
      "risk_class": "normal"
    },
    "review": {
      "required_profile_policy": "latest-approved-web-profile",
      "implementation_author_conversation_ids": [],
      "test_evidence": [],
      "artifact_evidence": [],
      "risk_focus": [],
      "prohibited_actions": ["modify repository", "commit", "push", "deploy"],
      "required_verdict_schema": {
        "verdict": "PASS | CHANGES_REQUESTED | NEEDS_EVIDENCE | BACKEND_FAILED",
        "reviewed_head": "<exact head>",
        "returned_package_id": "sha256:<64 lowercase hex>",
        "summary": "",
        "findings": [],
        "evidence_request": []
      }
    }
  }
}
```

For re-review, include previous findings and their resolution matrix. Do not put the request file's own SHA or the final Package ID in any package file.

### `full.diff`

Generate deterministic exact bytes using the same options as `scripts/validate_review_diff.py`, then validate the saved file:

```bash
python3 scripts/validate_review_diff.py \
  --repo <repository-root> --base <base> --head <head> --diff-file <full.diff>
```

The validator overrides diff/submodule configuration, compares exact generated bytes, independently compares changed paths, and inspects regular-file blobs so attributes or textconv cannot hide binary content. It reports symlink paths and, for binaries, path, old/new mode, and old/new object ID.

Never upload a shortened display, summary-only patch, or omitted path. If the complete diff exceeds a provider limit, split only at a coherent independently verifiable boundary consistent with the frozen contract; otherwise enter `WAITING_HUMAN`.

A binary is permitted only when its path is in scope, path/content scans are safe, Codex inspects the real artifact with an appropriate viewer or smoke test, and the Reviewer's decision does not depend on an opaque property. Record the binary evidence and artifact identity in context. Pause or split for security-critical, unsafe-to-transfer, or uninspectable binary content.

### `review-context.txt`

Include only explicitly selected tracked text and bounded evidence: necessary repository instructions, frozen contract excerpts, source context not understandable from the diff, test/artifact evidence, risk focus, and clear path separators. Do not include the Writer's desired verdict or another Reviewer's conclusions.

## Safe transfer

Apply both sensitive-path denial and content secret scanning before upload. Exclude secrets, tokens, keys, certificates, authentication headers, signed payloads, databases, real user data, unrelated logs, dereferenced symlink targets, and unlisted untracked files.

Binary diff data may be uploaded only under the binary rule above and after the same scans. If a safe complete package cannot be formed, enter `WAITING_HUMAN`.

## External Package v2 ID

Hash the exact bytes of all three files. Build these exact UTF-8 manifest bytes with LF endings, including the final LF:

```text
graph-review-package-v2
head_sha=<head>
review_request_sha256=<sha256 exact request bytes>
full_diff_sha256=<sha256 exact diff bytes>
review_context_sha256=<sha256 exact context bytes>
```

The Package ID is `sha256:` plus the SHA-256 of that manifest. Compute and validate it read-only:

```bash
python3 scripts/compute_review_package_digest.py \
  --head <head> --request review-request.json \
  --diff full.diff --context review-context.txt
```

The tool uses only the Python standard library. It rejects invalid JSON, duplicate keys, a non-positive sequence, stale declared head, or stale diff/context hashes. It does not canonicalize JSON, parse YAML, replace placeholders, scan reserved names, or embed a self hash.

Send the returned Package ID in the Browser message beside the three files and record it in run evidence. Require each Reviewer to echo it with the reviewed head. Any mutation of a package file or the reviewed head changes/invalidates the ID.

Increment `review_package_count` only for new package contents bound to a newly verified candidate. A second Reviewer, identical upload retry, recovered conversation, or bounded supplement does not create another package.

## Browser handoff

Before pausing or ending a turn, record every task conversation URL/ID and status. Close only blank or completed tabs created by this task; never close user-owned tabs. A browser/backend failure never creates a new package implicitly.
