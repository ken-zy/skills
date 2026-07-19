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
VERIFY -> BOUNDARY-CHECK
  confirmed boundary conflict -> UPDATE -> Exception 2 -> STOP
  not a boundary conflict      -> EVALUATE -> CLASSIFY -> PREMISE-CHECK -> UPDATE -> ACCEPT/REJECT
```

Never ACCEPT or REJECT a confirmed boundary conflict.

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

## The Two Escalation Exceptions

Only the two escalation exceptions defined in `SKILL.md` may pause the flow.

For Exception 1 (User-Premise Conflict), if accepting a Codex finding would
overturn an explicit user decision or invalidate that decision's factual
premise, pause before applying the fix and state:

- the explicit user decision
- the factual premise now believed false
- the evidence
- concrete options

For Exception 2 (Boundary-Conflict), if Codex reports or Claude Code identifies
that an upstream goal cannot be implemented without state or machinery the
upstream artifact never described, pause and state:

- the upstream sentence that forces the machinery
- the state or machinery that would be required
- the choice between amending the upstream artifact and narrowing its promise

After the user chooses, record `user-override` in the issue tracker and resume.
