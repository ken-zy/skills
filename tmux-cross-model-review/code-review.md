# Phase 4: Code Review

## Role Mode Banner

Each resolved review prompt starts with one of these banners:

```text
ROLE MODE: codex-primary
Codex is the primary driver and artifact owner. Claude Code is reviewer only.
Codex owns the lifecycle loop.
```

```text
ROLE MODE: claude-primary
Claude Code is the primary driver and artifact owner. Codex is reviewer only.
Claude Code owns the lifecycle loop.
```

## Step 0: Ensure PR Exists

```text
IF PR already exists on current branch -> proceed
IF no PR exists:
  1. Check gh auth.
  2. Push branch if needed.
  3. Create a PR with an auto-generated title and body from the spec/plan.
  4. Proceed to review.
IF gh auth is unavailable -> review local diff instead.
```

Do not ask the user. Do not invoke interactive commit or PR helpers.

## Tmux Backend Command

Use the active tmux helper for every external review round:

- `codex-primary`: `lib/invoke-claude.sh`
- `claude-primary`: `lib/invoke-codex-tmux.sh`

The helper wraps the phase prompt with cwd, the helper-designated output file,
write rules, and sentinels.

## Review Dimensions

Code review has three halves, in priority order: alignment with plan, code
logic, and vulnerabilities/data safety.

```text
Half A - Alignment with plan
  A1 - Coverage: every plan task has corresponding code in the diff?
  A2 - Drift: implementation substituted a different approach?
  A3 - Boundary (hard constraint): code adds state, tables, endpoints, config,
       or behavior the plan did not authorize?
  A4 - Plan-inherited bugs: faithful code implements a flawed plan step?

Half B - Code logic
  B1 - Correctness: off-by-one, null/empty, boundaries, state transitions
  B2 - Concurrency: races, stale reads, lost updates
  B3 - Error paths: partial failure, retry safety, rollback, malformed responses
  B4 - Edge cases tests miss: empty/max input, degraded dependency, version skew

Half C - Vulnerabilities and data safety
  C1 - Auth, permissions, tenant isolation, trust boundaries
  C2 - Data loss, corruption, duplication, irreversible state changes
  C3 - Injection, unsafe deserialization, SSRF, secrets, PII
  C4 - Observability gaps that hide future failures
```

## Prompt Template

```text
You are reviewing a PR or branch diff. Your job has three halves:
(A) Does the change faithfully execute the PLAN?
(B) Does the code logic actually work?
(C) Are there security, data-safety, or failure-mode vulnerabilities?

Default to skepticism. Your goal is to break confidence in this change, not validate it.
Prefer one strong finding over several weak ones.

Read these files in order:
1. The plan this change implements: <PLAN_FILE_PATH>
   If "N/A", skip Half A and note "no plan available".
2. <CONVENTION_FILE>
3. The diff. Run `git diff origin/main --stat`, then read changed files in full.

Write the complete result to the helper-designated output file. Do not edit any
source/spec/helper/git files.

=== HALF A: ALIGNMENT WITH PLAN ===

A1 - Coverage: Does every task/step in the plan have corresponding code?
A2 - Drift: Did the implementation silently substitute a different approach?
A3 - Boundary: Does the change include unauthorized files, abstractions, or
     features? See the boundary rule below.
A4 - Plan-inherited bugs: Does faithful code implement a flawed plan step?

=== PLAN BOUNDARY RULE (hard constraint) ===

The change must not add new tables, endpoints, config knobs, persisted state,
or externally visible behavior that the plan did not authorize. Internal
implementation detail -- helper functions, refactors within changed files,
test organization -- is not a boundary violation; anything that would appear
in the runtime or operations view is.

If a plan task cannot be implemented without machinery the plan never
described, do NOT specify the machinery and do NOT demand the author invent
it. Report it as [BOUNDARY-CONFLICT]: cite the exact plan step that forces the
machinery and the machinery it would require. Resolution belongs to the user,
not to this review loop.

=== HALF B: CODE LOGIC ===

B1 - Correctness: off-by-one, null/empty, boundaries, ordering assumptions,
     state transitions, idempotency, re-entrancy.
B2 - Concurrency: races, lock ordering, stale reads, lost updates.
B3 - Error paths: partial failure, retry safety, rollback, timeout or malformed
     downstream responses.
B4 - Edge cases tests miss: empty input, max input, degraded dependency,
     version skew, schema drift.

=== HALF C: VULNERABILITIES AND DATA SAFETY ===

C1 - Auth, permissions, tenant isolation, trust boundary holes.
C2 - Data loss, corruption, duplication, irreversible state changes.
C3 - Injection, unsafe deserialization, SSRF, secrets in logs or commits, PII.
C4 - Observability gaps that would hide a future failure.

=== WHAT TO IGNORE ===

- Pre-existing issues outside the diff
- Lint/type/formatting concerns unless they cause a real bug
- Style nitpicks not in <CONVENTION_FILE>
- Refactor suggestions without a concrete bug

=== OUTPUT ===

For each issue >= 70 confidence: ISSUE format.
Tag findings with [ALIGN-A1..A4], [LOGIC-B1..B4], [VULN-C1..C4], or
[BOUNDARY-CONFLICT].
Location format: "file:line".
If no substantive issues: "LGTM: faithful to plan, logic sound, no exploitable
surface found in <one-line scope statement>".
```

`<PLAN_FILE_PATH>` resolves to the plan file under `docs/superpowers/plans/`,
or `N/A` if no plan exists.

`<CONVENTION_FILE>` resolves to `AGENTS.md (project root) -- mandatory; read
before review.` when present. If absent, it resolves to `no convention file
available`, and the active reviewer must state that convention context was
unavailable.

## ACCEPT Action

The primary driver modifies code, commits one fix per accepted issue, and
pushes. Commit format: `fix(scope): <description>`.

A [BOUNDARY-CONFLICT] finding is never ACCEPT/REJECT material and must not be
resolved by editing code. It goes through Exception 2 (Boundary-Conflict
Escalation) in `SKILL.md`.

## Review Loop

Use the same Shared Review Loop from `SKILL.md`:

1. The external reviewer reviews via the active tmux helper.
2. The primary driver applies VERIFY, EVALUATE, CLASSIFY, PREMISE-CHECK, UPDATE.
3. Accepted fixes are implemented by the primary driver and committed one fix
   per commit.
4. Round 2+ is mandatory after accepted fixes.
5. Continue until LGTM, all remaining issues rejected, CEO Decision, or round
   limit.

## Step Final: Primary Safety Net

After the external review loop completes, the primary driver runs one fresh
local review of the final diff as the author-side safety net.

The primary safety net does not replace the external review. Any safety-net
finding goes through the full Response Protocol, including PREMISE-CHECK.

After safety-net fixes, the primary driver performs a single-pass diff
self-check and reports whether modifications were self-checked.

## Next Phase

After external review and the primary safety net complete, read `report.md` and
output the final report. No user confirmation.
