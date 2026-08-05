---
name: deploy-v2
description: Deploy and maintain the predict-v2 repository on its dedicated AWS EC2 host. Use this skill whenever jdy asks how to deploy predict-v2, requests a predict-v2 production or preflight deployment, asks to configure or accept the stable host bootstrap or GHCR pull identity, verify the deployed release, recover an exact deployment attempt, or restart the predict-v2 runtime topology. Do not use the legacy deploy skill for predict-v2.
---

# predict-v2 artifact-first deployment

This skill is the intent and safety router for predict-v2 deployment. It deliberately contains no executable
Git, SSH, registry, Compose, migration, service-switch, recovery, or secret-delivery command sequence. The
live repository runbook is the only production command source, so a stale cached skill cannot reintroduce a
checkout-based or partial-runtime deployment path.

## 1. Classify the requested authorization

Treat these as separate actions; never infer one from another:

1. explain the deployment model;
2. merge code or observe release CI;
3. install/upgrade/accept the stable host bootstrap;
4. create, prepare, rotate, or accept the GHCR pull identity or runtime material;
5. run a normal software deployment;
6. recover one exact interrupted attempt;
7. activate tasks, enable funding, sign, transfer, withdraw, or place orders.

For an explanation, read live sources and answer without GitHub or host mutation. A request to deploy authorizes
only the current runbook's normal deployment, not bootstrap maintenance, credential preparation, recovery, or
trading. Recovery requires the exact attempt and a separate authorization. Any credential or trading action
requires its own explicit authorization and project gates.

Do not connect to EC2 merely to answer a question or inspect repository state. Connect only when jdy explicitly
requests a live check or an authorized host action and the ROADMAP says that action is available.

## 2. Re-open the live sources every time

Locate the current predict-v2 checkout and read, in order:

1. `AGENTS.md` and applicable global policies;
2. `docs/design/ROADMAP.md` — the only current progress/frontier source;
3. `docs/operations/2026-07-14-single-host-production-compose-runbook.md` — the only public command and
   outcome source;
4. `CONTEXT.md` and the deployment ADRs referenced by the runbook;
5. the current authorized Issue/operation sheet named by ROADMAP, if any;
6. release workflow, manifest contract, deployment bundle or Compose files only when needed to verify the
   current requested action.

Never reconstruct commands from memory, an older chat, a historical acceptance record, `deploy/ops.sh`, a
server checkout, or this skill. If live sources disagree, stop and report the exact conflict. If ROADMAP says the
stable bootstrap or release pipeline is not implemented/accepted yet, do not substitute a legacy entrypoint.

## 3. Artifact-first release contract

PR CI verifies quickly and publishes no production artifacts. A protected `main` release workflow builds four
private GHCR artifacts on native ARM64: runtime image, frontend image, deployment bundle, and release manifest.
It pulls candidates back by digest, runs the full isolated rehearsal, then uses a serialized monotonic promotion
gate to advance the single `release-ready` discovery reference.

Normal deploy is independently authorized. The fixed host bootstrap resolves `release-ready` once, freezes one
immutable manifest digest, validates protocol/repository/artifact identity, retrieves the versioned bundle, and
hands control to that bundle's engine. The operator supplies no SHA, generation, branch, digest, checkout, or
local config.

A runtime digest change updates every configured runtime consumer as one coordinated software release:
control-plane, market-sync, workers, wallet observer, predict-auth-broker, dependent jobs, and frontend when its
digest changes. A frontend-only release has zero task, venue, runtime, and database effect. Task state plus the
machine-level unreachable `place_order` gate controls trading; absence of a worker process is not the safety
model.

Software deployment does not create/rotate credentials, activate new tasks, add funds, sign, transfer, withdraw,
or submit new orders. It may use already-approved material only for authoritative reads, required cancellation of
pre-existing affected buys, and adoption of existing sells/positions.

## 4. Pre-effect admission

Before any host or production effect, verify from the live runbook and authorized operation scope that:

- the relevant GitHub-native blockers are closed and the requested Issue is the current frontier;
- release CI produced a complete `RELEASE_READY` release and required checks/rehearsal passed;
- stable bootstrap installation/acceptance is complete if the action depends on it;
- the request separately authorizes this exact host action;
- there is no unresolved active attempt or concurrent deployment lock;
- manifest/protocol/repository identities, required material admission, disk, and authoritative runtime facts can
  be checked without exposing secret values;
- first-cutover versus normal rollback semantics are explicit.

If any item is missing, stop before effects. Do not fall back to Git checkout deployment, local build, old
preflight/fixed-apply/generation/doctor surfaces, or a manually assembled Compose sequence.

## 5. Secret and registry boundary

- Agents never run 1Password CLI locally or through SSH.
- Never read `.env`, secret values, wallet material, tokens, private keys, signed payloads, full authorization
  headers, or unfiltered process/container environments.
- Never run broad environment or container inspection commands.
- The only persistent registry secret allowed by the contract is the root-owned mode-`0600` GHCR pull credential
  file on encrypted EBS; never print or copy it.
- The dedicated GitHub machine identity must have Read permission only on the four explicitly allowed private
  predict-v2 packages, no source-repository collaboration, no other private package access, and a PAT classic
  limited to `read:packages`.
- Initial setup/rotation acceptance must prove allowlisted digest pulls succeed and non-allowlisted package,
  source repository, write, and delete access fail. Those checks are separately authorized identity maintenance,
  not normal deployment.
- Registry credentials must never appear in argv, environment, Compose, progress, exception, receipt, or logs.

If required runtime material is absent or incompatible, normal deploy must return `ACTION_REQUIRED` before an
active attempt and before task/database/service effects. Instruct jdy to use the exact human-only live procedure;
do not materialize it yourself.

## 6. Runtime rollout and recovery invariants

For runtime-affecting releases, enforce the runbook's fixed order:

1. complete read-only checks and freeze the manifest;
2. durably create the minimal active-attempt marker immediately before the first effect;
3. snapshot/pause runnable tasks with attempt-owned CAS;
4. cancel affected wallet buys and prove authoritative buy-zero;
5. stop every old runtime consumer;
6. run backward-compatible migration/bootstrap without database downgrade;
7. start and validate the complete candidate runtime topology;
8. adopt current sells/positions per exact task scope and resume eligible attempt-owned tasks;
9. revalidate digests, health, network, database, tasks, orders, and positions;
10. finalize current release, terminal receipt, and active marker in the mandated order.

Manual task changes win. Unknown order identity, stale/failed venue reads, `cancel_pending`, ambiguous position,
module mismatch, or incomplete task restoration is `ACTION_REQUIRED`; never retry automatically.

Recovery accepts only the exact attempt ID and derives candidate/previous identity from its evidence. It never
accepts an arbitrary release or database downgrade. From the second successful new-system release onward, a
candidate failure may restore the exact previous full release on the migrated database. The first new-system
cutover has no fabricated legacy baseline and no automatic rollback after effects.

## 7. Interpret only the three public outcomes

- `SUCCESS`: frozen candidate is current, every required module/boundary is healthy, pre-attempt runnable tasks
  are safely restored, and no unresolved attempt remains. Healthy already-current is also `SUCCESS`.
- `FAILED`: candidate is not current, but the exact previous full release and every eligible task are
  authoritatively safe; no operator action remains.
- `ACTION_REQUIRED`: every partial, unknown, contradictory, unsafe, or still-human-dependent state. Preserve the
  active marker and exact attempt identity; no normal retry.

Do not turn internal phases, warnings, reason codes, old `ACCEPTED`, `ALREADY_CURRENT`, `NEEDS_BOOTSTRAP`,
`NEEDS_RECOVERY`, `BLOCKED`, or doctor verdicts into additional public outcomes.

## 8. Evidence and reporting

Use only bounded, non-secret checks named by the live runbook. Actual runtime facts override pointers and
receipts. Required evidence is proportional to the authorized action and includes, where applicable:

- frozen release manifest and actual component digests;
- database revision and complete module health;
- PostgreSQL with no host-published port and frontend bound only to Tailscale;
- task pause/restore ownership and current authoritative order/position facts;
- current release, immutable terminal receipt, optional linked recovery closeout, and active-marker state;
- zero credential disclosure in process/Compose/progress/receipt/log surfaces.

Do not dump broad logs or container metadata. Keep diagnosis to narrow fields and bounded time ranges.

Report:

```markdown
部署结果：SUCCESS / FAILED / ACTION_REQUIRED / 未执行
授权动作：说明 / release 观察 / bootstrap 维护 / identity 维护 / normal deploy / exact-attempt recovery
冻结 manifest：<digest or 未冻结>
runtime topology：<完整健康 / 部分 / 未变更 / 未检查>
frontend：<健康且仅 Tailscale / 未变更 / 未检查>
database revision：<revision or 未检查>
task/venue truth：<已权威收口 / 不适用 / 未检查>
active attempt：<none / exact id / 未检查>
真实交易：未授权且未启用 / <only when separately authorized>
阻塞项：<none or exact evidence>
下一步：<one authorized action; never an inferred deploy/retry/trade>
```

Update progress only in `docs/design/ROADMAP.md` through the normal predict-v2 branch/PR workflow. Do not copy
transient production state into this skill.
