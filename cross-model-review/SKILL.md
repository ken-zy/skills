---
name: cross-model-review
description: Use when a design spec, implementation plan, or PR needs cross-model review before merging or executing
---

# Cross-Model Review

Full lifecycle review: **Design Review → Plan Review → Execution → Code Review**. Claude writes and executes; an external reviewer reviews. Auto-detects phase AND reviewer backend.

**Core principle:** Two models catch more than one. But reviews must be verified, not blindly accepted.

## AUTONOMOUS FLOW — NON-NEGOTIABLE

This skill is a **fully autonomous, closed-loop pipeline**. Once started, it runs through all applicable phases to completion without user interaction.

```
FORBIDDEN at ANY point between start and final report:
- "是否要继续？" / "需要我继续吗？"
- "是否要现在开始执行？"
- "要我进入下一阶段吗？"
- Any question that pauses execution waiting for user input
- Any confirmation request between phases

REQUIRED: Each phase MUST automatically transition to the next.
The ONLY user-visible output before the final report is:
- Phase announcements: "Starting Phase N: <name>"
- Round progress: "Round N: N issues found, N accepted"
- CEO Decisions (inline, no user input needed)
- the two escalation Exceptions below (User-Premise Conflict, Boundary
  Conflict) — the ONLY pauses that await user input (substantive, not an
  empty "may I continue?")
```

**User is NOT in the loop until the final report.** CEO Decisions are made by Claude, not escalated to the user. Phase transitions happen automatically. If you catch yourself about to ask the user anything, STOP — that is a bug in your execution. (The narrow carve-outs are the two Exceptions immediately below — read them before concluding you may interrupt.)

### The Two Exceptions — Escalations That Pause the Flow

Exactly two situations override the no-interruption rule.

#### Exception 1 — User-Premise Conflict Escalation

```
TRIGGER (all must hold):
- A reviewer finding is ABOUT TO BE ACCEPTED / applied (passed VERIFY/EVALUATE/CLASSIFY,
  confidence >= 70) — PREMISE-CHECK is the gate at that moment, not an after-the-fact test, AND
- Acting on it would OVERTURN a decision the user made EXPLICITLY, OR
  invalidate the FACTUAL PREMISE that decision was built on.

ACTION: PAUSE and surface the conflict to the user. Do NOT silently apply the
fix (that secretly vetoes the user's decision). Do NOT bury it for the final
report (the user is operating on a false premise NOW).
```

This is the rule from `superpowers:receiving-code-review` ("IF conflicts with your
human partner's prior decisions: Stop and discuss with your human partner first"),
which this skill lists as REQUIRED BACKGROUND. It is **not** a violation of the
autonomous flow — it is part of it.

#### Exception 2 — Boundary-Conflict Escalation

```
TRIGGER:
- A reviewer or primary driver identifies [BOUNDARY-CONFLICT]: an upstream goal
  (spec goal during plan review, plan task during execution or code review)
  cannot be implemented without state or machinery the upstream artifact never
  described.

ACTION: PAUSE and surface the conflict to the user. Cite the upstream sentence
that forces the machinery, describe the machinery it would require, and offer
the two resolutions — amend the upstream artifact to include the machinery, or
narrow the upstream promise so the machinery becomes unnecessary. Do NOT
resolve it unilaterally inside the review or execution flow, and do NOT invent
the machinery merely to satisfy the upstream promise.
```

**These are escalations, not confirmation prompts.** The difference is content:

```
FORBIDDEN (empty, pauses for no reason):    "要不要我继续？" / "进入下一阶段吗？"
THIS EXCEPTION (substantive, must escalate): "你之前的决定 B 依据的是『X』，但 Codex 复核确认
                                              实际是『Y』(证据: ...)。改正它会推翻决定 B。
                                              你要 (a) 维持原决定 (b) 按 Y 改 (c) ..."
```

State the conflicting decision, the false premise, the evidence, and the concrete
options. Then wait.

**After the user responds:** apply their chosen option, record it in the issue tracker
(status `user-override`) and in the final report's escalation section, then RESUME the
pipeline from the paused point. Do NOT ask anything further — this pause is now
closed and full autonomy resumes. Everything OUTSIDE this trigger runs fully autonomously
throughout.

## Step 1: Detect Reviewer Backend

**YOU MUST ACTUALLY RUN THIS COMMAND using the Bash tool.** Do NOT assume or guess whether codex is installed. Do NOT skip this step. Execute the command and read the output before deciding.

```bash
# MANDATORY: Run this via Bash tool. Do NOT skip or assume the result.
command -v codex && echo "BACKEND=codex" || echo "BACKEND=subagent"
```

If output contains `BACKEND=codex` → resolve plugin root, use codex companion as reviewer backend.
If output contains `BACKEND=subagent` → use subagent fallback.

**Plugin root resolution** (check in order, use first match):

```bash
# MANDATORY: Run this to find companion.mjs
CLAUDE_PLUGIN_ROOT=""
for p in ~/.claude/plugins/cache/openai-codex/codex/*/scripts/codex-companion.mjs \
         ~/.claude/plugins/marketplaces/openai-codex/plugins/codex/scripts/codex-companion.mjs; do
  if [ -f "$p" ]; then
    CLAUDE_PLUGIN_ROOT="$(dirname "$(dirname "$p")")"
    break
  fi
done
[ -z "$CLAUDE_PLUGIN_ROOT" ] && echo "BACKEND=subagent (companion not found)"
```

**Announce:** "Reviewer backend: codex (cross-model) via companion.mjs" or "subagent (fallback, blind-spot mitigation active)"

**Error fallback:** See Companion Failure Handling section below.

**If BACKEND="subagent"** → read `subagent-backend.md` in this directory for dispatch rules.

| Aspect | External (Codex) | Subagent (fallback) |
|--------|-----------------|---------------------|
| Convention file | AGENTS.md | CLAUDE.md |
| Reviewer count | 1 per phase | 5 parallel (D1-D5) |
| Model tiers | Single (configurable) | Mixed opus/sonnet |

### Model Configuration

```
MODEL  = user-specified (--model arg)  || gpt-5.5 (skill default)
EFFORT = user-specified (--effort arg) || xhigh   (skill default)
```

Both flags are forwarded to companion.mjs. `EFFORT` accepts `none|minimal|low|medium|high|xhigh` (see companion.mjs `--effort`). Default is `xhigh` because review correctness >> latency for this skill; lower it explicitly when you want a faster pass.

## Step 2: Detect Phase & Load Phase File

```
1. Parse explicit phase:
   "cross-model-review design <path>"  → read design-review.md
   "cross-model-review plan <path>"    → read plan-review.md
   "cross-model-review code"           → read code-review.md

2. Auto-detect:

   a. Extract topic from branch name:
      feat/scheduler-optimization → topic = "scheduler-optimization"
      If main/master → error exit: "Cannot auto-detect on main. Use: cross-model-review design|plan|code <path>"

   b. PR exists on current branch?
      gh pr list --head $(git branch --show-current) --state open --json number
      → yes → read code-review.md

   c. Code changes vs main?
      git diff --stat origin/main
      → changes exist, no PR:
        git diff --name-only origin/main | grep "docs/superpowers/plans/"
        → plan modified → read plan-review.md (code review follows after execution)
        → only code → read code-review.md

   d. Plan file exists? (skip if docs/superpowers/plans/ doesn't exist)
      ls docs/superpowers/plans/*${topic}*.md
      → one match → read plan-review.md
      → multiple → pick most recently modified
      → none → continue

   e. Spec file exists? (skip if docs/superpowers/specs/ doesn't exist)
      ls docs/superpowers/specs/*${topic}*.md
      → match → read design-review.md
      → none → error exit: "No reviewable artifact found for topic '${topic}'. Use: cross-model-review design|plan|code <path>"
```

**Announce:** "Detected: [spec exists, no plan] → starting at Design Review"

### Termination Mode — Design-Only / Spec-Only

By default the pipeline runs to the end (design → plan → execution → code).
**Some specs are the final deliverable** — a gating design / blueprint the user
wants reviewed but NOT implemented. For these, the pipeline must stop after Design
Review instead of auto-creating a plan and writing code.

```
DESIGN-ONLY mode is ON when EITHER:
- An explicit flag is passed: "cross-model-review design <path> --design-only"
  (also accept: --spec-only, "design only", "spec only"), OR
- The user's instruction says, in any wording, "review only / don't implement /
  don't build a repo / 只评审 / 不实现 / 不建 repo / 不写代码".

When ON: Design Review runs normally; on completion → go STRAIGHT to report.md.
         Do NOT create a plan, do NOT proceed to Plan Review / Execution / Code Review.
```

**Do NOT auto-guess** design-only from the document's content or filename — a
gating blueprint and a to-be-implemented spec look nearly identical, and guessing
wrong either skips real work or builds something unwanted. Require the explicit
flag or the user's "don't implement" instruction. When neither is present, default
to the full pipeline.

**Timing:** evaluate this ONCE at startup (during Step 2, before dispatching any
reviewer), reading the invocation flags + the user's instruction. Record the verdict;
the `design-review.md` "Next Phase" gate then ENFORCES it at the end of Phase 1.
Detection = startup; enforcement = end of Design Review.

**Announce when ON:** "Design-only mode: pipeline terminates after Design Review."

After completing one phase, **immediately** read the next phase file and continue — NO user interaction:
- Full pipeline: design-review.md → plan-review.md → execution.md → code-review.md → report.md
- Design-only:   design-review.md → report.md
(See AUTONOMOUS FLOW section above. This is the single most important rule of this skill.)

---

## Prompt Template Variable Injection

Each phase's Prompt Template contains `<PLACEHOLDER>` tokens. Before sending the
prompt to companion.mjs (or to subagents), Claude MUST substitute them with
concrete values resolved from the auto-detect step. **Do not send the raw
template** — Codex will literally read `<SPEC_FILE_PATH>` as a path.

| Placeholder | Resolved from | Used in | Fallback when missing |
|-------------|---------------|---------|-----------------------|
| `<SPEC_FILE_PATH>` | `docs/superpowers/specs/*${topic}*.md` (most recently modified if multiple) | Phase 1 (design), Phase 2 (plan) | `N/A` — Phase 2 skips Half A and notes "no spec available" |
| `<PLAN_FILE_PATH>` | `docs/superpowers/plans/*${topic}*.md` (most recently modified if multiple) | Phase 2 (plan), Phase 4 (code) | `N/A` — Phase 4 skips Half A and notes "no plan available" |
| `<CONVENTION_FILE>` | "AGENTS.md (project root)" for codex backend; "CLAUDE.md (project root)" for subagent | All phases | Hard error — convention file is required |

`${topic}` comes from the branch name extracted in Step 2 (e.g.
`feat/scheduler-optimization` → `scheduler-optimization`). Use the same topic
across all phases of a single review run so spec / plan / code paths stay
consistent.

Substitution happens at prompt-build time, in Claude's orchestration code (not
inside companion.mjs). Verify the substituted prompt before invoking Bash — if
any `<...>` token survives substitution, that is a bug.

---

## Shared: Review Loop Mechanics

All review phases use these shared rules.

### Companion Interface

**Round 1** — new session per phase:

```bash
node "${CLAUDE_PLUGIN_ROOT}/scripts/codex-companion.mjs" task \
  --model ${MODEL} \
  --effort ${EFFORT} \
  "PROMPT"
```

Stdout contains Codex's natural language response (no structured metadata).

**Round N ≥ 2** — resume most recent thread:

```bash
node "${CLAUDE_PLUGIN_ROOT}/scripts/codex-companion.mjs" task \
  --resume \
  --model ${MODEL} \
  --effort ${EFFORT} \
  "INCREMENTAL_PROMPT"
```

**Session identity rule:** Phases execute strictly sequentially (Phase 1 → 2 → 3 → 4), so `--resume` (which resolves to the most recent workspace thread) always targets the current phase's thread. Each phase starts a new thread (no `--resume` on Round 1).

Called via Bash tool (not slash commands), so orchestration is not subject to `codex-result-handling` "stop and ask user" rules.

**Key differences from old interface:**
- No `--output-schema`, no `review-schema.json`, no `mktemp`, no `jq`
- No `-o` output file flags — stdout is captured directly
- No `--ephemeral` concerns — companion manages session lifecycle
- No `codex exec` or `codex exec resume --last` — only `companion.mjs task` / `companion.mjs task --resume`
- No `run_in_background` + `TaskOutput` timeout pattern — companion runs foreground with retry-on-failure
- No threadId capture/parsing — phases are sequential, `--resume` auto-resolves to correct thread

### Convention File Rule

```
External (codex) → "Read AGENTS.md (project root)"
Subagent               → "Read CLAUDE.md (project root)"
```

### Confidence Filtering

Scale (unchanged):
```
0=false positive  25=might be real  50=real but minor
70=verified real   85=double-checked important  100=certain failure
```

**Threshold: >= 70.** Enforced by Claude during the CLASSIFY step of the response protocol. Issues below 70 are auto-filtered from the ACCEPT/REJECT list. The confidence score appears in per-round report tables.

No structured JSON parsing. Claude reads Codex natural language output and assigns confidence during reasoning.

### Context Budget

Raw Codex/subagent output is embedded into Claude's context. Without limits, multi-round reviews exhaust the context window.

Rules:
- **Per-round Codex output:** If stdout exceeds 16000 characters (~4000 tokens), Claude summarizes into an evidence-preserving digest (keep: dimension, location, severity, confidence, core argument). Raw text discarded after summarization.
- **Accumulated context:** Before each round, check total review context. If prior rounds + new output would exceed 48000 characters (~12000 tokens), summarize older rounds into a compact ledger (one line per issue: dim, location, status, confidence).
- **Subagent fallback (5 reviewers):** Each reviewer output capped at 8000 characters (~2000 tokens). Summarize before merge if exceeded.

### Issue Tracker

Orchestration maintains a lightweight issue tracker across rounds within each phase:

```
[phase, dimension, location, one-line summary, status, confidence]
```

- Claude populates this during the CLASSIFY step — does NOT require Codex to output structured JSON
- The tracker is always included in Claude's context
- Serves as stable reference for: termination checks ("same issue unresolved 2 rounds"), CEO decisions, and report generation
- Status values: `open`, `accepted`, `rejected`, `ceo-accepted`, `ceo-rejected`, `ceo-compromised`, `user-override` (set when an escalation Exception was resolved by the user)

### Response Protocol
**REQUIRED BACKGROUND:** superpowers:receiving-code-review

**Scope — applies to EVERY review source.** Run this protocol for issues from each
Codex round, from CEO decisions, AND from the Phase 4 Claude safety net (`code-review.md`
Step Final). No fix from any source is applied without passing PREMISE-CHECK — otherwise
a safety-net finding could silently veto a user's explicit decision through the back door.

For each issue confidence >= 70:
```
1. VERIFY   — Check actual artifact. Confirm issue is real.
2. BOUNDARY-CHECK — If verification shows the issue is a [BOUNDARY-CONFLICT],
                    whether tagged by the reviewer or identified by the primary
                    driver, UPDATE the issue tracker, escalate via Exception 2,
                    and STOP processing this issue. Never ACCEPT or REJECT a
                    confirmed [BOUNDARY-CONFLICT]. If the claim is not confirmed,
                    continue with the normal protocol below.
3. EVALUATE — Technically correct for THIS project?
4. CLASSIFY — Is this a bug, or an intentional design choice?
5. PREMISE-CHECK — Would accepting this overturn a decision the USER made
                   explicitly, or invalidate its factual premise?
                   → YES: escalate per Exception 1 (AUTONOMOUS FLOW section)
                          BEFORE applying any fix. Do not silently accept.
                   → NO: continue.
6. UPDATE issue tracker with [dimension, location, summary, verdict, confidence]
7. ACCEPT / REJECT
```
**NEVER blindly accept.** Reviewers can't run code.

**REJECT strategy:** When the issue is actually an intentional design choice (not a bug),
argue from business/product perspective, not just technical rebuttal. Reviewers withdraw
faster when shown the *why* behind a design decision. Example: "Manual refresh is
user-initiated and should always execute — deduping against themselves contradicts the UX intent."

**Volume control:** >10 issues → prioritize CRITICAL/HIGH. MEDIUM/LOW carry to next round.

### Round N > 1 Prompt

Since the thread is resumed, Codex already has the artifact and convention files from Round 1. Send incremental info plus explicit re-read instruction:

```
Before responding, re-read these modified files to verify the actual changes:
{list of files modified since last round}

The author reviewed your previous issues and responded:

ACCEPTED: [issue summary] — Modified as: [specific change description]
REJECTED: [issue summary] — Reasoning: [rebuttal with code evidence]

Re-evaluate REJECTED issues. Withdraw if pushback is sound.
If you still disagree, update confidence and provide additional evidence.
Also check whether ACCEPTED modifications introduced new problems.
```

**Fast-REJECT rule (Claude-side, applied when processing the response):**
If the reviewer re-raises an already-REJECTED issue without providing new concrete evidence
(new code path, new scenario, new counter-example not present in Round 1), Claude skips
VERIFY/EVALUATE and REJECTs immediately. This does NOT trigger CEO on its own — it simply
keeps the round moving. CEO fires only when ALL remaining open issues in the round are
such stale re-raises (satisfying the "same issues 2 consecutive rounds" termination condition).

**Do NOT re-send AGENTS.md.** Codex has it from Round 1.

### Termination

| Condition | Action |
|-----------|--------|
| LGTM | → next phase |
| All REJECTED, no modifications | → next phase |
| Same issues 2 consecutive rounds | → CEO Decision → next phase |
| Round >= 4 AND all remaining open issues are verification requests (no concrete bug claim, confidence < 70) | → LGTM early exit → next phase |
| Round >= 5 | → CEO Decision → next phase |

### CEO Decision

```
For each disagreement:
0. PRE-CHECK: Does resolving this overturn a decision the USER made explicitly,
   or invalidate its factual premise?
   → YES: do NOT self-decide. Escalate per Exception 1 above. CEO authority
          covers Claude-vs-reviewer disputes, NOT vetoing the user's own decisions.
   → NO: proceed with CEO self-decision below.
1. Claude's argument + evidence
2. Reviewer's argument + evidence
3. Which serves project long-term?
4. Verdict: ACCEPT / REJECT / COMPROMISE
5. Rationale (1-2 sentences)

Write: <!-- CEO Decision: [verdict]. [rationale] -->
```

CEO does NOT default to either side.

**Post-CEO verification:** If a CEO verdict (ACCEPT or COMPROMISE) produces artifact modifications, Claude performs a lightweight self-check: read the diff, verify no contradictions or regressions against existing accepted fixes. Single-pass — NOT a full review loop. Problems found → fix inline (a regression fix that would itself overturn the user's explicit decision / its premise is still subject to PREMISE-CHECK → escalate per Exception 1, do not silently apply). Unverified CEO changes flagged as `unreviewed` in report.
If verdict is REJECT and no artifact modifications were made → skip verification entirely.

### Phase Transition Checks

```
Phase 1→2: Spec modified? Check if plan references outdated spec content.
Phase 2→3: Re-read updated plan before executing. Don't use pre-review version.
Phase 3→4: Verify all plan tasks complete before creating PR.
```

**Transition is AUTOMATIC.** After each phase's review loop terminates (LGTM / CEO Decision), immediately read the next phase file and continue. Do NOT output anything that waits for user input.

### Fix Discipline: Root Cause First

When ACCEPTing a reviewer issue, fix the ROOT CAUSE in one shot. Do NOT do incremental approximations that let the reviewer chase the same issue across multiple rounds.

```
BAD:  Round 2: use epoch → Round 3: use DB query → Round 4: use per-platform query → Round 5: CEO
GOOD: Round 2: identify the fundamental requirement (dedicated per-platform timestamp, not a proxy),
      implement it completely in one modification.
```

Before modifying the plan for an ACCEPTED issue, ask yourself:
1. Can this issue be DISSOLVED by narrowing the requirement or shrinking the
   input set, instead of adding mechanism? If the narrowing changes an
   upstream artifact (spec or plan), that is Exception 2 — escalate. Prefer
   narrowing over mechanism whenever both resolve the issue.
2. What is the FUNDAMENTAL requirement this issue points to?
3. Is my fix addressing that requirement directly, or is it an approximation?
4. Will the reviewer likely find a flaw in my approximation next round?

If the answer to #4 is "maybe", go deeper NOW — but only within the upstream
artifact's boundary. If going deeper would introduce state or machinery the
upstream artifact never described, stop and escalate per Exception 2 instead.

---

### Companion Failure Handling

**Retry-on-failure protocol:**

```
companion.mjs returns non-zero or Bash timeout fires:
  1. Retry once with the same parameters
     → If Round 1: new task (fresh thread — orphaned remote turn is harmless)
     → If Round N: --resume (same thread, new turn)
  2. Second failure → switch current phase to subagent fallback
  3. Subsequent phases: probe companion once at phase start
     → Probe succeeds → use companion for this phase
     → Probe fails → subagent fallback for this phase
```

Rationale for probe-then-recover: companion failures may be transient (auth refresh, broker restart). Permanent fallback for all remaining phases is too aggressive.

---

## Red Flags

| Thought | Reality |
|---------|---------|
| "Codex probably isn't installed" | NEVER assume. Run `command -v codex` via Bash tool. Read the output. |
| "Sub-skill has interactive prompts" | ALL sub-skills run non-interactive. Make autonomous decisions. |
| "Reviewer found issue, fix immediately" | VERIFY first. Reviewer can't run code. |
| "Batch all fixes in one commit" | One commit per fix. Non-negotiable. |
| "Should I continue to the next phase?" | YES. ALWAYS. Automatic transition. Never ask. |
| "Let me check with the user first" | NO — UNLESS an ACCEPTED finding overturns the user's explicit decision / its factual premise (Exception 1), or a [BOUNDARY-CONFLICT] is reported (Exception 2). Then escalate. Otherwise: not in the loop until final report. |
| "Accept all reviewer feedback" | VERIFY → EVALUATE → then decide. |
| "Too many rounds, skip review" | Max 5 rounds, CEO decides. Never skip. |
| "No CLI → skip review" | Subagent fallback. Never skip entirely. |
| "Skip context budget, output is short" | Always check. One verbose Codex round can blow the budget. |
| "Parse Codex JSON output" | No JSON parsing. Claude reads natural language, reasons, classifies. |
| "Codex timed out → retry immediately" | Retry once. If second failure, subagent fallback. |
| "Re-send full plan in Round 2" | Use `--resume`. Codex has context. Only send incremental info. |
| "This fix is good enough for now" | Is it the root cause? If not, go deeper NOW. |
| "Fixed issues, moving to next phase" | NO. ANY phase with ACCEPTED modifications requires Round 2+. Fixes must be verified. |
