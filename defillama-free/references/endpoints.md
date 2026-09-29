# 接口与能力边界

官方入口：[免费 API 文档](https://api-docs.defillama.com/llms-free.txt)。以下均为无需密钥的 HTTPS GET；实际数据分布在四个主机，不能把文档中的通用 base URL 套给所有分类。

| 命令 | 主机和路径 | 主要口径 |
|---|---|---|
| search | api.llama.fi/protocols | 名称、slug、ID、父级和链 |
| protocol / compare | api.llama.fi/protocol/{slug} | TVL 历史与协议元数据 |
| volume | api.llama.fi/summary/dexs/{slug} | 成交量；预测市场不等同于传统现货 DEX |
| fees / revenue / holders | api.llama.fi/summary/fees/{slug}?dataType=... | dailyFees / dailyRevenue / dailyHoldersRevenue |
| supply-side | 同上，dailySupplySideRevenue | 经验性接口，按协议验证，不保证所有协议支持 |
| market / chains | api.llama.fi/v2/chains、/v2/historicalChainTvl[/{chain}] | 存量，不代表净流入 |
| 聚合流量 | api.llama.fi/overview/dexs[/{chain}]、/overview/fees[/{chain}] | 链上应用统计与链 gas 不可混为一谈 |
| stablecoins | stablecoins.llama.fi/stablecoins?includePrices=true、/stablecoin/{id}、/stablecoincharts/all 或 /{chain} | 历史总额使用 totalCirculatingUSD；可加 stablecoin=ID |
| yields | yields.llama.fi/pools、/chart/{pool} | APY、基础与奖励 APY、TVL 和历史 |
| prices | coins.llama.fi/prices/current/{coins}、/prices/historical/{timestamp}/{coins} | 价格、来源时间和置信度；最多 20 个代币 |
| options | api.llama.fi/summary/options/{slug} | dailyPremiumVolume 与 dailyNotionalVolume 分开 |
| open-interest | api.llama.fi/overview/open-interest | 最新持仓存量，即使字段名包含 24h 也不当作流量 |

历史 dimension 请求显式设置 `excludeTotalDataChart=false&excludeTotalDataChartBreakdown=true`。端点访问成功不等于历史统计可比；时间映射另见 [time-semantics.md](time-semantics.md)。不支持的值、实体或 dataType 逐项返回缺失，不以其他指标填充。

请求限制：独立请求并发最多 3，最多 2 次尝试，只重试网络／429／5xx。Retry-After 超过 30 秒时报告限流。最多 5 次白名单 HTTPS 重定向，实际响应体上限 32 MiB。25 秒是 socket 阻塞操作超时；读取过程中在块边界检查 60 秒经过时间，不承诺 DNS 或整个命令有严格 25 秒墙钟上限。

缓存有效期 5 分钟，保留首次抓取时间；过期缓存不会掩盖新的请求失败。`--refresh` 跳过读取并更新缓存，`--no-cache` 不使用缓存，`--cache-dir` 显式指定目录。缓存写入失败不会丢弃成功响应。
