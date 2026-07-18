---
name: deploy-dev
description: Use when starting the local development environment, or user says "本地启动", "本地部署", "启动开发环境", "start local", "local dev". Also use when user wants to test changes locally before deploying to production.
---

## 本地开发环境启动

执行 `./deploy/local/start-dev.sh` 一键启动本地开发环境。

脚本会自动完成：
1. Docker 环境检查
2. 端口冲突检测与自动清理（5432、8000、3000）
3. Backend 镜像智能重建（检测 requirements.txt / Dockerfile 变更）
4. 启动 PostgreSQL + Backend（含 alembic migration 自动执行）
5. 后端健康检查 + 平台注册验证
6. 前端依赖检查 + Vite dev server 启动

## 启动前检查（Agent 执行）

在运行脚本前，依次确认：

1. **Docker 运行中**：`docker info > /dev/null 2>&1`，未运行则提醒用户启动 Docker Desktop
2. **检查是否有未执行的 migration**：`ls -t backend/alembic/versions/*.py | head -3` 查看最近的 migration 文件，提醒用户注意数据库变更
3. **前端依赖是否需要更新**：检查 `frontend-v2/package.json` 是否比 `node_modules` 更新

## 执行

```bash
./deploy/local/start-dev.sh
```

注意：脚本最后会启动 Vite dev server 并阻塞终端（前台运行），用 Ctrl+C 停止前端服务器。

## 启动后验证

1. 后端 API：`curl -s http://localhost:8000/health`
2. 前端页面：浏览器访问 `http://localhost:3000`
3. 如果浏览器显示旧样式，提醒用户 Cmd+Shift+R 硬刷新清除缓存

## 服务地址

| 服务 | 地址 |
|------|------|
| 前端 | http://localhost:3000 |
| 后端 API | http://localhost:8000 |
| API 文档 | http://localhost:8000/docs |

## 仅重启后端（不重启前端）

如果只需要重启后端（如代码变更、migration 更新）：

```bash
docker compose restart backend
docker compose logs backend --tail 20
```

## 相关

- `/deploy` — 部署到 EC2 生产环境
- `/server-status` — 查看生产服务器状态
