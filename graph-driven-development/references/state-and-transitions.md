# State and Transition Contract

This file is normative. Read it before creating or resuming a run.

## Saved state

Store state in the task plan or an optional atomically replaced `run.json`:

```json
{
  "schema_version": 1,
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
  "reviewers": [],
  "task_worktree": "",
  "task_branch": "",
  "base_commit": ""
}
```

Additional evidence fields are allowed. Do not rename or reinterpret the fields above.

## Clocks

Normal tasks have a 3,600-second active-work ceiling. High-risk tasks have a 10,800-second ceiling.

- Increment `active_seconds` only while actively planning, implementing, verifying, packaging, reviewing, or reconciling.
- Do not increment it during `WAITING_HUMAN`, required CI/merge queues, or an unavailable required web session.
- Record wall-clock pause start/end and reason so excluded time is auditable.
- Derive one absolute `mandatory_pause_at` from the active-time ledger for reporting.
- An extension requires explicit user authorization and records a new absolute deadline plus the authorizing message/reference.
- Reaching the ceiling transitions to `WAITING_HUMAN`; it never resets counters or creates a fresh run automatically.

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

## Head and package invariants

A review candidate requires all of the following:

```text
head_sha == verified_head_sha == review_package_head_sha
review_package_digest is non-empty
all reviewers for that head use review_package_digest
```

Any repository content change after verification invalidates `verified_head_sha`, `review_package_head_sha`, and `review_package_digest` until tests/artifacts pass again and a new package is generated.

A checkpoint commit records a verified implementation unit. It is not a review candidate until all frozen candidate-level gates pass and the package exists.

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

## Required transition examples

1. Package 1 returns three accepted high findings: batch them, persist `implementation_rework_used: 1`, fix once, verify once, then create Package 2.
2. Package 2 returns only medium/low findings: mark them advisory; do not return to N2 and do not increment rework or package counters.
3. Package 3 returns an accepted blocking/high finding: record it, then enter `FAILED` or the applicable `WAITING_HUMAN`; Package 4 is forbidden.
4. Browser control disconnects while uploading Package 2: recover the saved conversation and re-upload the same digest; round, package, and rework counters remain unchanged.
5. Both Grok and ChatGPT Pro are quota-limited: refresh the ChatGPT Web inventory once, choose the highest-capability available model that confirms `Extra High`, and continue in fresh independent conversations. If no such model exists or an unavailable exact backend/model target applies, enter `WAITING_HUMAN`.

## Read-only validation

Run:

```bash
python3 scripts/validate_run_state.py path/to/run.json
```

The validator checks a saved snapshot. It does not advance state, edit the file, execute Git, open a browser, or authorize any action. Passing it is necessary but not sufficient for delivery.
