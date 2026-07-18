---
name: restart
description: One-click production backend restart with two-phase health verification. Invoke explicitly via /restart only.
disable-model-invocation: true
---

# Restart Backend

重启生产服务器的 Backend 容器，用于快速解除 OOM 风险等紧急情况。

## Execution

执行重启脚本：

```bash
ssh -i ~/.ssh/predict_market.pem ubuntu@100.85.109.119 'bash -s' < deploy/remote/restart-services.sh
```

## Output Handling

脚本输出包含重启前后状态对比，直接展示给用户。

根据退出码处理异常：

| 退出码 | 含义 | 建议 |
|--------|------|------|
| 0 | 重启成功 | 无需操作 |
| 1 | 应用健康检查超时 | 容器已启动但 /health 未就绪。检查 backend 日志: `ssh ... 'docker logs predict_market-backend-1 --tail 50'` |
| 2 | docker restart 失败 | Docker daemon 可能异常。SSH 手动检查: `ssh ... 'docker ps -a'` |
| 3 | 容器存活检查超时 | 容器启动后立即退出。检查日志: `ssh ... 'docker logs predict_market-backend-1 --tail 50'` |
