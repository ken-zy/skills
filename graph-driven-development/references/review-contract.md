# Review and Arbitration Contract

Read this file before preparing independent review inputs, interpreting Review results, or invoking an Arbiter.

## Reviewer input

Send a minimal, read-only package:

```yaml
review_request:
  review_id: uuid
  role: reviewer
  risk_level: normal
  objective: ""
  in_scope: []
  out_of_scope: []
  acceptance_criteria: []
  required_participations: []
  implementation_authors: []
  frozen_test_commands: []
  test_evidence: []
  tracked_files: []
  diff: ""
  prohibited_actions:
    - modify repository
    - run side-effecting commands
    - commit
    - push
    - deploy
```

Include enough surrounding code to verify the Diff. Do not include the Writer's conclusions, expected verdict, suspected defects, or desired fixes.

Record:

- backend and model, when visible;
- fresh conversation ID;
- input hash or exact attachment hashes;
- review start and completion time;
- whether the Reviewer remained read-only;
- whether the Reviewer session appears in `implementation_authors`; reject the Review if it does.

## Reviewer output

Require exactly one top-level verdict:

```text
PASS
CHANGES_REQUESTED
NEEDS_EVIDENCE
BACKEND_FAILED
```

Require this structure:

```yaml
verdict: PASS
summary: ""
findings: []
evidence_request: []
```

For every finding require:

```yaml
- finding_id: stable-id
  severity: blocking  # blocking | high | medium | low
  attribution: implementation  # implementation | plan | contract
  location: path:line
  claim: ""
  evidence: ""
  recommended_direction: ""
```

Reject or request correction for a `blocking/high` finding that lacks a concrete location, claim, or evidence. Do not discard it silently.

Interpret verdicts:

- `PASS`: no `blocking/high` finding; preserve any medium/low findings as advisory.
- `CHANGES_REQUESTED`: one or more findings require verification.
- `NEEDS_EVIDENCE`: provide one bounded evidence supplement, then require a final verdict.
- `BACKEND_FAILED`: the backend could not complete a reliable review.

## Finding verification

For each finding:

1. Verify the cited location against the actual reviewed snapshot.
2. Verify the claim against code, tests, and the frozen contract.
3. Classify it as `accepted`, `advisory`, or `disputed`.
4. Route accepted findings by severity and attribution.
5. Send a disputed `blocking/high` finding to an independent Arbiter.

Preserve count conservation:

```text
total findings
= accepted
+ advisory
+ overruled_by_arbiter
+ unresolved
```

Do not convert an unverified `blocking/high` finding into advisory merely to unblock delivery.

## Arbiter input

Use a fresh session and a backend or agent distinct from the Writer, original Reviewer, and any implementation author whose candidate is involved in the finding.

Send:

```yaml
arbitration_request:
  finding: {}
  frozen_contract: {}
  reviewed_snapshot_hash: sha256
  reviewer_evidence: ""
  writer_counter_evidence: ""
  implementation_authors: []
  prohibited_actions:
    - modify repository
    - introduce new scope
    - redesign unrelated code
```

Do not tell the Arbiter which party should win.

## Arbiter output

Require:

```yaml
verdict: SUPPORT_FINDING  # SUPPORT_FINDING | OVERRULE_FINDING | NEEDS_EVIDENCE | BACKEND_FAILED
finding_id: stable-id
reasoning: ""
decisive_evidence: ""
```

Apply:

- `SUPPORT_FINDING`: return to N2, N1, or `WAITING_HUMAN` according to attribution.
- `OVERRULE_FINDING`: save both sides' evidence and classify as `overruled_by_arbiter`.
- `NEEDS_EVIDENCE`: allow one bounded supplement; otherwise `WAITING_HUMAN`.
- `BACKEND_FAILED`: use the remaining fallback budget; otherwise `WAITING_HUMAN`.

## Scope discipline

Review only the frozen objective, acceptance criteria, Diff, and evidence.

Do not block V1 by requesting:

- a configurable graph or generic workflow engine;
- event sourcing, crash recovery, or concurrent-run locks;
- a generic source packaging framework;
- commit, push, PR, deploy, or production-side-effect orchestration;
- mechanisms justified only by hypothetical future needs.

Report a scope omission only when the frozen acceptance criteria cannot be satisfied safely without it.
