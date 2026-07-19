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
assert_file "claude-primary.md"
assert_file "lib/invoke-codex-tmux.sh"
assert_file "tests/test-invoke-codex-tmux.sh"

assert_contains SKILL.md "name: tmux-cross-model-review"
assert_contains SKILL.md "description: Use when coordinating a tmux-based cross-model review lifecycle"
assert_contains SKILL.md "Supports codex-primary mode"
assert_contains SKILL.md "Supports codex-primary mode, where Codex drives and Claude Code reviews through an explicit tmux pane, and claude-primary mode, where Claude Code drives and Codex reviews through an explicit tmux pane."
assert_contains SKILL.md "codex-primary   # default"
assert_contains SKILL.md "claude-primary"
assert_contains SKILL.md "If no mode is passed, use codex-primary"
assert_contains SKILL.md "primary session -> prompt file -> explicit tmux reviewer pane -> review result Markdown"
assert_contains SKILL.md "Claude Code -> Codex over tmux"
assert_contains SKILL.md "lib/invoke-codex-tmux.sh"
assert_contains SKILL.md "CODEX_REVIEW_TMUX_PANE"
assert_contains SKILL.md "CODEX_REVIEW_RESULT_V1"
assert_contains SKILL.md "CODEX_REVIEW_DONE"
assert_contains SKILL.md "AUTONOMOUS FLOW"
assert_contains SKILL.md "The Two Exceptions"
assert_contains SKILL.md "Exception 2 -- Boundary-Conflict Escalation"
assert_contains SKILL.md "A reviewer or primary driver identifies [BOUNDARY-CONFLICT]"
assert_contains SKILL.md "Step 1: Select Tmux Reviewer Pane"
assert_contains SKILL.md "Step 2: Detect Phase & Load Phase File"
assert_contains SKILL.md "Termination Mode -- Design-Only / Spec-Only"
assert_contains SKILL.md "Prompt Template Variable Injection"
assert_contains SKILL.md "Shared: Review Loop Mechanics"
assert_contains SKILL.md "Response Protocol"
assert_contains SKILL.md "BOUNDARY-CHECK"
assert_contains SKILL.md "Never ACCEPT or REJECT a confirmed [BOUNDARY-CONFLICT]."
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

assert_contains tmux-backend.md "--ask-for-approval never"
assert_contains tmux-backend.md "--sandbox workspace-write"
assert_contains tmux-backend.md "--no-alt-screen"
assert_contains tmux-backend.md "or an equivalent profile"
assert_contains tmux-backend.md "--ask-for-approval untrusted"
assert_contains tmux-backend.md "--ask-for-approval on-request"
assert_contains tmux-backend.md "--ask-for-approval on-failure"
assert_contains tmux-backend.md "--dangerously-bypass-approvals-and-sandbox"
assert_contains tmux-backend.md "lib/invoke-codex-tmux.sh"
assert_contains tmux-backend.md "CODEX_REVIEW_RESULT_V1"
assert_contains tmux-backend.md "CODEX_REVIEW_DONE"

assert_contains claude-primary.md "codex review"
assert_contains claude-primary.md "codex exec"
assert_contains claude-primary.md "No same-dialog"
assert_contains claude-primary.md "may not replace the tmux reviewer pane"
assert_contains claude-primary.md "The Two Escalation Exceptions"
assert_contains claude-primary.md "Boundary-Conflict"
assert_absent claude-primary.md "The only user pause is a user-premise conflict escalation."
assert_absent_regex claude-primary.md "codex review.*supported|supported.*codex review|codex exec.*supported|supported.*codex exec"

assert_contains report.md "Role mode"
assert_contains report.md "Primary driver"
assert_contains report.md "External reviewer"
assert_contains report.md "Primary result owner"

assert_absent SKILL.md "## Phase Templates"
assert_absent SKILL.md "You are reviewing a DESIGN SPECIFICATION"
assert_absent SKILL.md "You are reviewing an IMPLEMENTATION PLAN"
assert_absent SKILL.md "You are reviewing a PR"

runtime_docs_core=(
  SKILL.md
  design-review.md
  plan-review.md
  execution.md
  code-review.md
  report.md
  tmux-backend.md
)

for file in "${runtime_docs_core[@]}"; do
  assert_absent_regex "$file" "node .*companion\\.mjs"
  assert_absent_regex "$file" "codex-companion"
  assert_absent_regex "$file" "\\bcodex exec\\b"
  assert_absent_regex "$file" "\\bcodex review\\b"
  assert_absent_regex "$file" "/code-review:code-review"
  assert_absent_regex "$file" "Reviewer backend.*subagent"
  assert_absent_regex "$file" "subagent \\(fallback\\)"
  assert_absent_regex "$file" "same-dialog.*supported|same-conversation.*supported|supported.*same-dialog|supported.*same-conversation"
done

assert_contains tmux-backend.md "bypassPermissions"
assert_contains tmux-backend.md "dontAsk"
assert_contains tmux-backend.md "acceptEdits is invalid"
assert_contains tmux-backend.md "after-the-fact side-effect detection"
assert_contains SKILL.md "acceptEdits is invalid"
assert_contains SKILL.md "If project root AGENTS.md exists, the active reviewer must read it before review."
assert_contains SKILL.md 'If AGENTS.md is absent, inject and record `no convention file available`.'
assert_contains code-review.md "Your goal is to break confidence in this change, not validate it."
assert_contains SKILL.md 'prompt_tmp_dir="$(mktemp -d "${TMPDIR:-/tmp}/claude-review-prompt.XXXXXX")"'
assert_contains SKILL.md 'prompt_file="$prompt_tmp_dir/prompt.md"'
assert_contains SKILL.md "Do not create temporary prompt files under the repository or under docs/reviews."
assert_contains SKILL.md 'Review results are Markdown files under `docs/reviews/claude-code/YYYYMMDD/*.md`.'
assert_contains tmux-backend.md 'docs/reviews/claude-code/YYYYMMDD/*.md'

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
assert_contains report.md "Escalations (Exceptions 1-2)"
assert_contains report.md "boundary conflict"
assert_absent report.md "Overturned decision / false premise"
assert_contains report.md "Final Status"

printf 'PASS: skill phase file structure\n'
