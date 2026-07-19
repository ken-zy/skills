# Triage Init — one-time project question-setting

Produces `<repo root>/.claude/triage-profile.md`, the project binding for the
four questions. Run once per repository, or re-run when the project's module
layout / danger surfaces change materially.

The init itself is a requirement: it edits agent behavior specs, so it is at
least 轻档 — announce it, and every profile section needs jdy's confirmation
before writing the file.

## Flow

1. **Survey (read-only, no jdy time)**: repo layout (where is the main source
   root, what are its direct subpackages), data stores (which tables/stores
   hold data that upstream cannot regenerate), deployment path (scripts,
   skills, target hosts), existing conventions (decision log location,
   design-doc directory). Budget: minutes, greps and ls only.
2. **Draft the profile** using the template below, citing evidence for each
   anchor (path, table name, doc line).
3. **Confirm with jdy section by section** — batch the questions, grilling
   style. jdy's answers are the authority; the survey is only the draft.
4. **Write the profile** to `.claude/triage-profile.md` and deliver it via the
   tier the init itself was judged into (usually 轻: PR, jdy merges).

## Profile template

```markdown
# Triage Profile — <project name>

Authority: /triage skill. Rules: predict-v2 issue #72 comment 5013575156.
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
