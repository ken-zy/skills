# 免费 API 能力目录

维护核对日期：2026-09-30。此表是本版本包装范围，不宣称覆盖提供商全部免费接口。运行 `python3 scripts/fetch.py capabilities` 查看当前脚本白名单；接口权限/配额变化以官方文档和实际响应为准。

- [GeckoTerminal 公共 API](https://www.geckoterminal.com/dex-api) / [官方指南](https://apiguide.geckoterminal.com/)：固定根 `https://api.geckoterminal.com/api/v2`，无需 Key。
- [CoinGecko Demo 接口目录](https://docs.coingecko.com/demo/reference/endpoint-overview)：固定根 `https://api.coingecko.com/api/v3`，仅请求头 `x-cg-demo-api-key`，来源为进程环境变量 `COINGECKO_DEMO_API_KEY`。

## 调用约定

```bash
python3 scripts/fetch.py query --provider geckoterminal --endpoint token --param network=bsc --param address=0xbeea1d618e533a387d941f58a7d4c9b7bd377777 --out /tmp/token-evidence.json
python3 scripts/fetch.py query --provider coingecko-demo --endpoint market_chart --param id=bitcoin --param vs_currency=usd --param days=30 --out /tmp/bitcoin-history.json
```

所有路径与查询参数均用重复 `--param key=value` 输入。下表“必需”含路径参数；未列出的参数拒绝。默认值未注明时采用提供商默认，不意味着返回全部数据。逗号列表是一个参数值。

通用边界：page 为 1..10；查询文本 1..100 字符；标识符只接受字母/数字/下划线/连字符，最长128；保留地址大小写。布尔参数用 `true`/`false`。任意 URL、主机覆盖、Key 查询参数、未知参数和控制字符均拒绝。JSON 内容中提供商给出的 URL 不会被脚本继续访问。

## GeckoTerminal

`include`：除 token 外仅 `base_token,quote_token,dex` 的子集；token 仅 `top_pools`。

| endpoint | 必需参数 | 可选参数 / 约束 | 证据范围 |
|---|---|---|---|
| `networks` | — | page | 网络 ID 发现，分页 |
| `dexes` | network | page | 单网络 DEX 列表 |
| `search_pools` | query | network, include, page | 候选发现，不自动确认身份 |
| `token` | network, address | include | 指定链合约快照 |
| `token_info` | network, address | — | 元数据；持仓/安全字段为可选信号 |
| `token_pools` | network, address | include, page, sort | 有限池列表；sort 见下文 |
| `pool` | network, pool | include | 单池快照，可能是 V4 pool ID |
| `pool_ohlcv` | network, pool, timeframe | aggregate, before_timestamp, limit, currency, token, include_empty_intervals | 单池限定窗口，不是所有池合并历史 |
| `pool_trades` | network, pool | token, trade_volume_in_usd_greater_than | 最近有限成交样本 |
| `trending_pools` | network | include, page, duration | 单网络榜单；热度不等于质量 |
| `new_pools` | network | include, page | 新池发现；创建时间不等于项目发行时间 |

- token_pools sort：`h24_volume_usd_desc`、`h24_tx_count_desc`、`h24_volume_usd_liquidity_desc`。
- timeframe/aggregate：minute 配 1/5/15，hour 配 1/4/12，day 配 1；默认 aggregate=1。limit 1..1000。
- before_timestamp：秒级 Unix 时间，2009-01-01 到执行时刻后24小时以内。currency 为 `usd` 或 `token`。token 为 `base`、`quote` 或目标 CA；返回数据仍须验证目标视角。include_empty_intervals 为布尔。
- trade_volume_in_usd_greater_than：有限非负值，最大 10^15。**不接受** Pro-only `trading_period`、`cursor`、`per_page`，即使它们出现在公共 Swagger 中。不得把免费结果称为完整一天流水。
- duration：`5m`、`1h`、`6h`、`24h`。

## CoinGecko Demo

| endpoint | 必需参数 | 可选参数 / 约束 | 证据范围 |
|---|---|---|---|
| `search` | query | — | coin-ID 候选 |
| `coin` | id | localization, tickers, market_data, community_data, developer_data, sparkline（均布尔） | coin 汇总；部分字段可缺失 |
| `markets` | vs_currency | ids, category, order, per_page, page, sparkline, price_change_percentage | 分页 coin 市场快照 |
| `tickers` | id | page, order, depth（布尔） | CEX/DEX 交易对样本，非全市场份额 |
| `market_chart` | id, vs_currency, days | — | days 整数 1..365；提供商决定采样间隔 |
| `global` | — | — | 全球市场汇总 |
| `categories` | — | order | 分类汇总，成员/范围可变化 |
| `trending` | — | — | 搜索热度等提供商榜单 |

- markets：ids 最多50个；per_page 1..250；order 为 `market_cap_asc/desc`、`volume_asc/desc`、`id_asc/desc`；price_change_percentage 为 `1h,24h,7d,14d,30d,200d,1y` 的子集。
- tickers order：`trust_score_desc`、`trust_score_asc`、`volume_desc`、`volume_asc`。
- categories order：`market_cap_desc`、`market_cap_asc`、`name_desc`、`name_asc`、`market_cap_change_24h_desc`、`market_cap_change_24h_asc`。
- 提供商返回的历史变化百分比与自行根据 K 线计算的区间收益来源不同，不能静默互换。

## 预算、缓存和失败

默认本地预算 GT 5 次/分、Demo 30 次/分，都是保守客户端上限，不是官方承诺。标准运行最多180秒、12次网络尝试，单请求最多3次尝试/20秒，响应体上限8 MiB。仅暂时连接故障、429及5xx有限重试；不为400/401/403/404重试，不因429自动换提供商。

query/snapshot 共用 `--cache-dir DIR`、`--no-cache`、`--deadline SECONDS`（大于0且不超过180）、`--max-attempts N`（1..12）选项。默认缓存目录是用户目录下 `.cache/crypto-project-research`；同一提供商应使用同一目录协调预算，不更换目录绕过限流。snapshot 默认 quick，`--pool-pages 1|2` 默认1；standard 请求小时 aggregate=1、最多168根K线，以及参考池近期成交。返回根数不足/间断时按实际范围报告。

同一缓存目录中的进程共享限流锁与状态；禁用数据缓存不关闭限流。GT成功 JSON 才缓存（行情默认60秒，身份列表1小时）；缓存保留原采集时间。Demo认证响应不缓存。状态异常/锁或期限失败会停止网络请求。脚本不读取环境代理，不跟随重定向。

`missing_credential`、`rate_limited`、`timeout`、`budget_exhausted`、`http_error`、`invalid_response` 等状态是证据缺口，不应改写为零值或最新行情。可选数据失败产生部分报告；缺核心身份/token证据阻止该标的结论。

## 未包装或不能证明

- 官方有但本版本未包装：批量 token/pool、全网络热门/新池、其他 Demo onchain 路径、NFT/RWA/国库等。不能用手写任意 URL 绕过本脚本白名单；扩展应先核对免费权限与字段语义。
- 不提供：完整历史持仓/钱包实体标签、逐 tick 可执行深度、卖出仿真、审计结论、解锁日程、项目收入或自动跟踪。需要另行查证。
- GT 与 CG 共享数据体系，不构成独立双源。Demo mock 测试不验证用户真实 Key；一次 GT 成功不证明 Demo 认证可用。
