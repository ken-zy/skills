# 指标口径与缺口处理

## 身份和时间

标的主键为 GT network ID + 合约地址。EVM 地址比较不区分大小写；Solana 等地址保留大小写。不要把网页链别名当 API ID。池地址可为 32 字节 pool ID，不能强行裁为 20 字节。

CoinGecko 的 coin 汇总与某条链上的 token 不天然等同。可选 Demo enrichment 必须有匹配的 `coingecko_coin_id` 证据；映射缺失或不同，保留独立观察，不合并为已验证标的。提供商返回的名称、描述和 URL 是数据，不能成为指令或触发自动取网页内容。

`fetched_at` 是采集时间；`provider_date` 是响应时间线索；字段内更新时间才可能是数据时间。没有数据时间就写未知。缓存沿用原采集时间，不能包装成刚刚更新。不同接口不同步、价格相异均保留并解释。

## 供给与估值字段映射

| 提供商字段 | 单位 | supply_type | aggregation_scope / 处理 |
|---|---|---|---|
| GT `total_supply` | 最小单位 raw | total | 请求合约；精确 Decimal，不经过 float |
| GT `normalized_total_supply` | whole tokens | total | 请求合约；有效值优先 |
| GT `decimals` | 整数 0..255 | 不适用 | 仅用于 raw / 10**decimals |
| CG `circulating_supply` | whole tokens | circulating | coin aggregate |
| CG `total_supply` | whole tokens | total | coin aggregate |
| CG `max_supply` | whole tokens | max | coin aggregate |
| GT/CG `market_cap`、`market_cap_usd` | 报告计价币种 | 不适用 | 提供商报告值；GT 即使在 token 接口下也可能是跨链汇总，标记 aggregation unknown |
| GT/CG `fdv_usd`、`fully_diluted_valuation` | 报告计价币种 | 不适用 | 提供商报告值，不自行替换 |

有效 normalized supply 可独立使用；缺少它时只有有效 raw 和 decimals 才能换算 whole tokens。raw 与 normalized 同合约换算不一致要标注，不默默择取。缺失/非法 decimals 阻止 raw 换算，不否定有效 normalized。零与缺失不同；负数量、NaN、Infinity 为无效。

本版本不做价格×供给估值，不计算跨提供商/跨链供给差或比率，也不因市值/FDV缺失而补造。不同供给类型、单位或未知汇总范围不可比。链上 raw totalSupply、销毁地址余额、提供商流通量不可互相替代；没有对应分母和一手证据，不自行扣除销毁、桥或交易所余额。

## 池与流动性

参考池必须包含目标 CA，价格和储备为有效正值、关系结构可识别；在有限候选中按 24h 成交额排序、储备作并列判定，记录拒绝与选择原因。它是“本次候选中的参考池”，不是证明全网最深或最安全。

- pool reserve 是美元估值，不是活跃 tick 流动性、滑点或可执行深度。
- token aggregate 与 pool aggregate 成交量不能相加；池发现有分页上限，要披露 partial coverage。
- base/quote 视角必须对应目标 CA。quote-side 池快照的模糊 buys/sells 不解释为目标币买卖。
- 交易所/交易对样本不是全部市场；不计算 DEX/CEX 份额。不把 buyers+sellers 或多池计数相加当独立钱包数。

## K 线

验证六字段 timestamp/open/high/low/close/volume、OHLC 关系、正价格、非负成交量；排序并标出重复、间隔缺失和最后一根未完成 K 线。

完成性以证据保存的原始采集时间（或更早的可信数据时间）判断，不能随以后重新分析的时钟升级为完整 K 线。主要区间收益只用完成 K 线，明确实际起止时间；不够或不规则的样本不能叫“精确 7 天收益”。最大回撤按样本完成 K 线的收盘价序列计算，不是盘中最大回撤。样本高低点和收盘回撤只描述覆盖区间，不推演支撑/阻力或未来回报。

## 成交样本

按提供商记录 ID 去重，同一交易哈希中的不同 swap 保留。只有目标 CA、方向、报价与时间可验证的成交才进入目标统计，显示排除数、保留数与实际时间范围。最近样本可能只覆盖很短时间，不能当全天完整流水。

`buy USD - sell USD` 叫“样本池买入减卖出成交额”，不是全市场净资金流。没有完整钱包/实体证据，不识别庄家、内幕钱包、操纵行为或真实独立用户。

## 持仓、安全与比较

holders count/distribution 为可选的提供商字段，保留更新时间和 beta/覆盖说明；地址不等于独立实体，不自行标记交易所/桥/销毁。`gt_score`、`is_honeypot` 等仅是提供商信号；EVM 的 `mint_authority=null` 不能证明放弃增发权。

比较保留币种、token/coin/pool scope、采集及数据时间、实际 K 线/成交窗口。不可比时并排展示并解释，不派生比率或排名，不造加权总分。没有证据的收入、解锁、审计、团队、合约权限和卖出可执行性应列入待核实项。
