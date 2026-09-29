---
name: macro-dashboard
description: |
  宏观经济看板 — 覆盖利率环境、通胀数据、就业市场、市场情绪和加密宏观指标。
  横跨传统金融和加密市场的宏观全景。Triggers on "宏观", "macro dashboard",
  "macro overview", "经济数据", "利率", "通胀", "CPI", "非农", "FOMC",
  "宏观看板", or "market overview".
---

# Macro Dashboard

生成宏观经济全景看板，覆盖传统金融和加密市场的关键宏观指标。

## 插件行情与价差核验

使用 CoinGecko 和 Binance 插件；涉及当前加密价格时，先读取并执行[双源行情规则](references/plugin-market-data.md)。默认价差 ≥1% 告警，用户可覆盖阈值；告警必须进入本次输出摘要。单源失败、计价或时间无法对齐时明确标记未核验。新闻/日历不含当前价格时，无需额外拉取行情。

## Data Source Priority

### Layer 1: CoinGecko + Binance 插件
- **CoinGecko 插件** — BTC/ETH 的 USD 价格、市值、涨跌幅、全球加密市值与占比
- **Binance 插件** — BTC/ETH 现货价格，按双源行情规则换汇、核对并告警

### Layer 2: 官网数据
- **FRED：内置浏览器** — 先读取并执行 [FRED 浏览器规则](references/fred-browser.md)，访问 `https://fred.stlouisfed.org/series/{series_id}` — 利率/国债收益率/CPI/PCE/就业数据/GDP/美元指数
- **DefiLlama：Chrome CDP** — `defillama.com` — 稳定币总市值/全球加密 TVL/DeFi 总量/DEX 交易量

### Layer 3: Web Search
- 经济数据发布日历、FOMC 声明、市场评论
- VIX 数据、恐惧贪婪指数
- ⚠️ **禁止用 Web Search 获取加密价格** — 搜索结果是新闻报道，非实时数据

每个数据点标注 "Source: [source name]"。

## Workflow

### Step 1: Determine Scope
如用户未指定，默认生成完整看板。可选聚焦：
- `rates` — 仅利率环境
- `inflation` — 仅通胀数据
- `jobs` — 仅就业市场
- `sentiment` — 仅市场情绪
- `crypto-macro` — 仅加密宏观
- `calendar` — 仅未来 2 周数据发布日历

### Step 2: Fetch Traditional Macro Data
通过内置浏览器访问 FRED 官网，按 [FRED 浏览器规则](references/fred-browser.md)读取：

**利率环境:**
- 联邦基金利率 (FEDFUNDS)
- 10 年期国债收益率 (DGS10)
- 2 年期国债收益率 (DGS2)
- 2-10Y 利差（计算）
- 降息/加息预期（Web Search: CME FedWatch）

**通胀:**
- CPI YoY (CPIAUCSL)
- CPI MoM
- Core CPI (CPILFESL)
- PCE (PCEPI)
- 12 个月 CPI 趋势

**就业:**
- 非农就业人数变化 (PAYEMS)
- 失业率 (UNRATE)
- 初请失业金人数 (ICSA)
- 劳动参与率 (CIVPART)

### Step 3: Fetch Market Sentiment
通过 Chrome CDP 获取（URL 已知直接导航，失败则 Web Search 兜底）：
- VIX 指数（finance.yahoo.com/quote/%5EVIX）
- CNN 恐惧贪婪指数（edition.cnn.com/markets/fear-and-greed）
- 美元指数 DXY（finance.yahoo.com/quote/DX-Y.NYB）
- 主要股指表现（finance.yahoo.com/quote/%5EGSPC 等）

### Step 4: Fetch Crypto Macro
通过 CoinGecko 的 `get_coin_markets` 和 Binance 的 `get_spot_symbol_price_ticker` 同批获取 BTC/ETH，再执行双源行情规则。CoinGecko 的 `get_global_market` 提供全市场指标。禁止“首源成功即停”及通过旧 MCP / REST / 浏览器静默回退当前价格。

获取内容：
- BTC 价格 + 24h/7d 变化 + 市值
- ETH 价格 + 24h/7d 变化 + 市值
- 全球加密总市值
- 稳定币总市值（DefiLlama Chrome CDP）
- DeFi 总 TVL（DefiLlama Chrome CDP）
- BTC ETF 净流入（DefiLlama / Web Search）

### Step 5: Compile Dashboard

## Output Structure

### 1. 利率环境
| 指标 | 当前值 | 前值 | 变化 |
|------|--------|------|------|
| 联邦基金利率 | | | |
| 10Y 国债 | | | |
| 2Y 国债 | | | |
| 2-10Y 利差 | | | |
| 降息预期 | | | — |

### 2. 通胀
| 指标 | 最新值 | 前值 | 趋势 |
|------|--------|------|------|
| CPI YoY | | | |
| CPI MoM | | | |
| Core CPI | | | |
| PCE | | | |

### 3. 就业
| 指标 | 最新值 | 前值 | 预期 |
|------|--------|------|------|
| 非农就业 | | | |
| 失业率 | | | |
| 初请失业金 | | | |

### 4. 市场情绪
| 指标 | 当前值 | 信号 |
|------|--------|------|
| VIX | | 低波动/正常/高波动 |
| 恐惧贪婪指数 | | 极度恐惧~极度贪婪 |
| DXY | | |
| S&P 500 (周变化) | | |

### 5. 加密宏观
| 指标 | 当前值 | 7d 变化 | 30d 变化 |
|------|--------|---------|----------|
| BTC | | | |
| ETH | | | |
| 加密总市值 | | | |
| 稳定币总市值 | | | |
| DeFi TVL | | | |

### 6. 关键日历（未来 2 周）
| 日期 | 事件 | 类型 | 影响程度 |
|------|------|------|----------|
| | | 利率/通胀/就业/其他 | 高/中/低 |

## Output Format

- **Primary**: `Macro_Dashboard_{YYYYMMDD}.md`
- Footer: 数据来源、数据时间戳、免责声明
- FRED 数据系列 ID 标注在括号内供追溯

## Quality Checklist

- [ ] FRED 数据从内置浏览器官网页面读取，已标注数据期间、单位及来源；未获取项明确说明
- [ ] 所有 FRED 数据系列正确引用（ID 对应正确指标）
- [ ] 当前值和前值都已获取（可计算变化）
- [ ] 当前价格已尝试 CoinGecko + Binance 插件，输出价差/时间/核验状态，超阈值告警未遗漏
- [ ] 全市场和 DeFi 数据保留各自来源与口径
- [ ] 日历部分至少覆盖未来 2 周重要事件
- [ ] 降息预期来自实时数据（CME FedWatch），非猜测
- [ ] 数据时效性标注
