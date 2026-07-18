---
name: deploy
description: 部署到 AWS EC2 生产环境。用户说"部署"、"deploy"、"上线"、"发布到生产"时触发。
---

## 部署流程

执行 `./deploy/remote/remote-deploy.sh` 一键部署到生产服务器。

脚本会自动完成：
1. 检查本地工作区干净（无未提交变更）
2. `git push origin main`
3. 等待 GitHub CI 通过（轮询，超时 300s）
4. SSH 到 EC2 执行 `git pull` + `start-prod.sh`（含 alembic migration、镜像构建、服务重启）

## 部署前检查（Claude 执行）

在运行脚本前，依次确认：

1. **当前分支是 main**：`git branch --show-current` 必须是 `main`，否则提醒用户先合并
2. **有待部署的变更**：`ssh ... "cd predict_market && git fetch origin && git log --oneline HEAD..origin/main"` 对比线上与 GitHub，如果没有差异则无需部署
3. **检查是否有未执行的 migration**：`ls -t backend/alembic/versions/*.py | head -3` 查看最近的 migration 文件，与线上 `docker exec predict_market-backend-1 alembic current` 对比，提醒用户注意

## 执行

```bash
./deploy/remote/remote-deploy.sh
```

## 部署后验证

1. 检查容器状态：`ssh ... "docker ps --format 'table {{.Names}}\t{{.Status}}' | grep predict_market"`
2. 检查 backend 启动日志：`ssh ... "docker logs predict_market-backend-1 --since 1m 2>&1 | tail -10"`
3. 如有异常，立即报告并建议回滚方案

## 服务器信息

- SSH: `ssh -i ~/.ssh/predict_market.pem ubuntu@100.85.109.119`
- 项目目录: `~/predict_market`
- Compose: `docker-compose.yml` + `docker-compose.prod.yml`
