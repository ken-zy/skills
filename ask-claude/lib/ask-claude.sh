#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage:
  ask-claude.sh [--prompt-file <path>] [--model <model>] [--effort <level>] [--cwd <path>] [--log-dir <path>]

Options:
  --prompt-file <path>  Read prompt from file. If omitted, stdin is captured.
  --model <model>       Optional Claude model alias or full model name.
  --effort <level>      Optional low|medium|high|xhigh|max.
  --cwd <path>          Working directory. Default: current directory.
  --log-dir <path>      Log root. Default: ~/.codex/logs/ask-claude.
  --dry-run             Print command and derived paths without calling Claude.
  -h, --help            Show help.

The prompt is read from a file or stdin, never passed as a shell argument.
USAGE
}

prompt_file=""
model="${ASK_CLAUDE_MODEL:-}"
effort="${ASK_CLAUDE_EFFORT:-}"
cwd="$PWD"
log_root="${ASK_CLAUDE_LOG_DIR:-$HOME/.codex/logs/ask-claude}"
dry_run=0
owned_prompt_file=0

while [ "$#" -gt 0 ]; do
  case "$1" in
    --prompt-file)
      prompt_file="${2:?missing value for --prompt-file}"
      shift 2
      ;;
    --model)
      model="${2:?missing value for --model}"
      shift 2
      ;;
    --effort)
      effort="${2:?missing value for --effort}"
      shift 2
      ;;
    --cwd)
      cwd="${2:?missing value for --cwd}"
      shift 2
      ;;
    --log-dir)
      log_root="${2:?missing value for --log-dir}"
      shift 2
      ;;
    --dry-run)
      dry_run=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "ask-claude.sh: unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [ -n "$effort" ]; then
  case "$effort" in
    low|medium|high|xhigh|max) ;;
    *)
      echo "ask-claude.sh: unsupported --effort '$effort'" >&2
      exit 2
      ;;
  esac
fi

if ! command -v claude >/dev/null 2>&1; then
  echo "ask-claude.sh: claude CLI not found" >&2
  exit 127
fi

cwd="$(cd "$cwd" && pwd)"

if [ -z "$prompt_file" ]; then
  prompt_file="$(mktemp "${TMPDIR:-/tmp}/ask-claude-prompt.XXXXXX")"
  owned_prompt_file=1
  cat > "$prompt_file"
fi

if [ ! -s "$prompt_file" ]; then
  echo "ask-claude.sh: prompt is empty: $prompt_file" >&2
  [ "$owned_prompt_file" -eq 1 ] && rm -f "$prompt_file"
  exit 2
fi

day="$(date +%Y%m%d)"
stamp="$(date +%H%M%S)"
log_dir="$log_root/$day"
log_file="$log_dir/${stamp}.md"
mkdir -p "$log_dir"

branch="$(git -C "$cwd" branch --show-current 2>/dev/null || printf 'n/a')"

claude_cmd=(
  claude -p
  --permission-mode dontAsk
  --add-dir "$cwd"
  --disallowedTools "Edit,Write,MultiEdit"
  --output-format text
)

if [ -n "$model" ]; then
  claude_cmd+=(--model "$model")
fi

if [ -n "$effort" ]; then
  claude_cmd+=(--effort "$effort")
fi

{
  printf '# ask-claude %s\n\n' "$(date '+%Y-%m-%d %H:%M:%S')"
  printf -- '- **cwd**: %s\n' "$cwd"
  printf -- '- **branch**: %s\n' "$branch"
  printf -- '- **model**: %s\n' "${model:-default}"
  printf -- '- **effort**: %s\n\n' "${effort:-default}"
  printf '## Prompt\n\n```\n'
  cat "$prompt_file"
  printf '\n```\n\n## Response\n\n'
} > "$log_file"

if [ "$dry_run" -eq 1 ]; then
  printf 'prompt_file=%s\n' "$prompt_file"
  printf 'log_file=%s\n' "$log_file"
  printf 'command='
  printf '%q ' "${claude_cmd[@]}"
  printf '< %q\n' "$prompt_file"
  [ "$owned_prompt_file" -eq 1 ] && rm -f "$prompt_file"
  exit 0
fi

set +e
set -o pipefail
(
  cd "$cwd" || exit 1
  "${claude_cmd[@]}" < "$prompt_file"
) 2>&1 | tee -a "$log_file"
status=${PIPESTATUS[0]}
set +o pipefail
set -e

if [ "$owned_prompt_file" -eq 1 ]; then
  rm -f "$prompt_file"
fi

printf '\n[ask-claude] log: %s\n' "$log_file"
exit "$status"
