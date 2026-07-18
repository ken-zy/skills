# Claude-Primary Cross-Model Review

You are Claude Code. You are the primary driver and artifact owner.

Codex is reviewer only. Use Codex only through the explicit tmux reviewer pane
and `lib/invoke-codex-tmux.sh`.

## Lifecycle

```text
Design Review -> Plan Review -> Execution -> Code Review -> Report
```

Design-only/spec-only mode:

```text
Design Review -> Report
```

You own:

- artifact edits
- verification
- issue tracking
- phase transitions
- final report

Codex findings are evidence, not authority. For each Codex issue with
confidence `>= 70`, run:

```text
VERIFY -> EVALUATE -> CLASSIFY -> PREMISE-CHECK -> UPDATE -> ACCEPT/REJECT
```

## Required Codex Reviewer Pane

Set the target pane explicitly:

```text
--codex-tmux-pane <target>
CODEX_REVIEW_TMUX_PANE=<target>
```

The Codex reviewer pane must already be running with effective behavior
equivalent to:

```bash
codex --cd /path/to/repo \
  --sandbox workspace-write \
  --ask-for-approval never \
  --no-alt-screen
```

The same settings may come from a Codex profile, or an equivalent profile.

Invalid approval states:

- `--ask-for-approval untrusted`
- `--ask-for-approval on-request`
- `--ask-for-approval on-failure`
- any runtime mode that can pause for interactive approval

`--dangerously-bypass-approvals-and-sandbox` is not the default reviewer mode.
It may only be used with external sandboxing and explicit user opt-in.

## Preflight

Before the first real Claude-primary review round, run:

```bash
lib/invoke-codex-tmux.sh \
  --preflight \
  --cwd /path/to/repo \
  --codex-tmux-pane <target>
```

If preflight fails, stop Claude-primary mode before plan or code execution.
Review failure is not LGTM.

## Review Rounds

Create prompt files outside the repository:

```bash
prompt_tmp_dir="$(mktemp -d "${TMPDIR:-/tmp}/codex-review-prompt.XXXXXX")"
prompt_file="$prompt_tmp_dir/prompt.md"
```

Invoke Codex reviewer rounds with:

```bash
lib/invoke-codex-tmux.sh \
  --phase <PHASE> \
  --round <ROUND> \
  --cwd /path/to/repo \
  --prompt-file "$prompt_file" \
  --codex-tmux-pane <target> \
  --timeout-seconds 900 \
  --poll-seconds 5
```

Reviewer output files live under:

```text
docs/reviews/codex/YYYYMMDD/
```

Codex review files must contain:

```text
CODEX_REVIEW_RESULT_V1
CODEX_REVIEW_DONE
```

Pane scrollback is diagnostics only. The Markdown result file is the source of
truth.

## Forbidden Substitutes

No same-dialog review may replace the tmux reviewer pane.

`codex review`, `codex exec`, subagents, hidden processes, and local-only review
may not replace the tmux reviewer pane.

## User-Premise Conflict

The only user pause is a user-premise conflict escalation.

If accepting a Codex finding would overturn an explicit user decision or
invalidate that decision's factual premise, pause before applying the fix and
state:

- the explicit user decision
- the factual premise now believed false
- the evidence
- concrete options

After the user chooses, record `user-override` in the issue tracker and resume.
