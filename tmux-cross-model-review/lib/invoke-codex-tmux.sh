#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage:
  invoke-codex-tmux.sh --phase <name> --round <n> --prompt-file <path> --cwd <path> [options]
  invoke-codex-tmux.sh --preflight --cwd <path> [options]

Required for review rounds:
  --phase <name>
  --round <n>
  --prompt-file <path>
  --cwd <path>

Required for preflight:
  --cwd <path>

Options:
  --codex-tmux-pane <target>  tmux target pane, e.g. 1:0.1. Falls back to CODEX_REVIEW_TMUX_PANE.
  --output-dir <path>         Review output dir. Default: docs/reviews/codex/YYYYMMDD under --cwd.
  --output-file <path>        Exact review output file. Overrides --output-dir filename generation.
  --timeout-seconds <n>       Per-round timeout. Default: 900.
  --poll-seconds <n>          Poll interval. Default: 5.
  --preflight                 Run a transport smoke test instead of a review round.
  --dry-run                   Print derived paths and commands without dispatching.
  -h, --help                  Show help.

USAGE
}

phase=""
round=""
prompt_file=""
cwd=""
codex_tmux_pane="${CODEX_REVIEW_TMUX_PANE:-}"
output_dir=""
output_file=""
timeout_seconds=900
poll_seconds=5
preflight=0
dry_run=0

while [ "$#" -gt 0 ]; do
  case "$1" in
    --phase) phase="${2:?missing value for --phase}"; shift 2 ;;
    --round) round="${2:?missing value for --round}"; shift 2 ;;
    --prompt-file) prompt_file="${2:?missing value for --prompt-file}"; shift 2 ;;
    --cwd) cwd="${2:?missing value for --cwd}"; shift 2 ;;
    --codex-tmux-pane) codex_tmux_pane="${2:?missing value for --codex-tmux-pane}"; shift 2 ;;
    --output-dir) output_dir="${2:?missing value for --output-dir}"; shift 2 ;;
    --output-file) output_file="${2:?missing value for --output-file}"; shift 2 ;;
    --timeout-seconds) timeout_seconds="${2:?missing value for --timeout-seconds}"; shift 2 ;;
    --poll-seconds) poll_seconds="${2:?missing value for --poll-seconds}"; shift 2 ;;
    --preflight) preflight=1; shift ;;
    --dry-run) dry_run=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "invoke-codex-tmux.sh: unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

require_non_empty() {
  local name="$1"
  local value="$2"
  if [ -z "$value" ]; then
    echo "invoke-codex-tmux.sh: $name is required" >&2
    usage >&2
    exit 2
  fi
}

require_uint() {
  local name="$1"
  local value="$2"
  case "$value" in
    ''|*[!0-9]*) echo "invoke-codex-tmux.sh: $name must be a non-negative integer" >&2; exit 2 ;;
  esac
}

require_non_empty "--cwd" "$cwd"
require_non_empty "Codex target pane" "$codex_tmux_pane"
require_uint "--timeout-seconds" "$timeout_seconds"
require_uint "--poll-seconds" "$poll_seconds"

if [ "$preflight" -eq 0 ]; then
  require_non_empty "--phase" "$phase"
  require_non_empty "--round" "$round"
  require_non_empty "--prompt-file" "$prompt_file"
elif [ -z "$phase" ]; then
  phase="preflight"
fi

if ! command -v tmux >/dev/null 2>&1; then
  echo "invoke-codex-tmux.sh: tmux not found" >&2
  exit 127
fi

cwd="$(cd "$cwd" && pwd)"
if [ "$preflight" -eq 0 ] && [ ! -s "$prompt_file" ]; then
  echo "invoke-codex-tmux.sh: prompt is empty: $prompt_file" >&2
  exit 2
fi

if ! tmux list-panes -a -F '#{session_name}:#{window_index}.#{pane_index}' | grep -Fxq "$codex_tmux_pane"; then
  echo "invoke-codex-tmux.sh: Codex target pane not found: $codex_tmux_pane" >&2
  echo "Available panes:" >&2
  tmux list-panes -a -F '#{session_name}:#{window_index}.#{pane_index} command=#{pane_current_command} title=#{pane_title} path=#{pane_current_path}' >&2
  exit 2
fi

day="$(date +%Y%m%d)"
stamp="$(date +%H%M%S)"
if [ -z "$output_dir" ]; then
  output_dir="$cwd/docs/reviews/codex/$day"
elif [ "${output_dir#/}" = "$output_dir" ]; then
  output_dir="$cwd/$output_dir"
fi

if [ -z "$output_file" ]; then
  if [ "$preflight" -eq 1 ]; then
    output_file="$output_dir/${stamp}-preflight.md"
  else
    output_file="$output_dir/${stamp}-${phase}-r${round}.md"
  fi
elif [ "${output_file#/}" = "$output_file" ]; then
  output_file="$cwd/$output_file"
fi

mkdir -p "$(dirname "$output_file")"
output_file="$(cd "$(dirname "$output_file")" && pwd)/$(basename "$output_file")"

case "$output_file" in
  "$cwd"/*) output_rel="${output_file#"$cwd"/}" ;;
  *) output_rel="" ;;
esac

tmp_dir="$(mktemp -d "${TMPDIR:-/tmp}/codex-review-tmux.XXXXXX")"
cleanup() {
  rm -rf "$tmp_dir"
}
trap cleanup EXIT

before_status="$tmp_dir/before.status"
after_status="$tmp_dir/after.status"
delta_status="$tmp_dir/delta.status"
before_tracked_diff="$tmp_dir/before.tracked.diff"
after_tracked_diff="$tmp_dir/after.tracked.diff"
before_untracked_manifest="$tmp_dir/before.untracked.manifest"
after_untracked_manifest="$tmp_dir/after.untracked.manifest"
wrapper_prompt="$tmp_dir/wrapper-prompt.md"
preflight_prompt="$tmp_dir/preflight-prompt.md"

snapshot_untracked_manifest() {
  local manifest="$1"
  git -C "$cwd" ls-files --others --exclude-standard -z |
    while IFS= read -r -d '' path; do
      if [ -n "$output_rel" ] && [ "$path" = "$output_rel" ]; then
        continue
      fi
      if hash="$(git -C "$cwd" hash-object --no-filters -- "$path" 2>/dev/null)"; then
        printf '%s %s\n' "$hash" "$path"
      else
        printf 'unhashable %s\n' "$path"
      fi
    done | LC_ALL=C sort > "$manifest"
}

git -C "$cwd" status --short --untracked-files=all | sort > "$before_status"
git -C "$cwd" diff --no-ext-diff --binary HEAD > "$before_tracked_diff"
snapshot_untracked_manifest "$before_untracked_manifest"

if [ "$preflight" -eq 1 ]; then
  cat > "$preflight_prompt" <<'PREFLIGHT'
This is a Codex reviewer pane preflight. Do not inspect or edit repository files.
Write a minimal successful preflight result to the requested output file.
PREFLIGHT
  prompt_file="$preflight_prompt"
fi

cat > "$wrapper_prompt" <<PROMPT
You are acting as an external reviewer for Claude Code.

Working directory: $cwd
Review output file: $output_file

Rules:
- Read files only as needed for the review.
- Do not edit source, spec, plan, helper, git metadata, configuration, or secret files.
- The only write allowed is the review output file above.
- Write the complete result to the output file.
- The file must contain both sentinel lines:
  CODEX_REVIEW_RESULT_V1
  CODEX_REVIEW_DONE
- If you cannot write the file, say why in the pane.

Original prompt:

$(cat "$prompt_file")
PROMPT

if [ "$dry_run" -eq 1 ]; then
  printf 'codex_tmux_pane=%s\n' "$codex_tmux_pane"
  printf 'cwd=%s\n' "$cwd"
  printf 'prompt_file=%s\n' "$prompt_file"
  printf 'output_file=%s\n' "$output_file"
  printf 'timeout_seconds=%s\n' "$timeout_seconds"
  printf 'poll_seconds=%s\n' "$poll_seconds"
  printf 'preflight=%s\n' "$preflight"
  exit 0
fi

buffer_name="codex_review_${phase}_r${round:-0}_$$"
tmux load-buffer -b "$buffer_name" "$wrapper_prompt"
tmux send-keys -t "$codex_tmux_pane" C-u
tmux paste-buffer -t "$codex_tmux_pane" -b "$buffer_name"
sleep 0.2
tmux send-keys -t "$codex_tmux_pane" Enter
tmux delete-buffer -b "$buffer_name" 2>/dev/null || true

start_epoch="$(date +%s)"
permission_prompt_hits=0
while true; do
  if [ -f "$output_file" ] && grep -Fq 'CODEX_REVIEW_RESULT_V1' "$output_file" && grep -Fq 'CODEX_REVIEW_DONE' "$output_file"; then
    break
  fi

  pane_tail="$(tmux capture-pane -pt "$codex_tmux_pane" -S -80 -J 2>/dev/null || true)"
  live_tail="$(printf '%s\n' "$pane_tail" | awk 'NF { line[++n]=$0 } END { start=n-4; if (start<1) start=1; for (i=start; i<=n; i++) print line[i] }')"
  if printf '%s\n' "$live_tail" | grep -Eiq 'allow codex to run|approval requested|approval needed|needs your approval|yes, and don.t ask again for commands that start with|do you want to allow|allow this command|approval required|requires approval'; then
    permission_prompt_hits=$((permission_prompt_hits + 1))
  else
    permission_prompt_hits=0
  fi
  if [ "$permission_prompt_hits" -ge 2 ]; then
    echo "invoke-codex-tmux.sh: Codex target pane appears to be waiting for a permission prompt" >&2
    echo "Start the pane with --ask-for-approval never, --sandbox workspace-write, and --no-alt-screen, or use an equivalent profile." >&2
    exit 124
  fi

  now_epoch="$(date +%s)"
  if [ "$timeout_seconds" -gt 0 ] && [ $((now_epoch - start_epoch)) -ge "$timeout_seconds" ]; then
    echo "invoke-codex-tmux.sh: timed out waiting for Codex review output: $output_file" >&2
    tmux capture-pane -pt "$codex_tmux_pane" -S -80 -J >&2 || true
    exit 124
  fi

  sleep "$poll_seconds"
done

git -C "$cwd" status --short --untracked-files=all | sort > "$after_status"
git -C "$cwd" diff --no-ext-diff --binary HEAD > "$after_tracked_diff"
snapshot_untracked_manifest "$after_untracked_manifest"
comm -13 "$before_status" "$after_status" > "$delta_status"

if ! cmp -s "$before_tracked_diff" "$after_tracked_diff"; then
  echo "invoke-codex-tmux.sh: tracked file content changed during review round" >&2
  echo "Allowed output file: $output_file" >&2
  echo "Tracked diff before/after changed:" >&2
  diff -u "$before_tracked_diff" "$after_tracked_diff" >&2 || true
  tmux capture-pane -pt "$codex_tmux_pane" -S -80 -J >&2 || true
  exit 1
fi

if [ -s "$delta_status" ]; then
  if [ -n "$output_rel" ]; then
    allowed_line="?? $output_rel"
    unexpected="$tmp_dir/unexpected.status"
    grep -Fxv "$allowed_line" "$delta_status" > "$unexpected" || true
  else
    unexpected="$delta_status"
  fi
  if [ -s "$unexpected" ]; then
    echo "invoke-codex-tmux.sh: unexpected git-visible changes after review round" >&2
    echo "Before status:" >&2
    cat "$before_status" >&2
    echo "After status:" >&2
    cat "$after_status" >&2
    echo "Allowed output file: $output_file" >&2
    tmux capture-pane -pt "$codex_tmux_pane" -S -80 -J >&2 || true
    exit 1
  fi
fi

if ! cmp -s "$before_untracked_manifest" "$after_untracked_manifest"; then
  echo "invoke-codex-tmux.sh: pre-existing untracked files changed during review round" >&2
  echo "Allowed output file: $output_file" >&2
  echo "Untracked manifest before/after changed:" >&2
  diff -u "$before_untracked_manifest" "$after_untracked_manifest" >&2 || true
  tmux capture-pane -pt "$codex_tmux_pane" -S -80 -J >&2 || true
  exit 1
fi

cat "$output_file"
printf '\n[tmux-cross-model-review] codex output: %s\n' "$output_file"
