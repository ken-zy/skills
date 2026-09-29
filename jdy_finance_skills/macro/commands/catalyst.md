---
description: 催化剂日历 — 财报/经济数据/FOMC/代币解锁/空投快照/协议升级
argument-hint: "[tickers_or_tokens...] [horizon: 2w|month|quarter]"
allowed-tools: mcp__codex_apps__coingecko_*, mcp__codex_apps__binance_get_spot_*, mcp__cua_repl__*, WebSearch, WebFetch, Bash(python3:*)
---

# Catalyst Calendar

构建催化剂日历。

## Context

- User request: $ARGUMENTS
- Today's date: !`date "+%Y-%m-%d"`

## Data Source Priority

### Layer 1: CoinGecko + Binance 插件
- CoinGecko 插件获取加密行情、全市场指标或新闻线索；Binance 插件提供现货价格核对。
- 涉及当前价格时必须先读取 [双源行情规则](../skills/macro-dashboard/references/plugin-market-data.md)，默认价差 ≥1% 告警，缺源/不同步时明确标记。
- 新闻和日历没有引用当前价格时不额外查价；事件仍以原始公告为准。插件缺失时提示连接，不回退旧 MCP 或自行配置 API Key。

### Layer 2: 官网数据
- **FRED：内置浏览器** — 按 [FRED 浏览器规则](../skills/macro-dashboard/references/fred-browser.md)访问 `https://fred.stlouisfed.org/series/{series_id}` — 经济数据发布日期（CPI、非农、GDP）
- **DefiLlama：免费 API + 内置浏览器** — 先读取并执行[免费数据规则](../skills/macro-dashboard/references/defillama-free-api.md)；TVL、稳定币规模、DEX 交易量走无 Key 的公开 API，ETF/解锁/协议事件通过内置浏览器补充并核实日期。

### Layer 3: Web Search
- 财报日历、FOMC 日期、代币解锁日历、空投日期、加密会议

## Workflow

### Step 1: Define Scope
确认：关注标的、包含宏观事件？包含加密事件？时间范围（默认 2 周）

### Step 2: Gather Events
- **财报事件**: 季度财报日期、投资者日
- **企业事件**: 产品发布、监管决定、M&A
- **宏观事件**: FOMC、非农、CPI/PPI、GDP
- **加密事件**: 代币解锁、空投快照、TGE、协议升级、治理投票、加密会议

### Step 3: Build Calendar Table
按日期排序，标注类型和影响程度。

### Step 4: Weekly Preview
本周关键事件 + 下周预告 + 持仓影响。

## Output

- **Primary**: `YYYYMMDD-catalyst-calendar.md`
- 日历表格 + Weekly Preview

## Quality Checklist

- [ ] DefiLlama 指标已按免费数据规则标明 API/网页来源、统计期、读取时间和缺失/过期状态；事件经网页核实，未把 TVL 变化当作净流入
- [ ] 传统和加密事件都覆盖
- [ ] 财报日期经 IR 页面验证
- [ ] 代币解锁标注占流通量百分比
- [ ] FOMC 和重大经济数据不遗漏
- [ ] 影响程度合理评估
- [ ] 时区标注

## Skill Reference

This command invokes the **catalyst-calendar** skill. See `skills/catalyst-calendar/SKILL.md` for the complete calendar format and event categories.
