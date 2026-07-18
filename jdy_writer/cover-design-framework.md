# 封面设计框架（5 维度）

> jdy_writer 内置的封面图设计 rubric，借鉴自 baoyu-cover-image 的 5 维度模型并结合作者风格档案做了简化。
> Phase 6.2 必须按此框架自动选型，**不再临场拼凑**。

---

## 决策原则

封面图 = 视觉钩子 + 作者风格延续，不是装饰。

- **不放标题文字**（默认）。中文渲染容易翻车；作者风格档案"加粗克制"原则同样适用于封面。除非用户明确要求 `--text title-only`
- **必须与正文配图色调/风格一致**。两张图（封面 + 正文配图）应该看着是"同一只手画的"
- **40-60% 留白**。视觉锚点（人物剪影/物件/文字）放在画面左 1/3 或右 1/3，避免居中堆砌
- **不要营销海报感、不要 cyberpunk、不要真实人脸、不要 logo**

---

## 5 维度自动选型

### 1. Type（类型）

按文章主题选：

| 文章类型 | Type | 例 |
|---------|------|---|
| 哲学反思 / 抽象成长 / 顿悟 | `metaphor` | 「让 agent 替我决定」「那不是我的钱」 |
| 技术 / 框架 / 架构 / API | `conceptual` | 「DeFi 在救火」「复杂系统的脆弱连接处」 |
| 金句驱动 / 观点单刀直入 | `typography` | （罕用，作者很少做） |
| 个人故事 / 旅行 / 生活叙事 | `scene` | 「成都之行复盘」 |
| 极简 / 禅意 / 单一概念 | `minimal` | 「修心」 |
| 产品发布 / 重大事件 | `hero` | （极罕用） |

### 2. Palette（色板）

| 文章基调 | Palette | 关键词 |
|---------|---------|--------|
| 个人情绪 / 反思 / 温度 | `warm` | 暖驼、赭石、奶白 |
| 思辨 / 商业 / 专业 | `elegant` | 雾灰、深蓝、米白 |
| 技术 / 架构 / 数据 | `cool` | 冷蓝、灰绿、墨黑 |
| 自然 / 健康 / 朴素 | `earth` | 土褐、苔绿、亚麻 |
| 极简 / 禅 / 留白 | `mono` | 黑白灰 |
| 复古 / 童年 / 回忆 | `retro` | 焦糖、米黄、墨绿 |

**作者默认偏好**：`warm` 或 `earth`（绝大多数 Mode A/B 文章）。除非内容强烈指向其他色调。

### 3. Rendering（渲染）

| 内容氛围 | Rendering | 说明 |
|---------|-----------|------|
| 反思 / 个人 / 温度 / 编辑感 | `painterly` | 油画 / 水彩 / New Yorker editorial 质感 |
| 速记 / 涂鸦 / 不正式 | `hand-drawn` | 草图、手写笔触 |
| 技术 / 框架 / 平面 | `flat-vector` | 矢量、扁平、几何 |
| 数据 / 仪表 / 商务 | `digital` | 立体、polished、SaaS 感 |
| 教学 / 黑板 / 讲解 | `chalk` | 黑板粉笔 |
| 海报 / 剪影 / 限量感 | `screen-print` | 丝网印刷、双色对比 |

**作者默认偏好**：`painterly`。配合 warm/earth palette，做出稳定的"作者签名"视觉风格。

### 4. Text（文字）

| 选择 | 何时用 |
|------|--------|
| `none` | **默认**——视觉先行，无文字 |
| `title-only` | 用户明确要求 + 标题简短（≤ 8 字）+ 显示 OK |
| `title-subtitle` | 系列 / 教程文（罕用） |
| `text-rich` | 信息图、要点列表（罕用） |

**规则**：作者风格档案要求"加粗克制"，封面同理——除非用户特意指定，永远 `none`。

### 5. Mood（情绪）

| 选择 | 何时用 | 反义 |
|------|--------|------|
| `subtle` | 反思 / 思想 / 编辑感 | 不是抢眼 |
| `balanced` | 标准、教育、博客 | 中性 |
| `bold` | 公告 / 促销 / 娱乐 | 抢眼 |

**作者默认偏好**：`subtle`（低对比、克制、契合作者整体克制风格）。

---

## Aspect（比例）

固定 `16:9`（公众号封面标准）。除非用户明确指定其他比例（极罕用）。

---

## 自动选型决策树

```
文章风格档案信号
├── Mode A 日记体 → metaphor + warm + painterly + none + subtle
├── Mode B 反思 → metaphor + warm + painterly + none + subtle
├── Mode B 时事评论 → conceptual + cool + flat-vector + none + balanced
├── Mode B 框架长文 → conceptual + earth + painterly + none + balanced
├── Mode C 教程 → conceptual + cool + flat-vector + title-only(可选) + balanced
└── Mode D 长叙事 → scene + warm + painterly + none + subtle
```

---

## Prompt 生成规则

封面图 prompt 必须包含：

1. **比例**：`landscape 16:9`
2. **Type 词汇**：painterly editorial cover illustration / minimal conceptual diagram / etc.
3. **场景描述**：基于文章主话题（用 Phase 2 选定的主话题，不是所有板块）
4. **视觉锚点**：人物剪影 / 物件 / 抽象元素（左 1/3 或右 1/3）
5. **色板词汇**：warm muted tones / off-white / dusty terracotta / 等
6. **留白要求**："generous negative space" / "40-60% breathing room"
7. **禁区**：`No text, no logos, no watermarks, no realistic faces, no robots, no neon, no cyberpunk, no marketing-poster vibe`

---

## 与正文配图的关系

- **封面 = 正文配图的远景版本**：例如正文配图是"手放下缰绳的近景"，封面就是"远景剪影 + 同样的发光节点"
- 封面更"抽象、更静、更安静"；正文配图更"具体、更近、更触手可及"
- 同一组色板、同一种 rendering style——读者看完正文回到封面，应该感觉是同一支画笔

---

## 输出位置

封面图最终路径：`60_Output/公众号/{YYYYMM}/attachments/cover.png`

R2 上传 key：`illustrations/{YYYYMMDD}-cover.png`（多版本：`-cover-v2.png`）

R2 公网 URL：`https://pub-48c71f8223274ef1bc0c403d79a30f15.r2.dev/illustrations/{YYYYMMDD}-cover.png`
