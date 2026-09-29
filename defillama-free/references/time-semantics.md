# 时间语义证据与覆盖

实现日期：2026-09-30。`daily` 字段名、连续日期和午夜时间戳均不能单独证明 UTC 自然日统计。运行时只访问四个免费 API 主机，不读取 GitHub；下面的映射随代码审查发布。

## 已确认映射

仅 `polymarket-international`（协议 ID `711`）的 `volume`：`utc_calendar_day`、`interval_start`。适用 `/summary/dexs/polymarket-international` 的 `totalDataChart`，不适用 `total24h/7d/30d`，不自动扩展到父项目、其他预测市场、链或市场聚合。

证据：

- [固定版本的 Polymarket DEX adapter](https://github.com/DefiLlama/dimension-adapters/blob/5cbd343e7b562fdc40a6c013ff4814f3b8dc02ca/dexs/polymarket/index.ts)：声明 `version: 1`，所有交易分支明确使用 `startTimestamp <= event_time < endTimestamp`。adapter 将双边成交事件除以二，形成其定义的单边 USD 交易量。
- [官方 adapter 时间语义说明](https://docs.llama.fi/list-your-project/other-dashboards)：version 1 使用 UTC 自然日，version 2 支持指定时间区间。此说明是可变官方文档；映射冻结日期如上，adapter 链接绑定不可变修订。
- API 返回身份须与精确目录 slug、ID 和父协议匹配。只有这一身份满足映射；名称相似不够。

## 保留为 unknown 的流量

[相同修订的 Polymarket 费用 adapter](https://github.com/DefiLlama/dimension-adapters/blob/5cbd343e7b562fdc40a6c013ff4814f3b8dc02ca/fees/polymarket.ts) 是 `version: 2` 且 `pullHourly: true`。它计算费用、扣除分成后的收入和供应方收入，但此版本的 skill 未独立证实 API 对小时区间的完整自然日聚合约定。因此费用、收入、供应方收入和持有人收入的历史仍标记 `unknown`，不得只凭午夜日期计算自然日增长、费用率或收入分解。源观察值和源提供的滚动汇总仍可展示，并明确区间未知。

其他协议、全市场/链聚合和期权流量默认 `unknown`。这说明统计可比性尚未证实，不表示接口不可用或数据一定错误。后续扩展必须记录实体、指标、版本、适用范围和不可变 adapter/聚合证据，并补充测试。

TVL、稳定币美元估值、价格、OI 是存量；APY 是率。时间戳代表源观察时间，未知时保持空值，不能以抓取时间替代。稳定币图的 `totalCirculatingUSD` 已含美元估值；不能将 `totalCirculating` 的不同锚定币数量按 1:1 相加。

## 质量标记

保留源 `latestFetchIsOk`、`disabled`、methodology 信息。源健康差异不自动抹除独立有效历史，但也不代表其完整。日期覆盖和上游采集健康应分别展示。实证支持的 `dailySupplySideRevenue` 并非官方免费枚举对所有项目的统一承诺；它也不等于企业营销费用、净利润或所有激励成本。
