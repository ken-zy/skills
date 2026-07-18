---
name: ask-claude
description: Use when jdy explicitly invokes /ask-claude to consult Claude Code for a raw one-shot second opinion, diagnosis, review, or question from Codex.
---

# ask-claude

Direct Bash bridge from Codex to Claude Code for one prompt. No subagent layer, no summary, no rewrite, no fallback. Claude is read-only by default.

## Trigger

Use only when jdy explicitly enters `/ask-claude <prompt>` or asks Codex to make a one-shot Claude Code consultation.

For multi-round design/plan/PR review, use `tmux-cross-model-review` instead.

## Invocation

Two steps: write the full prompt to a temp file, then call the helper once.

### Step 1: write prompt to file

Write everything after `/ask-claude` exactly as provided, preserving newlines, backticks, code fences, `$`, quotes, and Unicode:

```text
/tmp/ask-claude-<unix_timestamp>.txt
```

Do not pass large or multi-line prompts as shell arguments.

### Step 2: call helper

```bash
/Users/jdy/Documents/skills/ask-claude/lib/ask-claude.sh \
  --prompt-file /tmp/ask-claude-<unix_timestamp>.txt
```

The helper writes a markdown log and streams Claude's stdout back to the current context.

## Defaults

| Setting | Default |
|---|---|
| Claude command | `claude -p` |
| model | Claude Code default, unless `--model` or `ASK_CLAUDE_MODEL` is set |
| effort | Claude Code default, unless `--effort` or `ASK_CLAUDE_EFFORT` is set |
| permission mode | `dontAsk` |
| write tools | `Edit`, `Write`, `MultiEdit` denied |
| logging | `~/.codex/logs/ask-claude/YYYYMMDD/HHmmss.md` |

## Optional Overrides

```bash
/Users/jdy/Documents/skills/ask-claude/lib/ask-claude.sh \
  --model sonnet \
  --effort high \
  --prompt-file /tmp/ask-claude-123.txt
```

Supported effort values are `low`, `medium`, `high`, `xhigh`, and `max`.

## Output Handling

Return Claude's stdout verbatim to the main context. Do not summarize, translate, filter, or rewrite it. If jdy wants a summary, wait for a follow-up request.

At the end, the helper prints:

```text
[ask-claude] log: <path>
```

## Failure Handling

No fallback. If `claude` is unavailable or exits non-zero, surface the error and log path. Do not pretend Claude reviewed the prompt.

If it hangs, the human can interrupt. Do not use GNU `timeout`; it is not available on this macOS environment by default.

## Common Mistakes

| Mistake | Correction |
|---|---|
| Using `timeout` | Do not rely on GNU timeout on macOS |
| Passing prompt in argv | Use `--prompt-file` or stdin |
| Using invented flags like `--input-file`, `--no-cache`, `--no-conversation` | Run `claude --help`; this helper uses verified flags |
| Using `claude --print -` | Not part of this contract |
| Letting Claude edit files | Keep `Edit`, `Write`, and `MultiEdit` denied |
| Summarizing Claude's answer | Return raw stdout |

## Baseline Failures This Skill Prevents

Pressure testing without this skill produced:
- reliance on unavailable `timeout`
- argv interpolation for multi-line prompts
- unverified `claude --print -`
- invented flags from memory

