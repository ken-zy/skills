# Interrupted deployment and one-shot residue

Read this reference only when a canonical deployment is quiet, interrupted, disconnected, apparently hung, or
blocked by possible one-shot bundle residue. It defines decisions, not executable commands; the live runbook
remains the command and acceptance authority.

## Preserve three separate facts

| Fact | Required statement |
|---|---|
| Canonical invocation | Terminal public output was observed, or it was not observed. |
| Convergent state | Database Attempt, revision, exact component digests, required-service health, network exposure, task ownership, and venue authority are accepted or unresolved. |
| One-shot lifecycle | The exact deployment bundle is absent, running, or exited residue. |

Never replace one fact with another. In particular, a terminal database `SUCCESS` does not fabricate a missing
canonical `SUCCESS` after the SSH session or outer launcher was interrupted.

## Handle quiet or interrupted execution

After SSH authentication completes, silence alone is not an authentication failure, deployment failure, or
permission to send `Ctrl-C`. Distinguish an explicit 1Password signing prompt or agent error from an accepted
remote session. Respect the runbook's bounded execution budget. If progress becomes uncertain, do not start a
second deployment; use only authorized narrow read-only status checks from the live runbook.

If the outer session is interrupted, do not assume the versioned bundle stopped. Treat
`BOOTSTRAP_ADMISSION_REQUIRED` as generic until narrow non-secret evidence identifies its cause. Resolve, in
order, the exact labeled one-shot inventory and digest, its lifecycle state, host locks, database Attempt and
lease, required-service acceptance, and current resource pressure. Never infer manifest-parser incompatibility
from the public reason code alone.

## Classify current facts

| Bundle and authoritative state | Decision |
|---|---|
| Running bundle plus unfinished Attempt or live lease | Deployment is active. Observe within the runbook budget; do not delete or start another deploy. |
| Running bundle plus terminal Attempt | Closeout may still be running or orphaned from its launcher. Continue bounded read-only observation; do not delete or retry. |
| One unique exited-zero bundle with exact matching label and digest, terminal `SUCCESS`, released lease, open authority, zero runnable tasks, zero owned pauses, and full revision/service/digest/network acceptance | Deployment effects are convergent and the container is an exact cleanup candidate. The canonical public result remains unobserved if its terminal output was not captured. |
| Multiple, foreign, nonzero-exit, nonterminal, or otherwise ambiguous bundles | Preserve the inventory as `ACTION_REQUIRED` input. Do not delete or retry. |

Severe memory, swap, or I/O pressure can explain delayed closeout. It is not proof of deployment failure and does
not authorize a signal, forced deletion, reboot, or redeploy. Treat it as an independent host-health fact unless
the live acceptance contract makes it a blocker.

## Clean one exact exited residue

Cleanup is a separate production mutation. A current request to repair or clean the already diagnosed
deployment problem is sufficient when narrow evidence leaves exactly one safe residue target; it need not repeat
the container ID or deletion verb. State the exact target and exclusions before acting. Do not inherit cleanup
permission from an earlier deploy or retry authorization alone.

Immediately before cleanup, re-resolve the unique container identity and every predicate in the exited-zero row
above. Remove only that exited container through the runbook's bounded exact-target path. Never use force for an
exited container, broad pruning, globs, or removal of images, volumes, databases, or application services. If the
bounded cleanup fails once, stop without rebooting or escalating deletion.

After cleanup, reverify zero labeled residue, deployment and database closeout, exact service digests and health,
network exposure, untouched task/trading boundaries, and current resource pressure. Cleanup never authorizes or
requires a redeploy. When deployment effects are already convergent, do not rerun solely to manufacture a
missing terminal SSH result. A retry still needs current evidence that deployment work remains and explicit
authorization for the no-argument entrypoint; apply the scope and consumption rule in SKILL.md section 1.

## Report without fabricating success

If terminal output was not captured, report `canonical public result not observed`; this is an observation, not
a fourth public outcome. Separately state whether deployment effects are convergent, whether one-shot cleanup
remains, the exact blocker, and the one next action that is actually authorized.
