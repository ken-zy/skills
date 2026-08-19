---
name: graph-driven-development
description: Coordinate software delivery through an isolated, auditable graph when the user explicitly requests Graph for a development task, the implementation has material state/permission/authentication/concurrency/migration/recovery/external-effect risk, or a multi-stage external implementation plus independent review is required. Keep Codex as the only repository writer and use only ChatGPT Web or Grok Web through the Codex built-in Browser or a connected Chrome browser for cognitive roles. Do not trigger merely because ChatGPT Pro or Grok is named, multiple opinions are requested, or the task is a one-shot review, explanation, diagnosis, or small isolated edit.
---

# Graph-Driven Development

Use one fixed cognitive graph inside an isolated delivery lifecycle:

```text
CREATE_TASK_WORKTREE → PREFLIGHT
→ N0 CONTRACT → N1 PLAN → N2 IMPLEMENT → N3 VERIFY
→ N4 INDEPENDENT_REVIEW → N5 VERIFY_FINDINGS → N6 HANDOFF
→ PUSH → PR → REQUIRED_CI → WAIT_FOR_MERGE
→ VERIFIED_CLEANUP → DELIVERED
```

Codex is the Orchestrator and only Repository Writer. External models are read-only cognitive participants.

## Hard invariants

- Keep N0–N6 fixed. Risk classification is a gate inside PREFLIGHT/N0, not another node.
- Create a fresh task branch and linked worktree for every Graph task.
- Use only `chatgpt-web` and `grok-web` through either the Codex built-in Browser or a connected Chrome browser controlled by Codex for external cognitive roles. Honor an explicit user browser choice; otherwise either allowed surface is valid. Never substitute a direct API, standalone Playwright, OpenCLI, a model CLI, local subagent, Claude, or another platform.
- Keep model identity, UI selection, and separately exposed reasoning setting distinct. Use only an approved live-observed profile from the Browser reference; never invent `Pro + Extra High` or a cross-provider reasoning equivalence.
- Let only Codex edit files, run repository mutations, and apply external proposals.
- Never let an implementation-authoring conversation review or arbitrate its own candidate.
- Derive tests and required PR checks from repository truth. Build and inspect real deliverables.
- Give Reviewers a complete, untruncated diff bound to the exact verified head.
- Keep merge, deploy, production mutation, credentials, funds, signing, orders, and other real external effects behind separate explicit authorization.

Read [references/state-and-transitions.md](references/state-and-transitions.md) before starting. Read the Browser and review references before using an external participant.

## Create and preflight the task worktree

Before N0:

1. Read repository instructions and the authoritative roadmap, ADR, spec, plan, or runbook.
2. Inspect the source checkout, status, worktrees, remotes, and required base branch.
3. Preserve existing or unowned changes. Never stash, clean, move, or reuse a dirty checkout.
4. Refresh the required tracking ref when available, create a unique task branch, and create a linked worktree outside the source checkout.
5. Record repository root, source checkout, worktree, branch, base ref, and base commit.
6. Discover worktree-local runtimes, package managers, repository scripts, CI sources, test entrypoints, and artifact commands. Reject cached paths or environments bound to another checkout.
7. Run only bounded startup checks. Do not install dependencies or touch remote/production systems without authorization.

Enter `WAITING_HUMAN` if ownership, base, remote, worktree path, or the documented command surface is ambiguous.

## N0: Freeze the contract and classify risk

Freeze objective, in/out of scope, acceptance criteria, tests, artifacts, participation, and authorization boundaries. Classify inside N0:

- `normal`: the change has bounded local effects and does not materially alter authentication, permissions, durable state, concurrency, migrations, recovery, or real external effects. Record concise `risk_notes`, including applicable failure behavior and containment/rollback.
- `high_risk`: the change touches one or more of those domains, can produce an unknown/irreversible outcome, or a failure could cross a security, data, production, or financial boundary. Complete the full [failure matrix](references/failure-matrix.md).

When evidence is insufficient to classify safely, use `high_risk` or pause; do not create a new graph node.

Normal tasks require at least one independent Reviewer and may keep state in the plan/handoff. High-risk tasks require two independent Reviewers and a minimal schema-v3 snapshot before review and delivery.

Record permissions explicitly. This Skill retains the user's standing bounded authorization for task branch/worktree creation, verified checkpoint commits, ready-branch push, PR creation, and verified post-merge cleanup; a current instruction may narrow it. It never authorizes merge, deploy, production, credentials, funds, signing, or orders.

## Active-time and rework pauses

| Task class | Progress report | Soft pause | Mandatory pause |
|---|---:|---:|---:|
| Normal | 30 min | 45 min | 1 hour |
| High risk | 1 hour | 2 hours | 3 hours |

Count active planning, implementation, verification, packaging, review, and reconciliation. Exclude recorded human waits, required CI/merge queues, and unavailable required web sessions.

Three review packages and two accepted blocking/high implementation reworks are default pause thresholds. At a time or rework threshold, stop at the smallest safe boundary, enter `WAITING_HUMAN`, and report the exact head, evidence, unresolved risks, and counters. A new explicit user authorization may raise the saved limit; preserve counters and do not disguise continuation as a fresh run.

## N1: Freeze a repository-derived plan

Use an Advisor only when independent analysis materially improves the plan. Freeze:

- scope, steps, acceptance criteria, and proportional risk evidence;
- exact affected-module and full-gate commands derived from repository scripts and CI configuration;
- path coverage and the authoritative source of required PR checks;
- real deliverables and artifact inspection/smoke-test commands;
- required review evidence and participation.

Do not invent a universal test command or call a narrow test the full gate. Record remote-only checks for PR CI. Pause on material scope expansion or an indeterminate required gate.

## N2: Implement with Codex as the only Writer

External participants may provide analysis, counterexamples, pseudocode, or a patch proposal, but never repository writes.

Treat an external proposal as untrusted input. Record backend, visible model, exact UI selection, separately exposed reasoning setting or `null`, Browser evidence, conversation ID/URL, role, and input evidence. Codex checks scope, dependencies, safety, and compatibility before applying it, then verifies the actual worktree state.

After an independently explainable unit passes scoped validation, create a task-only checkpoint commit when authorized. Never commit a known-broken state or unrelated changes. A new subsystem, dependency, migration, permission boundary, external effect, or material design deviation triggers the scope gate in the failure-matrix reference.

## N3: Verify tests and artifacts

Run the exact frozen commands. For every deliverable:

1. build the real artifact;
2. inspect the artifact itself, not only its source manifest;
3. verify required files, entrypoints, permissions, metadata, and migrations as applicable;
4. run the smallest safe smoke test against it;
5. record identity/digest and evidence.

An implementation defect routes to N2; a wrong frozen plan routes to N1; an unavailable or indeterminate required gate routes to `WAITING_HUMAN`. A review candidate exists only when the exact Git head is verified and Review Package v2 is generated. Any repository-content change invalidates both.

## N4: Obtain independent review

Read completely:

- [references/browser-and-review-package.md](references/browser-and-review-package.md)
- [references/review-contract.md](references/review-contract.md)

Normal tasks require at least one fresh read-only Reviewer; high-risk tasks require two. When two are required, use separate conversations, send the identical package/head, and hide each verdict from the other. Different backends are preferred, not required unless the frozen contract says so.

Every Reviewer receives exactly three uploaded files:

1. `review-request.json`;
2. `full.diff`;
3. `review-context.txt`.

This is not a three-source-file limit: `full.diff` may cover any number of changed files. Validate it with `scripts/validate_review_diff.py`, scan the transfer for secrets/sensitive data, then compute the external `graph-review-package-v2` ID with `scripts/compute_review_package_digest.py`. Send the package ID in the Browser message and require the Reviewer to echo it with the reviewed head.

Binary changes are not automatically rejected. They require safe paths, recorded mode/object evidence, real artifact inspection, and enough non-opaque evidence for the required review. Split or pause for security-critical or uninspectable binary content.

Accept only `PASS`, `CHANGES_REQUESTED`, `NEEDS_EVIDENCE`, or `BACKEND_FAILED`. One bounded evidence supplement may answer `NEEDS_EVIDENCE` without changing the package. Upload/browser retries of identical inputs do not consume a new package count.

## N5: Verify findings and bound rework

Independently check every finding against the frozen contract, code, tests, and artifacts. Preserve:

```text
total findings = accepted + advisory + overruled_by_arbiter + unresolved
```

Batch accepted implementation `blocking/high` findings from a round into one rework, then return once to N2. Required PR-CI repairs use the same task-wide budget. Medium/low findings remain advisory and cannot independently trigger implementation rework.

Route plan findings to N1 and material contract/scope findings to `WAITING_HUMAN`. Send disputed blocking/high findings to a fresh read-only Arbiter that is independent of the Writer, Reviewer, and any implementation author. Rework requires re-verification and a new package for the changed head.

## N6: Handoff and publish

Enter N6 only when local gates and artifacts pass, proportional review is complete, all findings are reconciled, no blocking/high finding remains, the diff is in scope, and schema-v3 state validates when used.

Report objective, changed files, test/artifact evidence, participant identities and independence, findings, counters, checkpoints, branch/worktree, delivery status, and every action not performed or requiring separate authorization.

When bounded publication remains authorized:

1. prove the worktree is clean and evidence matches the exact head;
2. push only the task branch and open one PR against the frozen base;
3. wait for every required check on that same remote head;
4. route implementation-caused CI repair through the remaining rework/package budget;
5. enter `WAITING_FOR_MERGE` when checks pass; never infer merge authorization;
6. after authoritative merge confirmation, prove the task worktree has no unpushed or unmerged work;
7. remove only that worktree, delete only its eligible task branch, and inspect/report other unmerged branches without deleting them.

If merge, cleanliness, ownership, or target identity is uncertain, enter `WAITING_HUMAN` and remove nothing.

## Terminal behavior

Use only the canonical state vocabulary in the state reference. Terminal states are `WAITING_HUMAN`, `DELIVERED`, `FAILED`, and `CANCELLED`. Reconstruct a paused run from its worktree, branch, exact head, evidence, counters, package ID, PR checks, and saved conversation IDs; do not promise automatic recovery.
