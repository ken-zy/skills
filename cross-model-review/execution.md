# Phase 3: Execution

**Claude executes the plan — NOT the reviewer.** Reviewer is for review only.

## Phase Skip Protocol

Most tasks CAN be executed autonomously, including:
- **SSH to EC2 for ops tasks** (health monitor fixes, docker-compose changes, DB scripts) — ALLOWED
- **Local code changes, tests, commits** — ALLOWED
- **`gh pr create`, `git push`** — ALLOWED

The ONLY operations that require user confirmation:
- **Wallet private key operations** (signing transactions, transferring funds)

If a task involves wallet keys, skip that specific task and note it in the report. Everything else: execute autonomously.

**NEVER stop and ask the user** — make skip decisions autonomously and continue.

**Escalation Exceptions (SKILL.md):** the wallet-key skip is not the only allowed pause. If,
during execution, an ACCEPTED finding would overturn the user's explicit decision / its
factual premise, PAUSE and escalate per Exception 1; if work cannot proceed without state or
machinery the plan never described, escalate per Exception 2. These are required
interruptions, not forbidden ones — they do not contradict the "never stop and ask" rule above.

## Pre-Execution Checks

Before starting implementation:
1. **Re-read the updated plan** (post-review version, not pre-review). Phase Transition Check.
2. **Check prerequisites** listed in the plan (e.g., PRs that must be merged first). If prerequisite not met, proceed with tasks that don't depend on it and note the gap.
3. **Record base SHA** (`git rev-parse HEAD`) for later code review diff.

## Execution Strategy (Auto-Select)

Read the plan's Task Dependency Graph:

```
IF tasks have parallel branches → Use subagent-driven-development
IF tasks are purely sequential  → Use executing-plans
IF mixed                        → subagent-driven-development for parallel groups,
                                  sequential between groups
```

**CRITICAL OVERRIDE:** When these execution skills are invoked from within cross-model-review:
- **Skip any "execution choice" prompts** — the strategy is auto-selected above
- **Skip any "review checkpoint" prompts** — cross-model-review Phase 4 handles review
- **Do NOT ask the user** for confirmation at any point during execution
- If a skill asks for user input, make the decision autonomously based on context

## Post-Execution: Prepare for Code Review

After all tasks complete:
1. **Rebase on latest main**: `git fetch origin && git rebase origin/main`
2. **Push**: `git push -u origin <branch>` (or `--force-with-lease` if already pushed)
3. PR creation happens automatically in Phase 4 Step 0.

## Next Phase — AUTOMATIC, DO NOT ASK USER

After Execution completes → **immediately** read `code-review.md` in this directory and proceed to Code Review. No user confirmation. Just announce "Starting Phase 4: Code Review" and continue.
