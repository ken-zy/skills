---
name: deploy-v2
description: Deploy and maintain the predict-v2 repository on its dedicated AWS EC2 host. Use this skill whenever jdy asks how to deploy predict-v2, requests a predict-v2 production or preflight deployment, asks to update the EC2 checkout, configure the server's GitHub read access, verify the deployed version, or restart the predict-v2 control plane. Do not use the legacy deploy skill for predict-v2.
---

# predict-v2 deployment

Deploy `predict-v2` to its dedicated ARM64 EC2 host through the repository's live production runbook. This skill is the intent and safety router; it deliberately does not duplicate executable Git, SSH, or Compose deployment commands. Keeping one command source prevents a stale skill from silently undoing reviewed runbook changes.

## 1. Resolve intent before acting

Classify the request before running remote commands:

- A question such as “服务器如何部署” asks for an explanation. Read the live documents and explain the process without modifying GitHub or the server.
- An instruction such as “开始部署” or “执行部署” authorizes only the normal no-money deployment workflow in the live runbook and the operation sheet selected by the ROADMAP.
- Enabling `worker-host`, setting `V2_WORKER_HOLD=0`, changing to `V2_ENVIRONMENT=production`, or performing a real trade requires separate, explicit approval from jdy. A general deployment instruction is not sufficient.
- If the requested target, commit, environment, or money boundary is ambiguous, stop and ask jdy to confirm it.

Never use `/Users/jdy/Documents/skills/predict/skills/deploy/SKILL.md` for this repository. That skill belongs to the legacy `predict_market` system and a different EC2 host.

## 2. Re-open the live sources of truth

Locate the checkout. Prefer the current Git root when it is `predict-v2`; otherwise use `/Users/jdy/Code/predict-v2` if it exists.

Before every deployment, read these live files rather than relying on commands copied into this skill:

1. `AGENTS.md` — repository safety and Git rules.
2. `docs/design/ROADMAP.md` — current phase, blockers, and permitted next step.
3. `docs/operations/2026-07-14-single-host-production-compose-runbook.md` — authoritative EC2 and Compose procedure.
4. `deploy/docker-compose.prod.yml` — actual services, profiles, dependencies, ports, and defaults.
5. The reviewed operation sheet named by the current ROADMAP step — the exact target-capture, deployment, and acceptance sequence for that operation.

The live runbook and reviewed operation sheet are the only executable deployment command sources. Do not reconstruct a deployment sequence from memory or from an older conversation. If the repository files disagree with one another, stop and report the conflict. If they disagree with this skill, the repository documents win; update this skill only after jdy approves the new deployment contract.

## 3. Command-source and release boundary

- Capture the target dynamically from the reviewed remote branch exactly once per deployment round. Never write a release commit into this skill or a reusable operation sheet.
- Require a clean local worktree, an immutable full target SHA on `origin/main`, required GitHub checks, and a ROADMAP state that permits the requested action.
- Require the EC2 checkout to be clean and fast-forwardable to the captured target. A dirty checkout, detached target, non-fast-forward update, or SHA mismatch is a blocker; never reset or overwrite it automatically.
- The production Compose contract has one Python runtime build owner. Build and service switching are separate phases; all required target images must exist before any running service is recreated.
- Classify control-plane and frontend independently from their running image tags. Both already at target means zero build; both off target permits the reviewed new-target path; a mixed state is a blocker before checkout or build.
- A missing target image under a no-build switch is a deployment failure. Never restore a combined build-and-up path as an improvised fallback.
- The two repository PRs for a deployment-contract change must both be merged before deployment when the live ROADMAP or operation sheet says they are coupled.

## 4. Non-negotiable safety boundary

- Connect only through `ssh predict-v2`; the remote checkout is `~/predict-v2`.
- Never read `.env`, `.env.production`, or secret values.
- Never run `env`, `printenv`, `set`, `docker inspect`, or `docker exec ... env`.
- Never print values whose names contain `KEY`, `SECRET`, `TOKEN`, `PRIVATE`, or `PASSWORD`.
- Runtime secrets remain under `/run/predict-v2/runtime-secrets`; verify only existence, non-empty size, owner, and mode.
- Never write secrets to the repository, EBS-backed ordinary files, shell history, Compose YAML, or logs.
- Never run `docker compose down -v`; it deletes the PostgreSQL named volume.
- Never run `alembic downgrade base` against an existing database. The downgrade round trip is only for a brand-new empty volume when the live runbook explicitly permits it.
- Never expose PostgreSQL port `5432` on the host.
- `V2_FRONTEND_BIND_IP` may only be the host's Tailscale IPv4 (unset falls back to loopback, which is fail-safe). Never `0.0.0.0`; port 80 must never bind a public interface, and the AWS security group must not open 80/443 to the internet.
- Do not enable the `host` profile during the default deployment.
- Keep `V2_ENVIRONMENT=preflight`. Keep `worker-host` stopped.
- No real-money canary is allowed until the live ROADMAP/runbook gates are satisfied, including off-host backup and restore validation where required.

- Agents never run the 1Password CLI (`op`), locally or through SSH. If the live runbook requires a 1Password step, stop and instruct jdy to execute that exact step personally in Terminal.app outside tmux. 1Password SSH Agent use through `ssh predict-v2` remains allowed.
- An EC2 reboot clears `/run`. Confirm `/run` is still tmpfs and only verify the required runtime-secret files by existence, non-empty size, owner, and mode. If a file is missing, stop for the jdy-only live-runbook procedure; do not materialize it yourself.
- The default no-money deployment must not materialize wallet credentials because `worker-host` remains off.

## 5. Required post-deployment evidence

Use the bounded, non-secret checks from the live runbook and operation sheet. Do not substitute broad log dumps or environment inspection. A successful no-money deployment must prove:

- remote checkout equals the captured target SHA and remains clean;
- control-plane and frontend both run the exact captured target image tags;
- control-plane health succeeds;
- frontend is bound only to the Tailscale IPv4, `/` returns 200, and `/api/internal/x` returns 403;
- PostgreSQL has no host-published port;
- `worker-host` is not running and no wallet credential was materialized;
- expected registry cardinality and operation-specific residue checks pass.

For a worker-off preflight, an application-level degraded status caused only by intentionally absent worker heartbeats may be expected when the live runbook says so. Any failed HTTP request, unhealthy container, database error, exposed PostgreSQL port, publicly bound frontend port, running worker, image-tag mismatch, checkout mismatch, or secret-file gate failure stops the deployment.

Do not broadly dump logs into the conversation. If diagnosis requires logs, keep the time and line range bounded and prevent URLs, credentials, headers, or secret values from entering the transcript.

## 6. Failure and rollback handling

- Stop at the first failed gate and report the exact failed command and non-secret evidence.
- Do not improvise a destructive rollback, reset a dirty checkout, delete volumes, or reverse migrations.
- Preserve the PostgreSQL volume and the last known image tag.
- Before rollback, inspect whether the failed release applied a forward migration and whether the previous application image is schema-compatible.
- Present a rollback plan to jdy and obtain approval before changing the remote checkout or recreating services with an earlier image.

## 7. Report format

Conclude with:

```markdown
部署结果：成功 / 已停止 / 失败
目标 commit：<full SHA>
服务器 commit：<full SHA or 未变更>
环境：preflight
control-plane：运行 / 未运行 / 未变更
frontend：运行（仅绑定 Tailscale IP）/ 未运行 / 未变更
worker-host：关闭
真实交易：未启用
数据库端口：未暴露 / 检查失败
健康检查：<HTTP result and status>
阻塞项：<none or exact blocker>
下一步：<one concrete action>
```

If the deployment changes the project's recorded phase or evidence, update only `docs/design/ROADMAP.md` through the repository's normal branch and PR workflow. Do not copy transient progress into `AGENTS.md` or this skill.
