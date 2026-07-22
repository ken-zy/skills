# Triage Init — one-time project question-setting

Produces `<repo root>/.agents/triage-profile.md`, the project binding for the
four questions. Run once per repository, or re-run when the project's module
layout / danger surfaces change materially.

The init itself is a jdy-specified 中档 task: it writes an agent-behavior
binding and makes project-specific boundary choices that jdy must confirm
before the file is written. Announce 中档 and silently scan Q4 as required for
all jdy-specified tiers. If the scan finds a Q4 conflict, report the hit and
wait for jdy's final tier ruling; do not write the file before confirmation.

## Flow

1. **Survey (read-only, no jdy time)**: repo layout (where is the main source
   root, what are its direct subpackages), data stores (which tables/stores
   hold data that upstream cannot regenerate), deployment path (scripts,
   skills, target hosts), existing conventions (decision log location,
   design-doc directory). Budget: minutes, greps and ls only.
2. **Draft the profile** using the template below, citing evidence for each
   anchor (path, table name, doc line). For any non-obvious binding, list the
   feasible alternatives and their tradeoffs.
3. **Confirm with jdy section by section** — batch the questions, grilling
   style (appearance 1). jdy's answers are the authority; the survey is only
   the draft.
4. **Write the profile** to `.agents/triage-profile.md`. The profile itself is
   the medium tier's half-page design product; do not create another design
   document for init.
5. Run `/tdd` and `/verify`; when the universal TDD exception applies, declare
   it in the PR and use `/verify` as the backstop.
6. Run one `/code-review` round. Fixes require another `/verify`.
7. Run `/merge-check`, open a GitHub PR, and let jdy merge (appearance 2).
8. Add one decision-log line pointing to the PR. If no decision log exists,
   record the decision in the PR description and say so.

Products: confirmed triage profile + decision-log line. Review cap: 2 rounds,
then escalate under `SKILL.md` universal rule 3.

## Profile template

```markdown
# Triage Profile — <project name>

Authority: /triage skill, including its later micro-tier GitHub PR ruling.
Baseline: predict-v2 issue #72 comment 5013575156.
Confirmed by jdy: <date>.

## Q3 anchors — blast radius
- Top modules: <definition, e.g. direct subpackages of src/<pkg>/>
- Cross-boundary contracts: <API forms, event/queue names, persistence
  boundaries that count as contracts>

## Q4 anchors — danger surfaces
- High-cost runtime semantics: <list, e.g. funds authorization, amount
  computation, order placement/cancellation, ledger, ownership>
  (hint directories: <dirs — hints only, judgment is semantic>)
- Non-resyncable data: <tables/stores that revert+redeploy cannot restore>
- Secrets & deployment boundaries: <env files, key delivery, deploy scripts>

## Micro-tier exclusions
- Operational/normative documents in this repo (never micro): <runbooks,
  deploy READMEs, spec acceptance sections, ...>

## Conventions — where chain products go
- Decision log: <e.g. ROADMAP §6>
- Design docs dir: <e.g. docs/design/>
- Deployment: <skill or process, e.g. deploy-v2, per-instance authorization>

## Anchor examples (calibration)
| Requirement | Path through the tree | Tier |
|---|---|---|
| <real example> | <Step/Q hits> | <tier> |
(3–7 rows, use real past requirements of this project)
```

## Missing-profile behavior (for judge mode)

Not an error. Judge with SKILL.md [default] anchors, append the init
suggestion to the announcement, continue. The generic Q4 defaults (funds /
non-resyncable data / secrets & deploy) keep un-initialized projects
fail-safe.
