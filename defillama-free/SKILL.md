---
name: defillama-free
description: 使用 DefiLlama 免费 API 查询 DeFi 协议、TVL、费用收入、成交量、稳定币及收益池，并进行有来源和口径校验的历史比较。适用于链上基本面研究与数据导出。
---

# DefiLlama Free

通过本 skill 内的 Python 3.10+ 标准库脚本取数，无须 API Key、付费 MCP 或安装依赖。脚本路径相对于此 skill 目录；执行时使用实际路径。

```bash
python3 scripts/defillama.py search polymarket
python3 scripts/defillama.py protocol polymarket-international --metrics tvl,volume,fees,revenue,supply-side --days 7,30,90
python3 scripts/defillama.py capabilities
```

先用 `search` 确认实体，存在多个候选时按用户指定范围选择或澄清。父项目、国际站、美国站、协议版本不能相互替代。Polymarket 国际站使用 `polymarket-international`。

根据问题选择数据，而非每次获取所有指标：

- 协议基本面与同类比较：`protocol`、`compare`；解释费用口径或历史变化前读 [methodology.md](references/methodology.md)。
- 大盘、链及资金规模：`market`、`chains`、`stablecoins`。
- 收益池、价格、期权与持仓量：`yields`、`prices`、`options`、`open-interest`；接口范围与限制见 [endpoints.md](references/endpoints.md)。
- 调研示例和导出方式见 [workflows.md](references/workflows.md)。涉及自然日流量比较时，核对 [time-semantics.md](references/time-semantics.md) 中的已验证映射。

## 使用结果

JSON 是默认输出；`sources` 提供请求 URL、原始抓取时间、缓存状态与上游方法，结果引用 source ID。`--raw` 额外返回原始响应；大数据仅在核查需要时读取，避免将整个收益池列表放入上下文。`--format csv --output PATH` 可导出；覆盖已有文件须显式 `--overwrite`。

引用结论时给出对应 API 或官方方法链接，注明观察日期、统计区间和范围。报告缺失、失败或不可比，不把 null 变成零。退出码 0 为完整可用，1 为部分／不可用，2 为参数或输出错误；不要因为退出码 1 丢弃其他成功指标。

TVL、稳定币规模与 OI 是存量；成交量、费用与收入是流量。每天一个点不证明自然日口径。只有有证据的 UTC 区间才能进行严格自然日求和和增长比较；滚动或未知口径保留原值、派生结果为空。未映射协议的流量不可比是明确的能力边界，不允许由调用者凭字段名擅自补算。

费用不是协议收入，协议收入不是净利润；supply-side 是适配器定义的分配项目，不是统一的营销成本。`holders` 指持有人收入，不是持有人数量。OI 不求和为成交量。APY 不保证未来收益；TVL 上升本身不证明净流入。价格可能引用 CoinGecko，不能作为其独立交叉验证。

本 skill 不提供完整的用户留存、集中度、融资、解锁、ETF、审计安全或交易执行能力。需要其他证据时说明缺口，并按用户授权另行研究；不静默转向收费接口或浏览器。参考了 [DefiLlama 官方技能](https://github.com/DefiLlama/defillama-skills) 的研究工作流，其订阅 MCP 并非本 skill 的依赖。
