# Implementation Plan: Claude-Primary Mode With Symmetric Tmux Review

Date: 2026-06-28

Spec: `docs/superpowers/specs/2026-06-28-claude-primary-mode-design.md`

## Goal

Update `tmux-cross-model-review` so it documents and supports two role modes:

```text
codex-primary   # default, current behavior
claude-primary  # Claude Code native session owns lifecycle; Codex reviews via tmux
```

Both modes must use the same interaction shape:

```text
primary session -> prompt file -> explicit tmux reviewer pane -> review result Markdown
```

No same-dialog review, hidden reviewer process, or non-tmux `codex review`
transport is allowed for Claude-primary mode.

## Files To Modify

- `SKILL.md`: add mode model, keep Codex-primary default, add Claude-primary
  handoff behavior and Codex reviewer bridge rules.
- `tmux-backend.md`: document both tmux reviewer backends and their pane-state
  requirements.
- `design-review.md`, `plan-review.md`, `execution.md`, `code-review.md`,
  `report.md`: add mode-aware wording and report fields while preserving the
  existing Codex-primary lifecycle.
- `tests/test-skill-structure.sh`: add static structure guards for the new
  mode, no same-dialog/non-tmux bridge, no Claude driver, Codex pane state, and
  report fields.
- `tests/test-invoke-claude-tmux.sh`: keep existing Claude helper behavior
  passing unchanged.

## Files To Create

- `claude-primary.md`: Claude-facing entrypoint that tells Claude Code it is the
  primary driver and must use Codex only through the Codex tmux reviewer helper.
- `lib/invoke-codex-tmux.sh`: review-only helper for Claude-primary mode.
- `tests/test-invoke-codex-tmux.sh`: fake-tmux tests for the Codex reviewer
  helper.

## Task 1: Add Static Guards First

Modify `tests/test-skill-structure.sh`.

Add assertions that runtime docs contain:

- `codex-primary`
- `claude-primary`
- `codex-primary   # default`
- `If no mode is passed, use codex-primary`
- `primary session -> prompt file -> explicit tmux reviewer pane -> review result Markdown`
- `Claude Code -> Codex over tmux`
- `lib/invoke-codex-tmux.sh`
- `CODEX_REVIEW_TMUX_PANE`
- `CODEX_REVIEW_RESULT_V1`
- `CODEX_REVIEW_DONE`
- `--ask-for-approval never`
- `--sandbox workspace-write`
- `--no-alt-screen`
- `or an equivalent profile`
- `--ask-for-approval untrusted`
- `--ask-for-approval on-request`
- `--ask-for-approval on-failure`
- `--dangerously-bypass-approvals-and-sandbox`
- `Role mode`
- `Primary driver`
- `External reviewer`
- `Primary result owner`
- `no convention file available`

Split static guard scopes:

- `runtime_docs_core` remains the existing seven runtime docs:
  `SKILL.md`, `design-review.md`, `plan-review.md`, `execution.md`,
  `code-review.md`, `report.md`, and `tmux-backend.md`.
- `claude-primary.md` is a new Claude-facing entrypoint, but it is not added to
  literal absence loops for `codex review` or `codex exec`, because it must
  contain those strings as explicit prohibitions.

Add absence guards that `runtime_docs_core` do not introduce:

- `lib/invoke-claude-driver.sh`
- literal `codex review`
- literal `codex exec`
- same-dialog/same-conversation review as a supported bridge

Add separate guards for `claude-primary.md`:

- it must contain the literal prohibitions for `codex review` and `codex exec`;
- it must contain `No same-dialog`, or equivalent wording, as a prohibition;
- it must not describe `codex review`, `codex exec`, subagents, hidden
  processes, or same-dialog review as supported transports.

Keep the existing core-doc absence guards against `codex-companion`, subagent
fallback, and removed session-file backends.

## Task 2: Create `lib/invoke-codex-tmux.sh`

Create a Bash helper mirroring the review-only safety model of
`lib/invoke-claude.sh`.

Interface:

```bash
lib/invoke-codex-tmux.sh \
  --phase <name> \
  --round <n> \
  --cwd <path> \
  --prompt-file <path> \
  --codex-tmux-pane <target> \
  --timeout-seconds 900 \
  --poll-seconds 5
```

Also support:

- `CODEX_REVIEW_TMUX_PANE` as the environment fallback for the target pane.
- `--output-dir <path>` and `--output-file <path>`.
- `--preflight` to run the required Codex reviewer-pane smoke test before the
  first real Claude-primary review round.
- `--dry-run` for tests and diagnostics.

Behavior:

1. Require explicit pane selection. No auto-detection.
2. Require non-empty `--cwd`.
3. Require a non-empty prompt file for normal review rounds.
4. In `--preflight`, create an internal minimal prompt instead of requiring
   `--prompt-file`.
5. Verify the target pane exists with `tmux list-panes`.
6. Default normal review output to
   `docs/reviews/codex/YYYYMMDD/<stamp>-<phase>-r<round>.md`.
7. Default preflight output to
   `docs/reviews/codex/YYYYMMDD/<stamp>-preflight.md`.
8. Wrap the prompt with:
   - working directory
   - output file
   - review-only write rules
   - required sentinels `CODEX_REVIEW_RESULT_V1` and `CODEX_REVIEW_DONE`
   - explicit ban on source/spec/helper/git/secret edits
9. Paste the wrapper prompt into the Codex reviewer pane via tmux buffer.
10. Poll for the output file and sentinel lines.
11. Detect approval prompts in pane scrollback and fail with a specific
    diagnostic.
12. Compare pre/post git status and tracked diff.
13. Allow only the designated Codex review output file as a new git-visible
    change.
14. Fail if any tracked file content changes or any unexpected untracked file
    appears.

The helper must not call `codex review`, `codex exec`, a subagent, or a hidden
reviewer process.

## Task 3: Test `lib/invoke-codex-tmux.sh`

Create `tests/test-invoke-codex-tmux.sh` using the same fake-tmux style as
`tests/test-invoke-claude-tmux.sh`.

Cover:

- rejects removed/unknown legacy flags.
- requires explicit Codex pane.
- `--dry-run` prints derived paths without dispatch.
- successful normal review allows only the designated Codex output file.
- `--preflight` succeeds with `CODEX_REVIEW_RESULT_V1` and
  `CODEX_REVIEW_DONE`.
- source/spec/helper/git mutations fail.
- dirty tracked file mutation fails.
- permission prompt fails with a Codex-specific diagnostic.
- output without Codex sentinel lines fails.

## Task 4: Add Claude-Facing Entrypoint

Create `claude-primary.md`.

Content requirements:

- State that Claude Code is the primary driver and artifact owner.
- State that Codex is reviewer only.
- Preserve the lifecycle:
  `Design Review -> Plan Review -> Execution -> Code Review -> Report`.
- Tell Claude Code to maintain the issue tracker and apply
  `VERIFY -> EVALUATE -> CLASSIFY -> PREMISE-CHECK -> UPDATE -> ACCEPT/REJECT`.
- Require `CODEX_REVIEW_TMUX_PANE` or `--codex-tmux-pane`.
- Require the Codex reviewer pane to be started with effective behavior
  equivalent to:

```bash
codex --cd /path/to/repo \
  --sandbox workspace-write \
  --ask-for-approval never \
  --no-alt-screen
```

- Require `lib/invoke-codex-tmux.sh --preflight` before the first real
  Claude-primary review round.
- State the invalid approval states:
  `--ask-for-approval untrusted`, `--ask-for-approval on-request`,
  `--ask-for-approval on-failure`, and any mode that can pause for interactive
  approval.
- State that `--dangerously-bypass-approvals-and-sandbox` is not the default
  reviewer mode and may only be used with external sandboxing plus explicit user
  opt-in.
- State that no same-dialog, `codex review`, `codex exec`, subagent, or hidden
  process may replace the tmux reviewer pane.
- State that reviewer output files live under `docs/reviews/codex/YYYYMMDD/`.

## Task 5: Update Runtime Docs

Modify `SKILL.md`.

Required changes:

- Keep the current Codex-primary flow as the default.
- Add a Role Modes section with:
  - `codex-primary`: Codex owns lifecycle; Claude Code reviews via
    `lib/invoke-claude.sh`.
  - `claude-primary`: Claude Code owns lifecycle; Codex reviews via
    `lib/invoke-codex-tmux.sh`.
- Add the shared interaction shape:
  `primary session -> prompt file -> explicit tmux reviewer pane -> review result Markdown`.
- If Codex receives a request to run Claude-primary mode, instruct Codex to hand
  off to `claude-primary.md` instead of driving a Claude pane.
- Preserve the existing `AGENTS.md` convention rule and design-only/spec-only
  termination behavior.
- Add Codex reviewer result contract and sentinel names.

Modify `tmux-backend.md`.

Required changes:

- Split the backend documentation into Claude reviewer pane and Codex reviewer
  pane sections.
- Keep the existing Claude pane requirements:
  `bypassPermissions` or `dontAsk`; `acceptEdits is invalid`.
- Add the Codex pane requirements:
  `--ask-for-approval never`, `--sandbox workspace-write`, `--no-alt-screen`,
  or equivalent profile.
- Add the invalid Codex pane states:
  `--ask-for-approval untrusted`, `--ask-for-approval on-request`,
  `--ask-for-approval on-failure`, and any runtime mode that can pause for
  interactive approval.
- Add the `--dangerously-bypass-approvals-and-sandbox` caveat: not default,
  allowed only with external sandboxing and explicit user opt-in.
- Document Codex reviewer preflight and fail-loud behavior.

Modify phase files.

Required changes:

- Add role banners for `codex-primary` and `claude-primary`.
- Replace hardcoded "Codex executes / Claude reviews" statements with
  mode-aware primary/reviewer wording where needed.
- Preserve phase-specific review dimensions and output formats.
- Preserve automatic transitions and the one user-premise escalation exception.

Modify `report.md`.

Required changes:

- Add table fields:
  - `Role mode`
  - `Primary driver`
  - `External reviewer`
  - `Primary result owner`
- Keep existing review-round, Codex safety net, CEO decision, escalation, and
  final status sections.

## Task 6: Verify

Run:

```bash
bash tests/test-skill-structure.sh
bash tests/test-invoke-claude-tmux.sh
bash tests/test-invoke-codex-tmux.sh
```

Then run targeted greps:

```bash
rg -n "lib/invoke-claude-driver.sh|codex-companion|Reviewer backend.*subagent|subagent \\(fallback\\)" SKILL.md claude-primary.md tmux-backend.md design-review.md plan-review.md execution.md code-review.md report.md lib/invoke-claude.sh lib/invoke-codex-tmux.sh
rg -n "\\bcodex review\\b|\\bcodex exec\\b" SKILL.md tmux-backend.md design-review.md plan-review.md execution.md code-review.md report.md
rg -n "\\bcodex review\\b|\\bcodex exec\\b" claude-primary.md
rg -n "same-dialog|same conversation|one conversation" SKILL.md claude-primary.md tmux-backend.md design-review.md plan-review.md execution.md code-review.md report.md
```

Expected:

- Tests pass.
- Removed backends do not appear.
- `codex review` and `codex exec` do not appear in the seven core runtime docs.
- `codex review` and `codex exec` appear in `claude-primary.md` only as explicit
  forbidden-context text, not as supported transports.
- Same-dialog wording appears only as a prohibition.

## Rollback

If the new helper or docs fail review, revert only the new files and edits from
this plan. The existing Codex-primary behavior remains recoverable because
`lib/invoke-claude.sh` and its tests are preserved unchanged except for
documentation references.
