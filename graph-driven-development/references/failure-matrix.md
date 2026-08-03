# Failure Matrix and Scope Gate

Use proportional evidence before implementation:

- normal tasks record concise `risk_notes` for applicable failure behavior, containment, and rollback; they do not fill a mostly `not_applicable` matrix;
- high-risk tasks involving state machines, concurrency, recovery, authentication, permissions, migrations, persistence, or external effects freeze the complete matrix in N1 and send it to Reviewers.

If a normal task later enters one of those risk domains, reclassify it as high risk and complete the matrix before continuing.

## Template

| Area | Failure or abuse case | Status | Prevention/detection | Verification evidence | Owner/next action |
|---|---|---|---|---|---|
| Inputs | malformed, missing, boundary, or oversized input | open | | | |
| Permissions | unauthorized identity/action or privilege escalation | open | | | |
| Concurrency | duplicate, reordered, stale, or racing operation | open | | | |
| Retry/idempotency | retry creates duplicate or inconsistent effects | open | | | |
| Persistence | partial write, incompatible schema, rollback failure | open | | | |
| External effects | unknown outcome, irreversible action, unsafe retry | open | | | |
| Observability | failure is silent, ambiguous, or lacks correlation | open | | | |
| Recovery | restart/resume violates invariants | open | | | |

For those high-risk domains, explicitly cover or mark N/A with reason:

- exact identity and original type preservation;
- idempotency and duplicate requests;
- failure before durable write;
- failure after durable write;
- partial installation and crash behavior;
- restart, replay, and checkpoint recovery;
- ownership conflicts and concurrent advancement;
- publication order for `READY`, `RECOVERING`, `DEGRADED`, and `HALTED`;
- backend truth versus frontend receipt/projection conflicts;
- command, task, and Worker consistency;
- orphan side effects that remain while health appears normal.

Allowed statuses:

- `covered`: design and test/evidence are named.
- `not_applicable`: a concrete reason explains why the area is outside this task's behavior.
- `open`: the gap is unresolved; record owner and next action.

Do not start implementation with an unexplained `open` row that can affect authentication, authorization, persistence, concurrency, migration, external effects, funds, signing, production, or irreversible data.

## Normal versus abnormal behavior

For each applicable row, state both:

- normal path: what must happen and what evidence proves it;
- abnormal path: how failure is detected, contained, reported, retried, or refused.

Never treat “the happy-path test passes” as coverage for unknown external outcomes, idempotency, or rollback.

## Scope-expansion gate

In N0/N1, list `delivery_units` and mark which risk domains each unit touches:

- UI/frontend projection;
- durable command/API;
- Runtime state machine;
- crash recovery/replay;
- permissions or real external side effects.

If one request spans more than two of these domains, propose phased delivery by default. Do not split when that would make either phase unsafe or unverifiable; record the reason.

Pause before implementing when new evidence requires any of these beyond the frozen contract:

- a new subsystem or public interface;
- a dependency addition/upgrade;
- a schema migration or compatibility policy;
- a new permission/authentication boundary;
- a new remote, production, financial, signing, or irreversible side effect;
- changes to acceptance criteria, risk class, or required participants;
- a workaround that changes the approved architecture rather than fixing it.

When triggered:

1. stop new writes at the smallest safe boundary;
2. record the new evidence and impacted matrix rows;
3. update the spec/plan or contract proposal;
4. state new verification and authorization needs;
5. enter `WAITING_HUMAN` when the expansion materially changes the result or authority.

Do not use this gate for a small implementation detail already implied by the frozen design.
