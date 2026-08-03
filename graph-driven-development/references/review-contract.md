# Review and Arbitration Contract

Read this before preparing a review request or interpreting a verdict.

## Reviewer input

Upload the identical `review-request.json`, `full.diff`, and `review-context.txt` to every current Reviewer. Send the external Package v2 ID in the Browser message, together with:

- backend, visible model, exact UI selection, separately exposed reasoning setting or `null`, and Browser evidence reference;
- Reviewer role and read-only/non-authoring constraints;
- exact reviewed head and Package ID;
- instruction to assess only the frozen scope, acceptance criteria, complete diff, risks, and evidence.

Do not include the Writer's desired verdict, suspected defect list, proposed fixes, or another Reviewer's conclusion. Reject a review conversation that appears in the implementation-author IDs.

## Reviewer output

Require one top-level verdict:

```text
PASS
CHANGES_REQUESTED
NEEDS_EVIDENCE
BACKEND_FAILED
```

Require this shape:

```json
{
  "verdict": "PASS",
  "reviewed_head": "<exact head>",
  "returned_package_id": "sha256:<64 lowercase hex>",
  "summary": "",
  "findings": [],
  "evidence_request": []
}
```

Each finding uses:

```json
{
  "finding_id": "stable-id",
  "severity": "high",
  "attribution": "implementation",
  "location": "path:line or exact artifact location",
  "claim": "",
  "evidence": "",
  "recommended_direction": ""
}
```

Allowed severities are `blocking`, `high`, `medium`, and `low`. Attribution is `implementation`, `plan`, or `contract`. A blocking/high finding needs a concrete location, claim, and evidence.

Reject a verdict whose head or returned Package ID differs from the immutable candidate.

Interpretation:

- `PASS`: no blocking/high finding; retain medium/low items as advisory.
- `CHANGES_REQUESTED`: Codex verifies every finding.
- `NEEDS_EVIDENCE`: allow one bounded supplement that does not change candidate inputs, then require a final verdict.
- `BACKEND_FAILED`: preserve the failure and follow Browser fallback policy; never substitute another platform.

After reconciliation, the current Reviewer state records final `PASS`, `findings_reconciled: true`, and `blocking_high_remaining: false`. Preserve completion time as evidence even though the schema validator does not try to prove wall-clock truth.

## Finding verification

For every finding:

1. verify the location against the reviewed snapshot;
2. verify the claim against code, tests, artifacts, and frozen contract;
3. classify it as `accepted`, `advisory`, or `disputed`;
4. route accepted findings by severity and attribution;
5. arbitrate disputed blocking/high findings.

Preserve count conservation:

```text
total findings = accepted + advisory + overruled_by_arbiter + unresolved
```

Never downgrade an unverified blocking/high finding merely to unblock delivery.

## Arbitration

Use a fresh read-only conversation distinct from Codex's Writer role, the original Reviewer, and any implementation-authoring conversation. Send the finding, frozen contract, reviewed head, Package ID, Reviewer evidence, and neutral counter-evidence. Do not authorize repository writes or new scope.

Require one of:

```text
SUPPORT_FINDING
OVERRULE_FINDING
NEEDS_EVIDENCE
BACKEND_FAILED
```

- `SUPPORT_FINDING`: route by attribution to implementation, planning, or `WAITING_HUMAN`.
- `OVERRULE_FINDING`: preserve both sides and classify `overruled_by_arbiter`.
- `NEEDS_EVIDENCE`: allow one bounded supplement.
- `BACKEND_FAILED`: preserve evidence and pause if no independent approved session remains.

## Scope discipline

Review only the frozen objective, acceptance criteria, complete diff, risk evidence, and test/artifact evidence. Do not block delivery by requesting a generic workflow engine, event-sourcing system, recovery framework, lock manager, source packager, or unrelated redesign.

Report a scope omission only when the frozen acceptance criteria cannot be satisfied safely without it. Material omissions use the scope-expansion gate instead of being silently added during rework.
