---
name: triage
description: Use when jdy proposes any new requirement, feature, bugfix, hotfix, or change request — before writing any code, plan, or design doc — to decide how much process the task deserves. Also use when starting work in a repository that has no triage profile (.claude/triage-profile.md), or when unsure whether a task needs design review, cross-model review, or just a quick PR.
---

# Triage

Judge every incoming requirement into a tier — 微 / 轻 / 中 / 重·简 / 重·繁 —
announce the verdict, then follow that tier's process chain (`chains.md`).

Two dimensions, two knobs: **complexity** decides how much upfront design
(plan depth); **cost of error** decides how strict the after-the-fact
verification is (review depth). Money-involvement is one input to cost, never
the tier criterion itself.

Authority: predict-v2 issue #72, comment 5013575156 (2026-07-19), confirmed
pair-by-pair by jdy. One later ruling supersedes that comment: micro-tier work
uses the standard GitHub PR flow, not a local no-PR merge. On every other
conflict, that comment wins.

## Mode dispatch

```
/triage init  -> read init.md, run project initialization once per repo
/triage       -> judge mode (implicit whenever a new requirement arrives)
```

Judge mode reads the project profile at `<repo root>/.claude/triage-profile.md`.
Missing profile does NOT block: judge with the [default] anchors below and
append to the announcement: 本项目未初始化 triage profile，建议先跑 /triage init。

## Decision tree (fixed order — never reorder)

```
Step 0: Pure record-keeping text?            -> 微 (micro). Done.
Step 1: Q4 (cost of error) hit or uncertain? -> 重 (heavy)
        └─ Q1/Q2/Q3 any "yes" or uncertain   -> 重·繁 (heavy-complex)
           all three clearly "no"            -> 重·简 (heavy-simple)
Step 2: Q1/Q2/Q3 any hit?                    -> 中 (medium)
Step 3: all four clearly "no"                -> 轻 (light)
```

Cost before complexity: a one-line change on a danger surface must never be
caught at Step 2 and settle as light/medium. Q4 locks the tier; complexity
only picks the heavy branch.

**Step 0 criterion**: touches no executable code, no config values, no agent
behavior specs (AGENTS.md / CLAUDE.md / skill files), AND the changed text
alters nobody's future operations, contracts, acceptance criteria, or safety
guidance — it records accomplished facts only. Runbooks, deploy steps, and
spec acceptance criteria are NOT micro (text a human follows is that human's
code). Code comments, typo fixes, decision-log lines, deploy-SHA backfills are.

## The four questions

**Q1 — Real design tradeoff?** Hit only if you can write down a SECOND
approach that (a) satisfies the same agreed requirements, (b) is feasible
under current constraints, (c) differs in a substantive tradeoff
(correctness / risk / complexity / performance / rollback). You must write
both the approach AND the tradeoff. Syntax, wrapper placement, or style
differences don't count.

**Q2 — Unverified external fact?** Hit if correctness rests on an assertion
with no current authoritative source and no reproducible test evidence.
Missing, vague, or possibly-stale docs count as hits; so do runtime/capacity
boundaries (performance, memory, rate limits). Stale repo notes are not
evidence.

**Q3 — Cross-boundary blast radius?** Hit if the diff touches a contract
crossing top-module / process / API / event / persistence boundaries, a DB
schema, or the runtime behavior of >=2 top modules. Top-module definition
from profile [default: direct subpackages of the main source root]. Tests,
docs, and mechanical follow-through edits don't count separately; "public
interface" excludes merely-imported functions.

**Q4 — High cost of error?** Hit if ANY of:
- (a) changes the **runtime semantics** of the profile's danger list
  [default: funds/trading authorization, amount computation, order
  placement/cancellation, ledger, ownership] — judged by semantics, NOT
  directory; profile directories are hints only; include transitive impact
  1–2 hops along the call chain, unclear = uncertain;
- (b) overwrites/deletes data that cannot be resynced from upstream
  (rollback test: does revert PR + redeploy fully restore?);
- (c) touches secrets or deployment boundaries.

## Uncertainty rule

Any question uncertain = treat as "yes". Q4-uncertain must be flagged with
the reason in the announcement. When uncertainty lands the task in heavy:
triage and read-only investigation proceed, but ANY code modification waits
for jdy's confirmation (fail-closed). jdy may downgrade after reading the flag.

## Cost constraint

Triage is a minutes-level act. Evidence budget: 1–2 greps / schema lookups.
If only an experiment can answer a question, that IS a Q2 hit — go medium and
let the spike step answer it. Never run experiments to triage.

## Announcement protocol

Before touching any code, as the first part of the reply, in Chinese:

```
[判档] 中档（命中问1：A vs B 存在取舍；问4 否：数据可重同步）
流程：grilling → 半页设计说明 → TDD → code review 一轮 → 合并
```

Effect by tier:
- 微: announce, then open a PR per chains.md; jdy confirms once at merge.
- 轻 / 中: announce and start immediately; jdy can re-judge at any time.
- 重: announce and STOP — the announcement merges into the chain's first
  confirmation point (重·简 batch confirm / 重·繁 grilling).

**jdy-specified tier** = initial ruling; skip normal triage but run a SILENT
Q4 scan. No conflict -> zero extra interaction. Conflict -> report the hits;
jdy's explicit confirmation is final, no re-litigation.

## Universal rules

1. **One review round** = issue list -> fixes -> original reviewer re-verifies
   the list. The re-verify is not a new round.
2. **Re-verify after fixes**: after any review fix, re-run /verify (at least
   affected paths) before merging.
3. **Cap without convergence**: no auto-extra-round, no auto-simplify.
   Escalate to jdy, three options: simplify the mechanism / authorize one more
   round / change approach. Default recommendation is always simplify.
4. **Upgrade-only ratchet**: new tradeoff/risk mid-task -> upgrade the tier
   yourself, tell jdy, backfill the target tier's artifacts. Downgrades need
   jdy's confirmation.
5. **Mixed requirements**: subtasks sharing one PR, one deployment, or a
   behavior boundary inherit the highest tier as a whole. Separate tiers only
   for independent PRs verifiable and rollbackable independently. Multiple
   requirements in one message: triage each, announce together.
6. **Hotfixes are not exempt.** In an emergency, first NARROW the task to the
   obviously-unique reversible mitigation, triage the narrowed task (usually
   重·简), and present the discarded mitigation alternatives in the batch
   confirm; the root-cause fix is a new requirement, triaged separately.
7. **Deployment is tier-independent**: always per-instance authorization from
   jdy. Heavy tiers additionally owe the post-deploy acceptance loop.
8. **Document ladder**: 微 0 (commit-message tag; PR is merge control only) ·
   轻 0 (one PR line) ·
   中 half-page + decision-log line · 重·简 0 docs (PR + decision-log line) ·
   重·繁 amendment + plan. No tier produces more.
9. **TDD exception (all tiers)**: when test scaffolding clearly costs more
   than the change itself (ops scripts, one-off migrations), declare
   "no TDD + reason" in the PR, back with /verify; jdy can veto at merge.

## Chains

REQUIRED: read `chains.md` in this directory for the five per-tier process
chains before executing the tier.

## Red flags

| Thought | Reality |
|---|---|
| "Obviously light, skip the announcement" | The announcement IS the mechanism. Always announce first. |
| "It's in a safe directory, so Q4 is no" | Q4 is semantic, not directory-based. Trace 1–2 hops. |
| "Can't think of a second approach, Q1 is no" | Write down why no feasible alternative exists. Uncertain = yes. |
| "Heavy seems excessive for one line" | One line on a danger surface is exactly what 重·简 exists for. |
| "Uncertain, but let me start coding" | Uncertainty into heavy blocks code changes until jdy confirms. |
| "A repo note says so" | Stale notes are not evidence. That's a Q2 hit. |
| "It's a hotfix, rules don't apply" | Narrow first, then triage the narrowed task. No exemption. |
