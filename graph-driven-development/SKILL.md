---
name: graph-driven-development
description: Coordinate complex software development through a fixed, auditable multi-agent graph with Codex as the only repository writer, external models optionally authoring implementation candidates, deterministic test gates, independent read-only review, evidence-based finding verification, and bounded rework. Use when the user explicitly requests Graph collaboration or multiple agents/models, wants ChatGPT Pro, Grok, or Claude to generate code for Codex to apply, requires named models or multiple reviewers to participate, or asks for a risky cross-module change involving state machines, permissions, authentication, concurrency, migrations, or external side effects. Do not use for small single-file edits, explanation-only work, diagnosis-only work, or an ordinary one-shot code review.
---

# Graph-Driven Development

Use one fixed V1 workflow:

```text
TASK_CONTRACT
→ ADVISE_AND_FREEZE_PLAN
→ IMPLEMENT
→ TEST
→ INDEPENDENT_REVIEW
→ VERIFY_FINDINGS
→ LOCAL_HANDOFF
→ READY_FOR_DELIVERY
```

Keep the current Codex control session as both Orchestrator and the only Repository Writer. Treat every other agent or model as a read-only cognitive participant.

## Preserve the V1 boundary

- Use the fixed seven-node flow. Do not add, delete, reorder, or configure nodes.
- Assign available backends to `Advisor`, `Reviewer`, or `Arbiter` based on the task, required context, independence, availability, and model strengths.
- Treat `implementation_author` as an Advisor task type, not a fourth cognitive role.
- Do not permanently bind a model to a role.
- Never count the current Writer as Reviewer or Arbiter.
- Never let an implementation-authoring session review or arbitrate its own candidate.
- End at local `READY_FOR_DELIVERY`.
- Do not commit, push, open a PR, deploy, or mutate production under this Skill. Hand those actions to the relevant workflow after completion.
- Do not create a transition engine, event log, lock manager, recovery system, generic source packager, delivery transaction, or arbitrary budget DSL.

## Route backends dynamically

Use this stable routing table:

| Backend class | Default use | Hard limit |
|---|---|---|
| Current Codex control session | Orchestrator and Repository Writer | Never count it as Reviewer or Arbiter |
| External model such as ChatGPT Pro, Grok, or Claude | Advisor, `implementation_author`, Reviewer, or Arbiter | Never grant repository write access; separate authoring from review and arbitration |
| Local agent with enforced read-only access | Advisor, Reviewer, or Arbiter | Exclude it when workspace write access cannot be reliably restricted |

Choose a backend at runtime:

1. Honor explicit `required_participations` before preferences.
2. Verify current availability, usable context surface, and read-only capability.
3. Match the task to the backend instead of assuming one model is always best.
4. For high risk, separate implementation authors from Reviewers and prefer different backends.
5. Record the backend, model when visible, role, task type, session ID, and selection reason.

Do not hardcode subscriptions, live availability, or a permanent model ranking. Apply the bounded fallback rules when a preferred backend is unavailable.

## Maintain the task state

Maintain the following lightweight state in the current task plan or an optional atomically replaced `run.json`:

```yaml
status: ACTIVE
current_node: N0
contract_hash: sha256
plan_version: 1
implementation_rework_used: 0
plan_rework_used: 0
required_participations: []
test_results: []
reviews: []
findings: []
implementation_authors: []
```

Use only these terminal states:

```text
WAITING_HUMAN
READY_FOR_DELIVERY
FAILED
CANCELLED
```

Do not promise automatic resume after an app, terminal, process, or machine failure. Reconstruct a new run from the current Diff, test evidence, and saved review conversations when necessary.

## N0: Create the task contract

Create and show or save this contract before implementation:

```yaml
objective: ""
in_scope: []
out_of_scope: []
acceptance_criteria: []
risk_level: normal  # normal | high
required_participations: []
preferred_backends: []
test_commands: []
permissions:
  repository_write: codex_only
  external_code_upload: allowed
budgets:
  implementation_rework: 2
  plan_rework: 1
  backend_fallbacks_per_role: 2
```

Express mandatory participation directly:

```yaml
required_participations:
  - backend_id: chatgpt-pro
    role: advisor
    task_type: implementation_author
    min_count: 1
```

- Resolve a user-named backend without a role to `advisor` or `reviewer` according to the task.
- Use `task_type: implementation_author` when the backend must return code or a patch for Codex to evaluate and apply.
- Enter `WAITING_HUMAN` when choosing the role would materially change the user's intent.
- Treat `preferred_backends` as replaceable.
- Treat `required_participations` as non-replaceable unless the user changes the contract.
- Reconcile every required participation in the final report.

## N1: Advise and freeze the plan

Use one or more Advisors only when their independent analysis materially improves the plan.

Freeze:

- task scope;
- implementation steps;
- acceptance criteria;
- exact required test commands;
- the minimum evidence required by Reviewers.

Allow at most one request for missing non-sensitive evidence. Enter `WAITING_HUMAN` if the plan still cannot be frozen.

## N2: Implement with one Writer

Let only the current Codex control session edit the repository.

Accept analysis, pseudocode, patch suggestions, and counterexamples from cognitive participants, but apply all repository changes yourself.

When using an external implementation author:

1. Send the frozen contract, necessary tracked source, relevant tests, and explicit output format.
2. Ask for a complete implementation candidate or unified Diff plus assumptions and test recommendations.
3. Record the backend, model, conversation ID, input hash, and `task_type: implementation_author`.
4. Treat the returned code as an untrusted proposal. Verify scope, dependencies, safety, and compatibility before applying it.
5. Apply or adapt the candidate only through the current Codex Writer, then run the frozen tests against the actual repository state.

Do not claim that externally authored code was implemented until Codex has written and tested it in the current workspace.

Before and after each write:

- verify that the change remains inside `in_scope`;
- preserve unrelated user changes;
- reject unauthorized files and side effects;
- keep external participants read-only.

Do not use a local agent for any cognitive role if its write access to the current workspace cannot be reliably restricted.

## N3: Run the frozen tests

Run only the commands frozen at N1.

Route each result:

| Result | Route |
|---|---|
| All required tests pass | N4 |
| Implementation defect | N2; consume one implementation rework |
| Frozen plan is wrong | N1; consume one plan rework |
| Command missing, environment unavailable, or result indeterminate | `WAITING_HUMAN` |

Do not silently substitute a fallback test. Return to N1 to freeze a changed command.

Set `FAILED` after two implementation reworks. Enter `WAITING_HUMAN` after one plan rework is exhausted.

## N4: Obtain independent Review

Read [references/review-contract.md](references/review-contract.md) completely before preparing review inputs or interpreting a Reviewer or Arbiter response.

For normal risk, obtain at least one Reviewer. For high risk, obtain at least two Reviewers and prefer different backends.

Require every Reviewer to:

- use a fresh session;
- remain read-only;
- receive only the frozen objective, required context, Diff, and test evidence;
- have made no implementation writes;
- differ from the current Codex Writer session;
- not be any session recorded in `implementation_authors`.

Accept only:

```text
PASS
CHANGES_REQUESTED
NEEDS_EVIDENCE
BACKEND_FAILED
```

Allow one `NEEDS_EVIDENCE` response per Reviewer. On `BACKEND_FAILED`, use at most two fallback attempts for that role. Enter `WAITING_HUMAN` when a required backend remains unavailable.

## Transfer source safely

For ChatGPT Pro, Grok, or another external backend, send only:

- explicitly listed Git-tracked text files;
- the task's Git Diff;
- test summaries and necessary log excerpts.

Exclude:

- `.env` files, tokens, secrets, keys, certificates, and secret directories;
- databases, real user data, unrelated logs, and unrelated files;
- binaries, symlinks, and unlisted untracked files.

Apply a path denylist and inspect content for secrets before transfer. Enter `WAITING_HUMAN` if a minimal safe review package cannot be formed. Do not build a generic packager in V1.

## N5: Verify every finding

Normalize every Review artifact using the format in [references/review-contract.md](references/review-contract.md). Import all findings; never select only convenient findings.

Enforce:

```text
total findings
= accepted
+ advisory
+ overruled_by_arbiter
+ unresolved
```

Route:

- accepted `blocking/high` implementation finding → N2;
- accepted `blocking/high` plan finding → N1;
- `blocking/high` contract finding → `WAITING_HUMAN`;
- `medium/low` finding → advisory;
- disputed `blocking/high` finding → a fresh Arbiter distinct from the Writer, original Reviewer, and relevant implementation author.

If no qualified Arbiter is available, enter `WAITING_HUMAN`.

Count N5-triggered implementation and plan returns against the same global rework budgets used by N3. Keep an accepted `blocking/high` finding unresolved until rework, retesting, and re-review all complete.

## N6: Produce the local handoff

Enter N6 only when:

- every frozen required test passes;
- every `required_participations` entry is satisfied;
- each Reviewer and Arbiter satisfies fresh-session and read-only requirements;
- every finding is classified;
- no unresolved `blocking/high` finding remains;
- the workspace Diff remains within scope.

Produce `final-report.md` or an equivalent final response containing:

1. objective, scope, and final state;
2. modified files;
3. passed, failed, and unrun tests;
4. each agent's backend, role, task type, contribution, and session independence;
5. required participation reconciliation;
6. every finding and its final classification;
7. implementation and plan rework counts;
8. commit, push, PR, deploy, and production actions not performed;
9. the recommended delivery workflow or human action.

Report `READY_FOR_DELIVERY` only after every gate passes.

## Keep loops bounded

Use exactly these budgets:

| Budget | Default | Exhaustion |
|---|---:|---|
| implementation rework | 2 | `FAILED` |
| plan rework | 1 | `WAITING_HUMAN` |
| needs evidence per Reviewer | 1 | replace Reviewer; otherwise `WAITING_HUMAN` |
| backend fallbacks per role | 2 | required role waits; optional Advisor skips |

Pause when scope, permissions, or acceptance criteria materially change. Do not automatically loop on a changed contract.
