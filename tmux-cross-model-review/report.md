# Phase 5: Report

After all executed phases complete, output this structured report to the user.
Include only phases that actually ran.

```markdown
# Tmux Cross-Model Review Report

## Summary
| Item | Value |
|------|-------|
| Reviewer backend | claude-code-tmux / codex-tmux |
| Role mode | codex-primary / claude-primary |
| Primary driver | Codex / Claude Code |
| External reviewer | Claude Code / Codex |
| Primary result owner | Codex / Claude Code |
| tmux pane | <target pane> |
| Spec | <path or N/A> |
| Plan | <path or N/A> |
| PR | <PR URL, local diff mode, or N/A> |
| Started at | <phase name> |
| Design Review | N rounds, accepted M, rejected K |
| Plan Review | N rounds, accepted M, rejected K |
| Code Review (Claude Code) | N rounds, accepted M, rejected K |
| Primary safety net / Codex safety net | No issues / N issues found, M fixed |
| CEO decisions | N |
| Escalations | N |

## Design Review
### Round 1
| # | Dim | Issue | Confidence | Verdict | Action |
|---|-----|-------|------------|---------|--------|

## Plan Review
| # | Dim | Issue | Confidence | Verdict | Action |
|---|-----|-------|------------|---------|--------|

## Code Review (Claude Code)
| # | Dim | Issue | Confidence | Verdict | Action |
|---|-----|-------|------------|---------|--------|

## Primary safety net / Codex safety net
| Result | Issues found | Issues fixed | Self-check |
|--------|--------------|--------------|------------|
| <No issues / N issues found> | <N> | <M> | self-checked / regression fixed |

## CEO Decisions
| # | Phase | Issue | Codex Argument | Claude Code Argument | Verdict | Verified | Rationale |
|---|-------|-------|----------------|----------------------|---------|----------|-----------|
| <n> | <phase> | <issue> | <summary> | <summary> | <ACCEPT/REJECT/COMPROMISE> | self-checked / unreviewed | <rationale> |

## Escalations
| # | Phase | Overturned decision / false premise | Evidence | User's choice |
|---|-------|-------------------------------------|----------|---------------|

## Final Status
<Complete / Complete with unresolved items>
```

The report must identify review failures separately from LGTM. Review failure is
not approval.
