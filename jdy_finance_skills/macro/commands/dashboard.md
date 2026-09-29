---
description: 宏观经济看板 — 利率/通胀/就业/市场情绪/加密宏观/经济日历
argument-hint: "[scope: rates|inflation|jobs|sentiment|crypto-macro|calendar|all]"
allowed-tools: mcp__codex_apps__coingecko_*, mcp__codex_apps__binance_get_spot_*, mcp__cua_repl__*, WebSearch, WebFetch
---

# Macro Dashboard

生成宏观经济全景看板。

## Context

- User request: $ARGUMENTS
- Today's date: !`date "+%Y-%m-%d"`

## Data Source Priority

### Layer 1: CoinGecko + Binance 插件
- CoinGecko 插件获取加密行情、全市场指标或新闻线索；Binance 插件提供现货价格核对。
- 涉及当前价格时必须先读取 [双源行情规则](../skills/macro-dashboard/references/plugin-market-data.md)，默认价差 ≥1% 告警，缺源/不同步时明确标记。
- 新闻和日历没有引用当前价格时不额外查价；事件仍以原始公告为准。插件缺失时提示连接，不回退旧 MCP 或自行配置 API Key。

### Layer 2: 官网数据
- **FRED：内置浏览器** — 按 [FRED 浏览器规则](../skills/macro-dashboard/references/fred-browser.md)访问 `https://fred.stlouisfed.org/series/{series_id}` — 利率/国债/CPI/PCE/就业/GDP/美元指数
- **DefiLlama：Chrome CDP** — `defillama.com` — 稳定币总市值/全球加密 TVL/DeFi 总量

### Layer 3: Web Search
- 经济数据日历、FOMC 声明、VIX、恐惧贪婪指数
- ⚠️ **禁止用 Web Search 获取加密价格**（返回新闻报道，滞后 1-2 天）

Always annotate: "Source: [source name]" on each data point.

## Workflow

### Step 1: Determine Scope
默认生成完整看板。可选聚焦范围：rates/inflation/jobs/sentiment/crypto-macro/calendar

### Step 2: Fetch Data
按 scope 获取对应数据：
- **利率**: 联邦基金利率/10Y国债/2Y国债/2-10Y利差/降息预期
- **通胀**: CPI YoY/MoM/Core CPI/PCE/12个月趋势
- **就业**: 非农/失业率/初请失业金/劳动参与率
- **情绪**: VIX/恐惧贪婪指数/DXY/主要股指
- **加密宏观**: BTC/ETH/加密总市值/稳定币总市值/DeFi TVL
- **日历**: 未来2周经济数据发布日期

### Step 3: Compile Dashboard
按输出结构整理，含当前值、前值、变化趋势。

## Output

- **Primary**: `YYYYMMDD-macro-dashboard.md`
- Footer: 数据来源、FRED 系列 ID、数据时间戳

## Quality Checklist

- [ ] FRED 数据系列 ID 正确
- [ ] 当前值和前值都已获取
- [ ] 当前价格已尝试两个插件，附价差、时间、告警/未核验状态
- [ ] 日历覆盖未来 2 周重要事件
- [ ] 降息预期来自实时数据（非猜测）
- [ ] 数据时效性标注

## Skill Reference

This command invokes the **macro-dashboard** skill. See `skills/macro-dashboard/SKILL.md` for the complete dashboard structure and FRED series IDs.
