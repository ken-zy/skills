# Align claude-cross-model-review With cross-model-review Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert `claude-cross-model-review` from a tmux review helper into a role-inverted full lifecycle clone of `/Users/jdy/Documents/skills/cross-model-review`.

**Architecture:** Keep `lib/invoke-claude.sh` as the only tmux backend primitive. Move phase-specific review content out of `SKILL.md` into `design-review.md`, `plan-review.md`, `execution.md`, `code-review.md`, and `report.md`, mirroring `cross-model-review` with backend and role substitutions. `SKILL.md` becomes the lifecycle orchestrator and must preserve autonomous flow, phase detection, shared review mechanics, CEO decisions, and reporting.

**Tech Stack:** Markdown skill files, Bash helper, Bash tests, `rg`, `git`, `tmux`.

## Global Constraints

- Source architecture: `/Users/jdy/Documents/skills/cross-model-review`.
- Only intentional differences: Claude Code reviewer via explicit tmux pane; Codex orchestrates, implements, verifies, and decides.
- Backend is tmux-only. Do not reintroduce Claude CLI, Codex companion, or subagent reviewer fallback.
- Tmux pane must use `bypassPermissions` or `dontAsk`; `acceptEdits` is invalid for the full lifecycle because code review needs Bash.
- Tmux has no harness-level read-only enforcement; use prompt constraints plus after-the-fact side-effect detection and fail closed.
- The helper owns review output-file injection. Phase templates must not use an `<OUTPUT_FILE>` placeholder.
- Design-only mode must terminate after Design Review and Report; it must not create a plan, execute, create a PR, or run code review.
- Any accepted reviewer fix requires Round 2+ before moving to the next phase.
- Review outputs under `docs/reviews/claude-code/` are local artifacts and are not part of this implementation commit unless explicitly requested.

---

## File Structure

- Modify: `SKILL.md`
  - Responsibility: lifecycle orchestration entry point, tmux backend selection, phase detection, prompt variable injection, shared review loop, response protocol, CEO decisions, failure handling, red flags.
- Create: `design-review.md`
  - Responsibility: Phase 1 design review prompt, accept action, mandatory re-review gate, design-only enforcement, design-to-plan handoff.
- Create: `plan-review.md`
  - Responsibility: Phase 2 plan review prompt, accept action, mandatory re-review gate, automatic transition to execution.
- Create: `execution.md`
  - Responsibility: Phase 3 Codex-owned plan execution rules, skip protocol, pre-execution checks, execution strategy, automatic transition to code review.
- Create: `code-review.md`
  - Responsibility: Phase 4 PR/local diff review prompt, fix rules, mandatory re-review gate, Codex safety net, automatic transition to report.
- Create: `report.md`
  - Responsibility: final report format with tmux pane, Claude Code review results, Codex safety-net result, CEO verification status, and escalations.
- Modify: `tmux-backend.md`
  - Responsibility: backend-specific pane state, prompt delivery, output contract, side-effect guard, timeout diagnostics.
- Modify: `tests/test-invoke-claude-tmux.sh`
  - Responsibility: keep existing helper behavior tests passing.
- Create: `tests/test-skill-structure.sh`
  - Responsibility: static guard that proves lifecycle phase files exist and runtime docs do not drift back to helper-only or removed backends.

---

### Task 1: Add Phase Files With a Failing Structure Test

**Files:**
- Create: `tests/test-skill-structure.sh`
- Create: `design-review.md`
- Create: `plan-review.md`
- Create: `execution.md`
- Create: `code-review.md`
- Create: `report.md`

**Interfaces:**
- Consumes: reviewed spec at `docs/superpowers/specs/2026-06-28-align-claude-cross-model-review-with-cross-model-design.md`.
- Consumes: source phase files under `/Users/jdy/Documents/skills/cross-model-review/`.
- Produces: phase files that `SKILL.md` can reference in Task 2.

- [ ] **Step 1: Write the failing structure test**

Create `tests/test-skill-structure.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

fail() {
  printf 'FAIL: %s\n' "$*" >&2
  exit 1
}

assert_file() {
  local path="$1"
  [ -f "$ROOT/$path" ] || fail "missing required file: $path"
}

phase_files=(
  design-review.md
  plan-review.md
  execution.md
  code-review.md
  report.md
)

for file in "${phase_files[@]}"; do
  assert_file "$file"
done

printf 'PASS: skill phase file structure\n'
```

- [ ] **Step 2: Run the structure test and verify RED**

Run:

```bash
bash tests/test-skill-structure.sh
```

Expected: FAIL with `missing required file: design-review.md`.

- [ ] **Step 3: Create phase files from the source architecture**

Use these source files:

```text
/Users/jdy/Documents/skills/cross-model-review/design-review.md
/Users/jdy/Documents/skills/cross-model-review/plan-review.md
/Users/jdy/Documents/skills/cross-model-review/execution.md
/Users/jdy/Documents/skills/cross-model-review/code-review.md
/Users/jdy/Documents/skills/cross-model-review/report.md
```

Create the target files with these exact responsibility mappings:

```text
cross-model-review/design-review.md -> design-review.md
cross-model-review/plan-review.md   -> plan-review.md
cross-model-review/execution.md     -> execution.md
cross-model-review/code-review.md   -> code-review.md
cross-model-review/report.md        -> report.md
```

Apply this source-to-target role table while creating the files:

| Source concept | Target concept |
|---|---|
| Claude as orchestrator / author / fixer / CEO | Codex as orchestrator / author / fixer / CEO |
| Codex as external reviewer | Claude Code as external reviewer |
| companion.mjs / Codex companion / subagent reviewer fallback | `lib/invoke-claude.sh` tmux helper |
| stdout reviewer response | helper-designated output file with sentinels |
| `/code-review:code-review` Claude safety net | fresh local Codex safety net |
| `codex (${MODEL}) / subagent` reviewer backend | `claude-code-tmux` reviewer backend |
| `CLAUDE.md` convention for subagent fallback | no subagent reviewer fallback |
| `AGENTS.md` convention for external backend | `AGENTS.md` when present |

Preserve these source mechanics verbatim in meaning:

```text
Design Review -> Plan Review -> Execution -> Code Review -> Report
Design-only: Design Review -> Report
VERIFY -> EVALUATE -> CLASSIFY -> PREMISE-CHECK -> UPDATE -> ACCEPT/REJECT
Fast-REJECT for stale re-raises
CEO Decision and post-CEO verification
Round 2+ after accepted modifications
Phase transition checks
Final report includes executed phases only
```

Use these target-specific details:

```text
Every review prompt says to write to the helper-designated output file.
No phase file defines or resolves an <OUTPUT_FILE> placeholder.
Every phase sends prompts through lib/invoke-claude.sh.
Plan creation after Design Review is performed by Codex when design-only is OFF and no plan exists.
Execution is performed by Codex, not Claude Code.
Code fixes are implemented by Codex, one fix per commit.
```

- [ ] **Step 4: Run the structure test and verify GREEN**

Run:

```bash
bash tests/test-skill-structure.sh
```

Expected: PASS with `PASS: skill phase file structure`.

- [ ] **Step 5: Commit Task 1**

Run:

```bash
git add tests/test-skill-structure.sh design-review.md plan-review.md execution.md code-review.md report.md
git commit -m "docs(review): add lifecycle phase files"
```

---

### Task 2: Rewrite SKILL.md as the Lifecycle Orchestrator

**Files:**
- Modify: `tests/test-skill-structure.sh`
- Modify: `SKILL.md`

**Interfaces:**
- Consumes: phase files from Task 1.
- Produces: an orchestration entry point that dispatches to the phase files and uses the tmux helper.

- [ ] **Step 1: Extend the structure test for orchestrator requirements**

Append these functions and assertions to `tests/test-skill-structure.sh` before the final `printf`:

```bash
assert_contains() {
  local path="$1"
  local pattern="$2"
  rg -n --fixed-strings -- "$pattern" "$ROOT/$path" >/dev/null || fail "expected '$pattern' in $path"
}

assert_absent() {
  local path="$1"
  local pattern="$2"
  if rg -n --fixed-strings -- "$pattern" "$ROOT/$path" >/dev/null; then
    fail "unexpected '$pattern' in $path"
  fi
}

assert_absent_regex() {
  local path="$1"
  local pattern="$2"
  if rg -n -- "$pattern" "$ROOT/$path" >/dev/null; then
    fail "unexpected regex '$pattern' in $path"
  fi
}

assert_contains SKILL.md "name: claude-cross-model-review"
assert_contains SKILL.md "description: Use when Codex needs Claude Code as an external reviewer"
assert_contains SKILL.md "AUTONOMOUS FLOW"
assert_contains SKILL.md "The ONE Exception"
assert_contains SKILL.md "Step 1: Select Tmux Reviewer Pane"
assert_contains SKILL.md "Step 2: Detect Phase & Load Phase File"
assert_contains SKILL.md "Termination Mode -- Design-Only / Spec-Only"
assert_contains SKILL.md "Prompt Template Variable Injection"
assert_contains SKILL.md "Shared: Review Loop Mechanics"
assert_contains SKILL.md "Response Protocol"
assert_contains SKILL.md "Fast-REJECT rule"
assert_contains SKILL.md "CEO Decision"
assert_contains SKILL.md "Phase Transition Checks"
assert_contains SKILL.md "Fix Discipline: Root Cause First"
assert_contains SKILL.md "Tmux Helper Interface"
assert_contains SKILL.md "design-review.md"
assert_contains SKILL.md "plan-review.md"
assert_contains SKILL.md "execution.md"
assert_contains SKILL.md "code-review.md"
assert_contains SKILL.md "report.md"

assert_absent SKILL.md "## Phase Templates"
assert_absent SKILL.md "You are reviewing a DESIGN SPECIFICATION"
assert_absent SKILL.md "You are reviewing an IMPLEMENTATION PLAN"
assert_absent SKILL.md "You are reviewing a PR"
```

Move the existing final line so it remains last:

```bash
printf 'PASS: skill phase file structure\n'
```

- [ ] **Step 2: Run the structure test and verify RED**

Run:

```bash
bash tests/test-skill-structure.sh
```

Expected: FAIL because current `SKILL.md` still has inline phase templates and lacks the full lifecycle orchestrator sections.

- [ ] **Step 3: Rewrite SKILL.md from source orchestration**

Rewrite `SKILL.md` using `/Users/jdy/Documents/skills/cross-model-review/SKILL.md` as the source structure. Preserve the YAML frontmatter as the first block:

```yaml
---
name: claude-cross-model-review
description: Use when Codex needs Claude Code as an external reviewer for a design spec, implementation plan, pull request, or multi-round review before executing or merging changes.
---
```

After the frontmatter, use these exact target sections:

```markdown
# Claude Cross-Model Review

Full lifecycle review: **Design Review -> Plan Review -> Execution -> Code Review -> Report**. Codex writes and executes; Claude Code reviews through an existing tmux pane.

## AUTONOMOUS FLOW -- NON-NEGOTIABLE
## The ONE Exception -- User-Premise Conflict Escalation
## Step 1: Select Tmux Reviewer Pane
## Step 2: Detect Phase & Load Phase File
## Termination Mode -- Design-Only / Spec-Only
## Prompt Template Variable Injection
## Shared: Review Loop Mechanics
### Tmux Helper Interface
### Convention File Rule
### Confidence Filtering
### Context Budget
### Issue Tracker
### Response Protocol
### Round N > 1 Prompt
### Termination
### CEO Decision
### Phase Transition Checks
### Fix Discipline: Root Cause First
### Tmux Helper Failure Handling
## Red Flags
```

Required content changes from the source `SKILL.md`:

```text
Replace Step 1 backend detection with explicit tmux pane selection.
Remove command -v codex, companion.mjs, MODEL, EFFORT, and subagent fallback.
Keep phase detection behavior, including branch topic extraction and design-only detection.
Keep placeholder injection for <SPEC_FILE_PATH>, <PLAN_FILE_PATH>, <CONVENTION_FILE>, <PHASE>, and <ROUND>.
Do not include <OUTPUT_FILE> as a phase-template placeholder.
Define the helper command using lib/invoke-claude.sh with --phase, --round, --cwd, --prompt-file, and --tmux-pane.
State that the helper wrapper injects output file and sentinel contract.
State that pane scrollback is diagnostics only and the result file is source of truth.
Keep confidence scale and threshold >= 70.
Keep issue tracker statuses: open, accepted, rejected, ceo-accepted, ceo-rejected, ceo-compromised, user-override.
Keep the full Response Protocol including PREMISE-CHECK.
Keep fast-REJECT.
Keep CEO Decision and post-CEO verification.
Keep phase transition checks.
Keep root-cause-first discipline.
Failure handling: retry helper failure once; if Round 1 fails twice, stop the Claude-backed phase and report failure; if Round 2+ fails twice, preserve the issue tracker and run a local Codex review of changed files before deciding whether to proceed.
```

The phase transition list must be:

```text
Full pipeline: design-review.md -> plan-review.md -> execution.md -> code-review.md -> report.md
Design-only:   design-review.md -> report.md
```

- [ ] **Step 4: Run the structure test and verify GREEN for SKILL.md**

Run:

```bash
bash tests/test-skill-structure.sh
```

Expected: PASS with `PASS: skill phase file structure`.

- [ ] **Step 5: Commit Task 2**

Run:

```bash
git add SKILL.md tests/test-skill-structure.sh
git commit -m "docs(review): align skill orchestration"
```

---

### Task 3: Update Tmux Backend Contract and Static Drift Guards

**Files:**
- Modify: `tests/test-skill-structure.sh`
- Modify: `tmux-backend.md`
- Modify: `SKILL.md`
- Modify: `report.md` if the report-field assertions expose a missing required field anchor from the spec.

**Interfaces:**
- Consumes: orchestrator from Task 2.
- Produces: tmux backend docs that match the reviewed spec and prevent removed backend drift.

- [ ] **Step 1: Extend the structure test for backend drift**

Append these assertions to `tests/test-skill-structure.sh` before the final `printf`:

```bash
runtime_docs=(
  SKILL.md
  design-review.md
  plan-review.md
  execution.md
  code-review.md
  report.md
  tmux-backend.md
)

for file in "${runtime_docs[@]}"; do
  assert_absent_regex "$file" "node .*companion\\.mjs"
  assert_absent_regex "$file" "codex-companion"
  assert_absent_regex "$file" "\\bcodex exec\\b"
  assert_absent_regex "$file" "/code-review:code-review"
  assert_absent_regex "$file" "Reviewer backend.*subagent"
  assert_absent_regex "$file" "subagent \\(fallback\\)"
done

assert_contains tmux-backend.md "bypassPermissions"
assert_contains tmux-backend.md "dontAsk"
assert_contains tmux-backend.md "acceptEdits is invalid"
assert_contains tmux-backend.md "after-the-fact side-effect detection"
assert_contains SKILL.md "acceptEdits is invalid"

assert_contains report.md "claude-code-tmux"
assert_contains report.md "tmux pane"
assert_contains report.md "Spec"
assert_contains report.md "Plan"
assert_contains report.md "PR"
assert_contains report.md "Started at"
assert_contains report.md "Claude Code"
assert_contains report.md "Codex safety"
assert_contains report.md "CEO"
assert_contains report.md "self-checked"
assert_contains report.md "unreviewed"
assert_contains report.md "Escalations"
assert_contains report.md "Final Status"
```

- [ ] **Step 2: Run the structure test and verify RED**

Run:

```bash
bash tests/test-skill-structure.sh
```

Expected: FAIL because current `tmux-backend.md` still lists `acceptEdits` as a valid mode.

- [ ] **Step 3: Update tmux-backend.md**

Modify `tmux-backend.md` to include these sections and meanings:

```markdown
# Tmux Backend

Claude review runs through an existing Claude Code pane. This backend does not start a hidden reviewer process.

## Required Pane State

The target pane must be a Claude Code session in `bypassPermissions` or `dontAsk`.

`acceptEdits` is invalid for the full lifecycle. It may auto-accept edits, but code review requires Bash commands such as `git diff origin/main --stat`; a pane that prompts for Bash will make `lib/invoke-claude.sh` fail the round.

Plan mode and prompt-on-write modes are invalid because the helper polls an output file and cannot answer interactive permission prompts.

## Pane Selection
## Prompt Delivery
## Output Contract
## Side-Effect Guard
## Timeout And Permission Diagnostics
## Retry
```

Preserve the existing side-effect guard contract:

```text
The helper must not edit .gitignore, .git/info/exclude, git config, or any other git-related file to hide review artifacts.
Allowed new git-visible changes are only the designated output file and parent directories created to hold it.
Any other new git-visible change fails the round.
```

Add the explicit tradeoff sentence:

```text
This backend does not provide harness-level read-only enforcement. It relies on prompt constraints plus after-the-fact side-effect detection.
```

- [ ] **Step 4: Update SKILL.md backend wording if needed**

Check:

```bash
rg -n "acceptEdits|bypassPermissions|dontAsk|permission" SKILL.md tmux-backend.md
```

Expected after edits:

```text
SKILL.md states bypassPermissions or dontAsk.
SKILL.md states acceptEdits is invalid.
tmux-backend.md states bypassPermissions or dontAsk.
tmux-backend.md states acceptEdits is invalid.
```

- [ ] **Step 5: Run backend and helper tests**

Run:

```bash
bash tests/test-skill-structure.sh
bash tests/test-invoke-claude-tmux.sh
```

Expected:

```text
PASS: skill phase file structure
PASS: invoke-claude tmux helper tests
```

- [ ] **Step 6: Commit Task 3**

Run:

```bash
git add SKILL.md tmux-backend.md report.md tests/test-skill-structure.sh
git commit -m "docs(review): tighten tmux backend contract"
```

---

### Task 4: Final Verification and Cross-Model Review Readiness

**Files:**
- Modify: only files with verification-driven corrections from Tasks 1-3.

**Interfaces:**
- Consumes: all runtime docs and tests.
- Produces: a branch ready for Claude Code implementation code review.

- [ ] **Step 1: Run full static and helper verification**

Run:

```bash
bash tests/test-skill-structure.sh
bash tests/test-invoke-claude-tmux.sh
git diff --check
```

Expected:

```text
PASS: skill phase file structure
PASS: invoke-claude tmux helper tests
```

`git diff --check` exits 0.

- [ ] **Step 2: Verify required files exist**

Run:

```bash
for file in SKILL.md design-review.md plan-review.md execution.md code-review.md report.md tmux-backend.md lib/invoke-claude.sh tests/test-invoke-claude-tmux.sh tests/test-skill-structure.sh; do
  test -f "$file" || { echo "missing $file"; exit 1; }
done
```

Expected: exits 0 with no output.

- [ ] **Step 3: Verify no removed backend mechanics remain in runtime docs**

Run:

```bash
rg -n "node .*companion\\.mjs|codex-companion|\\bcodex exec\\b|/code-review:code-review|Reviewer backend.*subagent|subagent \\(fallback\\)" SKILL.md design-review.md plan-review.md execution.md code-review.md report.md tmux-backend.md
```

Expected: exits 1 with no matches.

- [ ] **Step 4: Verify output-file ownership stays in the helper**

Run:

```bash
rg -n "<OUTPUT_FILE>|output-file placeholder" SKILL.md design-review.md plan-review.md execution.md code-review.md report.md tmux-backend.md
```

Expected: exits 1 with no matches.

Run:

```bash
rg -n "helper-designated output file|Review output file" SKILL.md design-review.md plan-review.md code-review.md lib/invoke-claude.sh
```

Expected: matches in runtime docs and `lib/invoke-claude.sh`.

- [ ] **Step 5: Verify lifecycle parity anchors**

Run:

```bash
rg -n "AUTONOMOUS FLOW|The ONE Exception|Design-only|Prompt Template Variable Injection|Fast-REJECT|CEO Decision|post-CEO|Phase Transition Checks|Root Cause First|Codex safety net|claude-code-tmux" SKILL.md design-review.md plan-review.md execution.md code-review.md report.md
```

Expected: each named anchor appears at least once across the runtime docs.

Run:

```bash
rg -n "claude-code-tmux|tmux pane|Spec|Plan|PR|Started at|Claude Code|Codex safety|CEO|self-checked|unreviewed|Escalations|Final Status" report.md
```

Expected: each required report field anchor appears in `report.md`.

- [ ] **Step 6: Inspect git status**

Run:

```bash
git status --short --branch --untracked-files=all
```

Expected:

```text
Tracked changes are only implementation files from this plan.
docs/reviews/claude-code/... may remain untracked.
```

- [ ] **Step 7: Commit final verification corrections if any were needed**

If Step 1-5 required corrections after Task 3, commit only those corrections:

```bash
git add SKILL.md design-review.md plan-review.md execution.md code-review.md report.md tmux-backend.md tests/test-skill-structure.sh tests/test-invoke-claude-tmux.sh
git commit -m "test(review): verify lifecycle parity docs"
```

If no files changed after Task 3, do not create an empty commit.

---

## Plan Self-Review

Spec coverage:

- Target file structure is covered by Task 1 and Task 4.
- `SKILL.md` orchestration, autonomous flow, ONE Exception, phase detection, design-only mode, prompt injection, shared loop, fast-REJECT, CEO decisions, phase transitions, and root-cause discipline are covered by Task 2.
- Tmux-only backend, explicit pane selection, `bypassPermissions` / `dontAsk`, invalid `acceptEdits`, output-file ownership, and side-effect tradeoff are covered by Task 3.
- Helper behavior remains covered by the existing `tests/test-invoke-claude-tmux.sh` and full verification in Task 4.
- Report requirements, Codex safety net, and CEO verification status are covered by Task 3 report.md assertions plus Task 4 report-scoped verification.

Placeholder scan:

- The plan uses literal placeholders only when describing runtime template tokens required by the reviewed spec.
- No step leaves an unspecified implementation choice.

Type / name consistency:

- The runtime phase filenames are consistent across all tasks.
- Test script names are consistent: `tests/test-skill-structure.sh` and `tests/test-invoke-claude-tmux.sh`.
- Commit scopes use `review` consistently.
