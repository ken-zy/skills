# 研究与导出示例

在 skill 目录运行，其他目录则改用脚本绝对路径。先查看 `--help` 或 `capabilities`，两者不联网。

```bash
python3 scripts/defillama.py search polymarket
python3 scripts/defillama.py protocol polymarket-international --metrics tvl,volume,fees,revenue,supply-side --days 7,30,90
python3 scripts/defillama.py protocol polymarket-international --metrics volume --start 2026-08-01 --end 2026-08-31 --raw --output polymarket-august.json
python3 scripts/defillama.py compare aave-v3 compound-v3 --metrics tvl --days 30
python3 scripts/defillama.py market --days 7,30
python3 scripts/defillama.py chains Polygon --days 30
python3 scripts/defillama.py stablecoins 1 --chain Ethereum --days 30
python3 scripts/defillama.py yields --chain Ethereum --stablecoin --min-tvl 10000000 --limit 10
python3 scripts/defillama.py prices coingecko:ethereum coingecko:bitcoin
python3 scripts/defillama.py options derive --kind notional --days 30
python3 scripts/defillama.py open-interest
python3 scripts/defillama.py protocol polymarket-international --metrics tvl --days 30 --format csv --output tvl.csv
```

收益池历史：先查询列表，取返回的 pool UUID，再执行 `yields --pool UUID`。历史价格：向 `prices` 传 `--timestamp`，使用 Unix 秒而非毫秒。指定日期例子仅用于语法；研究时按用户要求选择已完成 UTC 日。

Polymarket 调研可从国际站资金规模、交易量、收费与收入、分配项目、历史变化入手。先读取方法再解释，特别区分锁定抵押品、未赎回余额与当期成交量。接口未提供的用户留存、分市场集中度、法律实体及团队信息须另找证据，不能由 TVL 推算。

对每个问题给出关键数值、范围、时间、来源与缺口；不要机械输出所有 API 字段。多协议比较应说明为何可比，并保留不可比项目及原因。
