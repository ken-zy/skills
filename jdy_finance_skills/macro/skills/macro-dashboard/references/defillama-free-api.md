# DefiLlama：免费 API 取指标，内置浏览器补事件

适用于 macro-dashboard、morning-note、catalyst-calendar 和 news-digest。无需 Key 或 API 订阅，不安装官方付费 MCP。当前加密价格仍执行 [CoinGecko + Binance 双源规则](plugin-market-data.md)，本规则不提供价格替代源。

## 指标获取

使用相邻的 [Python 标准库脚本](../scripts/defillama_free.py)。将下方 `<skill-dir>` 替换为当前实际加载的 `macro-dashboard` skill 目录（安装缓存或仓库中的绝对路径），不要依赖用户当前目录。

```bash
python3 <skill-dir>/scripts/defillama_free.py dashboard
python3 <skill-dir>/scripts/defillama_free.py chains
python3 <skill-dir>/scripts/defillama_free.py search aave
python3 <skill-dir>/scripts/defillama_free.py protocol aave-v3
python3 <skill-dir>/scripts/defillama_free.py fees aave
python3 <skill-dir>/scripts/defillama_free.py revenue aave
```

`dashboard` 获取全市场 TVL、稳定币美元市值、DEX 交易量；其他命令按需执行。`search` 只列候选，不自动选择同名项目；区分 Aave 父协议和 Aave V3 等具体版本，输出实际名称与 slug。TVL、费用接口支持的实体可能不同，不将子协议 TVL 与父协议费用拼成同一口径，不把父子协议再次相加。

| 指标 | 实测免费地址 / 字段 |
|---|---|
| 全市场 TVL 历史 | `https://api.llama.fi/v2/historicalChainTvl`；`date`, `tvl` |
| 公链当前 TVL | `https://api.llama.fi/v2/chains`；`name`, `tvl` |
| 协议匹配 / 历史 | `https://api.llama.fi/protocols`；`/protocol/{slug}` 的 `tvl[].totalLiquidityUSD` |
| 稳定币美元市值历史 | `https://stablecoins.llama.fi/stablecoincharts/all`；各日 `totalCirculatingUSD` 各项之和 |
| DEX 交易量 | `https://api.llama.fi/overview/dexs?excludeTotalDataChart=false&excludeTotalDataChartBreakdown=true` |
| 协议费用 / 收入 | `https://api.llama.fi/summary/fees/{slug}?dataType=dailyFees` / `dailyRevenue` |

2026-09-30 实测：文档将稳定币地址统一写成 `api.llama.fi`，但该主机的 `/stablecoincharts/all` 返回 404；`stablecoins.llama.fi` 返回有效 JSON。按实测地址调用，不将所有数据组机械拼到同一主机。[官方免费接口目录](https://api-docs.defillama.com/llms-free.txt)

## 口径与时效

- TVL/市值是存量，不能跨日期相加。脚本按 UTC 日历日期计算 1d/7d/30d 变化 `(当前/前值-1)*100`，保留实际时间戳；基准日缺失或分母非正时返回 null，不向前填值或以零代替。
- 全市场 TVL 使用官方总体序列（默认排除流动性质押及重复计算）；不要对 `/protocols` 简单求和，该列表还包含 CEX 等类型。单协议按返回的 methodology 解释。美元 TVL 变化包含币价影响，不等于净流入。
- 稳定币只汇总 `totalCirculatingUSD`；`totalCirculating` 包含不同锚定币种，不能混合相加或全部按 1 美元估值。最新日缺少 USD 字段时标记缺失，不静默退到面值供应量。
- DEX/费用/收入的 `total24h`、`total7d`、`total30d` 保持上游含义；它们与 `totalDataChart` 最后一个日桶可能不同。脚本单独输出最后图表日值，不把图表日期冒充汇总字段的结束时间。汇总结束时间未知时明确标注；7d/30d 周期比较仅在前一个等长周期数据存在时计算。
- fees 是用户总支付，revenue 是协议保留部分，不混用；不默认年化短期峰值。输出的 `pct` 已是百分数，勿再乘 100。
- 每项保留 URL、读取时间 `fetched_at`、观测时间/统计期、单位与口径。`stale_over_48h=true` 是本流程的过期提示，不是官方更新承诺；未知观测时间不标为“实时”。晨报不能把日频数据写成精确隔夜变动。
- 若网页与 API 不同，保留两者日期/口径并说明待核实，不静默替换；币价 ≥1% 告警不套用于 TVL/市值等指标差异。

## ETF、解锁和事件补充

免费 API 不完整覆盖 ETF 资金流、未来解锁、升级/空投日期、融资和安全事件。用当前宿主的内置浏览器读取公开页面；在 Codex 使用 `mcp__cua_repl.js` 的 `iab`，按工具文档初始化。入口示例：

```javascript
const llamaTab = await cua.createBrowserTab("iab", "https://defillama.com/etfs", { visible: false });
```

- ETF：`https://defillama.com/etfs`。记录 Daily Stats 的交易日、资产（BTC/ETH）、净流入/流出、单位和页面标注的原始来源，区分 Flows 与 AUM。图表分组不代表 Daily Stats 的期间；不将周末无更新写成流入为零。
- 解锁：`https://defillama.com/unlocks`。可用页面的 `View unlocks calendar` 进入 `https://defillama.com/unlocks/calendar` 核对年月日；从列表进入目标详情，确认具体日期、时区、数量、占流通量比例与估计状态，再核对项目官方代币经济学/公告。只有倒计时而无确切日期时保持“预计”，不编造时区或精确时刻。
- 协议事件：从协议页面或 Web Search 找到项目官网/治理论坛/公告链接，然后在内置浏览器读取原文；搜索摘要只用于找线索。融资/黑客列表可作线索，不能仅凭 TVL 下跌断言发生黑客攻击。
- 记录文章发布时间与事件发生时间，去重后按具体 skill 输出：看板补资金流；晨报解释变化；日历仅收有日期证据的未来事件；新闻摘要保留原始公告链接。无法核实的条目明确标为未核实，不写“没有事件”。

内置浏览器不可用、页面付费或关键字段不可读时，说明缺失并继续其余指标，不调用隐藏付费接口、不自动切换外部 Chrome 或购买订阅。

## 限流与失败

脚本仅用 Python 3 标准库；请求超时 25 秒，网络错误/429/5xx 最多重试一次；遵守 Retry-After，等待超过 30 秒则停止该项。404、认证错误、非 JSON 或结构不匹配不盲目重试。无认证不代表无限额度。

临时目录缓存有效期 5 分钟，保留首次读取时间；`--refresh` 放在子命令前可重新读取。过期缓存不用于掩盖失败。逐项输出 `ok/unavailable`，部分失败仍保留成功项，退出码 1 表示有未获取项。Python/网络受限时直接标明阻塞；公开网页可以作为明确标注的补充，不声称 API 已通过。
