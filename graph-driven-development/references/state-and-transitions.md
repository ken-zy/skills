# State and Transition Contract

This file is normative for new v1.2 runs. Historical v1.1 evidence is not migrated automatically.

## Proportional persistence

- Normal Graph task: record the required state in the task plan or handoff; a standalone `run.json` is optional.
- High-risk Graph task: persist the minimal snapshot before review and again before delivery.

Additional evidence fields are allowed, but the validator deliberately ignores facts it cannot prove from one JSON snapshot.

## Schema v3

```json
{
  "schema_version": 3,
  "status": "ACTIVE",
  "state": "PREFLIGHT",
  "task_class": "normal",
  "task_worktree": "/absolute/task/worktree",
  "task_branch": "codex/task-slug",
  "base_commit": "<exact base sha>",
  "head_sha": null,
  "verified_head_sha": null,
  "active_seconds": 0,
  "active_limit_seconds": 3600,
  "time_extension_authorization_ref": "",
  "review_package_id": null,
  "review_package_count": 0,
  "review_package_limit": 3,
  "implementation_rework_used": 0,
  "implementation_rework_limit": 2,
  "budget_extension_authorization_ref": "",
  "accepted_blocking_high_pending": false,
  "reviewers": []
}
```

Default active limits are 3,600 seconds for `normal` and 10,800 seconds for `high_risk`. Default package and implementation-rework limits are 3 and 2.

An authorization may raise a saved limit. Record the new limit and a non-empty `time_extension_authorization_ref` or `budget_extension_authorization_ref`. Keep all counters; do not reset them or create a disguised fresh run. Authorization authenticity remains external evidence, not something JSON can prove.

Reviewer records retain release evidence:

```json
{
  "conversation_id": "stable browser conversation id",
  "backend": "chatgpt-web",
  "visible_model": "GPT-5.6 Sol Pro",
  "selection_label": "Pro",
  "reasoning_setting": null,
  "selection_evidence_ref": "browser observation or screenshot reference",
  "read_only": true,
  "authored_candidate": false,
  "head_sha": "<reviewed head>",
  "package_id": "sha256:<64 lowercase hex>",
  "verdict": "PASS",
  "completed_at": "timezone-aware timestamp",
  "findings_reconciled": true,
  "blocking_high_remaining": false
}
```

For ChatGPT `Extra High`, record `selection_label: "Extra High"` and `reasoning_setting: "Extra High"`. For Grok `Expert`, record the current visible Grok model, `selection_label: "Expert"`, and `reasoning_setting: null`. Exact model versions may advance without a schema change.

If external conversations helped author the implementation, record their IDs in the optional `implementation_author_conversation_ids` evidence field. A current Reviewer ID must not appear there.

## Canonical states and statuses

```text
PREFLIGHT, SPEC_READY, PLAN_READY, IMPLEMENTING, VERIFYING,
REVIEW_CANDIDATE, REVIEWING, REWORKING,
READY_FOR_AUTHORIZED_NEXT_ACTION, PR_CI, WAITING_FOR_MERGE,
MERGED, CLEANED_UP, WAITING_HUMAN, DELIVERED, FAILED, CANCELLED
```

Statuses are `ACTIVE`, `WAITING_HUMAN`, `DELIVERED`, `FAILED`, or `CANCELLED`. A terminal status and terminal state must match exactly.

## Time and counters

Increment `active_seconds` only during active task work. Exclude recorded human waits, required CI/merge queues, and unavailable required web sessions.

Reaching `active_limit_seconds` while active forces `WAITING_HUMAN`. The user may explicitly raise the limit; no strict timestamp choreography is required.

Increment `review_package_count` only for new package contents bound to a newly verified candidate. Sending one package to another Reviewer, retrying the same upload, reopening a conversation, or providing a bounded evidence supplement does not increment it.

Increment `implementation_rework_used` once for each accepted batch of implementation `blocking/high` findings. Required PR-CI repairs caused by the implementation use the same counter. Medium/low advice does not.

The saved package/rework limits are pause thresholds, not permanent correctness ceilings. If a pending accepted blocking/high finding exhausts either saved limit, enter `WAITING_HUMAN`. Continue only after a raised limit is explicitly authorized and saved.

## Completion invariants

Before `READY_FOR_AUTHORIZED_NEXT_ACTION`, `PR_CI`, `WAITING_FOR_MERGE`, `MERGED`, `CLEANED_UP`, or `DELIVERED`:

- `head_sha` and `verified_head_sha` are identical and non-empty;
- `review_package_id` is the current `sha256:` Package v2 ID;
- normal tasks have at least one independent Reviewer; high-risk tasks have at least two;
- current Reviewer conversation IDs are distinct and did not author the candidate;
- each Reviewer used `chatgpt-web` or `grok-web`, recorded a non-empty visible model, exact UI selection, Browser evidence, backend-appropriate reasoning setting, read-only mode, and the current head/package;
- every current Reviewer has final `PASS`, reconciled findings, and no blocking/high finding remaining;
- `accepted_blocking_high_pending` is false.

Historical or superseded review attempts belong in separate evidence, not the current `reviewers` list.

Any repository-content change after verification invalidates `verified_head_sha`, the current package ID, and all current Reviewer bindings until tests/artifacts pass again and a new package is generated.

## Allowed flow

```text
PREFLIGHT → SPEC_READY → PLAN_READY → IMPLEMENTING → VERIFYING
VERIFYING → IMPLEMENTING              implementation defect
VERIFYING → PLAN_READY                frozen plan correction
VERIFYING → REVIEW_CANDIDATE          exact head verified and package created
REVIEW_CANDIDATE → REVIEWING
REVIEWING → REWORKING                 accepted implementation finding
REWORKING → VERIFYING                 rework complete
REVIEWING → READY_FOR_AUTHORIZED_NEXT_ACTION
READY_FOR_AUTHORIZED_NEXT_ACTION → PR_CI   after authorized push and PR
PR_CI → REWORKING                     implementation-caused CI failure
PR_CI → WAITING_FOR_MERGE             required checks pass on exact head
WAITING_FOR_MERGE → MERGED            authoritative merge confirmation
MERGED → CLEANED_UP                   exact safe cleanup completed
```

Enter `WAITING_HUMAN` for a mandatory pause, exhausted saved budget with required work remaining, unavailable exact-required backend/profile, insufficient independent conversations, missing or ambiguous selection evidence, unsafe package transfer, material scope expansion, indeterminate required gate, or ambiguous destructive target.

Use `FAILED` only for a conclusive failure that cannot be repaired within the authorized contract. Do not use it to disguise missing authorization.

## Read-only validation

```bash
python3 scripts/validate_run_state.py path/to/run.json
```

The validator checks only schema/state values, saved limits and authorization references, mandatory pauses, completion head/package evidence, Reviewer release evidence, and pending blocking/high findings.

It does not prove browser inventory, model ranking, real CI status, Git ancestry, worktree cleanliness, wall-clock history, or authorization authenticity. Check those against the relevant external source before claiming completion.
