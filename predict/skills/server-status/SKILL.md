---
name: server-status
description: Use when checking production server health, diagnosing performance issues, or user says "查看服务器状态", "服务器状况", "server status". SSH to EC2 and output a comprehensive report file.
---

# Server Status Check

SSH 到生产服务器执行全面状态检查，输出报告文件。

## Execution

### Step 1: Get timestamp

```bash
date "+%Y%m%d" && date "+%H%M%S"
```

### Step 2: Run comprehensive check

通过单次 SSH 执行所有检查（减少连接开销）：

```bash
ssh -i ~/.ssh/predict_market.pem ubuntu@100.85.109.119 '
echo "===UPTIME===" ; uptime ;
echo "===MEMORY===" ; free -m ;
echo "===DISK===" ; df -h / | tail -1 ;
echo "===CONTAINERS===" ; docker ps -a --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" ;
echo "===DOCKER_STATS===" ; docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}" ;
echo "===HEALTH===" ; curl -s http://127.0.0.1:8000/health | python3 -m json.tool ;
echo "===TCP===" ; ss -s ;
echo "===TOP_CPU===" ; top -bn1 -o %CPU | head -15 ;
echo "===ERRORS_1H===" ; docker logs predict_market-backend-1 --since 1h 2>&1 | grep -i error | tail -15 ;
echo "===WARNINGS_1H===" ; docker logs predict_market-backend-1 --since 1h 2>&1 | grep -i warn | tail -15 ;
echo "===DB_CONNECTIONS===" ; docker exec predict_market-db-1 psql -U postgres -d predict -t -c "SELECT state, count(*) FROM pg_stat_activity GROUP BY state;" 2>/dev/null ;
echo "===DB_LONG_QUERIES===" ; docker exec predict_market-db-1 psql -U postgres -d predict -t -c "SELECT pid, now()-xact_start AS duration, left(query,80) FROM pg_stat_activity WHERE state!='"'"'idle'"'"' AND xact_start IS NOT NULL ORDER BY xact_start LIMIT 5;" 2>/dev/null ;
echo "===DB_TABLE_SIZES===" ; docker exec predict_market-db-1 psql -U postgres -d predict -t -c "SELECT pg_size_pretty(pg_database_size(current_database())) AS db_total;" 2>/dev/null ; docker exec predict_market-db-1 psql -U postgres -d predict -t -c "SELECT t.tablename, pg_size_pretty(pg_total_relation_size(format('"'"'public.%I'"'"', t.tablename))) AS total, pg_total_relation_size(format('"'"'public.%I'"'"', t.tablename)) AS bytes, c.reltuples::bigint AS est_rows FROM pg_tables t JOIN pg_class c ON c.relname = t.tablename WHERE t.schemaname = '"'"'public'"'"' ORDER BY bytes DESC LIMIT 8;" 2>/dev/null ;
echo "===MEMORY_DEBUG===" ; curl -s http://127.0.0.1:8000/debug/executors | python3 -m json.tool 2>/dev/null ;
echo "===MAKER_TASKS_BY_PLATFORM===" ; docker exec predict_market-db-1 psql -U postgres -d predict -t -c "SELECT platform, status, wallet_id, COUNT(*) FROM maker_tasks WHERE status IN ('"'"'running'"'"','"'"'paused'"'"','"'"'error'"'"','"'"'pending'"'"','"'"'starting'"'"','"'"'awaiting_first_buy'"'"') GROUP BY platform, status, wallet_id ORDER BY platform, wallet_id, status;" 2>/dev/null ;
echo "===WORKER_CONTAINERS===" ; for c in $(docker ps --format "{{.Names}}" | grep "worker-wallet"); do echo "--- $c ---" ; docker logs "$c" --since 5m 2>&1 | tail -5 ; echo "errors (1h):" ; docker logs "$c" --since 1h 2>&1 | grep -iE "error|exception" | grep -v "INFO:" | tail -5 ; echo "warnings (1h):" ; docker logs "$c" --since 1h 2>&1 | grep -iE "warn" | grep -v "INFO:" | sort -u | tail -5 ; done ;
echo "===RESTART_COUNTS===" ; docker inspect --format="{{.Name}} restarts={{.RestartCount}}" $(docker ps -q) 2>/dev/null ;
echo "===HEALTH_MONITOR===" ; tail -10 /var/log/health-monitor.log 2>/dev/null || echo "(log file not found)"
'
```

### Step 3: Analyze and write report

将结果解析为结构化报告，保存到：
```
server-reports/YYYYMMDD/HHmmss-server-status.md
```

报告格式：

```markdown
# Server Status Report — YYYY-MM-DD HH:MM:SS

## Summary
| 指标 | 值 | 状态 |
|------|-----|------|
| 系统负载 | x.xx | OK/WARN/CRIT |
| 系统内存 | xxx MB / 1907 MB (xx%) | OK/WARN/CRIT |
| Swap | xx% (xxx MB / xxxx MB) | OK/WARN/CRIT |
| 磁盘 | xx% | OK/WARN/CRIT |

## Containers
| 容器 | 状态 | CPU | 内存 | 重启次数 |
|------|------|-----|------|----------|

## Application Health
- Health endpoint: ok/error
- RSS: xxx MB / 512 MB (xx%)
- DB connections: x
- Dead tuple ratio: x.x%

## Database
- 连接分布: idle x, active x, idle-in-transaction x
- 长事务: (列出或"无")

## DB Storage
| 表 | 大小 | 行数 |
|---|---|---|
| tokens | xxx MB | xxx |
| markets | xxx MB | xxx |
| maker_logs | xx MB | xxx |
| maker_orders | xx MB | xxx |
| **DB 总计** | **xxx MB** | |

## Network
- TCP established: x
- TIME-WAIT: x

## Memory Debug
- GC objects: xxx (delta: +/- xxx)
- GC top growing types: (列出 gc_delta 中正增长最大的 3-5 个)
- asyncio tasks: x
- DB pool: size=x, checkedin=x, checkedout=x, overflow=x
- Open FDs: x
- Active executors: x (backend)

## Maker Task 分布
| Wallet | 平台 | DB 活跃数 | 运行容器 | 备注 |
|---|---|---|---|---|
| wallet_1 | opinion | x | backend | running/awaiting 分布 |
| wallet_2 | polymarket | x | backend |  |
| wallet_3 | predict.fun | x | backend |  |
| wallet_4 | polymarket | x | worker-wallet-1 | 通过 WireGuard |
| wallet_N | ... | x | worker-wallet-M | 通过 WireGuard |

**一致性检查**：backend `Active executors` + 各 worker 运行任务数 = DB 活跃任务总数

## Worker 容器状态
| 容器 | 最近 5min 活动 | 1h errors | 1h warnings | 异常信号 |
|---|---|---|---|---|
| worker-wallet-1 | 有/无下单 | x | x | (如持续 empty snapshot) |
| worker-wallet-2 | ... | | | |

## Errors & Warnings (past 1h)
(列出或"无异常")

## Health Monitor
(最近告警记录)

## Assessment
综合评估和建议（仅在发现问题时给出建议）
```

### Severity thresholds

| 指标 | OK | WARN | CRIT |
|------|-----|------|------|
| 系统负载 | < 1.5 | 1.5-3.0 | > 3.0 |
| 系统内存 used% | < 70% | 70-85% | > 85% |
| Swap | < 25% | 25-50% | > 50% |
| 磁盘 | < 70% | 70-85% | > 85% |
| Backend 内存 | < 70% limit | 70-85% limit | > 85% limit |
| DB 内存 | < 70% limit | 70-85% limit | > 85% limit |
| Backend CPU | < 30% | 30-60% | > 60% |
| idle-in-transaction | 0 | 1-2 | > 2 |
| 容器重启 | 0 | 1-3 | > 3 |
| DB 总大小 | < 1.5 GB | 1.5-3 GB | > 3 GB |
