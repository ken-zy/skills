---
name: deploy-v2
description: Deploy and maintain the predict-v2 repository on its dedicated AWS EC2 host. Use this skill whenever jdy asks how to deploy predict-v2, requests a predict-v2 production or preflight deployment, asks to configure or accept the stable host bootstrap or GHCR pull identity, verify the deployed release, retry an interrupted deployment, or restart the predict-v2 runtime topology. Do not use the legacy deploy skill for predict-v2.
---

# predict-v2 artifact-first deployment

Use this skill only as the intent and safety router. Keep executable Git, SSH, registry, Compose, migration,
service-switch, retry, and secret-delivery sequences out of this file. Obtain every production command and
public outcome definition from the live repository runbook.

## 1. Classify authorization

Classify the request as exactly one or more of:

1. explain the deployment model;
2. observe merge or release CI;
3. install, upgrade, or accept the stable host bootstrap;
4. accept or verify GHCR/runtime material prepared by jdy;
5. acquire an approved release on the host without deploying it;
6. run a normal software deployment;
7. retry the same no-argument deployment after repairing current facts or latest code;
8. activate tasks, fund, sign, transfer, withdraw, or place orders.

Treat every item as a separate authorization. Never infer bootstrap maintenance, credential work, deployment
retry, or trading permission from an earlier deploy request. Require a new explicit authorization before each
production retry, even though the operator command remains the same no-argument entrypoint.

Handle explanation requests without GitHub writes, host connection, or local mutation. Connect to EC2 only for
an explicitly requested live check or host action that the ROADMAP currently permits.

When Codex connects through the approved `ssh predict-v2` alias, allocate a local PTY so 1Password SSH Agent
can complete its signing interaction. Treat `ssh-add -l` only as evidence that the expected public identity is
available, not that a connection signature was approved. If signing hangs or reports agent communication
failure, stop the bounded attempt and tell jdy explicitly to unlock 1Password and approve the SSH-key prompt;
do not retry blindly or infer a host/deployment failure.

## 2. Read live authority

Read these sources before every action:

1. `AGENTS.md` and applicable global policies;
2. `docs/design/ROADMAP.md` for the only current progress/frontier state;
3. `docs/operations/2026-07-14-single-host-production-compose-runbook.md` for the only public command,
   outcome, execution-order, retry, and acceptance contract;
4. `CONTEXT.md` and the deployment ADRs referenced by the runbook;
5. implementation files only as needed to verify the requested action.

Stop on any disagreement. Never reconstruct a command from memory, an old chat, historical acceptance evidence,
`deploy/ops.sh`, a Git checkout, or this skill. Never substitute a legacy entrypoint when ROADMAP says the stable
bootstrap or release pipeline is not implemented or accepted.

## 3. Route the artifact-first flow

Explain the normal flow at this altitude only:

```text
protected main release CI
  -> four digest-bound private GHCR artifacts
  -> ARM64 pullback plus source/component identity verification
  -> serialized monotonic release-ready promotion
  -> separately authorized no-argument stable bootstrap
  -> one frozen manifest plus versioned deployment engine
```

Treat `release-ready` as artifact-ready only. It is not runtime-ready, migration-compatibility proof, or a
successful deployment. Keep runtime, database, fix-forward retry, and closeout acceptance inside the separately
authorized deployment attempt.

When the current ROADMAP and runbook allow acquisition without deployment, follow only their bounded
acquisition path. Do not continue into deployment admission, runtime verification, or deployment closeout.

Require no operator-supplied SHA, branch, generation, digest, checkout, or local config for normal deploy.
Require runtime-digest changes to cover every configured runtime consumer. Treat frontend-only and
already-current behavior exactly as the runbook defines. Keep task state plus the machine-level unreachable
`place_order` gate as the trading boundary; never use worker-process absence as the money boundary.

Do not reproduce the engine's internal rollout steps here. Verify their required evidence against the live
runbook instead.

## 4. Enforce pre-effect admission

Before every host or production effect, confirm:

- ROADMAP currently permits the exact requested host action and records no blocker to it;
- required four-artifact release CI and artifact-ready `release-ready` evidence exists;
- jdy separately authorized this exact host action;

For bootstrap installation or acquisition without deployment, require the exact reviewed install/acquisition
path named by ROADMAP and the runbook. Stop before EC2 if it does not exist. Apply only the bounded
regular-file, ownership, mode, atomic-replacement, credential, and exact-digest checks that those live sources
require. After the authorized artifacts are present, stop without starting them or producing task, database,
service, runtime, venue, wallet, funding, signing, or order effects, and without creating an active attempt.

For normal deployment or an authorized retry, additionally confirm:

- required stable-bootstrap acceptance already exists;
- no concurrent host or runtime-material lock exists; an unfinished database Attempt is input to the same
  no-argument workflow, not a separate recovery command or permanent barrier;
- the runbook's manifest, material, disk, and authoritative-fact admission can pass without secret disclosure;
- first-cutover versus normal previous-release semantics are explicit.

Stop before effects when any item is absent. Never fall back to checkout deployment, local build, fixed apply,
generation, doctor, old preflight, or manually assembled Compose steps.

## 5. Protect credentials and trading boundaries

Never run 1Password CLI locally or through SSH. Never read or print `.env`, secret values, wallet material,
tokens, private keys, signed payloads, authorization headers, or broad process/container environments.

For separately authorized GHCR identity maintenance, jdy prepares the credential material and the Agent never
reads its value. Require the dedicated account/package configuration to
grant Read on exactly the four predict-v2 packages, no private source-repository collaborator role, and a PAT
classic with only `read:packages`. Treat these as configuration facts and use successful exact-digest pulls as
the positive acceptance; do not actively probe a non-allowlisted package, source repository, write, or delete.
Accept it only through the credential-file or standard-input path approved by the live runbook, install it as
`root:root` mode `0600`, and keep it out of argv, environment, Compose, progress, exceptions, receipts, and
logs, but do not add broad scan machinery. Never turn identity maintenance into a normal-deploy side effect.

Do not create or rotate credentials, activate new tasks, add funds, sign, transfer, withdraw, or submit new
orders during software deployment. Permit only the existing-material safety reads, buy cancellation, and
sell/position adoption that the live runbook explicitly requires.

## 6. Handle outcomes and fix-forward retry

Use only `SUCCESS`, `FAILED`, and `ACTION_REQUIRED`, with the runbook's exact meanings. Treat internal phases,
warnings, reason codes, and legacy results as evidence, never additional public outcomes.

If `BOOTSTRAP_ADMISSION_REQUIRED` is traced through narrow non-secret evidence to an installed bootstrap library
that cannot parse the current release manifest, stop deployment and route to a separately authorized atomic
stable-bootstrap upgrade from the latest reviewed deployment bundle. When a support library changes, require the
installer to create a fresh immutable library generation before replacing the launcher; never overwrite an
existing generation in place. Treat this as failure repair, not a new normal-deploy preflight or public step.

On every `ACTION_REQUIRED` or `FAILED`, stop automatic retry and preserve the database Attempt's current blocker.
Repair current facts or latest code, obtain a new explicit deployment authorization, and rerun the same
no-argument command; do not select an old release, invoke a separate recovery command, read a legacy active
marker, downgrade the database, or add a second progress record. Apply the runbook's no-fabricated-baseline rule
to the first new-system cutover and revalidate every required task/order/position gate before terminal closeout.

## 7. Report bounded evidence

Use only the runbook's narrow, non-secret checks. Prefer actual component digests, database revision, module
health, network exposure, task ownership, and authoritative venue facts over pointers or receipts. Avoid broad
logs and container metadata.

Report only evidence relevant to the authorized action. For acquisition without deployment, report the frozen
manifest and exact component digests, successful presence on the host, the untouched deployment/trading
boundary, the exact blocker if any, and one authorized next action; do not require runtime, database, task,
venue, or Deployment Attempt evidence. For deployment or retry, report the public outcome or `未执行`, runtime
and frontend health, database revision, task/venue closeout, active-attempt state, untouched trading boundary,
exact blocker, and one authorized next action.

Do not modify ROADMAP, create/switch a branch, commit, push, or open a PR unless jdy separately authorizes those
specific Git and documentation actions. If authorized, update progress only in `docs/design/ROADMAP.md`; never
copy transient production state into this skill.
