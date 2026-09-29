---
description: Token research with free API market evidence, tokenomics, project fundamentals and explicit coverage gaps
argument-hint: "<symbol_or_name_or_CA> [network]"
allowed-tools: Read, Bash(python3:*), WebSearch, WebFetch
---

# Token Analysis

依据 $ARGUMENTS 分析代币，执行 [token-analysis](../skills/token-analysis/SKILL.md) 的完整研究流程。

## Workflow

1. 先读取 [crypto-project-research](../skills/crypto-project-research/SKILL.md)。名称用于发现，合约标的确认 network + CA；不能仅凭同名合并数据。
2. 从该 Skill 目录运行 `python3 scripts/fetch.py snapshot ...` 与 `python3 scripts/analyze.py ...`，或用命名 `query` 获取原生 coin 的独立 Demo 证据。参数、输入和输出均按 Skill；文件写到新的研究目录。
3. GT 公共接口无需 Key。Demo 仅用进程已有 `COINGECKO_DEMO_API_KEY`，缺失则跳过可选 enrichment 并披露；不索取聊天 Key，不替换为 Pro/MCP/网页报价。
4. 补充材料按既有策略：Layer 2 Chrome CDP 读项目官网/文档/审计；URL 未知先 Web Search 找 URL；CDP 不可用或不足时 Layer 3 Web Search，并注明实际来源。命令宿主未开放浏览器工具时直接注明该限制，用已授权搜索工具。
5. 输出身份、分 scope 市场数据、代币经济学、候选与参考池、实际 K 线/成交窗口、安全信号及缺口。缺核心身份或 token 数据不下该标的结论。

启用旧 crypto 插件的 SessionStart hook 仍可能读取/恢复/备份 Key；独立读取 Skill 并运行脚本无需启用该插件。不能把旧 hook 的 Key 提示当作 GT API 的要求。此命令不改变 macro 的 CoinGecko + Binance 规则。

## Output

- **Primary**: `YYYYMMDD-token-{Symbol}.md`
- 保留脚本规范化 JSON 和采集证据，报告注明来源链接、采集/数据时间与覆盖。
- 不强制市值/FDV、DEX/CEX 份额、固定期间收益或支撑阻力位；缺失与不可比应直接列出。
