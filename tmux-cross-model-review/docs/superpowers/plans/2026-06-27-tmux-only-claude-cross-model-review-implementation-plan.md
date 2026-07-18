# Tmux-Only Claude Cross-Model Review Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current `claude -p` review helper with a tmux-only workflow that sends prompts to an existing Claude Code pane and consumes a sentinel-delimited review file.

**Architecture:** `SKILL.md` remains the orchestration entry point and phase prompt source. A new `tmux-backend.md` documents backend mechanics. `lib/invoke-claude.sh` becomes a tmux-only helper that validates pane selection, sends prompts via tmux buffers, polls the result file, and fails closed on unexpected git-visible changes.

**Tech Stack:** Bash, tmux, git, ripgrep (`rg`) for verification, Markdown skill docs.

## Global Constraints

- Tmux is the only Claude reviewer backend; there is no `claude -p` fallback.
- Target pane must be provided by `--tmux-pane` or `CLAUDE_REVIEW_TMUX_PANE`; default auto-detection is not supported.
- Target pane must be in an auto-accept permission mode such as `bypassPermissions`, `dontAsk`, or `acceptEdits`.
- Review output defaults to `docs/reviews/claude-code/YYYYMMDD/` inside `--cwd`.
- Review output remains git-visible unless the repo owner separately ignores it.
- The helper must not edit `.gitignore`, `.git/info/exclude`, git config, or any other git-related file to hide review artifacts.
- Expected new git-visible changes after a round are only the designated output file and parent directories created solely for it.
- Claude Code output is evidence, not authority; Codex still verifies every issue before accepting it.

---

## File Structure

- Modify: `SKILL.md`
  - Replace CLI backend instructions with tmux-only orchestration.
  - Keep the existing design/plan/code review prompt templates, adjusted so Claude Code writes a result file.
  - Point agents to `tmux-backend.md` before invoking the helper.

- Create: `tmux-backend.md`
  - Document pane selection, required permission mode, prompt delivery, output contract, side-effect guard, timeout, retry, and diagnostics.

- Rewrite: `lib/invoke-claude.sh`
  - Remove all `claude -p`, session id, model, effort, allowedTools/disallowedTools, and heartbeat CLI logic.
  - Parse the tmux-only interface.
  - Build wrapper prompts, dispatch via tmux buffers, poll the result file, and enforce git-visible side-effect checks.

- Create: `tests/test-invoke-claude-tmux.sh`
  - A dependency-free bash test harness using a fake `tmux` binary and temporary git repositories.
  - Covers argument rejection, pane requirement, dry-run, successful sentinel polling, and side-effect failure.

---

### Task 1: Add Helper Test Harness

**Files:**
- Create: `tests/test-invoke-claude-tmux.sh`
- Modify: none

**Interfaces:**
- Consumes: current `lib/invoke-claude.sh` path.
- Produces: executable test command `bash tests/test-invoke-claude-tmux.sh`.

- [ ] **Step 1: Create the test script with fake tmux support**

Create `tests/test-invoke-claude-tmux.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HELPER="$ROOT/lib/invoke-claude.sh"
TMP_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/claude-tmux-test.XXXXXX")"

cleanup() {
  rm -rf "$TMP_ROOT"
}
trap cleanup EXIT

fail() {
  printf 'FAIL: %s\n' "$*" >&2
  exit 1
}

assert_contains() {
  local file="$1"
  local pattern="$2"
  if ! grep -Fq "$pattern" "$file"; then
    printf '--- %s ---\n' "$file" >&2
    cat "$file" >&2
    fail "expected pattern not found: $pattern"
  fi
}

make_repo() {
  local repo="$1"
  mkdir -p "$repo"
  git -C "$repo" init -q
  git -C "$repo" config user.email "test@example.com"
  git -C "$repo" config user.name "Test User"
  printf 'base\n' > "$repo/README.md"
  git -C "$repo" add README.md
  git -C "$repo" commit -qm "init"
}

install_fake_tmux() {
  local bin_dir="$1"
  mkdir -p "$bin_dir"
  cat > "$bin_dir/tmux" <<'FAKE_TMUX'
#!/usr/bin/env bash
set -euo pipefail

printf '%s\n' "$*" >> "${FAKE_TMUX_LOG:?}"

case "${1:-}" in
  list-panes)
    if printf '%s\n' "$*" | grep -Fq 'pane_current_command'; then
      printf '1:0.1 pid=123 active=0 command=claude title=Claude Code path=%s\n' "${FAKE_TMUX_PATH:-/tmp}"
    else
      printf '1:0.1\n'
    fi
    ;;
  capture-pane)
    if [ "${FAKE_PERMISSION_PROMPT:-0}" = "1" ]; then
      printf 'Do you want to allow this tool?\n'
    else
      printf 'Claude Code ready\n'
    fi
    ;;
  load-buffer|send-keys|paste-buffer|delete-buffer)
    if [ "${1:-}" = "send-keys" ] && [ -n "${FAKE_CLAUDE_OUTPUT:-}" ]; then
      mkdir -p "$(dirname "$FAKE_CLAUDE_OUTPUT")"
      cat > "$FAKE_CLAUDE_OUTPUT" <<'OUT'
CLAUDE_REVIEW_RESULT_V1

# Claude Code Review

## Result

LGTM: fake review result.

CLAUDE_REVIEW_DONE
OUT
    fi
    ;;
  *)
    ;;
esac
FAKE_TMUX
  chmod +x "$bin_dir/tmux"
}

run_expect_fail() {
  local name="$1"
  shift
  local out="$TMP_ROOT/$name.out"
  if "$@" > "$out" 2>&1; then
    cat "$out" >&2
    fail "$name unexpectedly succeeded"
  fi
  printf '%s\n' "$out"
}

test_rejects_removed_cli_flag() {
  local out
  out="$(run_expect_fail legacy-session "$HELPER" --phase design --round 1 --session-file old.session)"
  assert_contains "$out" "unknown argument: --session-file"
}

test_requires_explicit_pane() {
  local repo="$TMP_ROOT/repo-no-pane"
  make_repo "$repo"
  local prompt="$TMP_ROOT/prompt.md"
  printf 'Review this.\n' > "$prompt"
  local bin_dir="$TMP_ROOT/bin-no-pane"
  install_fake_tmux "$bin_dir"
  local out
  out="$(PATH="$bin_dir:$PATH" FAKE_TMUX_LOG="$TMP_ROOT/tmux.log" run_expect_fail no-pane \
    "$HELPER" --phase design --round 1 --cwd "$repo" --prompt-file "$prompt")"
  assert_contains "$out" "target pane is required"
}

test_dry_run_prints_paths_without_dispatch() {
  local repo="$TMP_ROOT/repo-dry"
  make_repo "$repo"
  local prompt="$TMP_ROOT/prompt-dry.md"
  printf 'Review this.\n' > "$prompt"
  local bin_dir="$TMP_ROOT/bin-dry"
  install_fake_tmux "$bin_dir"
  local out="$TMP_ROOT/dry.out"
  PATH="$bin_dir:$PATH" FAKE_TMUX_LOG="$TMP_ROOT/tmux-dry.log" \
    "$HELPER" --phase design --round 1 --cwd "$repo" --prompt-file "$prompt" \
      --tmux-pane 1:0.1 --dry-run > "$out" 2>&1
  assert_contains "$out" "tmux_pane=1:0.1"
  assert_contains "$out" "output_file="
}

test_success_allows_designated_output_only() {
  local repo="$TMP_ROOT/repo-success"
  make_repo "$repo"
  local prompt="$TMP_ROOT/prompt-success.md"
  printf 'Review this.\n' > "$prompt"
  local output="$repo/docs/reviews/claude-code/20991231/success.md"
  local bin_dir="$TMP_ROOT/bin-success"
  install_fake_tmux "$bin_dir"
  local out="$TMP_ROOT/success.out"
  PATH="$bin_dir:$PATH" FAKE_TMUX_LOG="$TMP_ROOT/tmux-success.log" FAKE_CLAUDE_OUTPUT="$output" \
    "$HELPER" --phase design --round 1 --cwd "$repo" --prompt-file "$prompt" \
      --tmux-pane 1:0.1 --output-file "$output" --timeout-seconds 5 --poll-seconds 1 > "$out" 2>&1
  assert_contains "$out" "CLAUDE_REVIEW_DONE"
  git -C "$repo" status --short --untracked-files=all > "$TMP_ROOT/status-success.out"
  assert_contains "$TMP_ROOT/status-success.out" "?? docs/reviews/claude-code/20991231/success.md"
}

test_unexpected_change_fails() {
  local repo="$TMP_ROOT/repo-side-effect"
  make_repo "$repo"
  local prompt="$TMP_ROOT/prompt-side-effect.md"
  printf 'Review this.\n' > "$prompt"
  local output="$repo/docs/reviews/claude-code/20991231/side-effect.md"
  local bin_dir="$TMP_ROOT/bin-side-effect"
  install_fake_tmux "$bin_dir"
  cat >> "$bin_dir/tmux" <<'EXTRA_SIDE_EFFECT'
if [ "${1:-}" = "send-keys" ] && [ -n "${FAKE_UNEXPECTED_FILE:-}" ]; then
  printf 'bad\n' > "$FAKE_UNEXPECTED_FILE"
fi
EXTRA_SIDE_EFFECT
  local out
  out="$(PATH="$bin_dir:$PATH" FAKE_TMUX_LOG="$TMP_ROOT/tmux-side-effect.log" \
    FAKE_CLAUDE_OUTPUT="$output" FAKE_UNEXPECTED_FILE="$repo/unexpected.txt" \
    run_expect_fail side-effect "$HELPER" --phase design --round 1 --cwd "$repo" \
      --prompt-file "$prompt" --tmux-pane 1:0.1 --output-file "$output" \
      --timeout-seconds 5 --poll-seconds 1)"
  assert_contains "$out" "unexpected git-visible changes"
}

test_permission_prompt_fails_with_specific_diagnostic() {
  local repo="$TMP_ROOT/repo-permission"
  make_repo "$repo"
  local prompt="$TMP_ROOT/prompt-permission.md"
  printf 'Review this.\n' > "$prompt"
  local output="$repo/docs/reviews/claude-code/20991231/permission.md"
  local bin_dir="$TMP_ROOT/bin-permission"
  install_fake_tmux "$bin_dir"
  local out
  out="$(PATH="$bin_dir:$PATH" FAKE_TMUX_LOG="$TMP_ROOT/tmux-permission.log" \
    FAKE_PERMISSION_PROMPT=1 run_expect_fail permission "$HELPER" --phase design \
      --round 1 --cwd "$repo" --prompt-file "$prompt" --tmux-pane 1:0.1 \
      --output-file "$output" --timeout-seconds 5 --poll-seconds 1)"
  assert_contains "$out" "target pane appears to be waiting for a permission prompt"
}

test_rejects_removed_cli_flag
test_requires_explicit_pane
test_dry_run_prints_paths_without_dispatch
test_success_allows_designated_output_only
test_unexpected_change_fails
test_permission_prompt_fails_with_specific_diagnostic

printf 'PASS: invoke-claude tmux helper tests\n'
```

- [ ] **Step 2: Run the test script and confirm current helper fails**

Run:

```bash
bash tests/test-invoke-claude-tmux.sh
```

Expected: FAIL on `test_rejects_removed_cli_flag`, because the current helper
does not yet report `unknown argument: --session-file` for removed CLI options.
This is the red step.

- [ ] **Step 3: Commit the failing test harness**

```bash
git add tests/test-invoke-claude-tmux.sh
git commit -m "test(review): add tmux helper contract tests"
```

---

### Task 2: Rewrite `invoke-claude.sh` As Tmux-Only Helper

**Files:**
- Modify: `lib/invoke-claude.sh`
- Test: `tests/test-invoke-claude-tmux.sh`

**Interfaces:**
- Consumes:
  - `--phase <name>`
  - `--round <n>`
  - `--prompt-file <path>`
  - `--cwd <path>`
  - `--tmux-pane <target>` or `CLAUDE_REVIEW_TMUX_PANE`
  - optional `--output-dir`, `--output-file`, `--timeout-seconds`, `--poll-seconds`, `--dry-run`
- Produces:
  - Markdown review output containing `CLAUDE_REVIEW_RESULT_V1` and `CLAUDE_REVIEW_DONE`
  - stdout path summary and review file content
  - non-zero exit on missing pane, timeout, permission prompt, bad sentinel, or unexpected git-visible side effects

- [ ] **Step 1: Replace the helper with tmux-only parsing and validation**

Replace `lib/invoke-claude.sh` with this complete implementation:

```bash
#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage:
  invoke-claude.sh --phase <name> --round <n> --prompt-file <path> --cwd <path> [options]

Required:
  --phase <name>
  --round <n>
  --prompt-file <path>
  --cwd <path>

Options:
  --tmux-pane <target>     tmux target pane, e.g. 1:0.1. Falls back to CLAUDE_REVIEW_TMUX_PANE.
  --output-dir <path>      Review output dir. Default: docs/reviews/claude-code/YYYYMMDD under --cwd.
  --output-file <path>     Exact review output file. Overrides --output-dir filename generation.
  --timeout-seconds <n>    Per-round timeout. Default: 900.
  --poll-seconds <n>       Poll interval. Default: 5.
  --dry-run                Print derived paths and commands without dispatching.
  -h, --help               Show help.

USAGE
}

phase=""
round=""
prompt_file=""
cwd=""
tmux_pane="${CLAUDE_REVIEW_TMUX_PANE:-}"
output_dir=""
output_file=""
timeout_seconds=900
poll_seconds=5
dry_run=0

while [ "$#" -gt 0 ]; do
  case "$1" in
    --phase) phase="${2:?missing value for --phase}"; shift 2 ;;
    --round) round="${2:?missing value for --round}"; shift 2 ;;
    --prompt-file) prompt_file="${2:?missing value for --prompt-file}"; shift 2 ;;
    --cwd) cwd="${2:?missing value for --cwd}"; shift 2 ;;
    --tmux-pane) tmux_pane="${2:?missing value for --tmux-pane}"; shift 2 ;;
    --output-dir) output_dir="${2:?missing value for --output-dir}"; shift 2 ;;
    --output-file) output_file="${2:?missing value for --output-file}"; shift 2 ;;
    --timeout-seconds) timeout_seconds="${2:?missing value for --timeout-seconds}"; shift 2 ;;
    --poll-seconds) poll_seconds="${2:?missing value for --poll-seconds}"; shift 2 ;;
    --dry-run) dry_run=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "invoke-claude.sh: unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

require_non_empty() {
  local name="$1"
  local value="$2"
  if [ -z "$value" ]; then
    echo "invoke-claude.sh: $name is required" >&2
    usage >&2
    exit 2
  fi
}

require_uint() {
  local name="$1"
  local value="$2"
  case "$value" in
    ''|*[!0-9]*) echo "invoke-claude.sh: $name must be a non-negative integer" >&2; exit 2 ;;
  esac
}

require_non_empty "--phase" "$phase"
require_non_empty "--round" "$round"
require_non_empty "--prompt-file" "$prompt_file"
require_non_empty "--cwd" "$cwd"
require_non_empty "target pane (--tmux-pane or CLAUDE_REVIEW_TMUX_PANE)" "$tmux_pane"
require_uint "--timeout-seconds" "$timeout_seconds"
require_uint "--poll-seconds" "$poll_seconds"

if ! command -v tmux >/dev/null 2>&1; then
  echo "invoke-claude.sh: tmux not found" >&2
  exit 127
fi

cwd="$(cd "$cwd" && pwd)"
if [ ! -s "$prompt_file" ]; then
  echo "invoke-claude.sh: prompt is empty: $prompt_file" >&2
  exit 2
fi

if ! tmux list-panes -a -F '#{session_name}:#{window_index}.#{pane_index}' | grep -Fxq "$tmux_pane"; then
  echo "invoke-claude.sh: target pane not found: $tmux_pane" >&2
  echo "Available panes:" >&2
  tmux list-panes -a -F '#{session_name}:#{window_index}.#{pane_index} command=#{pane_current_command} title=#{pane_title} path=#{pane_current_path}' >&2
  exit 2
fi

day="$(date +%Y%m%d)"
stamp="$(date +%H%M%S)"
if [ -z "$output_dir" ]; then
  output_dir="$cwd/docs/reviews/claude-code/$day"
elif [ "${output_dir#/}" = "$output_dir" ]; then
  output_dir="$cwd/$output_dir"
fi

if [ -z "$output_file" ]; then
  output_file="$output_dir/${stamp}-${phase}-r${round}.md"
elif [ "${output_file#/}" = "$output_file" ]; then
  output_file="$cwd/$output_file"
fi

mkdir -p "$(dirname "$output_file")"
output_file="$(cd "$(dirname "$output_file")" && pwd)/$(basename "$output_file")"

case "$output_file" in
  "$cwd"/*) output_rel="${output_file#"$cwd"/}" ;;
  *) output_rel="" ;;
esac

tmp_dir="$(mktemp -d "${TMPDIR:-/tmp}/claude-review-tmux.XXXXXX")"
cleanup() {
  rm -rf "$tmp_dir"
}
trap cleanup EXIT

before_status="$tmp_dir/before.status"
after_status="$tmp_dir/after.status"
delta_status="$tmp_dir/delta.status"
wrapper_prompt="$tmp_dir/wrapper-prompt.md"

git -C "$cwd" status --short --untracked-files=all | sort > "$before_status"

cat > "$wrapper_prompt" <<PROMPT
You are acting as an external reviewer for Codex.

Working directory: $cwd
Review output file: $output_file

Rules:
- Read files as needed for the review.
- Do not edit source, spec, helper, git metadata, or configuration files.
- The only write allowed is the review output file above.
- Write the complete result to the output file.
- The file must contain both sentinel lines:
  CLAUDE_REVIEW_RESULT_V1
  CLAUDE_REVIEW_DONE
- If you cannot write the file, say why in the pane.

Original prompt:

$(cat "$prompt_file")
PROMPT

if [ "$dry_run" -eq 1 ]; then
  printf 'tmux_pane=%s\n' "$tmux_pane"
  printf 'cwd=%s\n' "$cwd"
  printf 'prompt_file=%s\n' "$prompt_file"
  printf 'output_file=%s\n' "$output_file"
  printf 'timeout_seconds=%s\n' "$timeout_seconds"
  printf 'poll_seconds=%s\n' "$poll_seconds"
  exit 0
fi

buffer_name="claude_review_${phase}_r${round}_$$"
tmux load-buffer -b "$buffer_name" "$wrapper_prompt"
tmux send-keys -t "$tmux_pane" C-u
tmux paste-buffer -t "$tmux_pane" -b "$buffer_name"
sleep 0.2
tmux send-keys -t "$tmux_pane" Enter
tmux delete-buffer -b "$buffer_name" 2>/dev/null || true

start_epoch="$(date +%s)"
permission_prompt_hits=0
while true; do
  if [ -f "$output_file" ] && grep -Fq 'CLAUDE_REVIEW_RESULT_V1' "$output_file" && grep -Fq 'CLAUDE_REVIEW_DONE' "$output_file"; then
    break
  fi

  pane_tail="$(tmux capture-pane -pt "$tmux_pane" -S -80 -J 2>/dev/null || true)"
  live_tail="$(printf '%s\n' "$pane_tail" | awk 'NF { line[++n]=$0 } END { start=n-4; if (start<1) start=1; for (i=start; i<=n; i++) print line[i] }')"
  if printf '%s\n' "$live_tail" | grep -Eiq 'do you want to allow|allow this command|yes, and don.t ask again|no, and tell claude|approval required'; then
    permission_prompt_hits=$((permission_prompt_hits + 1))
  else
    permission_prompt_hits=0
  fi
  if [ "$permission_prompt_hits" -ge 2 ]; then
    echo "invoke-claude.sh: target pane appears to be waiting for a permission prompt" >&2
    echo "Switch the pane to bypassPermissions, dontAsk, or acceptEdits and retry." >&2
    exit 124
  fi

  now_epoch="$(date +%s)"
  if [ "$timeout_seconds" -gt 0 ] && [ $((now_epoch - start_epoch)) -ge "$timeout_seconds" ]; then
    echo "invoke-claude.sh: timed out waiting for review output: $output_file" >&2
    tmux capture-pane -pt "$tmux_pane" -S -80 -J >&2 || true
    exit 124
  fi

  sleep "$poll_seconds"
done

git -C "$cwd" status --short --untracked-files=all | sort > "$after_status"
comm -13 "$before_status" "$after_status" > "$delta_status"

if [ -s "$delta_status" ]; then
  if [ -n "$output_rel" ]; then
    allowed_line="?? $output_rel"
    unexpected="$tmp_dir/unexpected.status"
    grep -Fxv "$allowed_line" "$delta_status" > "$unexpected" || true
  else
    unexpected="$delta_status"
  fi
  if [ -s "$unexpected" ]; then
    echo "invoke-claude.sh: unexpected git-visible changes after review round" >&2
    echo "Before status:" >&2
    cat "$before_status" >&2
    echo "After status:" >&2
    cat "$after_status" >&2
    echo "Allowed output file: $output_file" >&2
    tmux capture-pane -pt "$tmux_pane" -S -80 -J >&2 || true
    exit 1
  fi
fi

cat "$output_file"
printf '\n[claude-cross-model-review] output: %s\n' "$output_file"
```

- [ ] **Step 2: Run tests to verify helper behavior**

Run:

```bash
bash tests/test-invoke-claude-tmux.sh
```

Expected: `PASS: invoke-claude tmux helper tests`

- [ ] **Step 3: Run static CLI removal check**

Run:

```bash
rg -n 'claude -p|--session-id|--resume|--model|--effort|permission-mode|allowedTools|disallowedTools' lib/invoke-claude.sh
```

Expected: no matches.

- [ ] **Step 4: Commit helper rewrite**

```bash
git add lib/invoke-claude.sh tests/test-invoke-claude-tmux.sh
git commit -m "fix(review): replace Claude CLI helper with tmux dispatch"
```

---

### Task 3: Add Tmux Backend Documentation

**Files:**
- Create: `tmux-backend.md`

**Interfaces:**
- Consumes: helper interface from Task 2.
- Produces: backend rules read by `SKILL.md`.

- [ ] **Step 1: Create `tmux-backend.md`**

````markdown
# Tmux Backend

Claude review runs through an existing Claude Code pane. This backend does not
start `claude -p` and does not create a hidden reviewer process.

## Required Pane State

The target pane must be a Claude Code session in an auto-accept permission mode:

- `bypassPermissions`
- `dontAsk`
- `acceptEdits`

`plan` mode and default prompt-on-write modes are invalid because the helper
polls an output file and cannot answer interactive permission prompts.

## Pane Selection

Pass exactly one of:

- `--tmux-pane <target>`
- `CLAUDE_REVIEW_TMUX_PANE=<target>`

Default auto-detection is not supported. If no pane is provided, the helper
prints available panes and exits.

## Prompt Delivery

The helper:

1. Records git status before dispatch.
2. Wraps the original prompt with cwd, output file, write rules, and sentinels.
3. Loads the wrapper prompt into a tmux buffer.
4. Clears partial input with `C-u`.
5. Pastes the buffer into the pane.
6. Sends Enter after a short delay.
7. Deletes the tmux buffer.

## Output Contract

The result file must contain:

```markdown
CLAUDE_REVIEW_RESULT_V1

# Claude Code Review

## Result

<ISSUE entries or LGTM>

CLAUDE_REVIEW_DONE
```

Codex reads the file. Pane scrollback is diagnostics only.

## Side-Effect Guard

Review output is repo-local by default:

```text
docs/reviews/claude-code/YYYYMMDD/
```

The helper must not edit `.gitignore`, `.git/info/exclude`, git config, or any
other git-related file to hide review artifacts.

After the review, allowed new git-visible changes are:

- the designated output file
- parent directories created only to hold the designated output file

Any other new git-visible change fails the round.

## Timeout And Permission Diagnostics

If the result file does not appear before timeout, the helper captures pane tail
for diagnostics.

If pane tail appears to show a permission prompt, the helper exits with a
permission-mode diagnostic instead of a generic timeout.

## Retry

Retry once with the same pane and a new output file. Review failure is not LGTM.
````

- [ ] **Step 2: Verify backend doc contains required sections**

Run:

```bash
rg -n 'Required Pane State|Pane Selection|Prompt Delivery|Output Contract|Side-Effect Guard|Timeout And Permission Diagnostics|Retry' tmux-backend.md
```

Expected: one match for each section.

- [ ] **Step 3: Commit backend documentation**

```bash
git add tmux-backend.md
git commit -m "docs(review): document tmux backend protocol"
```

---

### Task 4: Update `SKILL.md` To Tmux-Only Orchestration

**Files:**
- Modify: `SKILL.md`
- Reference: `tmux-backend.md`

**Interfaces:**
- Consumes: helper interface from Task 2 and backend doc from Task 3.
- Produces: updated skill instructions that no longer direct agents to run `claude -p`.

- [ ] **Step 1: Replace Overview and Backend Detection**

In `SKILL.md`, replace the current Overview and Backend Detection sections with:

```markdown
## Overview

Codex owns orchestration, verification, fixes, commits, and final decisions.
Claude Code is an external reviewer reached through an existing tmux pane.

Core rule: Claude's output is evidence, not authority. Codex must verify every
accepted finding against the actual repository before changing files.

This skill is tmux-only. Do not call `claude -p`; do not use session ids,
model flags, effort flags, or Claude CLI tool restrictions.

## Backend Requirements

Before invoking Claude, read `tmux-backend.md` in this skill directory.

The target Claude Code pane must:

- be explicitly provided by `--tmux-pane` or `CLAUDE_REVIEW_TMUX_PANE`
- run in an auto-accept permission mode such as `bypassPermissions`, `dontAsk`,
  or `acceptEdits`
- write review output to the file requested by the helper

Pane scrollback is diagnostics only. The result file is the source of truth.
```

- [ ] **Step 2: Replace Invocation Interface Examples**

Replace the current helper examples with:

````markdown
## Invocation Interface

Use the helper script. It reads the prompt from a file, sends it to the target
tmux pane, waits for a sentinel-delimited output file, and prints the file path.

Round 1:

```bash
/Users/jdy/Documents/skills/claude-cross-model-review/lib/invoke-claude.sh \
  --phase design \
  --round 1 \
  --cwd /path/to/repo \
  --prompt-file /tmp/claude-review-prompt.txt \
  --tmux-pane 1:0.1 \
  --timeout-seconds 900 \
  --poll-seconds 5
```

Round 2+:

```bash
/Users/jdy/Documents/skills/claude-cross-model-review/lib/invoke-claude.sh \
  --phase design \
  --round 2 \
  --cwd /path/to/repo \
  --prompt-file /tmp/claude-review-r2.txt \
  --tmux-pane 1:0.1 \
  --timeout-seconds 900 \
  --poll-seconds 5
```

The helper defaults to `docs/reviews/claude-code/YYYYMMDD/` under `--cwd`.
````

- [ ] **Step 3: Update Prompt Rules**

In `SKILL.md`, update Round 1 prompt requirements to include:

```markdown
- output file contract: Claude Code must write ISSUE entries or LGTM into the
  helper-designated file with `CLAUDE_REVIEW_RESULT_V1` and `CLAUDE_REVIEW_DONE`
```

Update Round 2+ prompt requirements to include:

```markdown
Before responding, re-read these modified files:
<files changed since last round>

Write the complete re-review result to the new helper-designated output file.
Do not edit any source/spec/helper/git files.
```

- [ ] **Step 4: Rewrite the Review Loop section**

Replace the current `Review Loop` section's dispatch and re-dispatch language with tmux semantics:

```markdown
## Review Loop

1. Dispatch Claude Code through the tmux helper with the phase prompt.
2. Read the helper-designated output file.
3. For every issue Claude claims with confidence >= 70:
   - VERIFY: inspect the actual file/code/spec.
   - EVALUATE: decide whether it is correct for this project.
   - CLASSIFY: bug, missing requirement, intentional tradeoff, or false positive.
   - UPDATE: maintain `[phase, location, summary, status, confidence]`.
   - ACCEPT or REJECT.
4. If any issue is accepted, fix root cause in one pass.
5. Re-dispatch an incremental prompt to the same `--tmux-pane` with the next
   `--round` number and a new output file. Include changed files plus the
   accepted/rejected issue ledger, and require Claude Code to re-read changed
   files before responding.
6. Stop only on LGTM, all remaining issues rejected with no changes, same issue
   repeated twice with no new evidence, or round 5.
```

- [ ] **Step 5: Update Failure Handling and Common Mistakes**

Replace the entire `Failure Handling` section, including the trailing
`Default per-round wait` and `Heartbeat output ... claude -p` paragraphs, with
tmux output-file language:

```markdown
If `invoke-claude.sh` exits non-zero, exits `124` after timeout, reports a
permission prompt, or returns an output file without required sentinels:
1. Retry once with the same pane and a new output file.
2. If Round 1 fails twice, stop the Claude-backed phase and report the failure.
3. If Round 2+ fails twice, keep the issue tracker and run a local Codex review
   of the changed files before deciding whether to proceed.

Review failure is not LGTM.
```

Remove common mistakes about unsupported CLI flags and replace them with:

```markdown
| Mistake | Correction |
|---|---|
| Calling `claude -p` | Use the tmux helper only |
| Letting the helper guess a pane | Provide `--tmux-pane` or `CLAUDE_REVIEW_TMUX_PANE` |
| Using a pane in default permission mode | Use `bypassPermissions`, `dontAsk`, or `acceptEdits` |
| Reading pane scrollback as the result | Read the output file only |
| Treating review failure as LGTM | Failure is not approval |
```

- [ ] **Step 6: Remove remaining CLI-only historical sections**

Delete the `Baseline Failures This Skill Prevents` section entirely. Do not
replace it with a historical migration note, because the static removal gate
below intentionally fails if active files still contain removed Claude CLI
tokens.

Also remove any leftover bullets or paragraphs that describe CLI read-only defaults,
`--session-id`, `--resume`, model/effort flags, allowedTools/disallowedTools, or
heartbeat behavior as active instructions.

- [ ] **Step 7: Verify `SKILL.md` no longer instructs CLI usage**

Run:

```bash
rg -n 'claude -p|--session-id|--resume|--model|--effort|permission-mode dontAsk|allowedTools|disallowedTools|heartbeat' SKILL.md
```

Expected: no matches.

- [ ] **Step 8: Commit skill documentation update**

```bash
git add SKILL.md
git commit -m "docs(review): switch skill instructions to tmux backend"
```

---

### Task 5: End-To-End Verification

**Files:**
- Modify: none unless verification exposes a bug.

**Interfaces:**
- Consumes: implemented helper, updated docs, current Claude Code tmux pane.
- Produces: verified tmux review output file and clean static checks.

- [ ] **Step 1: Run the helper test suite**

```bash
bash tests/test-invoke-claude-tmux.sh
```

Expected: `PASS: invoke-claude tmux helper tests`

- [ ] **Step 2: Run static CLI removal check across active files**

```bash
rg -n 'claude -p|--session-id|--resume|--model|--effort|permission-mode|allowedTools|disallowedTools' SKILL.md lib/invoke-claude.sh tmux-backend.md
```

Expected: no active CLI invocation or CLI-only option remains.

- [ ] **Step 3: Run helper dry-run against the live pane**

```bash
/Users/jdy/Documents/skills/claude-cross-model-review/lib/invoke-claude.sh \
  --phase design \
  --round 1 \
  --cwd /Users/jdy/Documents/skills/claude-cross-model-review \
  --prompt-file docs/superpowers/specs/2026-06-27-tmux-only-claude-cross-model-review-design.md \
  --tmux-pane 1:0.1 \
  --dry-run
```

Expected output includes:

```text
tmux_pane=1:0.1
output_file=/Users/jdy/Documents/skills/claude-cross-model-review/docs/reviews/claude-code/<date>/<time>-design-r1.md
```

- [ ] **Step 4: Run a live smoke review**

Create `/tmp/claude-review-smoke.md`:

```markdown
Review this smoke target:

/Users/jdy/Documents/skills/claude-cross-model-review/tmux-backend.md

Return LGTM unless the file is missing required backend sections.
Only report confidence >= 70.
```

Run:

```bash
/Users/jdy/Documents/skills/claude-cross-model-review/lib/invoke-claude.sh \
  --phase smoke \
  --round 1 \
  --cwd /Users/jdy/Documents/skills/claude-cross-model-review \
  --prompt-file /tmp/claude-review-smoke.md \
  --tmux-pane 1:0.1 \
  --timeout-seconds 900 \
  --poll-seconds 5
```

Expected:

- stdout includes `CLAUDE_REVIEW_RESULT_V1`
- stdout includes `CLAUDE_REVIEW_DONE`
- any new git-visible change is only the designated review output file

- [ ] **Step 5: Confirm final git status**

```bash
git status --short --untracked-files=all
```

Expected:

- tracked implementation files are committed
- review output files may remain untracked under `docs/reviews/claude-code/`
- no unexpected modified source/doc/test files remain

- [ ] **Step 6: Commit final verification fixes if needed**

If Steps 1-5 reveal fixes, apply them and commit:

```bash
git add SKILL.md tmux-backend.md lib/invoke-claude.sh tests/test-invoke-claude-tmux.sh
git commit -m "fix(review): close tmux backend verification gaps"
```

Do not commit review output files.
