# Graph-Driven Development v1.1 Optimization Spec

Status: Review rework implemented locally; awaiting independent re-review
Date: 2026-08-03
Owner: Codex
Target: `graph-driven-development/`

## 1. Problem

The current skill has a strong safety posture but mixes policy, procedure, examples, and browser operations in one long entrypoint. Several operational rules are also descriptive rather than mechanically checkable. Recent use exposed four recurring costs:

1. Review and rework loops can continue without a hard task-level ceiling.
2. Time limits do not distinguish active work from external waiting and do not define a single auditable deadline.
3. Checkpoint commits, review candidates, review packages, and PR-CI repairs are not represented as one coherent lifecycle.
4. Browser/model fallback, upload limits, and reviewer independence need exact invariants rather than prose conventions.

## 2. Goals

- Keep Codex as the only repository writer.
- Require a fresh task branch and isolated worktree for every new task.
- Make run limits, review-package limits, rework limits, and pause conditions explicit and auditable.
- Separate model identity from reasoning level. Reasoning is always `Extra High`; it is never a quota fallback mechanism.
- Permit ChatGPT Web model fallback only inside ChatGPT Web, in descending capability order, after the preferred model is unavailable or quota-limited.
- Use one immutable three-file review package for any number of changed source files.
- Make the skill entrypoint shorter through progressive disclosure without weakening gates.
- Add a narrow read-only validator for saved run-state invariants.

## 3. Non-goals

- No authorization beyond the Skill's explicitly listed lifecycle permissions.
- No third-party model platforms beyond ChatGPT Web and Grok Web.
- No inference that a lower reasoning level changes model quota.
- No general workflow engine, browser automation framework, or repository mutation script.
- No automatic deletion of a branch or worktree until merge is confirmed.

## 4. Authority boundaries

The following remain independent actions. Invoking this Skill may explicitly grant the bounded defaults shown below; a current user instruction may narrow them:

1. create task branch/worktree — allowed by the Skill;
2. checkpoint commit after scoped verification — allowed by the Skill;
3. push the ready task branch — allowed by the Skill;
4. create its PR — allowed by the Skill;
5. merge — separate explicit authorization;
6. deploy or other remote/production mutation — separate explicit authorization;
7. post-merge cleanup — exact worktree and local task branch allowed after authoritative merge confirmation; remote branch deletion requires authorization or confirmed platform auto-delete.

An implementation checkpoint may be committed only when the changed unit is independently verified and the current contract still permits it. A checkpoint is not automatically a review candidate. A review candidate is an exact verified Git head with a generated package and recorded evidence. This optimization run itself remains local-only because its current task instructions explicitly prohibit commit, push, and PR creation.

## 5. Task classes and time budgets

| Task class | Progress report | Soft pause | Mandatory pause |
| --- | ---: | ---: | ---: |
| Normal | 30 minutes | 45 minutes | 1 hour |
| High risk | 1 hour | 2 hours | 3 hours |

Only active task work counts. Time in `WAITING_HUMAN`, required CI/merge queues, and unavailable external web sessions is recorded separately and excluded. The run records:

- `active_started_at`;
- accumulated `active_seconds`;
- `paused_started_at` and `pause_reason` when paused;
- one derived `mandatory_pause_at` for the current class;
- any post-pause user-approved extension as a new active-time limit and absolute deadline plus its authorization evidence.

At the original mandatory deadline, the next state is always `WAITING_HUMAN`; no extension may silently bypass that pause. A later explicit authorization records the authorizer, message reference, active ledger position, larger active-time limit, and timezone-aware absolute deadline. Reaching the extended limit forces another pause. A soft pause means stop starting a new implementation unit, summarize progress and risk, and finish only the smallest safe verification needed to preserve evidence.

## 6. State model

Minimum states:

- `PREFLIGHT`
- `SPEC_READY`
- `PLAN_READY`
- `IMPLEMENTING`
- `VERIFYING`
- `REVIEW_CANDIDATE`
- `REVIEWING`
- `REWORKING`
- `PR_CI`
- `WAITING_HUMAN`
- `READY_FOR_AUTHORIZED_NEXT_ACTION`
- `MERGED`
- `CLEANED_UP`

Minimum persisted fields:

```json
{
  "schema_version": 2,
  "task_class": "normal|high_risk",
  "state": "PREFLIGHT",
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
  "active_seconds": 0,
  "mandatory_pause_at": null,
  "chatgpt_model_inventory": [],
  "model_inventory_observed_at": null,
  "selected_backend": null,
  "selected_cognitive_model": null,
  "required_reasoning_level": "Extra High",
  "selected_reasoning_level": "Extra High",
  "exact_backend_required": false,
  "exact_model_required": false,
  "exact_reasoning_level_required": true,
  "required_backend": null,
  "required_model": null,
  "implementation_author_conversation_ids": [],
  "reviewers": []
}
```

Core invariants:

1. `review_package_count <= 3` for the whole task, including implementation review, re-review, and PR-CI repair review.
2. `implementation_rework_used <= 2` for the whole task; only a batch of accepted blocking/high implementation findings or an implementation-caused required-CI failure consumes it.
3. A package count increases only when a newly verified head produces a new package. Reconnects, retries, reopening a URL, or re-uploading the same package do not increment it.
4. Reviewers reviewing the same head use the same package digest.
5. A review candidate requires `head_sha == verified_head_sha == review_package_head_sha`.
6. Any code change after package generation invalidates the package and requires re-verification before a new package.
7. When a hard cap or mandatory pause is reached, transition to `WAITING_HUMAN`; the workflow must not silently extend itself.
8. `required_reasoning_level` and `selected_reasoning_level` are exactly `Extra High` for every external cognitive role.
9. If a selected model cannot expose or confirm `Extra High`, transition to `WAITING_HUMAN`.
10. `selected_backend` and any non-null `required_backend` are only `chatgpt-web` or `grok-web`; account plan, visible model, and reasoning level are separate fields.
11. A selected ChatGPT model is the available Extra High-capable inventory entry with the lowest policy rank; an exact flag cannot legalize another platform or premature fallback.
12. `DELIVERED` and review-complete lifecycle states cannot retain an accepted blocking/high finding. Package 3 with one pending uses only `WAITING_HUMAN`, `FAILED`, or `CANCELLED`.
13. `REVIEW_CANDIDATE` may await verdicts, but review completion requires one valid Reviewer for normal work and two for high risk. Every recorded Reviewer is fresh, read-only, non-authoring, independent by conversation ID, and bound to the current head/package.
14. `graph-review-package-v1` recomputes from the exact head, canonical request hash, exact diff hash, and exact context hash. Changed paths and diff paths match exactly; binary paths block package creation; symlink target/mode changes remain in the diff.

## 7. Implementation and verification lifecycle

Before implementation, identify delivery units and their risk domains. If one request spans more than two of UI projection, durable command/API, Runtime state machine, recovery/replay, and permissions/real external effects, propose phased delivery by default.

Create a domain-neutral failure matrix covering at least:

- inputs and validation;
- permissions/authentication where applicable;
- concurrency, retries, and idempotency where applicable;
- persistence/migration compatibility where applicable;
- external side effects and rollback where applicable;
- observability and failure evidence.

Each row is `covered`, `not_applicable` with a reason, or `open`. Implementation cannot begin with an unexplained `open` high-risk row.

Verification is layered:

1. changed-unit checks;
2. repository-derived required test gates;
3. artifact checks such as diff integrity and generated package digest;
4. synthetic run-state checks for hard limits and invalid transitions.

Tests must be derived from repository instructions and affected behavior. The skill must not invent a universal test command.

## 8. Review architecture

High-risk work uses two independent reviewers, started in parallel by default. Normal work uses at least one unless its contract asks for two. Preferred backends are:

- ChatGPT Web reviewer;
- Grok Web reviewer.

Both are read-only and receive the same immutable review package. Neither sees the other's verdict before submitting its own. Codex owns reconciliation and all repository edits. Different backends are preferred, not a default exact requirement.

Task-controlled external-model browser state is capped at two active tabs/conversations. Conversation URL or stable conversation ID must be recorded so interrupted sessions can be recovered without opening duplicates.

When Grok or ChatGPT Pro is quota-limited, refresh the ChatGPT Web inventory and apply the permitted same-site model fallback. If both are quota-limited, two required reviewers may continue in separate fresh ChatGPT conversations. Exact backend/model requirements fail closed, and no fallback may cross to another platform.

## 9. ChatGPT model selection

At cognitive-backend preflight, inspect the models currently visible in ChatGPT Web once and record model/mode, consecutive zero-based preference rank, reasoning choices, availability, visible quota/recovery, and observation time. Refresh only when a preferred backend hits quota, the inventory is stale, or fallback is actually needed. The configured capability order is a 2026-08-03 synthetic baseline, not a claim that every account always exposes every model:

1. ChatGPT Pro;
2. GPT-5.6 Sol;
3. GPT-5.5;
4. GPT-5.3;
5. o3.

Selection rules:

1. Use the highest-capability visible model that supports confirmed `Extra High`.
2. If Grok or ChatGPT Pro is quota-limited or unavailable, move to the next visible compatible ChatGPT model in current menu capability order.
3. Never lower reasoning level as quota mitigation.
4. Never fall back from ChatGPT Web to another platform.
5. If no visible ChatGPT Web model supports confirmed `Extra High`, or an exact backend/model target is unavailable, enter `WAITING_HUMAN`.

The baseline observation showed GPT-5.5 as `Instant`; this is a mode label, not a general reasoning level. GPT-5.3 and o3 support must be checked live rather than inferred. Grok reasoning ambiguity is reported rather than guessed; permitted fallback stays inside ChatGPT Web.

## 10. Review package

Each reviewer receives at most three uploaded files, regardless of how many source files changed:

1. `review-request.yaml` — task, base/head SHAs, package digest, requirements, risk focus, validation evidence, and requested verdict schema.
2. `full.diff` — the complete, untruncated diff for the exact base/head range.
3. `review-context.txt` — repository instructions and only the necessary surrounding context that is not represented by the diff.

The three-file limit is an upload-container rule, not a changed-file limit. `full.diff` can contain changes to any number of files. If a complete diff cannot fit the browser/tool limit, do not truncate it; split the task at a coherent boundary or enter `WAITING_HUMAN`.

Generate and validate `full.diff` deterministically with Git binary/full-index output, external diff and text conversion disabled, stable prefixes, and rename detection disabled. Symlink target/mode changes are included. Any binary changed path blocks package creation before transfer rather than being silently omitted.

Use `graph-review-package-v1` to break digest self-reference: canonicalize the unique quoted `package_digest` scalar to 64 ASCII zeroes, hash the canonical request plus exact diff/context bytes, and hash one exact LF-delimited manifest with the head SHA. Record both actual and canonical request hashes outside `review-request.yaml`; neither may be embedded in the file it hashes. The standard-library reference scripts provide a reproducible test vector and read-only verification.

## 11. Progressive disclosure layout

`SKILL.md` remains the routing and gate document and should stay under 300 lines, ideally around 220–300. Detailed contracts move to:

- `references/state-and-transitions.md`;
- `references/failure-matrix.md`;
- `references/browser-and-review-package.md`;
- `references/review-contract.md`.

A narrow `scripts/validate_run_state.py` validates a JSON snapshot against critical invariants. It is read-only and must never perform Git, browser, or repository mutations.

## 12. Acceptance criteria

- The skill passes the standard skill validator, or any validator dependency failure is reported precisely.
- Every referenced local file exists.
- No rule permits reasoning-level downgrade.
- Model identity and reasoning level are separate fields everywhere.
- Normal and high-risk mandatory pauses are exactly 1 hour and 3 hours of active work.
- The task-wide caps are exactly three review packages and two implementation reworks.
- Synthetic states prove rejection of package 4, rework 3, mismatched head/package, wrong reasoning level, and work after mandatory pause.
- Synthetic states reject delivery with pending High findings, forbidden backends and aliases, premature model fallback, malformed extensions, stale/self-reviewing/duplicate Reviewer records, incomplete paths, binary packages, and non-reproducible digests.
- The review contract clearly states that three uploads may represent changes to more than three source files.
- The final diff contains no unrelated changes and does not include the untracked source prompt from the main checkout.

## 13. PR #7 review rework

The first immutable review package at head `1e351d4e864d56f751d882cef85d0de6fd61d844` returned `CHANGES_REQUESTED`. The verified disposition is:

| Finding | Resolution |
|---|---|
| PR7-H1 package digest non-reproducible | Add `graph-review-package-v1`, canonical request hashing with request hashes recorded externally, exact manifest bytes, a reference script, and a fixed test vector. |
| PR7-H2 complete diff omits paths | Include symlink changes, compare exact deterministic Git diff bytes, and fail closed on binary changed paths. |
| PR7-H3 delivered with pending High | Reject every delivered/review-complete state with pending blocking/high findings and constrain Package 3 terminal status. |
| PR7-H4 backend fallback bypass | Enforce the canonical backend allowlist and highest-priority available Extra High-capable ChatGPT selection. |
| PR7-M1 extension unusable | Require the original pause, then validate a separately authorized higher active limit and deadline. |
| PR7-M2 Reviewer binding incomplete | Validate every reviewer identity/head/digest and enforce risk-class count only at review completion, not while a candidate is merely waiting. |

This is one accepted plan/contract correction and one batched implementation rework. Repository changes invalidate Package 1; the next verified candidate is Package 2 and requires a fresh independent verdict.
