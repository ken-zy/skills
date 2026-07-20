# Subagent Backend: Blind-Spot Mitigation

When `BACKEND="subagent"` (initial detection) or companion fails twice in a phase (runtime fallback), apply three layers to compensate for same-model blind spots.

**Fallback trigger:** Companion fails twice in a single phase → subagent for that phase. Subsequent phases probe companion once before deciding (see SKILL.md Companion Failure Handling).

**State migration on mid-phase fallback:** If companion failed after Round 1+ completed, carry the issue tracker state into the subagent round. The issue tracker provides continuity — subagents receive the current tracker as context and continue from the last known state.

## Layer 1: Mixed Model Tiers

Each dimension gets a specific Claude tier — they reason differently:

```
D1 reviewer → opus   (strongest convention understanding)
D2 reviewer → sonnet (fast logic scanning)
D3 reviewer → sonnet (code consistency requires reading + comparing actual files)
D4 reviewer → opus   (architectural judgment)
D5 reviewer → sonnet (completeness coverage)
```

## Layer 2: Adversarial Role Injection

Prepend to each subagent's review prompt:

```
You are a hostile code reviewer who believes this artifact is fundamentally flawed.
Your job is to find the fatal weakness in dimension [D1-D5].
If you can't find one, try harder. Do NOT be lenient.
Do NOT give the benefit of the doubt — assume the worst case.
```

## Layer 3: Claude Blind-Spot Checklist

Append to every subagent prompt (last updated: 2026-03-24, review quarterly):

```
WARNING: The author is a Claude instance. Claude models tend to:
- Over-trust type systems and miss runtime edge cases
- Under-estimate concurrency issues in async code
- Assume APIs behave as documented (they don't always)
- Miss performance implications of N+1 queries
- Over-engineer abstractions for simple problems
- Under-specify error recovery paths
Look specifically for these patterns in your review.
```

## Dispatch Pattern

```python
for dimension in [D1, D2, D3, D4, D5]:
    launch Agent(
        model=TIER_MAP[dimension],
        prompt=ADVERSARIAL_ROLE
              + PHASE_REVIEW_PROMPT
              + BLIND_SPOT_CHECKLIST
              + f"Focus ONLY on dimension {dimension}. Ignore other dimensions."
              + "Read CLAUDE.md (project root) for conventions.",
        subagent_type="general-purpose"
    )
# Collect results, merge, deduplicate, apply confidence threshold
```

If CLAUDE.md is absent, replace the conventions line with `no convention file
available` (see SKILL.md Convention File Rule); the round is then not
convention-aware and the report must record that.

## Early-Stop Optimization

Dimensions that return LGTM in a round are excluded from subsequent rounds:

```
Round 1: dispatch D1, D2, D3, D4, D5
  → D1 LGTM, D3 LGTM, D2/D4/D5 have issues

Round 2: dispatch D2, D4, D5 only (D1, D3 excluded)
  → D4 LGTM, D2/D5 have issues

Round 3: dispatch D2, D5 only
  ...
```

## Result Merging

Deduplication rules (concrete, not semantic):

```
1. Same location + same dimension → duplicate. Keep highest confidence.
2. Same location + different dimension → distinct issues (keep both).
3. Different location + similar description → distinct issues (keep both).
```

## Code Review Variant

For Phase 4, subagents read the diff directly:

```bash
git diff origin/main
```

Each subagent reads the diff output + relevant source files. No temp patch file needed.
