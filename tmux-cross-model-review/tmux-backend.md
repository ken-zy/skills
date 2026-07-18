# Tmux Backend

Cross-model review runs through an existing reviewer pane. This backend does
not start a hidden reviewer process and does not put both models into one
conversation.

This backend does not provide harness-level read-only enforcement. It relies on
prompt constraints plus after-the-fact side-effect detection.

## Shared Interaction Shape

```text
primary session -> prompt file -> explicit tmux reviewer pane -> review result Markdown
```

No pane auto-detection is supported. If no pane is provided, the helper prints
available panes and exits.

## Claude Reviewer Pane

Used by `codex-primary`.

Backend helper:

```text
lib/invoke-claude.sh
```

The target pane must be a Claude Code session in one of these modes:

- `bypassPermissions`
- `dontAsk`

`acceptEdits is invalid` for the full lifecycle. It may auto-accept edits, but
code review requires Bash commands such as `git diff origin/main --stat`; a pane
that prompts for Bash will make `lib/invoke-claude.sh` fail the round.

Pass exactly one of:

- `--tmux-pane <target>`
- `CLAUDE_REVIEW_TMUX_PANE=<target>`

Review results are Markdown files under:

```text
docs/reviews/claude-code/YYYYMMDD/*.md
```

The result file must contain:

```markdown
CLAUDE_REVIEW_RESULT_V1

# Claude Code Review

## Result

<ISSUE entries or LGTM>

CLAUDE_REVIEW_DONE
```

Codex reads the file. Pane scrollback is diagnostics only.

## Codex Reviewer Pane

Used by `claude-primary`.

Backend helper:

```text
lib/invoke-codex-tmux.sh
```

The target pane must be an interactive Codex CLI session running with effective
behavior equivalent to:

```bash
codex --cd /path/to/repo \
  --sandbox workspace-write \
  --ask-for-approval never \
  --no-alt-screen
```

The same settings may come from a Codex profile, or an equivalent profile, but
the effective behavior must match those flags:

- `--ask-for-approval never` is required because the helper cannot answer
  command or write approval prompts inside the reviewer pane.
- `--sandbox workspace-write` is required so Codex can read the repository and
  write the designated review result file; in-workspace writes are still bounded
  by the side-effect guard below.
- `--no-alt-screen` is required for usable pane scrollback diagnostics after a
  timeout or permission failure.

Invalid Codex pane states:

- `--ask-for-approval untrusted`
- `--ask-for-approval on-request`
- `--ask-for-approval on-failure`
- any runtime mode that can pause for interactive approval

`--dangerously-bypass-approvals-and-sandbox` is not the default reviewer mode.
It may only be used with external sandboxing and explicit user opt-in.

Pass exactly one of:

- `--codex-tmux-pane <target>`
- `CODEX_REVIEW_TMUX_PANE=<target>`

Before the first real Claude-primary review round, run:

```bash
lib/invoke-codex-tmux.sh \
  --preflight \
  --cwd /path/to/repo \
  --codex-tmux-pane <target>
```

Preflight writes a minimal sentinel result under:

```text
docs/reviews/codex/YYYYMMDD/*.md
```

If preflight fails, Claude-primary mode is unavailable and must fail loudly
before plan or code execution.

Codex review results are Markdown files under:

```text
docs/reviews/codex/YYYYMMDD/*.md
```

The result file must contain:

```markdown
CODEX_REVIEW_RESULT_V1

# Codex Review

## Result

<ISSUE entries or LGTM>

CODEX_REVIEW_DONE
```

Claude Code reads the file. Pane scrollback is diagnostics only.

## Prompt Delivery

Each helper:

1. Records git status before dispatch.
2. Wraps the original prompt with cwd, output path, write rules, and sentinels.
3. Loads the wrapper prompt into a tmux buffer.
4. Clears partial input with `C-u`.
5. Pastes the buffer into the pane.
6. Sends Enter after a short delay.
7. Deletes the tmux buffer.

## Side-Effect Guard

Temporary prompt files are not review artifacts. Create them outside the
repository, for example in `${TMPDIR:-/tmp}`, and pass them through
`--prompt-file`.

The helper must not edit `.gitignore`, `.git/info/exclude`, git config, or any
other git-related file to hide review artifacts.

After the review, allowed new git-visible changes are:

- the designated output file
- parent directories created only to hold the designated output file

Any other new git-visible change fails the round. Tracked file mutations also
fail the round, even when the file was already dirty before review.

## Timeout And Permission Diagnostics

If the result file does not appear before timeout, the helper captures pane tail
for diagnostics.

If pane tail appears to show a permission prompt, the helper exits with a
permission diagnostic instead of a generic timeout.

## Retry

Try again once with the same pane and a new output file. Review failure is not
LGTM.
