---
name: deploy-v2
description: Deploy and maintain the predict-v2 repository on its dedicated AWS EC2 host. Use this skill whenever jdy asks how to deploy predict-v2, requests a predict-v2 production or preflight deployment, asks to update the EC2 checkout, configure the server's GitHub read access, verify the deployed version, or restart the predict-v2 control plane. Do not use the legacy deploy skill for predict-v2.
---

# predict-v2 deployment

Deploy `predict-v2` to its dedicated ARM64 EC2 host through the repository's current production runbook. Keep the default deployment money-safe: `preflight` environment, control plane plus the tailnet-only frontend, and worker hold enabled.

## 1. Resolve intent before acting

Classify the request before running remote commands:

- A question such as “服务器如何部署” asks for an explanation. Read the live documents and explain the process without modifying GitHub or the server.
- An instruction such as “开始部署” or “执行部署” authorizes the normal no-money deployment workflow described below.
- Enabling `worker-host`, setting `V2_WORKER_HOLD=0`, changing to `V2_ENVIRONMENT=production`, or performing a real trade requires separate, explicit approval from jdy. A general deployment instruction is not sufficient.
- If the requested target, commit, environment, or money boundary is ambiguous, stop and ask jdy to confirm it.

Never use `/Users/jdy/Documents/skills/predict/skills/deploy/SKILL.md` for this repository. That skill belongs to the legacy `predict_market` system and a different EC2 host.

## 2. Re-open the live sources of truth

Locate the checkout. Prefer the current Git root when it is `predict-v2`; otherwise use `/Users/jdy/Documents/predict-v2` if it exists.

Before every deployment, read these live files rather than relying on commands copied into this skill:

1. `AGENTS.md` — repository safety and Git rules.
2. `docs/design/ROADMAP.md` — current phase, blockers, and permitted next step.
3. `docs/operations/2026-07-14-single-host-production-compose-runbook.md` — authoritative EC2 and Compose procedure.
4. `deploy/docker-compose.prod.yml` — actual services, profiles, dependencies, ports, and defaults.

If these files disagree with this skill, stop and report the drift. The repository documents win; update this skill only after jdy approves the new deployment contract.

## 3. Non-negotiable safety boundary

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

## 4. Local release preflight

Run read-only checks first:

```bash
git status --short --branch
git branch --show-current
git fetch origin
git rev-parse HEAD
git rev-parse origin/main
```

Require all of the following before server deployment:

1. The local worktree is clean.
2. The target is an immutable full commit SHA.
3. The target commit is present on `origin/main`.
4. The GitHub checks required by the repository are green for that commit.
5. The ROADMAP permits the requested deployment stage.

Normal repository policy delivers changes through a reviewed GitHub PR. If local `main` is ahead of `origin/main`, do not silently push it. Stop and ask jdy whether to finish the normal PR flow or grant a specific direct-push exception.

Use `gh` to verify the commit and checks without exposing credentials. Do not report success based only on a local test run when the target is not yet on GitHub.

## 5. Verify server GitHub read access

The server should use a repository-scoped, read-only Deploy Key. Verify access without printing private key material:

```bash
ssh predict-v2 '
  set -eu
  cd "$HOME/predict-v2"
  git ls-remote origin HEAD >/dev/null
'
```

If access fails, stop before deployment. Recommend or configure a read-only Deploy Key only when jdy explicitly authorizes the GitHub-permission change. Do not copy a personal GitHub private key to EC2 and do not enable persistent SSH agent forwarding.

For this server, the repository-local SSH command should select its dedicated key:

```text
~/.ssh/predict-v2-github-deploy
```

The GitHub repository entry must show `read-only`. Do not enable “Allow write access”. One Deploy Key belongs to one repository.

## 6. Update the remote checkout safely

After deployment is authorized and the target commit is on `origin/main`:

```bash
ssh predict-v2 '
  set -euo pipefail
  cd "$HOME/predict-v2"
  test -z "$(git status --porcelain)"
  git fetch origin
  git checkout main
  git pull --ff-only origin main
  git rev-parse --verify HEAD
'
```

Require the resulting remote SHA to equal the approved target SHA. A dirty remote checkout, non-fast-forward update, detached target, or SHA mismatch is a blocker; do not reset or overwrite it automatically.

## 7. Check runtime-secret files without reading values

An EC2 reboot clears `/run`. Before Compose starts, confirm `/run` is still `tmpfs` and all files required by the live runbook exist, are non-empty, and have the expected owner/mode.

Do not display file contents. If any file is missing, rematerialize it from 1Password using the exact `send_secret` procedure in the live runbook. Treat any failed or empty pipe as a deployment failure.

The default control-plane deployment does not require materializing or mounting wallet credentials because `worker-host` remains off.

## 8. Deploy the no-money control plane and frontend

Use the remote Git commit as the immutable image tag and follow the live Compose dependency graph. Deploy `control-plane` first, then `frontend`:

```bash
ssh predict-v2 <<'REMOTE'
set -euo pipefail
cd "$HOME/predict-v2"

export V2_IMAGE_TAG="$(git rev-parse --verify HEAD)"
export V2_RUNTIME_SECRETS_DIR=/run/predict-v2/runtime-secrets
export V2_ENVIRONMENT=preflight
export V2_FRONTEND_BIND_IP="$(tailscale ip -4)"

docker compose -f deploy/docker-compose.prod.yml config --quiet
docker compose -f deploy/docker-compose.prod.yml \
  up -d --build --wait control-plane
docker compose -f deploy/docker-compose.prod.yml \
  up -d --build --wait frontend
REMOTE
```

Do not pass `--profile host`. Compose may run forward migration and database bootstrap through declared dependencies. Do not add a downgrade step.

Nginx resolves the `backend` upstream once at startup. Recreating `frontend` after the `control-plane` rebuild (the order above) refreshes that resolution; whenever `control-plane` is recreated without recreating `frontend`, run `docker compose -f deploy/docker-compose.prod.yml restart frontend` afterwards, per the runbook's Nginx note.

## 9. Verify deployment with evidence

Run bounded checks that do not expose runtime secrets:

```bash
ssh predict-v2 <<'REMOTE'
set -euo pipefail
cd "$HOME/predict-v2"

# Compose interpolates the whole file before any command, even read-only
# ones like `ps`, so the required variables must be exported here too.
export V2_IMAGE_TAG="$(git rev-parse --verify HEAD)"
export V2_RUNTIME_SECRETS_DIR=/run/predict-v2/runtime-secrets

docker compose -f deploy/docker-compose.prod.yml ps
curl --fail --silent http://127.0.0.1:8000/health

test -z "$(
  docker compose -f deploy/docker-compose.prod.yml \
    port postgres 5432 2>/dev/null || true
)"

if docker compose -f deploy/docker-compose.prod.yml \
  ps --status running --services | grep -qx worker-host; then
  echo "ERROR: worker-host is unexpectedly running"
  exit 1
fi

sudo ss -ltn "sport = :80"
ts_ip="$(tailscale ip -4)"
curl -s -o /dev/null -w 'frontend /: %{http_code}\n' "http://$ts_ip/"
curl -s -o /dev/null -w 'frontend /api/internal/x: %{http_code}\n' \
  "http://$ts_ip/api/internal/x"

git rev-parse --verify HEAD
REMOTE
```

For a worker-off preflight, HTTP 200 with JSON `status=degraded` can be expected because worker heartbeats are intentionally absent. Port 80 must appear bound only to the Tailscale IPv4 (never `0.0.0.0`), `/` must return 200, and `/api/internal/x` must return 403. A failed HTTP request, unhealthy container, database error, exposed PostgreSQL port, publicly bound frontend port, running worker, or SHA mismatch is a deployment failure.

Do not broadly dump logs into the conversation. If diagnosis requires logs, keep the time and line range bounded and prevent URLs, credentials, headers, or secret values from entering the transcript.

## 10. Failure and rollback handling

- Stop at the first failed gate and report the exact failed command and non-secret evidence.
- Do not improvise a destructive rollback, reset a dirty checkout, delete volumes, or reverse migrations.
- Preserve the PostgreSQL volume and the last known image tag.
- Before rollback, inspect whether the failed release applied a forward migration and whether the previous application image is schema-compatible.
- Present a rollback plan to jdy and obtain approval before changing the remote checkout or recreating services with an earlier image.

## 11. Report format

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
