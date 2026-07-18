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
    printf -- '--- %s ---\n' "$file" >&2
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

test_dirty_tracked_file_mutation_fails() {
  local repo="$TMP_ROOT/repo-dirty-tracked"
  make_repo "$repo"
  printf 'user work in progress\n' > "$repo/README.md"
  local prompt="$TMP_ROOT/prompt-dirty-tracked.md"
  printf 'Review this.\n' > "$prompt"
  local output="$repo/docs/reviews/claude-code/20991231/dirty-tracked.md"
  local bin_dir="$TMP_ROOT/bin-dirty-tracked"
  install_fake_tmux "$bin_dir"
  cat >> "$bin_dir/tmux" <<'EXTRA_DIRTY_TRACKED'
if [ "${1:-}" = "send-keys" ] && [ -n "${FAKE_MUTATE_FILE:-}" ]; then
  printf 'reviewer changed dirty tracked file\n' > "$FAKE_MUTATE_FILE"
fi
EXTRA_DIRTY_TRACKED
  local out
  out="$(PATH="$bin_dir:$PATH" FAKE_TMUX_LOG="$TMP_ROOT/tmux-dirty-tracked.log" \
    FAKE_CLAUDE_OUTPUT="$output" FAKE_MUTATE_FILE="$repo/README.md" \
    run_expect_fail dirty-tracked "$HELPER" --phase design --round 1 --cwd "$repo" \
      --prompt-file "$prompt" --tmux-pane 1:0.1 --output-file "$output" \
      --timeout-seconds 5 --poll-seconds 1)"
  assert_contains "$out" "tracked file content changed during review round"
}

test_preexisting_untracked_mutation_fails() {
  local repo="$TMP_ROOT/repo-untracked-mutation"
  make_repo "$repo"
  printf 'user scratch\n' > "$repo/notes.txt"
  local prompt="$TMP_ROOT/prompt-untracked-mutation.md"
  printf 'Review this.\n' > "$prompt"
  local output="$repo/docs/reviews/claude-code/20991231/untracked-mutation.md"
  local bin_dir="$TMP_ROOT/bin-untracked-mutation"
  install_fake_tmux "$bin_dir"
  cat >> "$bin_dir/tmux" <<'EXTRA_UNTRACKED_MUTATION'
if [ "${1:-}" = "send-keys" ] && [ -n "${FAKE_MUTATE_FILE:-}" ]; then
  printf 'reviewer changed untracked file\n' > "$FAKE_MUTATE_FILE"
fi
EXTRA_UNTRACKED_MUTATION
  local out
  out="$(PATH="$bin_dir:$PATH" FAKE_TMUX_LOG="$TMP_ROOT/tmux-untracked-mutation.log" \
    FAKE_CLAUDE_OUTPUT="$output" FAKE_MUTATE_FILE="$repo/notes.txt" \
    run_expect_fail untracked-mutation "$HELPER" --phase design --round 1 --cwd "$repo" \
      --prompt-file "$prompt" --tmux-pane 1:0.1 --output-file "$output" \
      --timeout-seconds 5 --poll-seconds 1)"
  assert_contains "$out" "pre-existing untracked files changed during review round"
}

test_preexisting_untracked_deletion_fails() {
  local repo="$TMP_ROOT/repo-untracked-deletion"
  make_repo "$repo"
  printf 'user scratch\n' > "$repo/notes.txt"
  local prompt="$TMP_ROOT/prompt-untracked-deletion.md"
  printf 'Review this.\n' > "$prompt"
  local output="$repo/docs/reviews/claude-code/20991231/untracked-deletion.md"
  local bin_dir="$TMP_ROOT/bin-untracked-deletion"
  install_fake_tmux "$bin_dir"
  cat >> "$bin_dir/tmux" <<'EXTRA_UNTRACKED_DELETION'
if [ "${1:-}" = "send-keys" ] && [ -n "${FAKE_DELETE_FILE:-}" ]; then
  rm -f "$FAKE_DELETE_FILE"
fi
EXTRA_UNTRACKED_DELETION
  local out
  out="$(PATH="$bin_dir:$PATH" FAKE_TMUX_LOG="$TMP_ROOT/tmux-untracked-deletion.log" \
    FAKE_CLAUDE_OUTPUT="$output" FAKE_DELETE_FILE="$repo/notes.txt" \
    run_expect_fail untracked-deletion "$HELPER" --phase design --round 1 --cwd "$repo" \
      --prompt-file "$prompt" --tmux-pane 1:0.1 --output-file "$output" \
      --timeout-seconds 5 --poll-seconds 1)"
  assert_contains "$out" "pre-existing untracked files changed during review round"
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
test_dirty_tracked_file_mutation_fails
test_preexisting_untracked_mutation_fails
test_preexisting_untracked_deletion_fails
test_permission_prompt_fails_with_specific_diagnostic

printf 'PASS: invoke-claude tmux helper tests\n'
