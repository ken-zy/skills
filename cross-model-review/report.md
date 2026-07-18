# Phase 5: Report

After all executed phases complete, output this structured report to terminal:

```markdown
# Cross-Model Review Report

## Summary
| Item | Value |
|------|-------|
| Reviewer backend | codex (${MODEL}) / subagent (fallback) |
| Spec | <path or N/A> |
| Plan | <path or N/A> |
| PR | <PR URL or N/A> |
| Started at | <phase name> |
| Design Review | N rounds, accepted M, rejected K |
| Plan Review | N rounds, accepted M, rejected K |
| Code Review (Codex) | N rounds, accepted M, rejected K |
| Code Review (Claude) | N issues found / No issues |
| CEO decisions | N (if any) |
| Escalations (Exceptions 1-2) | N (if any) |

## Design Review
### Round 1
| # | Dim | Issue | Confidence | Verdict | Action |
|---|-----|-------|------------|---------|--------|
(per-round tables, only for executed phases)

## Plan Review
(same format)

## Code Review (Codex)
(same format)

## Code Review (Claude Safety Net)
| Result | Issues found | Issues fixed | Self-check |
|--------|-------------|-------------|------------|
| <No issues / N issues found, M fixed> | | ✓ passed / ⚠ regression fixed |

## CEO Decisions
| # | Phase | Issue | Claude Argument | Reviewer Argument | Verdict | Verified | Rationale |
(only if CEO decisions were made. Verified = ✓ self-checked / ⚠ unreviewed)

## Escalations (Exceptions 1-2)
| # | Phase | Trigger (overturned decision / false premise / boundary conflict) | Evidence | User's choice |
(only if a user-premise or boundary-conflict escalation fired — the pipeline paused and the user decided)

## Final Status
<Complete / Complete with unresolved items>
```

Report only includes phases that were actually executed (based on entry point).
