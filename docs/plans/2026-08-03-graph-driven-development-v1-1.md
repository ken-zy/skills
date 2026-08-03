# Graph-Driven Development v1.1 Implementation Plan

Status: Completed
Date: 2026-08-03
Spec: `docs/specs/2026-08-03-graph-driven-development-v1-1.md`

## Delivery boundary

Implement the approved v1.1 workflow locally on branch `codex/optimize-graph-skill-v1-1`. This plan does not authorize commit, push, PR creation, merge, deploy, or cleanup.

## Task 1: Establish the durable workflow contract

Files:

- Modify `graph-driven-development/SKILL.md`
- Add `graph-driven-development/references/state-and-transitions.md`

Actions:

1. Rewrite the entrypoint as a concise phase router rather than a complete operations manual.
2. Preserve the only-writer rule, worktree preflight, repository-derived gates, read-only review, authorization boundaries, and post-merge cleanup.
3. Define normal/high-risk clocks and active-time semantics.
4. Define hard task-wide ceilings: three review packages and two implementation reworks.
5. Define checkpoint, verified head, review candidate, package invalidation, PR-CI repair, and pause transitions.
6. Link detailed transition rules from the exact phase where they are needed.

Verification:

- Search for contradictory time or count limits.
- Confirm bounded branch/checkpoint/push/PR permissions are explicit and merge remains separately authorized.
- Confirm the entrypoint is materially shorter than the current 397-line version and stays under 300 lines, ideally around 220–300.

## Task 2: Add failure-matrix and scope-expansion gates

Files:

- Add `graph-driven-development/references/failure-matrix.md`
- Modify `graph-driven-development/SKILL.md`

Actions:

1. Add a domain-neutral matrix template with `covered`, `not_applicable`, and `open` states.
2. Require reasons for `not_applicable` and evidence/owner for `open`.
3. Block implementation on unexplained high-risk rows.
4. Identify delivery units and propose phased delivery when more than two named risk domains are coupled.
5. Define scope-expansion triggers: new subsystem, new external side effect, migration, permission boundary, new dependency, or change beyond the approved design.
6. Require a spec/plan refresh and user authorization when expansion materially changes the result.

Verification:

- Check that small tasks can mark irrelevant rows N/A instead of fabricating analysis.
- Check that risky side effects fail closed.

## Task 3: Freeze browser, model, reviewer, and package rules

Files:

- Add `graph-driven-development/references/browser-and-review-package.md`
- Modify `graph-driven-development/references/review-contract.md`
- Modify `graph-driven-development/SKILL.md`

Actions:

1. Allow only ChatGPT Web and Grok Web through the Codex built-in Browser.
2. Cap task-controlled external-model tabs/conversations at two and require URL/ID recovery.
3. Separate `model` from `reasoning_level`; fix reasoning to `Extra High`.
4. Record structured inventory, observation time, selected model/reasoning, fallback reason, and exact backend/model/reasoning flags.
5. Encode the synthetic preference baseline `ChatGPT Pro -> GPT-5.6 Sol -> GPT-5.5 -> GPT-5.3 -> o3`, filtering to currently visible models that support confirmed `Extra High`.
6. Permit fallback only within ChatGPT Web after model unavailability/quota evidence; allow two independent ChatGPT conversations when both preferred backends are quota-limited.
7. Require high-risk work to use two independent read-only reviewers with the same exact package and hidden verdicts.
8. Define the three uploaded files and prohibit diff truncation.
9. Clarify that `full.diff` may contain any number of changed source files.

Verification:

- Search for any reasoning downgrade path.
- Search for any third-platform fallback path.
- Confirm retry/reconnect/re-upload of the same package does not consume another package count.

## Task 4: Implement read-only run-state validation

Files:

- Add `graph-driven-development/scripts/validate_run_state.py`
- Add `graph-driven-development/scripts/test_validate_run_state.py`
- Modify `graph-driven-development/SKILL.md`

Actions:

1. Accept one JSON run-state file and return success/failure without editing it.
2. Validate required types and enums.
3. Validate package and rework ceilings.
4. Validate `Extra High` exactly.
5. Validate review-candidate head equality and package digest presence.
6. Validate same-head reviewer package consistency.
7. Validate mandatory active-time limits for normal/high-risk tasks.
8. Keep the validator standard-library-only and intentionally narrower than a transition engine.

Verification:

- Run unit tests covering valid state plus package 4, rework 3, head mismatch, digest mismatch, wrong reasoning level, and expired active-time cases.
- Run the CLI once against a valid temporary JSON snapshot.

## Task 5: Update UI metadata and progressive disclosure

Files:

- Modify `graph-driven-development/agents/openai.yaml`
- Modify all newly linked references as needed

Actions:

1. Read the skill-creator OpenAI YAML reference before editing.
2. Keep the display name and description aligned with v1.1 behavior.
3. Keep the default prompt concise and explicit about worktree isolation, preferred web backends, ChatGPT-only fallback, fixed `Extra High`, hard ceilings, and authorization boundaries.
4. Verify every relative reference from `SKILL.md` resolves.

Verification:

- Parse or structurally inspect YAML using available local tooling.
- Run the standard skill validator.

## Task 6: Final validation and review-ready handoff

Files:

- All changed files in the task worktree

Actions:

1. Run `python3 -m unittest graph-driven-development/scripts/test_validate_run_state.py`.
2. Run `python3 /Users/jdy/.codex/skills/.system/skill-creator/scripts/quick_validate.py graph-driven-development`.
3. Run `git diff --check`.
4. Check reference existence and conflicting policy phrases.
5. Inspect `git diff --stat`, `git status --short`, and the full final diff.
6. Confirm main checkout's untracked optimization prompt was not copied or modified.
7. Report the exact validation results and remaining authorization boundary.

Exit condition:

- Local implementation is complete and verified as far as the environment permits.
- No commit, push, PR, merge, or cleanup has occurred.
