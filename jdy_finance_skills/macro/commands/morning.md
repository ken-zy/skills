---
description: 每日晨会笔记 — 隔夜市场动态/关键事件/交易想法，覆盖传统金融和加密市场
argument-hint: "[focus: stocks|crypto|macro|all]"
allowed-tools: mcp__codex_apps__coingecko_*, mcp__codex_apps__binance_get_spot_*, mcp__cua_repl__*, WebSearch, WebFetch, Bash(python3:*)
---

# Morning Note

生成每日晨会笔记。

## Context

- User request: $ARGUMENTS
- Today's date: !`date "+%Y-%m-%d"`

## Data Source Priority

### Layer 1: CoinGecko + Binance 插件
- CoinGecko 插件获取加密行情、全市场指标或新闻线索；Binance 插件提供现货价格核对。
- 涉及当前价格时必须先读取 [双源行情规则](../skills/macro-dashboard/references/plugin-market-data.md)，默认价差 ≥1% 告警，缺源/不同步时明确标记。
- 新闻和日历没有引用当前价格时不额外查价；事件仍以原始公告为准。插件缺失时提示连接，不回退旧 MCP 或自行配置 API Key。

### Layer 2: 官网数据
- **FRED：内置浏览器** — 按 [FRED 浏览器规则](../skills/macro-dashboard/references/fred-browser.md)访问 `https://fred.stlouisfed.org/series/{series_id}` — 经济数据发布（利率变动、就业数据等）
- **DefiLlama：免费 API + 内置浏览器** — 先读取并执行[免费数据规则](../skills/macro-dashboard/references/defillama-free-api.md)；TVL、稳定币规模、DEX 交易量走无 Key 的公开 API，ETF/解锁/协议事件通过内置浏览器补充并核实日期。
- **CME FedWatch + Polymarket：内置浏览器双源** — 涉及美联储加息/降息/不变概率时，先读取并执行[利率预期双源规则](../skills/macro-dashboard/references/fed-expectations-browser.md)；两站均尝试读取，按同次会议和结果口径并列展示。仅提及会议日期或普通新闻时不额外取概率。
- **Yahoo Finance：内置浏览器** — 引用 Yahoo 指数、传统市场行情或页面数据时，先执行[Yahoo 浏览器规则](../skills/macro-dashboard/references/yahoo-browser.md)，保留代码、行情时间/时区、市场状态和实时/延迟标记；不以搜索摘要兜底行情数值。
- **CNN Fear & Greed：内置浏览器** — 引用美股恐惧贪婪指数时，先执行[CNN 浏览器规则](../skills/macro-dashboard/references/cnn-browser.md)，读取主指数、页面标签和更新时间；不以搜索摘要兜底。

### Layer 3: Web Search
- 财经新闻、期货/盘前数据、加密新闻

## Workflow

### Step 1: Scan Overnight Developments
- **传统市场**: 盈利发布/指引变更/M&A/分析师评级/宏观数据
- **加密市场**: BTC/ETH 价格变动/项目公告/DeFi 事件/监管动态
- **宏观环境**: 期货/盘前/美元/商品/国债收益率

### Step 2: Compile Morning Note
格式：2 分钟内可读完
- 头条（最重要的一件事）
- 隔夜动态（传统市场）
- 加密市场
- 今日关注（含时间）
- 交易想法（如有）

### Step 3: Quick Takes on Earnings
如有关注标的发布财报，提供快速反应表格和观点。

## Output

- **Primary**: `YYYYMMDD-morning-note.md` 或对话中直接显示
- 保持 1 页以内
- 有观点 — 只转述不给观点的晨报没有价值

## Quality Checklist

- [ ] 如引用 CNN 指数，已通过内置浏览器读取主指数、页面标签及时间；历史比较保留期间，变化用指数点，缺失项未补零
- [ ] 如引用 Yahoo 数据，已通过内置浏览器核对主标的和代码，注明行情时间/时区、市场状态及缺失项；历史变化注明起止日期，未将盘中值当收盘值
- [ ] DefiLlama 指标已按免费数据规则标明 API/网页来源、统计期、读取时间和缺失/过期状态；事件经网页核实，未把 TVL 变化当作净流入
- [ ] 最重要事件在头条
- [ ] 传统和加密市场都覆盖
- [ ] 事件有观点（不只转述）
- [ ] 今日关注含具体时间
- [ ] 交易想法含风险提示
- [ ] 数据来自实时源

## Skill Reference

This command invokes the **morning-note** skill. See `skills/morning-note/SKILL.md` for the complete morning note format and workflow.
