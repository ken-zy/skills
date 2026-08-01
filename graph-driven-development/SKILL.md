---
name: graph-driven-development
description: Coordinate complex software development in an isolated task worktree through a fixed, auditable multi-agent graph with Codex as the only repository writer and ChatGPT Pro web plus Grok web as the only cognitive backends, both accessed exclusively through the Codex built-in Browser. Includes checkpoint commits after verified implementation steps, deterministic test gates, independent read-only review, evidence-based finding verification, bounded rework, final branch push and pull-request creation, and post-merge worktree cleanup. Use when the user explicitly requests Graph collaboration or multiple agents/models, wants ChatGPT Pro or Grok to generate code for Codex to apply, requires named models or multiple reviewers to participate, or asks for a risky cross-module change involving state machines, permissions, authentication, concurrency, migrations, or external side effects. Do not use for small single-file edits, explanation-only work, diagnosis-only work, or an ordinary one-shot code review.
---

# Graph-Driven Development

Use one fixed V1 cognitive graph inside an isolated delivery lifecycle:

```text
CREATE_TASK_WORKTREE
→ (TASK_CONTRACT
   → ADVISE_AND_FREEZE_PLAN
   → IMPLEMENT
   → TEST
   → INDEPENDENT_REVIEW
   → VERIFY_FINDINGS
   → LOCAL_HANDOFF)
→ READY_FOR_DELIVERY
→ PUSH_BRANCH
→ OPEN_PULL_REQUEST
→ WAIT_FOR_MERGE
→ CLEANUP_TASK_WORKTREE
→ DELIVERED
```

Keep the current Codex control session as both Orchestrator and the only Repository Writer. Treat every other agent or model as a read-only cognitive participant.

## Preserve the V1 boundary

- Use the fixed seven-node flow. Do not add, delete, reorder, or configure nodes.
- Assign only ChatGPT Pro web or Grok web to `Advisor`, `Reviewer`, or `Arbiter` based on the task, required context, independence, availability, and model strengths.
- Treat `implementation_author` as an Advisor task type, not a fourth cognitive role.
- Do not permanently bind a model to a role.
- Never count the current Writer as Reviewer or Arbiter.
- Never let an implementation-authoring session review or arbitrate its own candidate.
- Keep the seven cognitive nodes fixed. Treat worktree setup, checkpoint commits, publication, merge waiting, and cleanup as lifecycle operations rather than additional cognitive nodes.
- Reach local `READY_FOR_DELIVERY` before pushing or opening a pull request, then continue through verified post-merge worktree cleanup.
- Do not merge the pull request, deploy, mutate production, or perform any other real external side effect without its own explicit authorization. Creating the task branch and worktree, committing scoped task changes, pushing the ready branch, opening its pull request, and removing the recorded task worktree after verified merge are authorized by this Skill.
- Do not create a transition engine, event log, lock manager, recovery system, generic source packager, delivery transaction, or arbitrary budget DSL.

## Isolate every task in a worktree

Before N0, create a dedicated branch and linked worktree for every new task.

1. Read the repository instructions and inspect the source checkout, existing worktrees, remotes, and default branch.
2. Preserve every existing user change and worktree. Never stash, move, clean, or reuse a dirty checkout to make room for the task.
3. Refresh the configured remote tracking branch when available, then create a unique task branch from the repository's required base. Follow repository branch naming rules; otherwise use `codex/<task-slug>`.
4. Add a new linked worktree at a unique, task-specific path outside the source checkout. Never implement the task in the default checkout.
5. Record the repository root, source checkout, task worktree path, branch, base ref, and base commit before implementation.

Enter `WAITING_HUMAN` rather than guessing when the base branch, remote, safe worktree location, or ownership of existing changes is ambiguous.

## Use only the fixed cognitive backends

Use this fixed allowlist:

| Backend ID | Access surface | Allowed use | Hard limit |
|---|---|---|---|
| `codex-writer` | Current Codex control session | Orchestrator and Repository Writer | Never count it as Advisor, Reviewer, or Arbiter |
| `chatgpt-pro-web` | Authenticated ChatGPT Pro website in the Codex built-in Browser | Advisor, `implementation_author`, Reviewer, or Arbiter | Read-only; never review or arbitrate the same session's implementation candidate |
| `grok-web` | Authenticated Grok website in the Codex built-in Browser | Advisor, `implementation_author`, Reviewer, or Arbiter | Read-only; never review or arbitrate the same session's implementation candidate |

Do not use Claude, a local subagent, another external model, an API, or a model CLI for any cognitive role. Choose between the two allowed cognitive backends at runtime:

1. Honor explicit `required_participations` before preferences.
2. Verify current availability, usable context surface, and read-only capability.
3. Match the role and task to ChatGPT Pro web or Grok web instead of permanently binding either backend to one role.
4. For high risk, separate implementation authors from Reviewers and prefer different backends.
5. Record the backend, model when visible, role, task type, session ID, and selection reason.

Do not assume that either website is currently authenticated or available, and do not define a permanent ranking between them. Apply bounded fallback only from one allowed backend to the other.

## Require the Codex built-in Browser

Route every interaction with ChatGPT Pro web or Grok web through the Codex built-in Browser using `browser:control-in-app-browser`. Treat both the fixed backend allowlist and the Browser route as hard requirements.

- Do not use the user's Chrome, OpenCLI, Playwright, a terminal browser wrapper, a direct HTTP API, a model CLI, Claude, a local subagent, or another website as a substitute.
- Before assigning a cognitive backend, verify that the Codex built-in Browser is available and that the required authenticated ChatGPT Pro or Grok website session is usable.
- When one optional backend is unavailable, fallback only to the other allowed backend when role independence remains valid.
- When a required backend is unavailable, or neither allowed backend is usable through the Codex built-in Browser, enter `WAITING_HUMAN`. Never weaken the backend allowlist or bypass the Browser requirement.
- Keep each Reviewer and Arbiter in the fresh, independent conversation required by N4, and record its backend, visible model, role, task type, conversation ID, and Browser session evidence.

## Maintain the task state

Maintain the following lightweight state in the current task plan or an optional atomically replaced `run.json`:

```yaml
status: ACTIVE
phase: WORKTREE_SETUP
current_node: N0
contract_hash: sha256
plan_version: 1
implementation_rework_used: 0
plan_rework_used: 0
required_participations: []
allowed_backends:
  - chatgpt-pro-web
  - grok-web
test_results: []
reviews: []
findings: []
implementation_authors: []
repository_root: ""
source_checkout: ""
task_worktree: ""
task_branch: ""
base_ref: ""
base_commit: ""
checkpoint_commits: []
pull_request_url: ""
merge_commit: ""
```

Use only these overall terminal states:

```text
WAITING_HUMAN
DELIVERED
FAILED
CANCELLED
```

Treat `READY_FOR_DELIVERY`, `PR_OPEN`, `WAITING_FOR_MERGE`, and `MERGED` as non-terminal lifecycle gates. Do not promise automatic resume after an app, terminal, process, or machine failure. Reconstruct a new run from the recorded worktree, branch, commits, current Diff, test evidence, pull request, and saved review conversations when necessary.

## N0: Create the task contract

Create and show or save this contract before implementation:

```yaml
objective: ""
in_scope: []
out_of_scope: []
acceptance_criteria: []
risk_level: normal  # normal | high
required_participations: []
allowed_backends:
  - chatgpt-pro-web
  - grok-web
test_commands: []
permissions:
  repository_write: codex_only
  external_code_upload: allowed
  create_task_branch: allowed
  create_task_worktree: allowed
  checkpoint_commit: allowed_after_scoped_validation
  push: allowed_after_ready_for_delivery
  open_pull_request: allowed_after_push
  merge_pull_request: requires_separate_authorization
  cleanup_task_worktree: allowed_after_verified_merge
  deploy: denied
  production_mutation: denied
budgets:
  implementation_rework: 2
  plan_rework: 1
  backend_fallbacks_per_role: 2
```

Express mandatory participation directly:

```yaml
required_participations:
  - backend_id: chatgpt-pro-web
    role: advisor
    task_type: implementation_author
    min_count: 1
```

- Reject a required participation whose backend is not `chatgpt-pro-web` or `grok-web`; enter `WAITING_HUMAN` unless the user changes the contract.
- Resolve a user-named allowed backend without a role to `advisor` or `reviewer` according to the task.
- Use `task_type: implementation_author` when the backend must return code or a patch for Codex to evaluate and apply.
- Enter `WAITING_HUMAN` when choosing the role would materially change the user's intent.
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

Do not use any local agent or subagent for a cognitive role. Only the current Codex control session may operate locally, and only as Orchestrator and Repository Writer.

After each coherent implementation action is complete and its scoped validation passes, create one checkpoint commit containing only that action's task-owned changes. Interpret an action as an independently explainable implementation unit, not an individual edit, command, or tool call. Do not create empty commits, commit known-broken intermediate states, or include unrelated user changes. Record each commit hash, message, covered action, and validation evidence.

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

Give Reviewers the complete task-branch Diff from the recorded base commit, including all checkpoint commits, rather than only the latest commit.

Accept only:

```text
PASS
CHANGES_REQUESTED
NEEDS_EVIDENCE
BACKEND_FAILED
```

Allow one `NEEDS_EVIDENCE` response per Reviewer. On `BACKEND_FAILED`, use at most two fallback attempts for that role. Enter `WAITING_HUMAN` when a required backend remains unavailable.

## Transfer source safely

For ChatGPT Pro web or Grok web, send only:

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
8. checkpoint commits and their validation evidence;
9. branch, worktree, push, pull request, merge, cleanup, deploy, and production-action status;
10. the recommended human action when merge or another separately authorized operation remains pending.

Report `READY_FOR_DELIVERY` only after every gate passes and every task change is committed on the recorded task branch.

## Publish and clean up the task worktree

After N6 reaches `READY_FOR_DELIVERY`:

1. Recheck that the task worktree is clean, every commit is in scope, the branch still descends from the recorded base, and required tests and reviews apply to the exact branch head.
2. Push only the recorded task branch to its configured remote. Never push the default branch or unrelated refs.
3. Open one pull request targeting the repository's required base branch. Include the objective, scoped changes, test evidence, review results, finding disposition, checkpoint commits, and explicit statements that merge, deploy, and production mutation were not performed.
4. Record the pull request URL and enter `WAITING_FOR_MERGE`. Do not merge it unless separately authorized.
5. After the pull request is confirmed merged by authoritative remote state, verify the recorded task worktree is clean and contains no unpushed or unmerged task work.
6. Remove only the exact recorded task worktree, then prune stale worktree metadata if needed. Delete the local task branch only when merge is confirmed, it is not checked out anywhere, and repository policy permits deletion. Do not delete the remote branch unless separately authorized or the repository's PR merge policy does so automatically.
7. Verify that the source checkout and every unrelated worktree remain unchanged, then report `DELIVERED` with the pull request URL, merge commit, and cleanup result.

If merge cannot be confirmed, the worktree is dirty, commits are unpushed or unmerged, or the target path differs from the recorded worktree, enter `WAITING_HUMAN` and do not remove anything.

## Keep loops bounded

Use exactly these budgets:

| Budget | Default | Exhaustion |
|---|---:|---|
| implementation rework | 2 | `FAILED` |
| plan rework | 1 | `WAITING_HUMAN` |
| needs evidence per Reviewer | 1 | replace Reviewer; otherwise `WAITING_HUMAN` |
| backend fallbacks per role | 2 | required role waits; optional Advisor skips |

Pause when scope, permissions, or acceptance criteria materially change. Do not automatically loop on a changed contract.
