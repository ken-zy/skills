# indie-finance-plugin

独立投资者金融分析插件 — 覆盖传统金融（美股/港股）和加密市场（代币/DeFi/空投），全部基于免费数据源。

## 插件架构

本项目是一个 Claude Code 插件市场，包含四个子插件：

| 子插件 | 命令 | 数据源 |
|--------|------|--------|
| `tradfi` | `/comps` `/dcf` `/earnings` `/screen` `/thesis` `/model-update` `/debug-model` | Alpha Vantage (MCP) + Yahoo Finance (Chrome CDP) |
| `crypto` | `/token` `/defi` `/airdrop` `/onchain` | token: GT 公共 + CG Demo REST；其他流程保留 Dune (MCP) + DefiLlama (Chrome CDP) 等 |
| `macro` | `/dashboard` `/morning` `/catalyst` | CoinGecko + Binance 插件（价格双源核验）+ FRED（内置浏览器）+ DefiLlama（免费 API + 内置浏览器）+ CME FedWatch / Polymarket（内置浏览器双源）+ Yahoo Finance（内置浏览器） |
| `portfolio` | `/rebalance` `/tlh` | Yahoo Finance (Chrome CDP) |

另有自动触发 skill（无独立命令）：`crypto-project-research`（按 chain + CA 的免费 API 市场证据）、`news-digest`（新闻补充）、`competitive-analysis`（竞争分析）、`audit-xls`（电子表格审计）、`idea-generation`（投资想法筛选）。

## 三层 Fallback 策略

crypto `/token` 的市场证据先用 [crypto-project-research](crypto/skills/crypto-project-research/SKILL.md)：GT 公共 REST 无 Key；CoinGecko Demo REST 仅用进程已有 `COINGECKO_DEMO_API_KEY`，缺 Key 保留可选数据缺口，不自动替换为 MCP、Pro 或网页报价。独立读取 Skill/运行 Python 脚本无需启用插件，不读密钥文件；启用旧 crypto 插件仍会先运行能读取/恢复/备份 Key 的 SessionStart hook，不能将它描述为被新路由隔离。GT 不要求完成旧 Key 配置。项目官网/审计等补充材料继续按下方浏览器/搜索规则。

macro 的当前加密价格使用 [CoinGecko + Binance 双源规则](macro/skills/macro-dashboard/references/plugin-market-data.md)：默认价差 ≥1% 告警，不回退旧 MCP / REST / 浏览器 / 搜索价格；缺源时说明未核验，macro 不索取或同步 Key。FRED 使用[内置浏览器规则](macro/skills/macro-dashboard/references/fred-browser.md)，不自动回退外部 Chrome、API 或搜索数值。macro DefiLlama 使用[免费数据规则](macro/skills/macro-dashboard/references/defillama-free-api.md)，不接入付费 MCP。美联储政策概率使用 [CME FedWatch + Polymarket 内置浏览器双源规则](macro/skills/macro-dashboard/references/fed-expectations-browser.md)，不以 API、外部 Chrome 或搜索概率兜底。macro Yahoo Finance 使用[内置浏览器规则](macro/skills/macro-dashboard/references/yahoo-browser.md)，不自动以外部 Chrome、API 或搜索数值兜底；非 macro 的 Yahoo 访问方式保持原样。其余数据获取逻辑遵循：

```
Layer 1: MCP 数据源（首选）
  → 查询对应的 MCP server
  → 成功则使用，标注 "Source: [MCP名称]"

Layer 2: Chrome CDP 直接访问（MCP 不可用或数据不足时）
  → URL 已知（见"数据源-场景映射"表）→ 直接导航访问
  → URL 未知 → 先 Web Search 取 URL，再 Chrome CDP 访问
    · Web Search 也无法找到 URL → 直接降到 Layer 3
  → 标注 "Source: Direct Fetch - [URL]"

  【页面过大时的工具降级顺序】
  Step 1: get_page_text（默认）
  Step 2: Step 1 报 "Output exceeds character limit" →
          read_page 获取 DOM 结构，定位数据所在区域的 ref_id，
          再用 read_page(ref_id=...) 精准读取；
          若无法找到目标 ref_id 或返回空内容 → 直接 Step 4
  Step 3: Step 2 成功但目标数据不完整
          （表格行缺失、财务指标关键行缺失等可观测缺口）→
          get_page_text(max_chars=200000) 补全；
          若仍报超限或数据仍不完整 → Step 4
  Step 4: fallback 回 Layer 3 Web Search 兜底

Layer 3: Web Search 摘要兜底（Chrome CDP 失败时）
  → 使用 WebSearch 工具搜索
  → 优先搜索权威来源（SEC EDGAR, Yahoo Finance, CoinGecko 网页等）
  → 标注 "Source: Web Search - [URL]"
```

## 数据源-场景映射

| 场景 | Layer 1 (MCP) | Layer 2 (Chrome CDP URL) | Layer 3 (Web Search 兜底) |
|------|--------------|--------------------------|--------------------------|
| Yahoo Finance（macro 专用规则） | 内置浏览器读取官网 | 不适用 | 不自动兜底 |
| 股票行情/财报（美股；非 macro） | — | `finance.yahoo.com/quote/{ticker}` | finance.yahoo.com |
| 股票行情（A股） | — | `xueqiu.com/S/{code}` 或 `quote.eastmoney.com/sz{code}.html` | 东方财富/雪球 |
| 股票行情（港股；非 macro） | — | `xueqiu.com/S/{code}` 或 `finance.yahoo.com/quote/{ticker}` | 雪球/Yahoo Finance |
| 技术指标 | alpha-vantage | `tradingview.com/chart/?symbol={ticker}` | tradingview.com |
| SEC Filing | — | `sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={ticker}` | sec.gov/edgar |
| 电话会议 | alpha-vantage | `seekingalpha.com/symbol/{ticker}/earnings/transcripts` | seekingalpha.com |
| 分析师预期 | — | `tipranks.com/stocks/{ticker}/forecast` | tipranks.com, wsj.com |
| 代币行情（crypto `/token` 专用） | GT 公共 / CG Demo REST，见 Skill | 不自动回退 | 不自动回退 |
| DeFi 数据（crypto；macro 见免费数据规则） | — | `defillama.com/protocol/{protocol}` | defillama.com |
| 链上数据 | dune | `dune.com/queries/{query_id}` | dune.com |
| 美联储政策概率（专用规则） | 内置浏览器读取 CME FedWatch + Polymarket | 不适用 | 不自动兜底 |
| 宏观经济（FRED 专用规则） | 内置浏览器读取官网 | 不适用 | 不自动兜底 |
| 新闻 | alpha-vantage | ⚠️ URL 未知 → Web Search 取文章 URL → Chrome CDP 读全文；Web Search 找不到 URL → 降 Layer 3 | Web Search 搜索摘要（google news search） |

## 输出格式规则

### 估值模型（/comps, /dcf）
- 输出 `.xlsx` 文件（带公式，蓝色=输入，黑色=公式）+ Markdown 摘要
- 存放于当前工作目录

### 分析报告（/earnings, /screen, /token, /defi, /macro）
- 输出 Markdown 文件
- 如在 Obsidian vault 中使用，自动添加 `[[双链]]`
- 文件命名：`YYYYMMDD-{类型}-{标的}.md`

### 项目评估（/airdrop）
- 输出 Markdown 文件
- 格式对齐 `P-xxx` 项目评估模板
- 包含 v3 门槛+加权评分表 + 档位判定

### 链上查询（/onchain）
- 对话内表格输出
- 用户可追加"保存"输出为文件

### 通用标注（所有输出底部）
- 数据来源（哪个 MCP / 哪个 URL）
- 数据时间（截至 YYYY-MM-DD HH:MM）
- 免责声明：本分析仅供参考，不构成投资建议。数据来源为第三方，可能存在延迟或误差。

## API 限流注意

| 数据源 | 限制 | 注意事项 |
|--------|------|---------|
| CoinGecko Demo REST | 配额以当前方案为准；不硬编码为授权承诺 | crypto 代币研究可选；使用独立脚本预算，认证请求不缓存 |
| GeckoTerminal 公共 REST | 客户端默认 5 次/分为保守预算，非官方配额声明 | crypto 代币研究默认；限流时披露，不切源绕过 |
| Alpha Vantage | 25次/天, 5次/分 | 官方 MCP，仅用于电话会议和技术指标 |
| Dune | 15+40次/分 | 官方 MCP，链上查询 |
| Yahoo Finance | 网站访问限制；不能假设无限制或全部实时 | macro：内置浏览器；其他子插件保持 Chrome CDP / Web Search 原路径 |
| DefiLlama | 免费 API 有限流，无明确无限额度承诺 | macro：免费 API + 内置浏览器；官方 MCP 需要 API 订阅，crypto 访问方式不变 |
| CME FedWatch / Polymarket | 网站访问限制；不承诺实时或无限访问 | 内置浏览器公开页面，无需 Key；核对会议、结算规则和时间 |
| FRED | 网站限制；不套用 API 配额 | 内置浏览器访问官网，无需 API Key |
| FMP | 250次/天 | 无官方 MCP，Chrome CDP / Web Search 兜底 |
