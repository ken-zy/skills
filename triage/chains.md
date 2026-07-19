# Triage Process Chains

Five chains, one per tier. Product locations (decision log, design-doc dir,
deployment) come from the project profile's Conventions section; without a
profile, record decisions in the PR description and say so.

## 微 (micro) — pure record-keeping text

1. Branch, edit.
2. Self-review the diff.
3. `/merge-to-main` local merge (no-PR path: rebase origin/main ->
   merge --no-ff -> push -> delete branch). **No PR, no confirmation.**

jdy appears 0 times. Tag the commit message with 微档 for audit. Safety =
criterion (zero behavior change) + red line (text turns out operational ->
upgrade immediately) + `git revert` restores fully.

## 轻 (light) — behavior change, obviously-unique approach

1. Branch.
2. `/tdd` (universal exception clause applies — SKILL.md rule 9).
3. `/verify`: actually drive the affected path, not just green tests.
4. `/code-review`, one round.
5. Fixes made -> re-run `/verify`.
6. `/merge-check`, open PR, jdy merges.

Product: one decision line in the PR description. jdy appears once (merge).
**Review cap 1 round** — a structural finding means the triage was wrong:
upgrade to medium and backfill the design note; never add rounds.
Red line: a tradeoff / unverified fact / cross-boundary / danger surface
appears mid-task -> upgrade.

## 中 (medium) — tradeoff / unknown / cross-boundary, but recoverable

1. `/grilling` on jdy's requirement and initial leaning. **Opening mandatory
   move: list ALL candidate approaches (including ones to discard).** Grill
   the tradeoffs between approaches; batch questions for jdy.
2. **Spike first**: unknowns that affect the choice (Q2 hits) must be settled
   by a minimal experiment BEFORE jdy decides; implementation-detail unknowns
   can wait until before implementation.
3. **jdy picks** (appearance 1) -> half-page design note: what was chosen,
   what was discarded, why. If Q1 triggered the tier, "discarded" must not be
   empty — it proves enumeration happened.
4. `/tdd` -> `/verify`.
5. One review round: default `/code-review`; if the core dispute is the design
   tradeoff, a single cross-model review may replace it, but its prompt must
   cover BOTH correctness and design (not additive — still one round). Fixes
   -> re-run `/verify`.
6. `/merge-check`, PR, jdy merges (appearance 2).
7. One line in the project decision log pointing at the PR — the decision
   entry point must be searchable.

Products: half-page note + decision-log line. jdy appears twice.
**Review cap 2 rounds**; at cap, escalate per SKILL.md rule 3.
Red line: Q4 surfaces mid-task -> upgrade to heavy and STOP for confirmation.

## 重 (heavy) — high cost of error

Announce and STOP. The announcement merges into the chain's first
confirmation point. Branch selection: Q1/Q2/Q3 any yes-or-uncertain ->
重·繁; all clearly no -> 重·简. Mid-task tradeoff appears in 重·简 ->
switch to 重·繁 and backfill.

### 重·简 (heavy-simple) — obviously-unique approach

1. One batch confirm before any work (appearance 1): what changes, which risk
   surface, how to roll back, what to observe after deploy. jdy nods -> start.
2. `/tdd` -> `/verify`.
3. Cross-model code review (prompt covers correctness + risk surface),
   **cap 2 rounds**, fixes -> re-run `/verify`.
4. `/e2e-pr-validation` when there is an end-to-end surface.
5. `/merge-check`, jdy merges (appearance 2).
6. Deployment separately authorized (appearance 3); **post-deploy: close the
   loop on the observation items agreed in step 1**, record in decision log.

Products: PR description states risk surface + rollback path; decision-log
line. No amendment, no plan.

### 重·繁 (heavy-complex) — tradeoff / unknown / cross-boundary

1. `/grilling` (medium-tier version: mandatory enumeration opening, batch
   confirm) (appearance 1).
2. Spike rule as medium: choice-affecting unknowns settled before decisions.
3. Design doc / amendment into the design-docs dir; jdy finalizes
   (appearance 2).
4. Cross-model design review, **cap 2 rounds**.
5. `/superpowers:writing-plans` -> cross-model plan review, **cap 2 rounds**.
6. `/tdd` -> `/verify`; add `/security-review` when secrets/deploy boundaries
   are involved.
7. `/code-review` + cross-model code review, **cap 3 rounds**, fixes ->
   re-run `/verify`.
8. `/e2e-pr-validation` when there is an end-to-end surface.
9. `/merge-check`, jdy merges (appearance 3).
10. Deployment separately authorized (appearance 4); **post-deploy: walk the
    plan's acceptance checklist item by item**, record in decision log.

Products: amendment + implementation plan + decision-log record.

### Shared heavy rules

- Post-deploy acceptance loop is a REQUIRED step on both branches.
- Review caps escalate per SKILL.md rule 3 (three options, default simplify).
- A `[BOUNDARY-CONFLICT]` raised during any cross-model review (implementing
  an upstream promise requires machinery the spec/plan never described) pauses
  per that skill's Exception 2 — never resolved inside the review loop.
