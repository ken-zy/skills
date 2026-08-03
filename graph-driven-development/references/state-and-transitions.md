# State and Transition Contract

This file is normative. Read it before creating or resuming a run.

## Contents

- Saved state
- Clocks
- Counters
- Head, package, and diff invariants
- Reviewer completion invariants
- Allowed transitions
- Required transition examples
- Read-only validation

## Saved state

Store state in the task plan or an optional atomically replaced `run.json`:

```json
{
  "schema_version": 2,
  "status": "ACTIVE",
  "state": "PREFLIGHT",
  "task_class": "normal",
  "active_seconds": 0,
  "mandatory_pause_at": null,
  "extension_authorization": null,
  "head_sha": null,
  "verified_head_sha": null,
  "review_package_head_sha": null,
  "review_package_digest": null,
  "package_digest_algorithm": null,
  "review_request_sha256": null,
  "review_request_canonical_sha256": null,
  "full_diff_sha256": null,
  "review_context_sha256": null,
  "review_diff_verified": false,
  "review_package_changed_paths": [],
  "review_package_diff_paths": [],
  "review_package_binary_paths": [],
  "review_package_symlink_paths": [],
  "review_round": 0,
  "review_package_count": 0,
  "implementation_rework_used": 0,
  "plan_rework_used": 0,
  "accepted_blocking_high_pending": false,
  "rework_trigger": null,
  "chatgpt_model_inventory": [],
  "model_inventory_observed_at": null,
  "selected_backend": null,
  "selected_cognitive_model": null,
  "required_reasoning_level": "Extra High",
  "selected_reasoning_level": "Extra High",
  "model_fallback_reason": "",
  "reasoning_level_selection_reason": "fixed_skill_policy",
  "exact_backend_required": false,
  "exact_model_required": false,
  "exact_reasoning_level_required": true,
  "required_backend": null,
  "required_model": null,
  "implementation_author_conversation_ids": [],
  "reviewers": [],
  "task_worktree": "",
  "task_branch": "",
  "base_commit": ""
}
```

Additional evidence fields are allowed. Do not rename or reinterpret the fields above. `selected_backend` and any non-null `required_backend` use only `chatgpt-web` or `grok-web`; record ChatGPT account plan separately. A non-null selected model requires a selected allowed backend. Each `chatgpt_model_inventory` entry records its consecutive zero-based `preference_rank` in policy order.

## Clocks

Normal tasks have a 3,600-second active-work ceiling. High-risk tasks have a 10,800-second ceiling.

- Increment `active_seconds` only while actively planning, implementing, verifying, packaging, reviewing, or reconciling.
- Do not increment it during `WAITING_HUMAN`, required CI/merge queues, or an unavailable required web session.
- Record wall-clock pause start/end and reason so excluded time is auditable.
- Derive one absolute `mandatory_pause_at` from the active-time ledger for reporting.
- Reaching the original ceiling always transitions to `WAITING_HUMAN` before any extension can take effect. It never resets counters or creates a fresh run automatically.
- A later extension requires a new explicit user authorization after that pause. Record `authorized_by`, `authorization_ref`, `authorized_at_active_seconds`, `new_active_limit_seconds`, and a timezone-aware absolute `new_deadline`.
- The new active limit must exceed both the original class ceiling and `authorized_at_active_seconds`. Reaching it forces another `WAITING_HUMAN` pause; extensions never lower reasoning, reset counters, or erase the initial pause evidence.

Every scheduled status report includes current node, active time used, exact head, changed-file count, review round, used/remaining rework budget, largest risk/blocker, and whether task splitting is recommended.

## Counters

`review_package_count` is task-wide and cannot exceed 3. Increment it only when a newly verified head produces a new immutable package.

Do not increment for:

- reconnecting to a saved conversation;
- opening the same conversation URL again;
- retrying an upload;
- re-uploading the same digest;
- sending the same package to the second Reviewer;
- supplying the one allowed bounded evidence supplement without changing head.

`implementation_rework_used` is task-wide and cannot exceed 2. Before returning from N5 to N2 for a batch of accepted blocking/high implementation findings, persist one increment and set `rework_trigger: accepted_blocking_high`. Medium/low findings are advisory and never trigger this transition. Batch all accepted findings from one round into one rework.

An implementation-caused required PR-CI failure is blocking implementation evidence and follows the same persist-before-N2 rule. Ordinary targeted-test repair inside an unfrozen N2 candidate does not consume a review rework or create a review round; it remains bounded by the active-time clock.

`plan_rework_used` cannot exceed 1. A material contract expansion is not hidden inside this counter; return to N0/N1 and obtain user confirmation when required.

At package 3 or rework 2, the current review may finish. If Package 3 still has an accepted blocking/high finding, enter `FAILED` or the applicable `WAITING_HUMAN` immediately; Package 4 and rework 3 are forbidden.

`review_round` identifies the candidate review cycle and normally equals `review_package_count`. Model fallback, backend retry, upload retry, and browser reconnection do not change either value.

## Head, package, and diff invariants

A review candidate and every later review-complete/delivery state require all of the following:

```text
head_sha == verified_head_sha == review_package_head_sha
review_package_digest is non-empty
package_digest_algorithm == graph-review-package-v1
the package digest recomputes from the exact head and three component hashes
review_package_changed_paths == review_package_diff_paths
review_package_binary_paths is empty
review_package_symlink_paths is a subset of the included diff paths
all reviewers for that head use review_package_digest
```

Use `scripts/validate_review_diff.py` to prove exact diff-byte equality against the frozen base/head and to collect path evidence. Symlink target/mode changes are reviewable Git text and remain included. A binary changed path prevents creation of a safe complete package and routes to `WAITING_HUMAN` or a coherent task split.

Use `scripts/compute_review_package_digest.py` for the versioned canonical digest. Store the final request file SHA separately from the canonical request SHA so the manifest does not depend on its own output.

Any repository content change after verification invalidates `verified_head_sha`, `review_package_head_sha`, and `review_package_digest` until tests/artifacts pass again and a new package is generated.

A checkpoint commit records a verified implementation unit. It is not a review candidate until all frozen candidate-level gates pass and the package exists.

## Reviewer completion invariants

`REVIEW_CANDIDATE` may legitimately have no completed verdict yet. Every reviewer record that exists must still be fresh, read-only, non-authoring, use an allowed backend, and match the current package head and digest.

Before entering `READY_FOR_AUTHORIZED_NEXT_ACTION`, `PR_CI`, `WAITING_FOR_MERGE`, `MERGED`, `CLEANED_UP`, or `DELIVERED`:

- normal tasks have at least one valid Reviewer;
- high-risk tasks have at least two valid Reviewers;
- conversation IDs are non-empty and distinct;
- no Reviewer conversation appears in `implementation_author_conversation_ids`;
- every Reviewer records `role: reviewer`, `read_only: true`, `authored_candidate: false`, and `selected_reasoning_level: Extra High`;
- every Reviewer head and package digest match the current frozen candidate.

Historical reviewers for an older head belong in separate history evidence, not the current `reviewers` list.

## Allowed transitions

```text
PREFLIGHT → SPEC_READY → PLAN_READY → IMPLEMENTING → VERIFYING
VERIFYING → IMPLEMENTING              implementation defect and budget remains
VERIFYING → PLAN_READY                frozen plan correction
VERIFYING → REVIEW_CANDIDATE          exact head verified and package created
REVIEW_CANDIDATE → REVIEWING
REVIEWING → REWORKING                 accepted implementation finding
REWORKING → VERIFYING                 rework complete
REVIEWING → READY_FOR_AUTHORIZED_NEXT_ACTION
READY_FOR_AUTHORIZED_NEXT_ACTION → PR_CI   after authorized push and PR
PR_CI → REWORKING                     implementation-caused CI failure
PR_CI → WAITING_FOR_MERGE             all required CI passes on exact head
WAITING_FOR_MERGE → MERGED            authoritative merge confirmation
MERGED → CLEANED_UP                   exact safe cleanup completed
```

Any non-applicable document gate may be recorded as satisfied with evidence rather than silently skipped.

Transition to `WAITING_HUMAN` on a mandatory pause, exhausted counter, an unavailable exact-required backend/model, insufficient independent conversations after permitted fallback, unsupported/unconfirmed `Extra High`, unsafe review package, material contract expansion, indeterminate required gate, or ambiguous destructive target.

Transition to `FAILED` only for a conclusive task failure that cannot be repaired within the frozen contract. Do not use `FAILED` to disguise a missing authorization or unavailable human/backend.

`DELIVERED` and every success lifecycle gate require `accepted_blocking_high_pending: false`. At Package 3 with a pending accepted blocking/high finding, only `WAITING_HUMAN`, `FAILED`, or `CANCELLED` is valid.

## Required transition examples

1. Package 1 returns three accepted high findings: batch them, persist `implementation_rework_used: 1`, fix once, verify once, then create Package 2.
2. Package 2 returns only medium/low findings: mark them advisory; do not return to N2 and do not increment rework or package counters.
3. Package 3 returns an accepted blocking/high finding: record it, then enter `FAILED` or the applicable `WAITING_HUMAN`; Package 4 is forbidden.
4. Browser control disconnects while uploading Package 2: recover the saved conversation and re-upload the same digest; round, package, and rework counters remain unchanged.
5. Both Grok and ChatGPT Pro are quota-limited: refresh the ChatGPT Web inventory once, choose the highest-capability available model that confirms `Extra High`, and continue in fresh independent conversations. If no such model exists or an unavailable exact backend/model target applies, enter `WAITING_HUMAN`.
6. A normal run reaches 3,600 active seconds: pause first. A later user message authorizes a 1,800-second extension at that ledger position, so record a new 5,400-second active limit and absolute deadline; reaching 5,400 forces another pause.
7. A high-risk `REVIEW_CANDIDATE` may have zero completed reviewers while awaiting N4. It cannot advance past review completion until two valid independent reviewer records exist.

## Read-only validation

Run:

```bash
python3 scripts/validate_run_state.py path/to/run.json
```

The validator checks a saved snapshot. It does not advance state, edit the file, execute Git, open a browser, or authorize any action. Passing it is necessary but not sufficient for delivery.
