---
name: news-digest
description: |
  自动新闻补充 — 当用户提及公司或代币时，自动判断是否需要补充最新新闻。
  不设独立命令，作为辅助 skill 自动触发。Triggers on any company ticker,
  token symbol, or when user asks "最新消息", "latest news", "新闻",
  "what's happening with", "[ticker/token] news", or "有什么新消息".
---

# News Digest

当用户提及特定公司或代币时，自动补充最新相关新闻。

## Trigger Logic

**自动触发条件**（满足任一即触发）：
- 用户明确询问某标的的最新消息
- 用户在分析过程中提到的标的有重大近期新闻（24h 内）
- 用户使用 token-analysis 或 earnings-analysis 等 skill 时，补充新闻上下文

**不触发条件**：
- 用户只是在讨论历史数据，不需要新闻
- 已经在 morning-note 中覆盖了该标的的新闻
- 标的没有任何近期新闻

## 插件行情与价差核验

使用 CoinGecko 和 Binance 插件；涉及当前加密价格时，先读取并执行[双源行情规则](../macro-dashboard/references/plugin-market-data.md)。默认价差 ≥1% 告警，用户可覆盖阈值；告警必须进入本次输出摘要。单源失败、计价或时间无法对齐时明确标记未核验。新闻/日历不含当前价格时，无需额外拉取行情。

## Data Source Priority

### Layer 1: MCP
- **CoinGecko 插件** — `get_crypto_news` 获取新闻线索，保留原始标题/时间/链接；不声称覆盖全部社区讨论
- **Binance 插件** — 仅在引用当前价格时进行现货价核对

### Layer 2: 免费 API 与官网数据
- **DefiLlama：免费 API + 内置浏览器** — 先读取并执行[免费数据规则](../macro-dashboard/references/defillama-free-api.md)；TVL、稳定币规模、DEX 交易量走无 Key 的公开 API，ETF/解锁/协议事件通过内置浏览器补充并核实日期。
- **CME FedWatch + Polymarket：内置浏览器双源** — 涉及美联储加息/降息/不变概率时，先读取并执行[利率预期双源规则](../macro-dashboard/references/fed-expectations-browser.md)；两站均尝试读取，按同次会议和结果口径并列展示。仅提及会议日期或普通新闻时不额外取概率。
- **Yahoo Finance：内置浏览器** — 引用 Yahoo 指数、传统市场行情或页面数据时，先执行[Yahoo 浏览器规则](../macro-dashboard/references/yahoo-browser.md)，保留代码、行情时间/时区、市场状态和实时/延迟标记；不以搜索摘要兜底行情数值。
- **CNN Fear & Greed：内置浏览器** — 引用美股恐惧贪婪指数时，先执行[CNN 浏览器规则](../macro-dashboard/references/cnn-browser.md)，读取主指数、页面标签和更新时间；不以搜索摘要兜底。

### Layer 3: Web Search
- 财经新闻网站（Reuters, Bloomberg, CNBC, CoinDesk, The Block）
- 公司 IR 页面（press releases）
- 项目官方公告（Twitter/X, Medium, Discord）

## Workflow

### Step 1: Identify Target
- 解析用户提到的公司/代币
- 确定标的类型（股票 vs 加密）

### Step 2: Fetch Recent News
按标的类型获取：

**股票:**
- 最近 7 天的重大新闻
- 财报/指引更新
- 分析师评级变化
- M&A/监管动态

**加密:**
- 最近 7 天的重大新闻
- 项目公告（升级、合作、代币经济学变化）
- 安全事件（黑客、漏洞）
- 监管动态

协议 TVL 异常按免费数据规则获取，原因通过内置浏览器核对原始公告。API/网页失败时写“未获取/未能核实”，不能据此声称“无重大新闻”。

### Step 3: Filter and Prioritize
- 按时效性排序（最新优先）
- 按影响程度筛选（仅保留重大新闻）
- 去重（同一事件多个来源只保留最权威的）

### Step 4: Present Digest

格式简洁，嵌入当前对话流中：

```
**[标的] 近期新闻速览:**
- [日期] [标题] — 一句话摘要 (Source: [来源])
- [日期] [标题] — 一句话摘要 (Source: [来源])
- [日期] [标题] — 一句话摘要 (Source: [来源])
```

如无重大新闻，简短说明：
> 近 7 天无重大新闻。

## Output Format

- 嵌入对话流，不单独生成文件
- 每条新闻一行，含日期、标题、一句话摘要、来源
- 最多 5 条，按重要性排序

## Quality Checklist

- [ ] 如引用 CNN 指数，已通过内置浏览器读取主指数、页面标签及时间；历史比较保留期间，变化用指数点，缺失项未补零
- [ ] 如引用 Yahoo 数据，已通过内置浏览器核对主标的和代码，注明行情时间/时区、市场状态及缺失项；历史变化注明起止日期，未将盘中值当收盘值
- [ ] DefiLlama 指标已按免费数据规则标明 API/网页来源、统计期、读取时间和缺失/过期状态；事件经网页核实，未把 TVL 变化当作净流入
- [ ] 如引用当前加密价格，已执行双源核验并显示价差告警或未核验原因
- [ ] 新闻来源可靠（主流财经/加密媒体）
- [ ] 新闻时效性标注（具体日期）
- [ ] 不重复已在其他 skill 输出中覆盖的新闻
- [ ] 每条新闻标注来源
- [ ] 无重大新闻时明确说明
- [ ] 不混淆同名不同标的的新闻
