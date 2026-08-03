# Graph-Driven Development v1.2 Simplification Spec

Status: Implemented locally; verification complete
Date: 2026-08-03
Owner: Codex
Target: `graph-driven-development/`

## 1. Context

Graph-Driven Development has the right core direction: isolate every task, keep Codex as the only repository writer, verify real repository behavior and artifacts, obtain independent read-only review, preserve authorization boundaries, and clean up only after confirmed merge.

The v1.1 hardening work made several of those rules mechanically checkable, but it also moved too much policy into an internal state machine and a custom review-package protocol. The resulting Skill now spends disproportionate complexity proving that its own records are internally consistent. Package 3 then reached the hard rework ceiling while still containing accepted High findings, forcing a separately authorized ordinary repair task. That is evidence that some controls now create artificial process boundaries rather than directly reducing delivery risk.

v1.2 is a subtraction release. It preserves the delivery graph and safety boundaries while removing validation machinery that does not prove external reality.

## 2. Outcome

Make the Skill easier to trigger correctly, operate, resume, and maintain without weakening the controls that prevent real repository, review, authorization, or production mistakes.

The intended result is a coordination workflow with proportional gates, not a general workflow engine or a cryptographic transport protocol.

## 3. Design principles

1. Preserve controls that prevent real external harm or false delivery claims.
2. Prefer repository and platform truth over self-declared run-state truth.
3. Use machine validation only where deterministic validation materially improves safety.
4. Use explicit human authorization for continuation instead of manufacturing a new task boundary.
5. Keep normal Graph work lighter than high-risk Graph work.
6. Keep volatile model inventory as observed policy evidence, not hard-coded validator logic.
7. Keep one source of truth for each rule and avoid copying constants into every task contract.
8. Do not add a replacement framework while removing the current one.

## 4. Preserved invariants

v1.2 must preserve all of the following:

- a fresh task branch and isolated worktree for every Graph task;
- Codex as the only repository writer and mutation executor;
- ChatGPT Web and Grok Web through the Codex built-in Browser as the only external cognitive backends;
- backend-specific approved web profiles with live selection evidence, without confusing model, UI mode, or reasoning level;
- frozen objective, scope, acceptance criteria, risk class, and repository-derived verification gates;
- real deliverable construction and artifact inspection where artifacts exist;
- external implementation proposals treated as untrusted input;
- independent read-only review, including two Reviewers for high-risk work;
- no self-review by an implementation-authoring conversation;
- complete, untruncated task diff transfer;
- secret and sensitive-data exclusion before external upload;
- exact reviewed head/package binding and invalidation after any repository-content change;
- separate authorization for merge, deploy, production mutation, credentials, funds, signing, and other real external effects;
- authoritative merge confirmation before cleanup;
- preservation and reporting of unrelated worktrees and branches.

The N0–N6 cognitive graph remains unchanged:

```text
N0 CONTRACT → N1 PLAN → N2 IMPLEMENT → N3 VERIFY
→ N4 INDEPENDENT_REVIEW → N5 VERIFY_FINDINGS → N6 HANDOFF
```

Worktree creation, publication, PR CI, merge waiting, and cleanup remain lifecycle operations around that graph.

## 5. Non-goals

- Do not change the allowed cognitive platforms.
- Do not lower or dynamically tune reasoning level.
- Do not remove independent review or high-risk dual review.
- Do not remove repository-derived tests, artifact validation, or complete-diff validation.
- Do not authorize merge, deploy, production, funds, credentials, or signing implicitly.
- Do not add hooks, a daemon, a database, a generic workflow engine, or a browser automation framework.
- Do not add a new runtime dependency for package or state validation.
- Do not optimize historical v1.1 run records or rewrite their evidence.
- Do not make normal one-shot reviews, explanations, or diagnoses enter Graph.

## 6. Trigger contract

Use Graph when at least one of these is true:

1. the user explicitly invokes Graph or `$graph-driven-development` for a development task;
2. the requested implementation is high risk across state machines, permissions, authentication, concurrency, migrations, recovery, or real external side effects;
3. the user requests a multi-stage development workflow with external implementation participation plus independent review.

The following are not sufficient triggers by themselves:

- naming ChatGPT Pro or Grok;
- requesting multiple opinions;
- asking for a one-shot review, Advisor answer, explanation, or diagnosis;
- making a small or isolated edit without high-risk behavior.

The frontmatter description and `agents/openai.yaml` default prompt must express the same trigger boundary without contradiction.

## 7. Proportional execution lanes

Both lanes use N0–N6, but their evidence burden differs.

### Normal Graph task

- Freeze objective, scope, acceptance criteria, tests, artifacts, participation, and authorization boundaries.
- Record concise `risk_notes` covering the applicable failure modes and rollback/containment approach.
- Use at least one independent Reviewer.
- Keep run state in the task plan or handoff; a standalone `run.json` is optional.

### High-risk Graph task

- Freeze the complete failure matrix.
- Use two independent Reviewer conversations.
- Persist the minimal run-state snapshot before review and before delivery.
- Require explicit abnormal-path, recovery, permission, concurrency, persistence, and external-effect evidence where applicable.

Normal tasks must not be forced to fill a full matrix with mostly `not_applicable` rows. High-risk tasks must not use the normal lane to avoid evidence.

## 8. Time and rework budgets

Keep the existing mandatory active-work pauses:

| Task class | Mandatory pause |
|---|---:|
| Normal | 1 hour |
| High risk | 3 hours |

Keep three review packages and two implementation reworks as default pause thresholds, not absolute correctness ceilings.

When a time or rework threshold is reached:

1. stop at the smallest safe boundary;
2. enter `WAITING_HUMAN` and report the exact head, evidence, unresolved risks, and counters;
3. continue only after explicit user authorization;
4. preserve and continue the counters rather than resetting them or creating a disguised fresh run.

An authorization may set a new active-time, package, or rework limit. The saved state needs the new limit and a non-empty authorization reference. It does not need second-level forensic proof that the authorization timestamp is later than the pause timestamp.

No Package number is inherently invalid after explicit continuation authorization. Silent extension remains invalid.

## 9. Minimal run state

Introduce a simplified schema for new v1.2 runs. It contains only release-critical state:

```json
{
  "schema_version": 3,
  "status": "ACTIVE",
  "state": "PREFLIGHT",
  "task_class": "normal",
  "task_worktree": "",
  "task_branch": "",
  "base_commit": "",
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

Reviewer records retain only evidence needed for independence and release:

- conversation ID;
- backend, visible model, exact UI selection label, separately exposed reasoning setting when present, and Browser evidence reference;
- read-only and non-authoring confirmation;
- reviewed head and package ID;
- verdict, completion time, reconciliation status, and remaining blocking/high status.

The run-state validator must check only:

- canonical status/state values;
- default limits and explicit authorization for raised limits;
- mandatory pause when active work reaches the current limit;
- non-empty and matching head/verified-head/package evidence at review completion;
- required Reviewer count, independence, allowed backend, non-empty selection evidence, head/package match, and final PASS evidence;
- no pending accepted blocking/high finding in success states.

The validator must not attempt to prove live browser inventory, real CI status, worktree cleanliness, Git ancestry, wall-clock history, or external authorization authenticity from self-declared JSON. Those remain explicit external checks.

## 10. Review package v2

Keep exactly three uploaded files, but replace the self-referential YAML digest protocol:

```text
review-package/
├── review-request.json
├── full.diff
└── review-context.txt
```

`review-request.json` contains the frozen review request plus:

- package version `graph-review-package-v2`;
- package sequence;
- base and head commits;
- declared `full.diff` and `review-context.txt` SHA-256 values;
- required verdict schema and prohibited actions.

It does not contain its own SHA or the final package ID.

Compute the package ID outside all three files from exact bytes:

```text
graph-review-package-v2
head_sha=<head>
review_request_sha256=<sha256 exact request bytes>
full_diff_sha256=<sha256 exact diff bytes>
review_context_sha256=<sha256 exact context bytes>
```

The package ID is `sha256:` plus the SHA-256 of those LF-delimited manifest bytes. Send the package ID in the Browser message accompanying the three files and record it in run evidence. Require the Reviewer to return it with the reviewed head.

The reference tool may use the Python standard-library JSON parser to reject duplicate keys and validate declared head/diff/context values. It must not implement a YAML parser, canonical zero replacement, embedded self hash, reserved field-name scan, or actual-versus-canonical request hash pair.

Preserve `validate_review_diff.py` protection against truncated or configuration-hidden paths. Package v2 must remain invalid after any repository-content change.

## 11. Model and backend policy

Keep ChatGPT Web and Grok Web as the only external cognitive backends. Select the latest available model version exposed by each authenticated website under a currently approved UI profile. Exact model versions are runtime observations, not validator constants.

The current observed profiles on 2026-08-03 are:

| Backend | UI selection | Visible model | Separate reasoning setting | Use |
|---|---|---|---|---|
| `chatgpt-web` | `Pro` | `GPT-5.6 Sol Pro` | not separately exposed | primary formal profile |
| `chatgpt-web` | `Extra High` | `GPT-5.6 Sol` | `Extra High` | fallback when Pro is unavailable or quota-limited |
| `grok-web` | `Expert` | `Grok 4.5` | not separately exposed | highest formal profile available under the current subscription |

`Pro` and `Extra High` are alternative ChatGPT Web selections. Never record or require a fictitious `Pro + Extra High` combination. `Expert` is a Grok UI mode, not an OpenAI reasoning level; never invent a cross-provider `Extra High` equivalence.

At runtime:

1. inspect the live website menu when the backend is first needed;
2. record the backend, account plan when visible, visible model, exact selection label, separately exposed reasoning setting or `null`, and Browser evidence reference;
3. use ChatGPT `Pro` first, then ChatGPT `Extra High` when Pro is unavailable or quota-limited;
4. use Grok `Expert`; do not require unavailable `Heavy`, and do not use `Auto`, `Fast`, or `Build` for a formal cognitive role;
5. do not use ChatGPT `High`, `Medium`, `Instant`, or a silent mini fallback for a formal cognitive role;
6. if Grok is unavailable, a fresh independent ChatGPT conversation may fill the slot only when the frozen contract does not require Grok exactly; if no approved profile remains, enter `WAITING_HUMAN`.

When a provider upgrades the visible model while the approved selection semantics remain intact, use the newer version and record the new observation without changing the graph, state schema, or validator. If the selection semantics change or the role-quality mapping cannot be established from current first-party UI evidence, enter `WAITING_HUMAN` until the browser policy is updated.

Do not hard-code `GPT-5.6`, `Grok 4.5`, or a model ranking in `validate_run_state.py`. The validator checks allowlisted backend plus complete selection/evidence fields; the Browser policy owns the current profile mapping.

## 12. Failure matrix and binary changes

The complete failure matrix is mandatory only for high-risk tasks or when an applicable risk domain emerges. Normal tasks use concise risk notes.

Binary changes are not automatically forbidden. The diff validator must report binary paths, modes, and object hashes. A binary change may proceed when:

- its path is in scope and passes secret/sensitive-path checks;
- Codex inspects the real artifact with an appropriate viewer or smoke test;
- its identity and evidence are recorded in the review context;
- correctness does not depend on an opaque property that the required Reviewer cannot evaluate.

Enter `WAITING_HUMAN` or split the task when the binary content itself is security-critical, cannot be safely transferred or inspected, or is essential to a Reviewer decision without adequate evidence.

## 13. Authorization boundaries

v1.2 does not broaden authority. Preserve these independent actions:

- local file modification;
- branch/worktree creation;
- checkpoint commit;
- push;
- PR creation;
- merge;
- deploy and remote/production mutation;
- credentials, funds, signing, and orders.

The Skill may retain the user's standing bounded authorization for branch/worktree creation, verified checkpoint commits, ready-branch push, PR creation, and verified post-merge cleanup. Merge and every production or real external effect still require separate explicit authorization.

## 14. Migration

- New tasks started after v1.2 adoption use package v2 and state schema v3.
- Historical v1.1 evidence remains readable and must not be rewritten.
- An active v1.1 task may finish under its frozen contract or migrate only after the user approves the changed evidence contract.
- Do not maintain two executable package/state protocols by default. Preserve v1.1 through Git history and documentation; retain executable compatibility only if a currently active task explicitly depends on it.
- Update the v1.1 spec status to reflect that its repair was committed, pushed, and merged; do not rewrite its historical review narrative.

## 15. Acceptance criteria

1. The trigger description does not activate Graph merely because a model is named or a one-shot review is requested.
2. N0–N6, task worktree isolation, Codex-only writes, repository-derived verification, independent review, and authorization boundaries remain intact.
3. Normal tasks can complete without a full failure matrix or standalone `run.json`; high-risk tasks still require both proportional evidence and two Reviewers.
4. Package/rework thresholds force `WAITING_HUMAN` but an explicit authorization can raise the saved limits without resetting counters or starting a disguised new run.
5. The active-time limits remain exactly 1 hour for normal and 3 hours for high risk; an extension requires an authorization reference but not strict timestamp choreography.
6. New review packages use `review-request.json`, `full.diff`, and `review-context.txt` with a reproducible external `graph-review-package-v2` ID and no self-reference.
7. Mutating any package file or the head changes the package ID; stale declared head/diff/context values fail validation.
8. No custom YAML lexical parser, canonical request hash, embedded package digest placeholder, or reserved-field scan remains in the v2 path.
9. The run-state validator is limited to release-critical invariants, contains no concrete model versions, and accepts backend-appropriate nullable reasoning settings when the UI selection and Browser evidence are recorded.
10. A newer visible model does not block an otherwise approved profile; ambiguity pauses only when it changes the meaning or quality of the selected profile.
11. Complete textual diffs remain untruncated and path-complete under hostile Git configuration.
12. In-scope binary changes with safe hash plus real artifact evidence can proceed; opaque critical binary changes still fail closed.
13. Existing independent-review, no-self-review, secret-transfer, merge, production, and cleanup protections have regression coverage.
14. Runtime instructions contain no stale v1.1-only field, package, or state requirement.
15. The official Skill validator passes when its PyYAML runtime dependency is available; missing dependency is reported as an environment limitation rather than a Skill failure.

## 16. Delivery boundary

The user accepted this spec and authorized local implementation on 2026-08-03. Commit, push, PR, merge, dependency installation, and cleanup remain separately unauthorized.
