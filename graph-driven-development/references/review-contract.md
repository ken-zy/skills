# Review and Arbitration Contract

Read this before interpreting a verdict.

## Reviewer input manifest

Put the request in `review-request.yaml`; upload it with `full.diff` and `review-context.txt`:

```yaml
review_request:
  review_id: "uuid"
  package_sequence: 1
  package_digest: "sha256"
  backend: "chatgpt-web"
  model: "visible model name"
  required_reasoning_level: "Extra High"
  selected_reasoning_level: "Extra High"
  exact_backend_required: false
  exact_model_required: false
  exact_reasoning_level_required: true
  role: "reviewer"
  risk_level: "normal"
  objective: ""
  in_scope: []
  out_of_scope: []
  acceptance_criteria: []
  implementation_authors: []
  base_commit: ""
  head_commit: ""
  test_evidence: []
  artifact_evidence: []
  risk_focus: []
  prohibited_actions:
    - "modify repository"
    - "run side-effecting commands"
    - "commit"
    - "push"
    - "deploy"
```

Both Reviewers must receive identical attachment digests and head SHA. Record backend, visible model, selected reasoning level, fallback reason, fresh conversation URL/ID, start/completion time, and read-only confirmation. Reject a review whose conversation appears in `implementation_authors`.

Do not include the Writer's conclusions, expected verdict, suspected defects, desired fixes, or the other Reviewer's verdict.

## Reviewer output

Require exactly one top-level verdict:

```text
PASS
CHANGES_REQUESTED
NEEDS_EVIDENCE
BACKEND_FAILED
```

Require:

```yaml
verdict: "PASS"
reviewed_head: "sha"
package_digest: "sha256"
summary: ""
findings: []
evidence_request: []
```

Every finding uses:

```yaml
- finding_id: "stable-id"
  severity: "blocking"  # blocking | high | medium | low
  attribution: "implementation"  # implementation | plan | contract
  location: "path:line"
  claim: ""
  evidence: ""
  recommended_direction: ""
```

Reject or request correction for a `blocking/high` finding without concrete location, claim, and evidence. Reject a verdict whose head or package digest differs from the immutable package.

Interpretation:

- `PASS`: no blocking/high finding; retain medium/low findings as advisory.
- `CHANGES_REQUESTED`: verify every finding.
- `NEEDS_EVIDENCE`: allow one bounded supplement without changing candidate inputs, then require a final verdict.
- `BACKEND_FAILED`: record the failure and follow the browser/backend contract; do not substitute a new platform.

## Finding verification

For every finding:

1. verify the location against the reviewed snapshot;
2. verify the claim against code, tests, artifacts, and frozen contract;
3. classify as `accepted`, `advisory`, or `disputed`;
4. route accepted findings by severity and attribution;
5. arbitrate disputed blocking/high findings.

Preserve count conservation:

```text
total findings = accepted + advisory + overruled_by_arbiter + unresolved
```

Never downgrade an unverified blocking/high finding merely to unblock delivery.

## Arbitration

Use a fresh read-only conversation distinct from the Writer, original Reviewer, and relevant implementation author. Preserve the two-tab cap and approved backend allowlist.

Send neutrally:

```yaml
arbitration_request:
  finding: {}
  frozen_contract: {}
  reviewed_head: "sha"
  package_digest: "sha256"
  reviewer_evidence: ""
  writer_counter_evidence: ""
  implementation_authors: []
  prohibited_actions:
    - "modify repository"
    - "introduce new scope"
    - "redesign unrelated code"
```

Require:

```yaml
verdict: "SUPPORT_FINDING"  # SUPPORT_FINDING | OVERRULE_FINDING | NEEDS_EVIDENCE | BACKEND_FAILED
finding_id: "stable-id"
reasoning: ""
decisive_evidence: ""
```

- `SUPPORT_FINDING`: return to implementation, planning, or `WAITING_HUMAN` according to attribution.
- `OVERRULE_FINDING`: preserve both sides and classify `overruled_by_arbiter`.
- `NEEDS_EVIDENCE`: allow one bounded supplement.
- `BACKEND_FAILED`: preserve evidence and enter `WAITING_HUMAN` if no independent approved session remains.

## Scope discipline

Review only the frozen objective, acceptance criteria, complete diff, failure risks, and evidence. Do not block delivery by requesting a generic workflow engine, event sourcing, crash recovery framework, lock manager, generic source packager, or unrelated redesign.

Report a scope omission only when the frozen acceptance criteria cannot be satisfied safely without it. A material omission goes through the scope-expansion gate rather than being silently added during rework.
