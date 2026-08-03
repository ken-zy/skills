# Graph-Driven Development v1.1 Implementation Plan

Status: Final bounded rework implemented; Package 3 verification in progress
Date: 2026-08-03
Spec: `docs/specs/2026-08-03-graph-driven-development-v1-1.md`

## Delivery boundary

Implement the approved v1.1 workflow on branch `codex/optimize-graph-skill-v1-1`. The original local-only boundary was superseded by later explicit commit, push, and PR authorization; PR #7 already exists. The current rework authorization includes scoped checkpoint commits. A changed branch may be pushed only after the exact new head passes local gates and independent re-review. Merge, deploy, and production actions remain separately unauthorized.

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
- No merge, deploy, production action, or post-merge cleanup has occurred without its separate gate.

## Task 7: Repair the immutable review package contract

Files:

- Modify `graph-driven-development/SKILL.md`
- Modify `graph-driven-development/references/browser-and-review-package.md`
- Modify `graph-driven-development/references/review-contract.md`
- Add `graph-driven-development/scripts/compute_review_package_digest.py`
- Add `graph-driven-development/scripts/validate_review_diff.py`
- Add `graph-driven-development/scripts/test_review_package.py`

Actions:

1. Define `graph-review-package-v1` with exact canonical request replacement and manifest bytes.
2. Record the actual and canonical request SHAs outside the self-referential request; embed neither one.
3. Recompute exact deterministic Git diff bytes and path evidence.
4. Include symlink target/mode changes and fail package creation on binary changed paths.
5. Keep the scripts read-only, standard-library-only, and narrower than a generic packager.

Verification:

- Run the fixed digest test vector and mutation cases.
- Prove an exact text diff passes, a symlink target change remains visible, a binary change fails closed, and a truncated diff fails.

Status: Completed in checkpoint `4308ac9`.

## Task 8: Enforce delivery, backend, pause, and Reviewer invariants

Files:

- Modify `graph-driven-development/references/state-and-transitions.md`
- Modify `graph-driven-development/scripts/validate_run_state.py`
- Modify `graph-driven-development/scripts/test_validate_run_state.py`

Actions:

1. Upgrade saved snapshots to schema version 2 and bind package evidence mechanically.
2. Reject delivery/review completion with unresolved blocking/high findings.
3. Enforce the backend allowlist independently of exact-match flags.
4. Enforce consecutive model priority and reject premature fallback.
5. Make an extension valid only after the original mandatory pause and before its new limit.
6. Validate every Reviewer identity/head/digest immediately and require risk-class count at review completion.

Verification:

- Run adversarial unit tests for every accepted High and both Medium findings.
- Preserve a valid waiting `REVIEW_CANDIDATE` with no completed Reviewer.

Status: Completed in checkpoint `80db1e4`.

## Task 9: Rebuild and re-review Package 2

Actions:

1. Run both test modules, the standard skill validator, `git diff --check`, reference checks, policy searches, and final diff inspection.
2. Commit the synchronized spec/plan evidence.
3. Generate `full.diff` for the exact base/new-head range and validate it with the new diff tool.
4. Generate the three Package 2 attachments, run the secret scan, compute/inject/verify the package digest, and record actual attachment hashes.
5. Send identical Package 2 materials to a fresh read-only ChatGPT Pro Web conversation with Extra High.
6. Verify the returned head/digest and every finding. Push the changed PR head only after a valid `PASS` and then wait for required PR CI.

Status: Completed; Package 2 returned four accepted High findings and one advisory Medium finding.

Current local evidence:

- Package 2 independently reproduced all attachment hashes and ran the then-current 45 unit tests successfully.
- `git diff --check` and reference existence checks pass.
- The standard `quick_validate.py` cannot import `yaml` in either available Python runtime (`ModuleNotFoundError: No module named 'yaml'`); no dependency was installed. An equivalent read-only structural check against the validator's exact rules passes.

## Task 10: Apply the final bounded Package 2 rework

Files:

- Modify `graph-driven-development/scripts/validate_review_diff.py`
- Modify `graph-driven-development/scripts/test_review_package.py`
- Modify `graph-driven-development/scripts/validate_run_state.py`
- Modify `graph-driven-development/scripts/test_validate_run_state.py`
- Synchronize `graph-driven-development/SKILL.md`, relevant references, this plan, and the spec

Actions:

1. Derive changed paths from raw base/head tree records and independently parse paths from the supplied patch.
2. Override submodule ignore behavior and inspect regular-file blobs directly so hostile Git configuration or attributes cannot hide changed paths or binary data.
3. Enforce the exact canonical lifecycle state vocabulary and reject success-like aliases.
4. Enforce fixed relative priority for known ChatGPT models; make unknown model priority an explicit `WAITING_HUMAN` ambiguity.
5. Count only final reconciled `PASS` Reviewer records toward normal/high-risk completion.
6. Require persisted mandatory-pause evidence and temporal ordering before an extension becomes valid.

Verification:

- Run hostile `.gitattributes` and `diff.ignoreSubmodules=all` diff tests.
- Run lifecycle-alias, reversed/unknown-model, Reviewer-placeholder, and extension-timeline state tests.
- Run both complete unit-test modules plus final structural, diff, and reference checks.

Status: Completed in checkpoints `c61bbc2` and `7598192`; 61 unit tests pass.

This consumes `implementation_rework_used: 2`. No further implementation rework is allowed for this task.

## Task 11: Build Package 3 and obtain the final verdict

Actions:

1. Commit the final bounded rework only after scoped and full local validation.
2. Generate and mechanically validate Package 3 for the exact final head.
3. Upload exactly the three immutable files to a fresh ChatGPT Pro Web conversation using `Extra High`.
4. Independently verify the returned head, digest, verdict, and findings.
5. If no accepted blocking/high finding remains, push the branch and wait for required PR checks on the exact remote head.
6. If Package 3 has an accepted blocking/high finding, stop in `WAITING_HUMAN` or `FAILED`; do not create Package 4 or rework 3.

Status: In progress.
