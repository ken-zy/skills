---
name: crypto-project-research
description: Research a token by chain and contract address using GeckoTerminal public and optional CoinGecko Demo APIs. Collect auditable snapshots, inspect DEX pools and bounded price/trade samples, or compare saved snapshots. Use for onchain token research and named free API queries; macro price verification retains its separate plugin workflow.
---

# Crypto Project Research

将“查这个 CA / 分析这个代币 / 比较两个项目”转为有来源、时间和覆盖边界的研究报告。只读行情，不交易、不连接钱包、不做后台监控。Python 3.10+，仅标准库。

## 入口与凭据

可直接读取本文件并运行旁边的脚本，无需启用插件或安装 MCP。`scripts/` 路径相对于本 Skill；从 Git 仓库根目录使用 `jdy_finance_skills/crypto/skills/crypto-project-research/scripts/`。

- GeckoTerminal 默认无 Key。CoinGecko Demo 仅在明确请求时使用进程已有的 `COINGECKO_DEMO_API_KEY`；缺少 Key 就记录缺口，继续 GT 研究。
- 不读取密钥文件、不让用户在聊天粘贴 Key、不修改全局配置。Demo Key 只发往固定 Demo 主机的请求头。失败不自动切到 Pro、MCP 或网页行情。
- **独立入口边界**：上述无密钥文件操作保证属于这些脚本。启用整个旧版 `crypto` 插件会先运行既有 SessionStart hook，可能读取、恢复或备份 Key；本 Skill 没有更改或隔离那个 hook。GT 请求本身不因旧 hook 的 Key 提示而要求 Key。

## 工作流

1. **确认身份**：以 `network + CA` 为标的。名称/符号只用于 `search_pools` 发现；有多个候选时列出链和 CA，不自动挑同名币。网络用 GT ID，未知时查 `networks`。保留非 EVM 地址大小写。CoinGecko ID 必须与 CA 映射相符才能合并统计。
2. **采集快照**：quick 获取 token、info、pools；standard 再取所选参考池的小时 K 线及近期成交样本。结果目录应为新的研究输出目录，不放在 Skill 中、不覆盖旧报告。

   ```bash
   python3 scripts/fetch.py snapshot --network bsc --address 0xbeea1d618e533a387d941f58a7d4c9b7bd377777 --mode standard --out-dir /tmp/token-research-run
   python3 scripts/analyze.py /tmp/token-research-run --out /tmp/token-research-report.md
   ```

   只有需要且身份已确认时才附加 `--coin-id ID`。脚本返回部分失败时检查 manifest 和报告缺口；不得把 HTTP 成功等同于研究完整。
3. **解释证据**：读 [methodology.md](references/methodology.md)，按实际池、样本时间、供给单位和覆盖范围解释。市场报告之外的团队、收入、解锁、审计等，需要另外查一手材料并单独注明来源。
4. **比较**：`python3 scripts/analyze.py --compare RUN_DIR_A RUN_DIR_B --out REPORT.md`。时间、币种、统计范围不一致时只并排展示，保留不可比提示。

需要单个接口而非快照时，先运行 `python3 scripts/fetch.py capabilities`，再读 [capabilities.md](references/capabilities.md) 的参数表。例如：

```bash
python3 scripts/fetch.py query --provider geckoterminal --endpoint search_pools --param query=PONS --out /tmp/pons-discovery.json
```

## 输出与解释边界

使用生成的规范化 JSON 和中文 Markdown 作为证据底稿，按 [report-format.md](references/report-format.md) 补充用户需要的项目分析。区分已核实、推断、未知；每项结论保留来源、采集时间和数据时间。缺少核心身份或 token 数据时停止该标的结论，只报告发现和缺口。

不把池储备当可成交深度，不把成交买卖差当净资金流，不从局部交易对推算全市场 DEX/CEX 份额，不把提供商安全信号当合约审计。CoinGecko 与 GeckoTerminal 属于同一数据体系，不能写成独立双源验证。供给不跨单位/类型/链混算；本版本不做价格乘供给估值，不强制补齐市值/FDV，也不编造固定期间收益或支撑阻力位。
