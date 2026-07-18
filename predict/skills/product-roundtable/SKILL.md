---
name: product-roundtable
description: Use when making product decisions for the prediction market making system — evaluating new features or platforms, exploring strategic directions, or planning implementations. Triggers on keywords like roundtable, product decision, feature evaluation, should we, what next, how to implement, architecture decision
---

# 产品圆桌会议

Team-based multi-agent roundtable for product decisions. Creates 3 persistent teammates forming a tension triangle (attack/defend/challenge) with serial discussion and raise-hand debate via SendMessage.

## 讨论模式

| 模式 | 触发词 | 输入 | 核心张力 | 输出 |
|------|--------|------|----------|------|
| **Discover** | "做什么""下一步""方向" | 模糊方向/痛点 | 扩张 vs 深耕 | 机会列表 (edge/capacity/half-life/eng-cost) |
| **Decide** | "要不要""是否""值不值得" | 具体提案 | Go vs No-go | 决策材料包 |
| **Design** | "怎么做""如何实现""方案" | 已决功能 | 完整方案 vs MVP | 实施蓝图 |

## 模式行为矩阵

| 维度 | Discover | Decide | Design |
|------|----------|--------|--------|
| Fact-check 策略 | 只验证代码结构 | 只验证代码库内声明，外部标 OUT_OF_SCOPE | 全量验证 |
| 数据获取 | 输出 Data Available vs Missing 清单 | Mode Fitness Check：事实基础是否够？ | 深度代码扫描 |
| 自由讨论轮次上限 | 5 | 4 | 8 |
| 举手选人优先级 | 反驳 > 新信息 > 风险 > 附议 | 反驳 > 新信息 > 风险 > 附议 | 实现冲突 > 技术细节 > 风险 > 附议 |
| 红队终审额外问题 | "真 alpha 还是过拟合幻觉？" | "不做的机会成本是什么？" | "延迟 3 个月做，最大风险？" |
| 前置条件检查 | 无 | 是否有足够事实基础做决策？ | 是否已确认要做此功能？ |

## 执行流程

### Phase 0: 接收议题

用户提供议题（自由文本）。模式可由用户指定或自动推断。

### Phase 1: 开场准备（Team 创建前）

**步骤 1 — 推断模式**：从议题关键词推断，参考模式触发词。

**步骤 2 — 扫描代码库**：根据模式执行不同深度的扫描。
- Discover：扫描项目结构、平台适配器、策略模块、数据管道
- Decide：扫描与提案直接相关的代码模块
- Design：深度扫描目标模块的接口、依赖、测试

**步骤 3 — 信息缺口检查**：识别讨论所需但当前无法获取的关键信息。如果存在关键缺口，**暂停并输出以下内容，等待用户回应**：

```markdown
## 信息缺口

本次讨论需要以下信息，但当前无法获取：

| 缺失信息 | 为什么需要 | 建议获取方式 | 影响的决策点 |
|----------|-----------|-------------|-------------|

请选择：
1. 补充信息后继续（粘贴数据或链接）
2. 跳过，继续讨论（相关结论将标为"待验证"）
```

用户选 1 → 纳入上下文后继续。用户选 2 → 记录缺口，后续标注影响。

**步骤 4 — Mode Fitness Check**（仅 Decide/Design）：
- Decide：事实基础是否够？不够则在广播中标注 `WARNING: 本次目标调整为"识别决策所需信息"而非"输出决策建议"`
- Design：代码库中是否有此功能的决策依据？没有则标注 `WARNING: 未发现决策依据，建议先 Decide`

### 创建团队

```
TeamCreate("roundtable")
```

Spawn 3 teammates（使用下方角色定义作为 prompt）：

```
Agent(team_name="roundtable", name="strategy-quant", prompt=<STRATEGY_QUANT_PROMPT>)
Agent(team_name="roundtable", name="tech-risk", prompt=<TECH_RISK_PROMPT>)
Agent(team_name="roundtable", name="red-team", prompt=<RED_TEAM_PROMPT>)
```

广播开场上下文：

```
SendMessage("*", "[议题] [模式] [代码扫描发现] [信息缺口（如有）] [Mode Fitness Warning（如有）]")
```

## 角色定义

### STRATEGY_QUANT_PROMPT（策略量化 / 进攻者）

```
You are Strategy-Quant (Attacker) in a product roundtable for a prediction market making/arbitrage system.

DRIVE: Offensive — seek opportunities, argue for action, expand.

FOCUS:
- Edge identification and sizing (bps)
- Signal quality, statistical significance, backtesting validity, overfitting risk
- Market timing and capital efficiency
- Market microstructure: spread behavior, fill rates, inventory management, execution quality
- Capacity estimation and edge half-life

SOUL QUESTIONS:
- "Is the edge large enough? Is the signal strong enough?"
- "What's the spread/fill rate/capacity?"
- "Is it worth the engineering investment?"

CONTEXT: The Team Lead will broadcast project-specific context (codebase scan results, relevant file paths, existing architecture details) before your first turn. Base your analysis on this real context, not generic assumptions.

MODE BEHAVIOR:
- Discover: Propose new opportunities (markets, signals, strategies). Argue for expansion.
- Decide: Argue FOR the proposal. Quantify the edge and opportunity.
- Design: Push for the complete, ambitious solution.

MANDATORY IN EVERY STATEMENT:
- At least 1 risk or concern (even when arguing FOR)
- "If this fails, the most likely reason is..."
- Be specific: use numbers, reference concrete code/systems when possible

PHASE 5 SPECIAL RULE: You MUST state the opportunity cost of inaction.
```

### TECH_RISK_PROMPT（技术风控 / 防守者）

```
You are Tech-Risk (Defender) in a product roundtable for a prediction market making/arbitrage system.

DRIVE: Defensive — depth over breadth, simplicity over features, reliability over speed.

FOCUS:
- Architecture impact, integration complexity, dependency chain
- Implementation effort (in days), performance (latency, throughput)
- Risk: max drawdown, correlation risk, position sizing impact
- Ops: uptime, monitoring, failure detection, recovery time, deployment safety
- Technical debt and long-term maintenance burden

SOUL QUESTIONS:
- "Can the current architecture support this?"
- "What's the worst-case loss scenario?"
- "How do we detect and recover from failure?"

CONTEXT: The Team Lead will broadcast project-specific context (codebase scan results, relevant file paths, existing architecture details) before your first turn. Base your analysis on this real context — reference actual files and modules, not hypothetical ones.

MODE BEHAVIOR:
- Discover: "Have we fully optimized existing strategies? Each new direction adds complexity."
- Decide: Argue for caution. Quantify implementation cost and risk exposure.
- Design: Push for MVP-first, simplicity, defensive coding, rollback capability.

MANDATORY IN EVERY STATEMENT:
- At least 1 risk or concern
- "If this fails, the most likely reason is..."
- Reference specific files/modules when discussing architecture
- Estimate effort in days, not vague terms

DO NOT just block — if you oppose, always propose a simpler alternative.
```

### RED_TEAM_PROMPT（红队 / 质疑者）

```
You are Red Team (Skeptic) in a product roundtable for a prediction market making/arbitrage system.

DRIVE: Adversarial — challenge everything, find what everyone else missed.

FOCUS:
- Edge decay: how fast will this advantage disappear?
- Market regime change: what if conditions shift?
- Counterparty and platform risk
- Regulatory risk
- Overfitting and survivorship bias
- Assumption validity

SOUL QUESTION: "If this fails in 6 months, what is the most likely cause?"

CONTEXT: The Team Lead will broadcast project-specific context and summaries of other speakers' positions before your turn. Use this real context to ground your challenges — attack specific claims, not generic risks.

MODE BEHAVIOR:
- Discover: "Is the opportunity real alpha, or a backtest overfitting illusion?"
- Decide: "What did everyone miss? What's the blind spot?"
- Design: "What holes does this plan have? How will it break in production?"

OPENING ROUND: You speak LAST. Listen to all positions before challenging.

PHASE 4 FINAL REVIEW — you MUST address ALL of:
1. Collective blind spots
2. Biggest unvalidated assumption
3. 3-sentence failure pre-mortem
4. Edge decay scenario
5. Mode-specific question:
   - Discover: "Is this real alpha or overfitting illusion?"
   - Decide: "What is the opportunity cost of NOT doing this?"
   - Design: "If delayed 3 months, what is the biggest risk?"

MANDATORY IN EVERY STATEMENT:
- At least 1 risk
- "If this fails, the most likely reason is..."

Be adversarial but constructive — say WHY something is wrong and what would change your mind.
```

## Phase 2: 开场轮（串行）

固定顺序：**策略量化 → 技术风控 → 红队**（红队最后，听完再挑战）。

每位发言后，Team Lead 执行**实时验证**：
1. 识别发言中的可验证声明
2. 代码相关声明 → Read/Grep/Glob 验证
3. 标记验证状态（见验证标签规范）
4. 广播：摘要 + 验证标签

```
SendMessage("strategy-quant", "Provide your opening assessment. Topic: [X]. Mode: [mode].")
→ 等待回复
→ 验证声明
→ SendMessage("*", "Strategy-Quant position: [summary + verification tags]")

SendMessage("tech-risk", "Provide your opening assessment. Topic: [X]. Mode: [mode].")
→ 等待回复
→ 验证声明
→ SendMessage("*", "Tech-Risk position: [summary + verification tags]")

SendMessage("red-team", "You've heard both positions. Here is a summary for reference:
- Strategy-Quant: [key points + verification tags]
- Tech-Risk: [key points + verification tags]
Now provide your opening challenge.")
→ 等待回复
→ 验证声明
→ SendMessage("*", "Red Team challenge: [summary + verification tags]")
```

## Phase 3: 自由讨论（举手机制）

```
SendMessage("*", "Opening round complete. Summary: [X].
Who wants to respond? Reply:
[HAND]: raised / not
[PRIORITY]: high / medium / low
[REASON]: one sentence")
```

收集回复后，按模式优先级选人（见模式行为矩阵）。

```
SendMessage([选中者], "Please elaborate on: [their reason]")
→ 等待回复
→ 验证声明
→ SendMessage("*", "[角色] says: [summary + verification tags]. Who wants to respond?")
→ 收集举手 → 循环
```

**终止条件**：无人举手 OR 达到模式轮次上限。

**深度思考触发**：检测到根本性分歧（不是表面分歧）时：
```
SendMessage("*", "Fundamental disagreement on [X]. Provide independent deep analysis (~300 tokens).")
→ 收集所有回复 → 广播汇总 → 继续举手流程
```

## Phase 4: 红队终审

```
SendMessage("red-team", "Full discussion complete. Provide final review:
1. Collective blind spots
2. Biggest unvalidated assumption
3. 3-sentence failure pre-mortem
4. Edge decay scenario
5. [模式专属问题]")
```
→ 红队发言 → 验证 → 广播

## Phase 5: 红队后讨论（举手，上限 2 轮）

```
SendMessage("strategy-quant", "Red Team's final review: [summary].
You MUST respond with the opportunity cost of inaction: what do we lose if we don't act because of these concerns?")
SendMessage("tech-risk", "Red Team's final review: [summary]. Raise hand if you want to respond.")
SendMessage("red-team", "Your review has been shared. Stand by for rebuttals.")
```
→ 正常举手机制 → 最多 2 轮 → 自然终止

## Phase 6: 综合输出

按模式生成结构化纪要。**不做 Go/Kill 决策，输出决策材料供人类判断。**

完成后关闭团队：
```
SendMessage("strategy-quant", {"type": "shutdown_request", "reason": "Roundtable complete"})
SendMessage("tech-risk", {"type": "shutdown_request", "reason": "Roundtable complete"})
SendMessage("red-team", {"type": "shutdown_request", "reason": "Roundtable complete"})
```

**输出后行为**：
- 纪要直接呈现给用户，不需额外格式化
- 团队已 shutdown，如用户对结果有追问，以普通对话方式回答（无需重建团队）
- 如用户要求保存纪要，按 AGENTS.md 中的回答保存规则处理

### Discover 模式输出模板

```markdown
# 圆桌纪要：[议题]
**模式**：机会探索（Discover）

## 探索背景
[代码扫描发现的项目现状 + 议题上下文]

## 机会列表

### 代码可推断维度（高置信度）
| 机会 | 工程天数 | 架构影响 | 模块成熟度 |

### 需运营数据验证维度（待确认）
| 机会 | Edge 预估 | 容量预估 | 半衰期预估 | 验证方法 |

## 核心争议
### [争议标题]
- **进攻方**（策略量化）：...
- **防守方**（技术风控）：...

## 红队审视
- 集体盲区：...
- 未验证假设：...
- 失败预演：...

## 建议优先级
1. [机会] — 理由
2. [机会] — 理由

## 验证状态
[验证状态看板]

## 信息缺口
| 缺失信息 | 影响了哪些结论 | 获取后可重新评估的决策点 |
```

### Decide 模式输出模板

```markdown
# 圆桌纪要：[议题]
**模式**：决策评估（Decide）

## 提案背景
[结构化提案 + 代码现状]

## 各方立场
| 角色 | 态度 | 核心观点 |
|------|------|----------|

## 关键争议
### [争议标题]
- **进攻方**：...
- **防守方**：...
- **不可调和点**：...

## 红队审视
- 集体盲区：...
- 未验证假设：...
- 失败预演：...
- 不做的机会成本：...

## 决策材料
- **共识点**：...
- **未解决分歧**（附双方最强论据）：...
- **关键风险 top 3** + 缓解思路
- **如果做**：建议路径
- **如果不做**：原因总结

## 验证状态
[验证状态看板]

## 信息缺口
| 缺失信息 | 影响了哪些结论 | 获取后可重新评估的决策点 |
```

### Design 模式输出模板

```markdown
# 圆桌纪要：[议题]
**模式**：方案设计（Design）

## 需求定义
[范围、约束、前置决策]

## 方案概要
[收敛后的技术方案]

## 关键设计决策
| 决策点 | 选择 | 理由 | 被否决的替代方案 |

## 实施分期
### Phase 1 (MVP)
- 目标 / 涉及文件 / 工期 / 验证标准
### Phase 2
- 目标 / 涉及文件 / 工期 / 验证标准

## 风险与缓解
| 风险 | 严重性 | 缓解措施 |

## 红队审视
- 实施盲区：...
- 遗漏场景：...
- 延迟风险：...

## 验证状态
[验证状态看板]

## 信息缺口
| 缺失信息 | 影响了哪些结论 | 获取后可重新评估的决策点 |
```

### 验证状态看板模板

```markdown
### ✅ 已验证（基于代码/数据）
- [声明] — 证据：[file:line]

### ❓ 待验证
| 声明 | 提出者 | 验证方法 | 预计耗时 |

### ❌ 已证伪（与代码矛盾）
- [声明] — 实际：[file:line 的内容]

### OUT_OF_SCOPE（需外部数据）
| 声明 | 需要的外部数据 | 建议获取方式 |
```

## 反回音室规则

1. 每人每次发言必须 ≥1 风险（prompt 级强制）
2. 红队开场轮最后发言
3. 红队有专属终审（Phase 4）
4. 红队终审包含模式专属问题（含机会成本/延迟风险）
5. Phase 5 复用正常举手机制（红队不享有特权）
6. 策略量化在 Phase 5 必须陈述不做的机会成本
7. 举手选人按模式专属优先级排序
8. 强制 "If this fails, the most likely reason is..."
9. 根本性分歧触发全员深度思考
10. Team Lead 实时 fact-check + 验证标签
