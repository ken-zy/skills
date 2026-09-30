---
description: 宏观经济看板 — 利率/通胀/就业/市场情绪/加密宏观/经济日历
argument-hint: "[scope: rates|inflation|jobs|sentiment|crypto-macro|calendar|all]"
allowed-tools: mcp__codex_apps__coingecko_*, mcp__codex_apps__binance_get_spot_*, mcp__cua_repl__*, WebSearch, WebFetch, Bash(python3:*)
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
- **项目官方 X 公告：内置浏览器** — 引用项目官方 X 公告时按[官方 X 核验规则](../skills/macro-dashboard/references/official-x-browser.md)执行：官网确认账号，读取原帖与官方原文，区分计划、自述与实施证据；时间/修订冲突及访问缺失明确说明。
- **Tokenomist + DefiLlama 解锁：内置浏览器双源** — 涉及代币解锁时先执行[解锁核验规则](../skills/macro-dashboard/references/token-unlocks-browser.md)，两站均尝试读取，按同一事件/窗口比较日期、数量、接收方和分母；差异回到项目原始资料核实并提示，付费或缺失项明确说明。
- **FRED：内置浏览器** — 按 [FRED 浏览器规则](../skills/macro-dashboard/references/fred-browser.md)访问 `https://fred.stlouisfed.org/series/{series_id}` — 利率/国债/CPI/PCE/就业/GDP/美元指数
- **DefiLlama：免费 API + 内置浏览器** — 先读取并执行[免费数据规则](../skills/macro-dashboard/references/defillama-free-api.md)；TVL、稳定币规模、DEX 交易量走无 Key 的公开 API，ETF/解锁/协议事件通过内置浏览器补充并核实日期。
- **美联储 FOMC：内置浏览器** — 会议日期、正式声明、纪要和 SEP 按[FOMC 官网规则](../skills/macro-dashboard/references/fomc-browser.md)读取，区分会议/发布日期、已公布政策、官员预测和市场概率。
- **CME FedWatch + Polymarket：内置浏览器双源** — 涉及美联储加息/降息/不变概率时，先读取并执行[利率预期双源规则](../skills/macro-dashboard/references/fed-expectations-browser.md)；两站均尝试读取，按同次会议和结果口径并列展示。仅提及会议日期或普通新闻时不额外取概率。
- **Yahoo Finance：内置浏览器** — 引用 Yahoo 指数、传统市场行情或页面数据时，先执行[Yahoo 浏览器规则](../skills/macro-dashboard/references/yahoo-browser.md)，保留代码、行情时间/时区、市场状态和实时/延迟标记；不以搜索摘要兜底行情数值。
- **公司 IR / 正式披露：内置浏览器** — 涉及公司事件或业绩时按[IR 核验规则](../skills/macro-dashboard/references/company-ir-browser.md)执行：第三方日历找线索、IR 确认时间、正式披露核对内容；区分预计/确认状态及财报/电话会时间。
- **CNN Fear & Greed：内置浏览器** — 引用美股恐惧贪婪指数时，先执行[CNN 浏览器规则](../skills/macro-dashboard/references/cnn-browser.md)，读取主指数、页面标签和更新时间；不以搜索摘要兜底。

### Layer 3: Web Search
- 其他经济数据日历；FOMC、CNN 和 VIX 分别按各自内置浏览器规则读取
- ⚠️ **禁止用 Web Search 获取加密价格**（返回新闻报道，滞后 1-2 天）

Always annotate: "Source: [source name]" on each data point.

## Workflow

### Step 1: Determine Scope
默认生成完整看板。可选聚焦范围：rates/inflation/jobs/sentiment/crypto-macro/calendar

### Step 2: Fetch Data
按 scope 获取对应数据：
- **利率**: 联邦基金利率/10Y国债/2Y国债/2-10Y利差/降息、加息及不变预期（CME + Polymarket 双源）
- **通胀**: CPI YoY/MoM/Core CPI/PCE/12个月趋势
- **就业**: 非农/失业率/初请失业金/劳动参与率
- **情绪**: VIX/恐惧贪婪指数/DXY/主要股指
- **加密宏观**: BTC/ETH/加密总市值/稳定币总市值/DeFi TVL/DEX交易量/BTC ETF净流入
- **日历**: 未来2周经济数据发布日期

### Step 3: Compile Dashboard
按输出结构整理，含当前值、前值、变化趋势。利率预期单独使用[双源概率表](../skills/macro-dashboard/references/fed-expectations-browser.md#输出)，标注会议日期、结果口径、百分点差和可比状态。

## Output

- **Primary**: `YYYYMMDD-macro-dashboard.md`
- Footer: 数据来源、FRED 系列 ID、数据时间戳

## Quality Checklist

- [ ] 如引用项目 X 公告，已核对官网账号关联、原帖/原文和时间；同源材料未当独立证据，实施状态、修订冲突及访问缺口已说明
- [ ] 如涉及解锁，已尝试 Tokenomist 与 DefiLlama 网页、保留时间/分母/估计口径；未解释的差异已提示并核对项目原文，受限和示例数据未冒充真实事件
- [ ] 公司事件/业绩已按 IR 规则保留官网与披露证据、报告期、时间/时区和确认状态；未将管理层指引当一致预期或因访问失败声称无新闻
- [ ] 如引用 CNN 指数，已通过内置浏览器读取主指数、页面标签及时间；历史比较保留期间，变化用指数点，缺失项未补零
- [ ] 如涉及 FOMC，已用内置浏览器核实官网日期和文件，会议/发布日期分开，政策决定/官员预测/市场概率未混用，缺失材料已说明
- [ ] 如引用 Yahoo 数据，已通过内置浏览器核对主标的和代码，注明行情时间/时区、市场状态及缺失项；历史变化注明起止日期，未将盘中值当收盘值
- [ ] DefiLlama 指标已按免费数据规则标明 API/网页来源、统计期、读取时间和缺失/过期状态；事件经网页核实，未把 TVL 变化当作净流入
- [ ] FRED 数据系列 ID 正确
- [ ] 当前值和前值都已获取
- [ ] 当前价格已尝试两个插件，附价差、时间、告警/未核验状态
- [ ] 日历覆盖未来 2 周重要事件
- [ ] 利率预期已尝试 CME + Polymarket 内置浏览器双源；会议/规则/时间可比性明确，缺源与快照状态已标注
- [ ] 数据时效性标注

## Skill Reference

This command invokes the **macro-dashboard** skill. See `skills/macro-dashboard/SKILL.md` for the complete dashboard structure and FRED series IDs.
