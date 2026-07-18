# Tmux-Only Claude Cross-Model Review Design

Date: 2026-06-27
Status: Draft
Target skill: `/Users/jdy/Documents/skills/claude-cross-model-review`

## Problem

`claude-cross-model-review` currently invokes Claude Code through a new local
`claude -p` process. That does not match the intended collaboration model:
Codex should orchestrate an already-open Claude Code session inside a tmux pane,
send it review tasks, and read its persisted review output from files.

The current helper builds a `claude -p` command and captures stdout into a log.
That creates a separate reviewer session, ignores the Claude Code pane that jdy
already opened, and makes tmux collaboration a manual one-off rather than a
repeatable skill behavior.

## Goals

1. Make tmux the only Claude reviewer backend.
2. Remove the CLI backend completely; no `claude -p`, no `--session-id`, no
   `--resume` CLI session management, no model or effort flags for Claude CLI.
3. Let Codex send prompts to a specific Claude Code tmux pane using tmux text
   primitives, not screen capture or OCR.
4. Require Claude Code to write every review result to a deterministic Markdown
   file under a configured review-output directory.
5. Let Codex read the output file directly, verify every claimed issue against
   the repository, and keep Claude's output as evidence rather than authority.
6. Preserve the existing review phases and prompt intent: design review, plan
   review, code review, round 2+ re-review, and failure handling.
7. Detect unsafe reviewer side effects by comparing git status before and after
   the tmux review round.
8. Explicitly accept that tmux cannot provide harness-enforced read-only
   permissions; this workflow uses prompt-level constraints plus after-the-fact
   repository state checks.

## Non-Goals

- Do not preserve a fallback CLI mode.
- Do not copy the full autonomous lifecycle from `cross-model-review`.
- Do not promise sandbox-level prevention of writes. Claude Code is instructed
  to write only the review output file and parent directory, and Codex detects
  unexpected repository changes after the round.
- Do not auto-create PRs, implement fixes, or run the full design-plan-code
  pipeline. Codex remains the owner of verification, fixes, commits, and final
  decisions.
- Do not use screenshots, OCR, Chronicle, or visual inspection.

## Reference Pattern

Use `/Users/jdy/Documents/skills/cross-model-review` as a structure reference,
not as behavior to copy wholesale.

Reusable ideas:

- The main skill doc owns orchestration and shared review rules.
- Backend mechanics are separated from phase-specific review prompts.
- Every reviewer finding must go through VERIFY, EVALUATE, CLASSIFY before
  Codex accepts it.
- Reports should include only phases that actually ran.

Do not import these behaviors:

- Fully autonomous phase transitions.
- Subagent fallback.
- PR creation and execution phases.
- Codex companion backend detection.

## Considered Approaches

### Approach A: Minimal Helper Rewrite

Rewrite `lib/invoke-claude.sh` in place so the existing skill keeps the same
interface but the helper talks to tmux instead of `claude -p`.

Pros:

- Smallest migration.
- Existing examples can keep using the same helper path.
- Easier to verify no CLI mode remains by grepping one script.

Cons:

- Backend details and prompt policy can stay mixed in `SKILL.md`.
- Future tmux edge cases may bloat the main skill doc.

### Approach B: Skill Split With Tmux Backend Doc

Keep `SKILL.md` as the orchestration source of truth, rewrite
`lib/invoke-claude.sh` as a tmux-only helper, and add `tmux-backend.md` for pane
detection, prompt delivery, output-file contract, timeout, and side-effect rules.

Pros:

- Matches the useful separation in `cross-model-review` without importing its
  full lifecycle.
- Keeps tmux mechanics discoverable and testable.
- Reduces the chance that future prompt edits accidentally bypass backend
  safety rules.

Cons:

- Slightly more files.
- Requires `SKILL.md` to explicitly tell Codex when to read `tmux-backend.md`.

### Approach C: Manual Tmux Protocol Only

Remove the helper and document raw `tmux capture-pane`, `tmux paste-buffer`, and
`tmux send-keys` commands in `SKILL.md`.

Pros:

- No script abstraction.
- Easy to debug in a single terminal.

Cons:

- Too easy for Codex to skip required checks.
- Harder to enforce output sentinels, timeouts, and git side-effect checks.
- Repeats shell quoting and tmux buffer details every time.

## Decision

Use Approach B.

The skill should be tmux-only but still deterministic. A helper script should
handle repeatable mechanics, while `tmux-backend.md` explains the protocol and
failure modes. `SKILL.md` should remain concise and focus on when to use the
skill, review loop rules, and phase prompt templates.

This design accepts the central tradeoff raised during external review:
`claude -p` can enforce read-only behavior through CLI tool restrictions, while
a live Claude Code tmux pane cannot be locked down by Codex at the same harness
layer. The tmux-only workflow is chosen anyway because the desired operating
model is live collaboration with the already-open Claude Code pane, not a
separate hidden reviewer process.

Therefore the safety model is cooperative and auditable:

- Cooperative: the prompt tells Claude Code that the only allowed write is the
  designated review output file.
- Auditable: the helper records repository state before and after the round and
  fails closed if unexpected changes appear.
- Not a sandbox: this does not prevent all possible filesystem side effects
  before they happen, and the spec must not describe it as equivalent to
  harness-level read-only enforcement.

## User-Facing Workflow

1. User starts Claude Code in another tmux pane with an auto-accept permission
   mode that can run review commands and write the result file without human
   confirmation. Valid modes include `bypassPermissions`, `dontAsk`, or
   `acceptEdits`; `plan` mode and default prompt-on-write modes are invalid.
2. Codex identifies the target pane by explicit argument or environment
   variable.
3. Codex writes a review prompt to a temp file.
4. Codex invokes the tmux helper.
5. The helper sends the prompt into the Claude Code pane.
6. Claude Code reviews the requested artifact and writes a Markdown result file.
7. The helper waits until the result file contains the completion sentinel.
8. Codex reads the result file, verifies findings, and accepts or rejects them.
9. If accepted changes are made, Codex sends a round 2 prompt to the same tmux
   pane and requires a new output file.

## Tmux Pane Selection

The helper supports two pane selection modes, in priority order:

1. `--tmux-pane <target>`: explicit target such as `1:0.1`.
2. `CLAUDE_REVIEW_TMUX_PANE=<target>`: environment default.

Default auto-detection is intentionally not supported. Tmux does not expose a
reliable Claude Code session identity: `pane_current_command`, title, and cwd
are useful diagnostics but not a safe targeting mechanism. A mis-targeted prompt
can write a review file in the wrong session when the pane is in auto-accept
mode.

If neither `--tmux-pane` nor `CLAUDE_REVIEW_TMUX_PANE` is set, the helper must
fail and print the available panes as diagnostics. A future explicit
`--auto-detect-pane` debug mode may be added, but it must be opt-in and must
print candidate evidence before dispatch.

## Helper Interface

`lib/invoke-claude.sh` becomes the tmux-only helper. It should reject legacy
CLI-only flags instead of silently ignoring them.

Required options:

- `--phase <name>`
- `--round <n>`
- `--prompt-file <path>`
- `--cwd <path>`

Pane/output options:

- `--tmux-pane <target>` optional only when `CLAUDE_REVIEW_TMUX_PANE` is set.
- `--output-dir <path>` default:
  `docs/reviews/claude-code/YYYYMMDD/`
- `--output-file <path>` optional explicit result path.
- `--timeout-seconds <n>` default `900`.
- `--poll-seconds <n>` default `5`.
- `--dry-run` prints derived pane, prompt file, output file, and tmux commands
  without sending input.

Removed options:

- `--session-file`
- `--resume`
- `--fresh`
- `--model`
- `--effort`
- any `claude` CLI permission/tool flags

## Prompt Delivery Protocol

The helper must use tmux buffer primitives:

1. Record git status before dispatch.
2. Build a wrapper prompt that includes:
   - original review prompt
   - exact cwd
   - exact output file path
   - read-only rule with a single write exception for the output file
   - required output sentinel format
3. Load the wrapper prompt into a temporary tmux buffer.
4. Send `C-u` to clear any partial input in the target pane.
5. Paste the buffer into the pane.
6. Send Enter.
7. Delete the tmux buffer.

The helper should not rely on terminal scrollback for the result. It may capture
the pane tail only for diagnostics on timeout or failure.

If the pane tail indicates Claude Code is waiting for a permission decision, the
helper should fail with a permission-mode diagnostic instead of reporting a
generic timeout. The diagnosis should tell the operator to restart or switch the
target pane into `bypassPermissions`, `dontAsk`, or `acceptEdits`.

## Output File Contract

Claude Code must write the result file itself. The result file is the only
source Codex reads for the review conclusion.

Every result file must follow this shape:

```markdown
CLAUDE_REVIEW_RESULT_V1

# Claude Code Review

- Target: <artifact or PR/diff>
- Phase: <design|plan|code|task>
- Round: <n>
- Cwd: <path>

## Result

<ISSUE entries or LGTM>

## Notes

<optional reviewer context>

CLAUDE_REVIEW_DONE
```

The helper treats the round as incomplete until the file exists and contains
both `CLAUDE_REVIEW_RESULT_V1` and `CLAUDE_REVIEW_DONE`.

Recommended write pattern for Claude Code:

1. Write to `<output-file>.tmp`.
2. Verify sentinels are present.
3. Rename tmp file to `<output-file>`.

If Claude Code cannot write the file, it should say so in the pane, but the
helper still reports failure because Codex cannot consume pane-only output as a
successful review.

## Side-Effect Guard

The side-effect guard is an audit mechanism, not a permission boundary. It
exists because tmux-only review intentionally gives up the stronger
`claude -p` tool-deny mechanism.

Review output files are local artifacts in the current repo. The helper must
not edit `.gitignore`, `.git/info/exclude`, git config, or any other git-related
file to hide them. Whether to ignore, delete, keep, or commit review artifacts
is left to the repo owner after the review.

Before sending a prompt, the helper records:

```bash
git -C "$cwd" status --short --untracked-files=all
```

After completion, it records status again and compares the two states.

Expected git-visible changes:

- The designated review output file.
- Parent directories under the configured review output directory, when they
  were created only to hold the designated review output file.
- Nothing else.

Unexpected changes cause the helper to fail and print:

- before status
- after status
- output file path if available
- pane tail diagnostics

Known limits:

- Changes outside `cwd` are outside this guard.
- Ignored files are not reported by normal `git status`.
- Non-file side effects, such as network calls or external service mutations,
  are not detectable by this guard.

These limits are accepted for the tmux-only workflow. The helper must not
auto-revert anything. Codex reports the unexpected changes and decides how to
proceed with jdy.

## Review Loop Semantics

Round 1:

- Send the full phase prompt.
- Require confidence threshold `>= 70`.
- Require ISSUE entries or LGTM.
- Require file output.

Round 2+:

- Send incremental prompt to the same pane.
- Include files modified since the previous round.
- Include accepted/rejected issue ledger.
- Require Claude Code to re-read modified files before responding.
- Require a new output file for each round.

Codex remains responsible for:

- VERIFY: check the claimed issue against actual files.
- EVALUATE: decide if the issue matters for this project.
- CLASSIFY: bug, missing requirement, intentional tradeoff, or false positive.
- UPDATE: maintain the issue ledger.
- ACCEPT/REJECT: only accepted issues can lead to edits.

## Failure Handling

Hard failures:

- tmux is unavailable.
- target pane is missing.
- target pane is not provided by `--tmux-pane` or `CLAUDE_REVIEW_TMUX_PANE`.
- target pane appears to be waiting for a permission prompt.
- prompt file is empty.
- output file is not completed before timeout.
- output file lacks required sentinels.
- unexpected git-visible changes appear after the review round.

There is no fallback to `claude -p`.

Unexpected repository changes are treated as a failed review round even if the
review file contains `CLAUDE_REVIEW_DONE`. A completed file only proves Claude
Code produced a result; it does not override the side-effect audit.

Retry policy:

1. Retry once with the same pane and a new output file.
2. If retry fails, stop the Claude-backed review phase.
3. Report failure explicitly. Do not treat failure as LGTM.

## Documentation Changes

Update `SKILL.md`:

- Replace all CLI backend language with tmux-only language.
- Remove Backend Detection for `command -v claude`.
- Add requirement to read `tmux-backend.md` before invoking the helper.
- Update examples to include `--tmux-pane` and `--output-dir`.
- Keep existing design/plan/code review prompt templates, with only the output
  contract updated to say Claude Code must write a result file.

Add `tmux-backend.md`:

- Pane selection.
- Required Claude Code permission mode.
- Prompt delivery protocol.
- Output file contract.
- Side-effect guard.
- Timeout and retry behavior.
- Troubleshooting commands.

Rewrite `lib/invoke-claude.sh`:

- Preserve the filename for existing callers.
- Remove all `claude -p` command construction.
- Implement tmux dispatch and result-file polling.
- Reject removed flags with a clear error.

## Verification Plan

Static checks:

```bash
rg -n "claude -p|--session-id|--resume|--model|--effort|permission-mode|allowedTools|disallowedTools" /Users/jdy/Documents/skills/claude-cross-model-review
```

Expected: no active CLI invocation remains. Historical migration notes may only
appear if clearly marked as removed behavior.

Dry-run helper check:

```bash
/Users/jdy/Documents/skills/claude-cross-model-review/lib/invoke-claude.sh \
  --phase design \
  --round 1 \
  --cwd /Users/jdy/Documents/predict-fun \
  --prompt-file /tmp/claude-review-prompt.txt \
  --tmux-pane 1:0.1 \
  --dry-run
```

Expected: prints resolved pane and output file without touching Claude Code.

Live smoke test:

1. Create a small review prompt against a harmless Markdown file.
2. Dispatch it to the Claude Code pane.
3. Confirm a result file appears under `docs/reviews/claude-code/YYYYMMDD/`.
4. Confirm the result contains both sentinels.
5. Confirm the only new git-visible changes are the designated review output
   file and any parent directories created solely for that file.

Failure test:

1. Run with a nonexistent pane.
2. Confirm helper fails closed and does not create a fake LGTM.

## Output Directory Decision

Default output stays in the current repo:

```text
docs/reviews/claude-code/YYYYMMDD/
```

This keeps review artifacts next to the skill being reviewed while avoiding
hidden git behavior inside the skill. The helper does not add ignore rules.
Operators can still pass `--output-dir` for a different location, but the
default is repo-local and visible to normal git status unless the repo owner has
chosen to ignore it.
