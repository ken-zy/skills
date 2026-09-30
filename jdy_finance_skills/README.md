# indie-finance-plugin

独立投资者金融分析插件 — 基于 Anthropic [financial-services-plugins](https://github.com/anthropics/financial-services-plugins) 架构，替换为免费数据源，新增 Crypto 模块。

为独立投资者提供机构级金融分析能力，覆盖传统金融（美股/港股）和加密市场（代币/DeFi/空投）。

## 快速开始

### 1. 安装插件

在终端中添加插件市场：

```bash
claude plugin marketplace add ken-zy/indie_finance_plugin
```

然后在 Claude Code 会话内安装子插件：

1. 输入 `/plugin` → 进入 **Discover** 标签页
2. 用 **Space** 键逐个选中需要的子插件，**Enter** 确认安装
3. 安装完成后输入 `/reload-plugins` 激活

| 子插件 | 用途 |
|--------|------|
| tradfi | 传统金融分析 |
| crypto | 加密市场分析 |
| macro | 宏观经济 |
| portfolio | 投资组合管理 |

### 2. 配置数据连接

tradfi / crypto 的既有 MCP 保留原 API key 配置流程；新增代币研究 Skill 可独立使用 GT 无 Key API 和可选 Demo REST，见下方独立入口。macro 使用宿主中已连接的 CoinGecko 与 Binance 插件，不再自动检测、恢复或同步 Key。

你也可以随时手动配置：

```bash
/tradfi:setup     # 配置 Alpha Vantage key
/crypto:setup     # 配置 CoinGecko + Dune key
/macro:setup      # 实测 CoinGecko / Binance 插件连接
```

既有配置与可选 API key（Key 的注册不代表任意 MCP 或 API 套餐均可用）：

| 服务 | 注册地址 | 用途 | 子插件 |
|------|---------|------|--------|
| CoinGecko | [coingecko.com/en/api/pricing](https://www.coingecko.com/en/api/pricing) | 新 Skill 的可选 Demo REST；既有 MCP 依其认证方案 | crypto |
| Alpha Vantage | [alphavantage.co/support](https://www.alphavantage.co/support/#api-key) | 技术指标、电话会议（官方 MCP） | tradfi |
| Dune Analytics | [dune.com/settings/api](https://dune.com/settings/api) | 链上查询（官方 MCP） | crypto |

> FRED 通过内置浏览器访问官网，无需 API Key；macro 的 DefiLlama 使用免费 API + 内置浏览器，无需 Key；macro 的 Yahoo Finance 和 CNN Fear & Greed 使用内置浏览器；crypto 的 DefiLlama 和非 macro 的 Yahoo Finance 保留既有方式。

### Key 管理机制

- 旧版 tradfi / crypto MCP 配置的 API key 保存在 `~/.indie-finance/keys.json`（与插件目录分离，权限 600）
- 这些旧版流程在插件更新后会自动从备份恢复 Key；独立研究脚本不参与
- macro 不参与 Key 备份和同步；插件若要求认证，在宿主的插件设置中完成

## 子插件

### tradfi — 传统金融分析

Fork 自 Anthropic 官方 `financial-analysis` 和 `equity-research` 插件，保留分析框架，替换数据源为免费 MCP。

| 命令 | 用途 | 输出 |
|------|------|------|
| `/tradfi:comps [ticker]` | 可比公司分析 | Excel + Markdown |
| `/tradfi:dcf [ticker]` | DCF 估值模型 | Excel + Markdown |
| `/tradfi:earnings [ticker] [Q]` | 财报分析 | Markdown |
| `/tradfi:screen [条件]` | 股票筛选 | Markdown |
| `/tradfi:thesis [ticker]` | 投资论文追踪 | Markdown |
| `/tradfi:model-update [ticker]` | 模型更新（财报后） | Markdown + Excel |
| `/tradfi:debug-model` | 电子表格审计 | Markdown |

自动触发 skill（无需命令）：competitive-analysis、idea-generation、audit-xls、clean-data-xls

数据源：Alpha Vantage (MCP) → Yahoo Finance (Chrome CDP) → Web Search

### crypto — 加密市场分析

全新模块，覆盖代币基本面、DeFi 协议、空投评估、链上查询。

| 命令 | 用途 | 输出 |
|------|------|------|
| `/crypto:token [symbol]` | 代币全面分析 | Markdown |
| `/crypto:defi [protocol]` | DeFi 协议分析 | Markdown |
| `/crypto:airdrop [project]` | 空投项目评估（v3 门槛+加权） | Markdown |
| `/crypto:onchain [query]` | 链上数据查询 | 对话内表格 |

代币市场证据：[crypto-project-research](crypto/skills/crypto-project-research/SKILL.md) 使用 GeckoTerminal 公共 REST + 可选 CoinGecko Demo REST；Dune、DeFi/空投等其他流程保持既有方式。macro 当前价格仍使用 CoinGecko + Binance 插件双源核验。

#### 独立无 Key 入口

无需启用旧 crypto 插件；从 `ken-zy/skills` Git 仓库根目录运行（Python 3.10+，无第三方依赖）：

```bash
python3 jdy_finance_skills/crypto/skills/crypto-project-research/scripts/fetch.py snapshot --network bsc --address 0xbeea1d618e533a387d941f58a7d4c9b7bd377777 --mode quick --out-dir /tmp/crypto-research-run
python3 jdy_finance_skills/crypto/skills/crypto-project-research/scripts/analyze.py /tmp/crypto-research-run --out /tmp/crypto-research-report.md
```

从本 `jdy_finance_skills` 目录运行时省去路径中的 `jdy_finance_skills/`。Codex/Claude 也可直接读取该 SKILL.md 再执行脚本；不会自动全局安装。使用新的输出路径，重复运行不得覆盖前次证据。

`fetch.py capabilities` 列出命名查询和接受的参数；standard 快照增加参考池 K 线/成交；`analyze.py --compare RUN_A RUN_B --out REPORT.md` 比较保存快照。可选 `--coin-id` enrichment 仅在身份映射确认后组合，并只读进程已有 `COINGECKO_DEMO_API_KEY`。缺 Key 不阻止 GT；不要在聊天粘贴密钥。

**边界**：独立脚本不读取密钥文件；启用整个旧 crypto 插件仍运行既有 SessionStart hook，可能读取、恢复或备份 Key，本次没有更改或隔离它。旧 hook 的提示不是 GT 请求的前置要求。接口覆盖、免费参数和数据限制见 [能力目录](crypto/skills/crypto-project-research/references/capabilities.md)。

### macro — 宏观经济

横跨传统和加密市场的宏观经济看板。

| 命令 | 用途 | 输出 |
|------|------|------|
| `/macro:dashboard` | 宏观经济看板 | Markdown |
| `/macro:morning` | 晨间市场笔记 | Markdown |
| `/macro:catalyst` | 催化剂日历 | Markdown |

自动触发 skill（无需命令）：news-digest

数据源：CoinGecko + Binance 插件（价格双源核验）；FRED（内置浏览器官网）；DefiLlama（免费 API + 内置浏览器）；美联储 FOMC（内置浏览器官网文件）；CME FedWatch + Polymarket（内置浏览器双源利率预期）；Yahoo Finance（内置浏览器）；CNN Fear & Greed（内置浏览器）；公司 IR / 正式披露（内置浏览器）；Tokenomist + DefiLlama（内置浏览器双源解锁）；项目官方 X 公告（内置浏览器核验）；其他新闻/事件（Web Search）

### portfolio — 投资组合管理

管理多账户投资组合，税务优化。

| 命令 | 用途 | 输出 |
|------|------|------|
| `/portfolio:rebalance` | 税务感知再平衡 | Excel + Markdown |
| `/portfolio:tlh` | 税收损失收获 | Excel + Markdown |

数据源：Yahoo Finance (Chrome CDP) → Web Search

## 数据架构

### 三层 Fallback

除 crypto 代币研究的免费 REST 路由及 macro 当前加密价格、FRED、macro DefiLlama、美联储 FOMC、利率预期双源、macro Yahoo Finance、CNN Fear & Greed、公司 IR / 正式披露、代币解锁双源及项目官方 X 公告的专用规则外，命令遵循以下数据获取策略。macro 当前价格只使用 CoinGecko + Binance 插件，统一计价后默认价差 ≥1% 告警；失败时标明未核验，不自动回退网页或旧 MCP。详见[双源行情规则](macro/skills/macro-dashboard/references/plugin-market-data.md)。

1. **MCP 数据源** — 首选，通过 MCP 协议直接查询
2. **Chrome CDP** — MCP 不可用时，直接导航访问目标页面
3. **Web Search** — Chrome CDP 失败时，搜索权威来源兜底

FRED 单独遵循[内置浏览器规则](macro/skills/macro-dashboard/references/fred-browser.md)，不走外部 Chrome、API 或搜索数值兜底。

macro 的 DefiLlama 遵循[免费 API + 内置浏览器规则](macro/skills/macro-dashboard/references/defillama-free-api.md)：指标由 Python 标准库脚本获取、缓存并计算变化；ETF/解锁/事件通过内置浏览器补齐。

美联储政策概率遵循 [CME FedWatch + Polymarket 双源规则](macro/skills/macro-dashboard/references/fed-expectations-browser.md)：两站均用内置浏览器读取，按同次会议和结算口径展示概率；只在可比时计算百分点差，缺源或时间不明时标注快照/未完成核验。

macro 的 Yahoo Finance 遵循[内置浏览器规则](macro/skills/macro-dashboard/references/yahoo-browser.md)：行情与历史数据从官网页面读取，失败标注未获取，不回退外部 Chrome、API 或搜索数值；非 macro 子插件保留原访问方式。

macro 的 CNN Fear & Greed 遵循[内置浏览器规则](macro/skills/macro-dashboard/references/cnn-browser.md)：读取主指数、情绪标签、历史比较值和页面时间；失败标注未获取，不回退外部 Chrome、API 或搜索数值。

美联储 FOMC 遵循[官网浏览器规则](macro/skills/macro-dashboard/references/fomc-browser.md)：从官方日历进入声明、纪要、预测及发布会材料，分别保留会议日期和发布时间；不以搜索摘要替代官网事实。

macro 公司事件/业绩遵循[IR 核验规则](macro/skills/macro-dashboard/references/company-ir-browser.md)：第三方日历找线索，内置浏览器访问公司官网确认时间，并读取正式披露核对内容。保留预计/确认状态，区分财报和电话会时间，不以搜索摘要替代原文；其他子插件保持原方式。

macro 解锁遵循[Tokenomist + DefiLlama 双源规则](macro/skills/macro-dashboard/references/token-unlocks-browser.md)：内置浏览器读取两站公开页，按事件/窗口、接收方、数量和分母对照；差异回到项目原文核实并提示。付费字段及未确认日期明确标注，不把占已释放量当占流通量，不接入付费 API。

macro 项目 X 公告遵循[官方 X 浏览器规则](macro/skills/macro-dashboard/references/official-x-browser.md)：从官网确认账号，读原帖和官方原文，按需用治理/发布/链上记录核实实施状态；保留时间、修订和访问缺口，不把同源转载视为独立证据。不使用付费 API，无需 Key。

### MCP 数据源总览

仅启用通过安全审计的官方 MCP server（详见 [安全审计报告](docs/mcp-security-audit.md)）。

| MCP Server | 类型 | 官方 | 限制 | 子插件 |
|-----------|------|------|------|--------|
| CoinGecko | 官方 MCP | 是 | 依实际 API 方案 | crypto |
| CoinGecko + Binance | 宿主插件 | 以宿主插件来源为准 | 以实际连接和工具限制为准 | macro |
| Alpha Vantage | 官方 MCP | 是 | 25次/天 | tradfi |
| Dune Analytics | 官方 MCP | 是 | 55次/分 | crypto |

以下数据源按各自网页访问规则读取：

| 数据源 | 限制 | 覆盖场景 |
|--------|------|---------|
| Yahoo Finance | 网站访问限制，行情可能延迟 | macro：内置浏览器读取指数及传统市场数据；其他子插件保留原方式 |
| DefiLlama | 免费 API 有限流，未承诺无限额度 | macro：免费 API + 内置浏览器；crypto：保留既有方式 |
| CME FedWatch + Polymarket | 网站访问限制，无需 Key；不承诺实时或无限访问 | 内置浏览器读取并比较美联储政策预期 |
| CNN Fear & Greed | 网站访问限制，无需 Key | 内置浏览器读取美股情绪指数 |
| 美联储 FOMC | 公开网页，无需 Key；受网站访问限制 | 内置浏览器读取会议日历和政策材料 |
| 公司 IR / 正式披露 | 公开网页受站点限制，无需 API Key | macro：内置浏览器确认公司事件和业绩原文 |
| Tokenomist + DefiLlama 解锁 | 只用公开免费部分，无需 Key；付费/登录限制标缺失 | macro：内置浏览器双源对照，项目原文核实差异 |
| 项目官方 X 公告 | 无需 API Key；登录、限流及内容可见性受站点限制 | macro：内置浏览器核对原帖、官网及实施证据 |
| FRED | 网站访问受站点限制，不套用 API 配额 | 内置浏览器读取宏观经济指标 |
| FMP | 250次/天 | SEC filing、分析师数据 |

## 目录结构

```
indie-finance-plugin/
├── .claude-plugin/marketplace.json    # 插件市场入口
├── .gitignore
├── CLAUDE.md                          # Claude 使用指引
├── README.md
├── tradfi/                            # 传统金融子插件
│   ├── .claude-plugin/plugin.json
│   ├── .mcp.json
│   ├── commands/                      # setup, comps, dcf, earnings...
│   ├── skills/
│   └── hooks/
│       ├── hooks.json                 # SessionStart hook 配置
│       └── check-keys.sh             # API key 检测与恢复
├── crypto/                            # 加密市场子插件
│   ├── .claude-plugin/plugin.json
│   ├── .mcp.json
│   ├── commands/                      # setup, token, defi, airdrop...
│   ├── skills/
│   └── hooks/
│       ├── hooks.json
│       └── check-keys.sh
├── macro/                             # CoinGecko + Binance 插件行情核验
│   ├── .claude-plugin/plugin.json
│   ├── .mcp.json
│   ├── commands/                      # setup 检查连接，dashboard, morning...
│   ├── skills/                        # 含 macro-dashboard/references 双源规则
│   └── hooks/hooks.json               # 无自动 Key 操作
├── portfolio/                         # 投资组合管理子插件（MCP 配置为空）
│   ├── .claude-plugin/plugin.json
│   ├── commands/
│   ├── skills/
│   └── hooks/hooks.json
├── packages/                          # 共享工具包
│   └── chrome-cdp/                    # Chrome CDP 抓取器（Layer 3 内部实现）
│       ├── src/                       # cache.ts, cdp.ts, chrome.ts, index.ts, markdown.ts
│       └── tests/
├── docs/                              # 文档与规格（安全审计报告、设计文档）
├── scripts/                           # 辅助脚本（validate_plugin.py）
└── _reference/                        # 官方机构 skill（不激活，供参考）
```

## 致谢

- 分析框架 Fork 自 [anthropics/financial-services-plugins](https://github.com/anthropics/financial-services-plugins)
- 免费数据源：Yahoo Finance, CoinGecko, DefiLlama, FRED, Alpha Vantage, FMP, Dune Analytics
