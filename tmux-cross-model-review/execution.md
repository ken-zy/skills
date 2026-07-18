# Phase 3: Execution

The primary driver executes the plan. The secondary model remains the reviewer
only.

## Role Mode Banner

Each resolved execution prompt starts with one of these banners:

```text
ROLE MODE: codex-primary
Codex is the primary driver and artifact owner. Claude Code is reviewer only.
Codex owns the lifecycle loop.
```

```text
ROLE MODE: claude-primary
Claude Code is the primary driver and artifact owner. Codex is reviewer only.
Claude Code owns the lifecycle loop.
```

## Phase Skip Protocol

Most tasks can be executed autonomously, including local code changes, tests,
commits, `git push`, `gh pr create`, and ordinary read/write repository work.

The only operations that require user confirmation are wallet private-key
operations such as signing transactions or transferring funds. If a task
requires wallet keys, skip that specific task, note it in the report, and
continue with independent tasks.

The two escalation exceptions from `SKILL.md` still apply: if accepting a
reviewer finding would overturn the user's explicit decision or the factual
premise behind it, pause and escalate per Exception 1; if work cannot proceed
without state or machinery the plan never described, escalate per Exception 2.

## Pre-Execution Checks

Before implementation:

1. Re-read the updated plan after Plan Review.
2. Check prerequisites listed in the plan. If a prerequisite is missing, proceed
   with independent tasks and note the gap.
3. Record base SHA with `git rev-parse HEAD` for later code review diff.

## Execution Strategy

Read the plan's task dependency graph:

```text
IF tasks have parallel branches -> use the available parallel-task workflow
IF tasks are sequential         -> execute the plan step by step inline
IF mixed                        -> parallelize independent groups, sequence between groups
```

When invoking execution helpers from this skill:

- skip execution-choice prompts
- skip review-checkpoint prompts
- do not ask the user for confirmation between tasks
- make context-based decisions autonomously unless an escalation exception fires

## Post-Execution

After all tasks complete:

1. Run the plan's verification commands.
2. Rebase on latest main: `git fetch origin && git rebase origin/main`.
3. Push the branch. Use `git push -u origin <branch>` for the first push, or
   `git push --force-with-lease` after a rebase of an already-pushed branch.
4. PR creation happens automatically in Phase 4 Step 0.

## Next Phase

After Execution completes, announce "Starting Phase 4: Code Review", read
`code-review.md`, and proceed automatically. No user confirmation.
