# CoinGecko + Binance 插件行情规则

适用于 macro-dashboard、morning-note，以及 news-digest / catalyst-calendar 引用的当前加密价格。仅在执行这些 skill 时核对并在当前报告中提示；不自动创建后台监控、不对外发送消息。

## 工具路由

先发现当前会话中 CoinGecko、Binance 插件的工具并读取实际参数。下面是 Codex 当前工具名；若宿主前缀变化，按插件来源与功能匹配，不猜造工具或将旧 crypto 插件的 execute 当成同一连接。

| 数据 | 工具与参数示例 |
| --- | --- |
| 当前 USD 价格、市值、24h 涨跌幅 | `mcp__codex_apps__coingecko_get_coin_markets({ids:["bitcoin","ethereum","tether"]})`；单次最多 20 个 ID，含换汇币 |
| 全球市值、BTC/ETH 占比 | `mcp__codex_apps__coingecko_get_global_market({})` |
| 身份确认 | `mcp__codex_apps__coingecko_search_coins({query:"..."})`、`mcp__codex_apps__coingecko_get_coin_info({id:"..."})` |
| 新闻线索 | `mcp__codex_apps__coingecko_get_crypto_news({coinId:"bitcoin",limit:5})`；保留原始标题、时间和链接 |
| 历史价格 | `mcp__codex_apps__coingecko_get_coin_market_chart({id:"bitcoin",days:"7"})`；不可用无时间索引的 sparkline 推断精确区间涨跌幅 |
| Binance 现货价格 | `mcp__codex_apps__binance_get_spot_symbol_price_ticker({symbol:"BTCUSDT"})`；取 `result.price`，不是期货、标记价格或 AI 分析文本 |
| Binance 交易对核实 | `mcp__codex_apps__binance_get_spot_exchange_information({symbol:"BTCUSDT"})`；核实 baseAsset / quoteAsset、现货支持和 TRADING 状态 |

CoinGecko 优先解析 structuredContent.coins；Binance 优先解析 structuredContent.result；宿主仅给文本时解析其 JSON，并先检查 isError / error。空值、非有限数或价格 ≤0 均无效。

行情必须尝试两个插件，不能在第一个成功后停止。可并行读取以减小采集时间差。Binance 优先指定单个 symbol；批量 symbols 若返回 `Duplicate values for parameter 'symbols'`，改为逐币查询一次，不重复发送同一失败参数。不省略 symbol 拉取全部市场。

不自动回退旧 npx MCP、直接 REST、浏览器或搜索新闻来补当前加密价格。缺少插件、认证失败或限流时保留有效单源值并明确提示“未完成双源核验”；两源都失败则当前价格留空。遵守 Retry-After，瞬时错误最多重试一次；Session terminated 提示重连，不能写成额度耗尽。不读取、备份或索取 API Key；如插件要求认证，由用户在插件设置中完成。

## 同一资产、计价与时间

1. 已知映射：bitcoin ↔ BTCUSDT，ethereum ↔ ETHUSDT。其他资产先确认 CoinGecko ID、项目/链/合约（适用时），再用 Binance 交易对元数据核实；同名代币、包装币、杠杆代币不能直接当成原币。Binance 未上市、停牌或身份不明时标记“不可比较”，不可换用永续合约凑齐第二源。
2. 统一为 USD：CoinGecko 返回 USD；Binance 的 USDT 报价乘以同批 CoinGecko `tether.currentPrice`（USD/USDT）。明确记录该汇率来自 CoinGecko，因此换汇部分不是独立第三源。不能默认 USDT=USD；汇率缺失或无效则展示原币报价，价差留空并提示“计价未统一”。比较 USDT 本身时不可用同一个 USDT/USD 值构造第二源造成循环核验；缺少独立报价则不可比较。其他 quoteAsset 需取得明确方向的有效换汇数据，否则不可比较。
3. 每个源分别记录采集时间及源更新时间（若返回），不要把采集时间冒充源更新时间。请求完成时间差 >120 秒，或已知源数据距采集时间 >300 秒，视为不同步/过期；刷新相关数据一次，仍不满足则不作有效价差判断。未知源更新时间必须标注“源时间未知，以下仅为采集快照比较”；可以计算快照价差，但不能声称实时同步核验通过。
4. 本规则的 120/300 秒和下述 1% 是可由用户覆盖的工作默认值，不是交易所保证或投资标准。24h、隔夜、7d 等变化必须标明实际统计区间，24h 涨跌幅不冒充隔夜涨跌幅。

## 价差计算与告警

设 C 为 CoinGecko USD 价格，B 为 Binance 折算 USD 价格：

`价差百分比 = abs(B - C) / C * 100`

- 默认阈值 `1%`，用户指定时使用用户阈值并写入报告；以未四舍五入值判断 `价差百分比 >= 阈值`。
- 首次超阈值即保留“⚠️ 价格差异告警”，两源及换汇值同批复查至多一次。复查仍超阈值：标注持续；复查低于阈值：标注已回落并保留首次数值/时间；复查失败：标注未确认，不抹掉首次告警。不得因为没有源时间戳而静默丢弃超阈值快照，需同时提示时效不确定。
- 在报告摘要及对应价格旁显示：资产、两源原始报价和币种、汇率、Binance 折算 USD、价差、阈值、两源采集/更新时间及复查状态。不可用平均价格掩盖差异，不能直接断定任一源错误或存在可执行套利机会。
- 未触发阈值时显示价差；源时间未知则写“快照价差未超阈值（时效未核实）”。缺源、缺汇率、错资产、已知过期或不同步时写“⚠️ 未完成双源核验：原因”，价差为 N/A，不写成 0% 或通过。
- 市值/供给量等 CoinGecko 汇总指标保留原源；Binance 单一交易所成交量不与全市场成交量作同口径校验。

建议输出：

| 资产 | CoinGecko USD | Binance 原始价/币种 | 换汇率 | Binance 折 USD | 价差 | 状态 |
| --- | --- | --- | --- | --- | --- | --- |

价格行附来源和时间；有异常时先展示告警再给分析。新闻/事件仍需通过原文、官方公告核实；插件未覆盖的解锁/快照/升级日历不能编造。
