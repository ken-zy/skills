---
name: token-analysis
description: |
  Analyze cryptocurrency token fundamentals, tokenomics, market structure and
  research gaps. Use for token analysis, 代币分析, tokenomics, or coin fundamentals.
  Route contract-specific market evidence to crypto-project-research.
---

# Token Analysis

综合分析代币市场证据与项目基本面。链上市场采集使用 [crypto-project-research](../crypto-project-research/SKILL.md)；它的口径和缺口规则优先于旧式行情清单。

## Data Source Priority

### Market Evidence: Free REST
- GeckoTerminal 公共 API：按 chain + CA 确认身份、池、K线及成交样本，无需 Key。
- CoinGecko Demo：可选 coin 汇总、交易对和历史；仅用进程已有 Demo Key，不经 Pro MCP。按新 Skill 执行脚本，不把连接器安装状态等同于接口可用。
- 不自动回退其他行情来源；失败/限流/缺 Key 均记录。macro 当前价格仍遵循其 CoinGecko + Binance 插件专用规则。

### Layer 2: Chrome CDP
- 项目官网、文档与审计报告；URL 未知时先 Web Search 找一手 URL。

### Layer 3: Web Search
- 补充解锁、团队、监管事件和新闻；CDP 不可用时标注实际使用的搜索来源。

旧 crypto 插件的 SessionStart hook 仍可能读取/恢复/备份 Key。直接读取新 Skill 并运行脚本可不启用该插件；不要让旧 hook 的提示阻止无 Key 的 GT 查询。

## Workflow

1. **身份**：名称/符号用于发现，network + CA 才是 token 标的。不同链或同名币有歧义时确认候选；原生 coin 要明确 CG ID。没有合约的原生 coin 可用 Demo 命名接口查询，不能伪造 GT CA。
2. **市场证据**：有 CA 时运行新 Skill 的 quick/standard snapshot 与 analyze；可选 Demo enrichment 只有验证 coin-ID 映射后才合并。原生 coin 的独立 Demo query 保留 coin scope。
3. **项目材料**：查团队/产品、代币分配与机制、解锁、收入和审计一手材料。没有资料时列出待核实，不把 GT score 当审计，不从行情推出营收。
4. **报告**：在脚本证据报告上补充基本面。每个数据点标注 Source、采集时间、已知数据时间与统计范围；将披露、事实和推断分开。

## Output Structure

- **基础数据**：价格、提供商报告市值/FDV（可缺失）、分类型供给、排名与成交量（如有）。GT token 与 CG coin 汇总分开。
- **代币经济学**：供给单位/类型/范围、分配、发行销毁机制与解锁来源；不做价格乘供给估值或跨链供给差计算。
- **市场结构**：观测到的交易所/交易对、DEX 候选与参考池、覆盖限制和可选持仓字段。样本不产生全市场 DEX/CEX 份额。
- **价格与成交区间**：有效完整 K 线的实际时间范围、缺口、样本收益/高低点/回撤与成交统计。不强制固定 7/30/90 天、支撑阻力位或 BTC/ETH 相关性。
- **风险与缺口**：身份、审计具体来源/日期/结论、权限未知项、可执行深度未知项，以及与项目相关的事件。安全信号不等于无风险。

## Output Format

- **Primary**: `YYYYMMDD-token-{Symbol}.md`
- Footer: 来源链接、数据/采集时间、第三方数据限制。

## Quality Checklist

- [ ] 标的身份无同名/跨链混淆；原生 coin 与合约 token 分开。
- [ ] 每个指标保留单位、类型、币种、scope、时间和覆盖；缺失不写零。
- [ ] 市值/FDV 缺失和供给不可比时明确注明，不自行补算。
- [ ] 窗口、分页和样本限制可见；没有将成交差叫净资金流。
- [ ] 一手基本面材料与市场证据分别引用；风险与未核实项明确。
