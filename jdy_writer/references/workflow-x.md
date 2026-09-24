# x

本文件中的脚本、风格档案及资源相对路径，均以 Skill 根目录（上一级）为基准。仅执行本次请求的部分；沿用已给出的选择和授权，不重复确认。

## Phase 7: X 中文推文（公众号流程结束后）

公众号发布完成后（6.4 完成或用户明确跳过后），进入 X 中文推文生成。

> **2026-05-10 调整**：删除英文版路径——作者只发中文 X，不再做语义重写英文版/Thread。

### 7.1 直接使用公众号原文

中文版**不做任何改写**，直接使用公众号文章全文作为推文内容。

**长文处理**：公众号文章通常超过 280 字符，使用 **X Article**（长文章）格式发布，而非普通推文。

**X Article markdown 文件准备**：
- 文件命名：`{YYYYMMDD}-x-post-cn.md`，保存在与公众号文章同一目录
- 内容 = 公众号原文（含配图），但**剥离**：
  - **正文开头的封面图行**（即 Phase 6.2 插入的 `![](https://...cover.png)` 那一行，封面通过 `--cover` 单独传）
  - **发布链接行**（`> 发布链接：...`）
  - **`## 关联` 小节**（vault 内部双链区，对外读者无意义）
  - **主话题键 HTML 注释**（`<!-- 主话题: ... -->`）
- 添加 YAML frontmatter：`title: 原标题`（不含序号前缀）
- 配图复用正文 R2 URL；发布器需要本地文件时仅下载到临时目录，不在 Vault 新建图片目录

**排版格式化**（发布时强制执行）：
- 段落级别的句末标点（句号、问号、感叹号）后换行
- 引号内的句号不换行（如"塔勒布说过：'xxx。'今天..."整体保持在一行）
- 不同段落之间空一行
- 这是 X 的阅读体验要求，密排文字在手机上难以阅读

**日记体（Mode A）特殊处理**：日记体多话题，不能全发。先展示选择界面：

```
## X 推文：选择板块

| # | 板块 | 一句话摘要 | 推荐 |
|---|------|-----------|------|
| 1 | BTC 行情 | 96k 横盘，等方向 | ★★☆ |
| 2 | 某项目踩坑 | 花了三小时发现是合约地址错了 | ★★★ |
| 3 | 晚饭 | 做了红烧肉 | ☆☆☆ |

→ 选择要发 X 的板块编号（如 "1,2"），或 "全部"，或 "跳过"
```

用户选择后，每个选中板块使用该板块的原文内容。

### 7.2 输出格式

一次性输出预览，用户一次确认：

```
## X 中文推文预览

[公众号原文，排版格式化后]

→ 确认 / 调整 / 跳过 X 发布？
```

### 7.3 发布

> **2026-05-10 内化**：从 `baoyu-post-to-x` 外部 skill 迁入 jdy_writer 自带的 `x-publisher/`，完全自包含（同 wechat-publisher 模式）。原 baoyu 路径不再依赖。

用户确认后，调用 jdy_writer 内置的 x-publisher：

```bash
SKILL_DIR=/Users/jdy/Documents/skills/jdy_writer
PROFILE=~/.local/share/x-browser-profile-cn

# X Article 长文（Mode B/C/D 或 Mode A 全文）
bun "$SKILL_DIR/x-publisher/x-article.ts" \
  "<vault-path>/<YYYYMM>/<YYYYMMDD>-x-post-cn.md" \
  --cover "$LOCAL_COVER_PATH" \
  --profile "$PROFILE"

# 普通推文（280 字以内）— 使用 x-browser.ts（同样在 x-publisher/ 下）
```

**首次运行需安装依赖**（一次性）：

```bash
cd "$SKILL_DIR/x-publisher" && bun install
```

**Profile 配置**：
- 默认 profile：`~/.local/share/x-browser-profile-cn`（中文账号）
- 首次使用 profile 时需在 baoyu 启动的 Chrome 窗口里手动登录 X
- baoyu 默认 profile 是 `~/Library/Application Support/baoyu-skills/chrome-profile`（macOS），如不传 `--profile` 会用这个；为了用 X 中文账号 profile，**必须显式传 `--profile`**

**已知行为**：
- 默认是 **draft 模式**——脚本完成后浏览器保持打开，等用户人工 review 后点"发布"。加 `--submit` 可自动发布
- X Article 的 `--cover` 必须传本地图片路径（如 `/tmp/jdy-writer-cover/<YYYYMMDD>-cover.png`），不要传 R2 URL；当前 `x-article.ts` 会把 URL 当成本地路径解析，导致封面看似设置但实际不显示。
- 若 macOS 缺 Accessibility 权限，自动粘贴会失败，脚本会复制 HTML 到剪贴板并等 30s 让用户手动 Cmd+V
- **占位符残留**：x-article.ts 偶尔在第二张图后留下 `XIMGPH_N` 占位符文本（图片实际已插入）。发布前 Cmd+F 搜 `XIMGPH` 检查并删除

### 7.4 带图发布（可选）

如果本次流程执行了 Phase 6.1 文章配图，询问是否将配图用于 X 推文：

```
公众号配图可用于 X 推文。是否附图？（y/n）
```

附图时加 `--image` 参数。
