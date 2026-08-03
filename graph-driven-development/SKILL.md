---
name: graph-driven-development
description: Coordinate complex software development in a fresh isolated worktree through a fixed auditable graph. Keep Codex as the only repository writer and use only ChatGPT Web plus Grok Web through the Codex built-in Browser for external cognitive roles. Enforce active-time pause limits, verified checkpoints, repository-derived tests, complete three-file review packages, independent read-only review including two reviewers for high risk, bounded rework, required PR CI, and cleanup after confirmed merge. Use when the user requests Graph or multiple models, names ChatGPT Pro or Grok as participants, requires independent reviewers, or requests risky cross-module work involving state machines, permissions, authentication, concurrency, migrations, or external side effects. Do not use for small edits, explanation-only work, diagnosis-only work, or ordinary one-shot review.
---

# Graph-Driven Development

Run one fixed cognitive graph inside a task-isolated delivery lifecycle:

```text
CREATE_TASK_WORKTREE → PREFLIGHT
→ N0 CONTRACT → N1 PLAN → N2 IMPLEMENT → N3 VERIFY
→ N4 INDEPENDENT_REVIEW → N5 VERIFY_FINDINGS → N6 HANDOFF
→ PUSH → PR → REQUIRED_CI → WAIT_FOR_MERGE
→ VERIFIED_CLEANUP → DELIVERED
```

The current Codex session is the Orchestrator and only Repository Writer. External models are read-only cognitive participants.

## Hard invariants

- Keep nodes N0–N6 fixed. Worktree, Git publication, CI, merge waiting, and cleanup are lifecycle operations, not new cognitive nodes.
- Use only canonical backends `chatgpt-web` and `grok-web` through the Codex built-in Browser for Advisor, implementation-author, Reviewer, or Arbiter work. Record ChatGPT account plan and visible model separately from backend.
- Never use Chrome, an API, CLI, local subagent, Claude, or another platform as a cognitive substitute.
- Use reasoning level `Extra High` for every external cognitive role. Model identity and reasoning level are separate; never reduce reasoning to handle quota.
- Let only Codex edit files, run repository mutations, and apply external proposals.
- Never let an implementation-authoring conversation review or arbitrate its own candidate.
- Use at most three review packages and two accepted-blocking/high implementation reworks for the whole task, including PR-CI repair loops.
- Treat checkpoint commits and review candidates as different gates.
- Never truncate a review diff.
- Merge, deploy, production mutation, credentials, funds, signing, and other real external side effects require separate explicit authorization.

Read [references/state-and-transitions.md](references/state-and-transitions.md) before starting. Its state fields, clocks, counters, and transition invariants are normative.

## Create a new worktree for every task

Before N0:

1. Read repository instructions and the authoritative roadmap, ADR, spec, plan, or runbook.
2. Inspect the source checkout, status, worktrees, remotes, and required base branch.
3. Preserve all existing and unowned changes. Never stash, clean, move, or reuse a dirty checkout.
4. Refresh the remote tracking ref when available.
5. Create a unique task branch from the required base. Follow repository rules; otherwise use `codex/<task-slug>`.
6. Create a linked worktree at a unique path outside the source checkout.
7. Record repository root, source checkout, worktree path, branch, base ref, and base commit.

Enter `WAITING_HUMAN` if ownership, base, remote, or a safe worktree path is ambiguous.

## Preflight the worktree

Before N0:

1. Read authoritative development, dependency, test, build, and CI configuration.
2. Verify required runtimes, package managers, repository scripts, and test entrypoints exist.
3. Reject virtual environments, shebangs, generated config, or cached paths bound to another checkout.
4. Record worktree-local bootstrap commands, runtime versions, CI sources, and required PR checks.
5. Run only bounded startup checks. Do not install/upgrade dependencies or touch remote/production systems without authorization.

Enter `WAITING_HUMAN` if the documented command surface cannot start safely. Do not defer toolchain discovery until N3.

## Start the active-time clock

Classify the task in N0:

| Class | Progress report | Soft pause | Mandatory pause |
|---|---:|---:|---:|
| Normal | 30 min | 45 min | 1 hour |
| High risk | 1 hour | 2 hours | 3 hours |

Count only active task work. Exclude recorded `WAITING_HUMAN`, required CI/merge queues, and unavailable external web sessions. At soft pause, stop starting new implementation units and report progress/risk. At the mandatory deadline, enter `WAITING_HUMAN` before any new implementation or review-package work. Only a new explicit user authorization may set a later absolute deadline.

## N0: Freeze the task contract

Create and show or save:

```yaml
objective: ""
in_scope: []
out_of_scope: []
acceptance_criteria: []
risk_level: normal  # normal | high_risk
required_participations: []
allowed_backends: [chatgpt-web, grok-web]
model_policy:
  required_reasoning_level: Extra High
  exact_reasoning_level_required: true
  exact_backend_required: false
  exact_model_required: false
ci_sources: []
test_commands: []
artifacts: []
required_pr_checks: []
permissions:
  repository_write: codex_only
  external_code_upload: allowed_after_secret_scan
  create_task_branch: allowed
  create_task_worktree: allowed
  checkpoint_commit: allowed_after_scoped_validation
  push: allowed_after_ready_for_delivery
  open_pull_request: allowed_after_push
  merge_pull_request: requires_separate_authorization
  cleanup_after_verified_merge: allowed
  deploy: denied
  production_mutation: denied
budgets:
  review_packages: 3
  implementation_reworks: 2
  plan_reworks: 1
```

Invoking this Skill authorizes only the listed branch/worktree, verified checkpoint-commit, ready-branch push, PR creation, and verified post-merge cleanup lifecycle. A current user instruction may narrow those permissions. It never authorizes merge, deploy, or production effects.

Express named participation explicitly with backend, role, task type, and minimum count. Backend/model substitution is allowed within the browser contract unless the user explicitly sets its `exact_*_required` flag. Reject any cognitive platform outside the allowlist.

Before implementation, complete [references/failure-matrix.md](references/failure-matrix.md). Pause on unexplained high-risk gaps or material scope expansion.

## N1: Advise and freeze the plan

Use an Advisor only when independent analysis materially improves the plan. Freeze:

- scope, steps, acceptance criteria, and failure matrix;
- exact required test commands derived from repository CI/scripts/configuration;
- path coverage and authoritative CI source for each gate;
- real deliverables and exact build/artifact inspection commands;
- required PR checks and minimum review evidence.

Do not invent a universal test command or omit a remote-only required check. Record unavailable local gates for required PR CI. Allow one bounded request for missing non-sensitive evidence, then enter `WAITING_HUMAN` if the plan cannot be frozen.

Freeze layered verification: targeted affected-module tests during N2; one complete local test, coverage, build, and artifact gate for each frozen candidate; after accepted review rework, targeted tests followed by one final complete gate and one re-review. Never call a narrow test a full gate, and do not rerun the full suite after every edit to an unfrozen candidate.

## N2: Implement with one Writer

Only Codex edits the repository. External participants may provide analysis, counterexamples, pseudocode, or a patch proposal.

For an external implementation author:

1. Send the frozen contract, only necessary tracked source, relevant tests, and an explicit output format.
2. Record backend, visible model, reasoning level, conversation URL/ID, input digest, and `task_type: implementation_author`.
3. Treat all returned code as untrusted. Check scope, dependencies, safety, and compatibility.
4. Codex applies/adapts the proposal and verifies the actual worktree state.

Before and after every write, preserve unrelated changes and confirm scope. If a change introduces a new subsystem, dependency, migration, permission boundary, external effect, or material design deviation, use the scope-expansion gate in the failure-matrix reference.

After an independently explainable implementation unit passes scoped validation, create a task-only checkpoint commit if the current contract permits it. Never commit a known-broken state, unrelated changes, or an individual tool action merely to increase checkpoint count. Prefer roughly 3–5 logical commits for a substantial task; exceeding that is a scope-growth signal, not an automatic failure.

## N3: Verify tests and artifacts

Run the exact frozen local commands. For every artifact:

1. build the real deliverable;
2. inspect the produced artifact, not only its source manifest;
3. verify required files, entrypoints, permissions, metadata, and migrations as applicable;
4. run the smallest safe smoke test against the artifact itself;
5. record identity/digest and evidence.

Route results:

| Result | Route |
|---|---|
| Required local gates and artifacts pass | build review candidate, then N4 |
| Implementation defect in an unfrozen candidate | N2; targeted repair, bounded by active time |
| Frozen plan wrong or scope changed materially | N1 or `WAITING_HUMAN` |
| Missing command, unavailable environment, indeterminate result | `WAITING_HUMAN` |

Do not substitute an easier test silently. A review candidate exists only when the exact head is verified and its immutable review package is generated. A later code change invalidates it.

## N4: Obtain two independent reviews

Read both of these completely before preparing inputs or interpreting output:

- [references/browser-and-review-package.md](references/browser-and-review-package.md)
- [references/review-contract.md](references/review-contract.md)

High-risk tasks require two independent read-only Reviewer conversations. Normal-risk tasks require at least one unless the contract requires two. When two are used, start them in parallel by default, give both the same package digest/head, and hide each verdict from the other. Prefer different backends, but do not treat that preference as an exact requirement unless `exact_backend_required: true`.

The three uploaded files are always:

1. `review-request.yaml`;
2. `full.diff`;
3. `review-context.txt`.

This is not a three-source-file limit. `full.diff` may contain any number of changed files. If a complete safe diff cannot fit, split the task coherently or enter `WAITING_HUMAN`; never truncate it.

Validate `full.diff` with `scripts/validate_review_diff.py` before upload. Include symlink target/mode changes. Any binary changed path blocks package creation until the task is coherently split or a new approved contract makes the complete transfer safe. Compute and verify `graph-review-package-v1` with `scripts/compute_review_package_digest.py`; never invent package digest bytes manually.

Accept only `PASS`, `CHANGES_REQUESTED`, `NEEDS_EVIDENCE`, or `BACKEND_FAILED`. Allow one bounded evidence supplement per Reviewer. Backend retries and re-uploads of an identical package do not consume another review-package count.

## N5: Verify every finding

Normalize every finding using the review contract. Enforce:

```text
total findings = accepted + advisory + overruled_by_arbiter + unresolved
```

Batch accepted `blocking/high` implementation findings from a round, persist one rework increment, then route once to N2. An implementation-caused required PR-CI failure uses the same global budget. Route plan findings to N1 and contract/scope findings to `WAITING_HUMAN`. Medium/low findings are advisory and cannot independently trigger N5 → N2.

Send disputed `blocking/high` findings to a fresh read-only Arbiter distinct from the Writer, Reviewer, and involved implementation author. If none is available within the two approved backends while preserving independence, enter `WAITING_HUMAN`.

Rework requires re-verification and a new review candidate. Do not start package 4 or implementation rework 3.

## N6: Produce the local handoff

Enter N6 only when:

- preflight passed;
- all locally executable frozen gates pass;
- artifacts are verified or explicitly empty;
- required participation and independent review are satisfied;
- every finding is classified and none blocking/high remains unresolved;
- the diff remains in scope;
- state invariants pass `scripts/validate_run_state.py` when a `run.json` is used.

Report objective, files, tests/artifacts, participant identities and independence, findings, counters, checkpoints, branch/worktree, delivery status, and every unperformed or separately authorized action.

`READY_FOR_DELIVERY` requires that task changes are verified and checkpointed as permitted by the contract.

## Publish, wait, and clean up

When the contract still authorizes delivery and N6 is ready:

1. Confirm the worktree is clean, commits are scoped, and evidence applies to the exact head.
2. Push only the recorded task branch.
3. Open one PR against the required base and report evidence plus explicit merge/deploy exclusions.
4. Wait for every frozen required check on the same remote head.
5. Route implementation-caused CI repair to N2 using the remaining global rework budget. Re-verify and re-review any changed head using the remaining package budget.
6. Enter `WAITING_FOR_MERGE` after all required checks pass. Do not merge without separate authorization.
7. After authoritative merge confirmation, prove the recorded worktree is clean and has no unpushed/unmerged work.
8. Remove only that worktree. Delete its local branch when no worktree uses it and policy allows. Delete the remote branch only with authorization or confirmed platform auto-delete.
9. Inspect remaining branches/worktrees for unmerged work and report it; never delete unrelated branches automatically.

If merge, cleanliness, ownership, or exact target identity is uncertain, enter `WAITING_HUMAN` and remove nothing.

## Terminal behavior

Use terminal states `WAITING_HUMAN`, `DELIVERED`, `FAILED`, or `CANCELLED`. Lifecycle gates such as `READY_FOR_DELIVERY`, `PR_CHECKS_PASSED`, `WAITING_FOR_MERGE`, and `MERGED` are non-terminal.

Do not promise automatic recovery. Reconstruct from the recorded worktree, branch, head, test/artifact evidence, package digest, counters, PR checks, and saved web conversation URLs/IDs.
