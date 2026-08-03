# Graph-Driven Development v1.2 Simplification Plan

Status: Complete
Date: 2026-08-03
Spec: `docs/specs/2026-08-03-graph-driven-development-v1-2-simplification.md`

## Scope

Implement the accepted subtraction release without adding dependencies or a replacement framework. Preserve N0–N6, worktree isolation, Codex-only writes, real verification, independent review, complete diffs, and authorization boundaries.

## Task 1: Correct triggers and proportional lanes

- Narrow `SKILL.md` and `agents/openai.yaml` triggers.
- Add risk classification inside preflight/N0 without creating a new graph node.
- Keep concise risk notes for normal work and the full failure matrix for high risk.

## Task 2: Replace review package v1 with v2

- Replace the self-referential YAML protocol with `review-request.json` plus an external package ID.
- Rewrite the standard-library digest tool and focused mutation tests.
- Update the Browser and Reviewer contracts.

## Task 3: Reduce run-state validation

- Replace schema v2 with the minimal schema v3.
- Treat package/rework counts as authorized pause thresholds.
- Remove model inventory ranking and timestamp choreography from the validator.
- Preserve release-critical head, Reviewer, pending-High, reasoning, backend, and authorization checks.

## Task 4: Make binary handling proportional

- Keep exact diff-byte and changed-path validation under hostile Git configuration.
- Report binary path/mode/object evidence instead of rejecting every binary.
- Keep opaque critical binaries fail-closed in the workflow contract.

## Task 5: Synchronize runtime documentation

- Align all four references with the simplified contracts.
- Remove stale v1-only runtime requirements and duplicated constants.
- Update the historical v1.1 status without rewriting its review history.

## Task 6: Verify

- Run focused package, diff, and run-state unit tests.
- Run the complete local test set, reference checks, metadata/structure checks, and `git diff --check`.
- Run the official Skill validator when PyYAML is available; otherwise report the exact environment limitation and run the equivalent structural check.
- Inspect the final diff and confirm no unrelated or user-owned file is included.

## Task 7: Correct browser model/profile semantics

- Separate provider model, UI selection, and separately exposed reasoning setting.
- Record ChatGPT `Pro` and `Extra High` as alternative approved profiles.
- Record Grok `Expert` as the current subscription maximum without hard-coding `Grok 4.5` in validator logic.
- Preserve automatic adoption of newer provider model versions when the approved UI-profile meaning remains intact.
- Add run-state coverage for ChatGPT Pro, ChatGPT Extra High, Grok Expert, missing selection evidence, and future model labels.

## Delivery boundary

Stop after verified local implementation. Do not commit, push, open a PR, merge, install dependencies, or clean up the worktree without separate authorization.

## Verification result

- 38 focused package, diff, and run-state tests pass, including ChatGPT Pro, ChatGPT Extra High, Grok Expert, missing selection evidence, and future model labels.
- Package v2 and schema-v3 command-line smoke tests pass.
- Skill/reference links, YAML metadata structure, frontmatter limits, and `git diff --check` pass.
- The official `quick_validate.py` cannot start because its environment lacks PyYAML (`ModuleNotFoundError: yaml`). No dependency was installed; the equivalent structural validation passes.
