# wechat

本文件中的脚本、风格档案及资源相对路径，均以 Skill 根目录（上一级）为基准。仅执行本次请求的部分；沿用已给出的选择和授权，不重复确认。

## Phase 6: 公众号后续操作（按需）

按 Phase 5.5 选择执行（完成后自动进入 Phase 7 X 推文）。

**文件路径约定**：Phase 5.1 保存的文件路径（如 `60_Output/公众号/202603/20260323 标题.md`）作为后续所有步骤的输入。

**架构**：所有发布相关动作走 jdy_writer 内置工具链，**不再依赖 baoyu-skills 任何路径**。
- 图片生成：codex companion 调内置 `image_gen` 工具
- 公众号发布：`{SKILL_DIR}/wechat-publisher/wechat-api.ts`（自包含，已剥离浏览器模式）
- 凭据管理：`~/.jdy_writer/.env`（用户自管，AI 永不读取也永不写入）

---

### 6.0 凭据安全 ⛔ BLOCKING（每次发布前自检）

**核心规则（绝对不可违反）**：

1. **禁止用户在对话中粘贴 App ID / App Secret / 任何 token**——对话内容会进 Anthropic API + 本地 transcript（.jsonl），任何粘贴 = 泄露
2. **AI 永不读取 `~/.jdy_writer/.env` 内容**——只检查文件存在 + 文件大小 > 0，不 cat 不 grep
3. **AI 永不写入凭据**——配置由用户用 `nano ~/.jdy_writer/.env` 自己写

**首次设置流程**（`~/.jdy_writer/.env` 不存在时）：

引导用户自己在终端执行：

```bash
mkdir -p ~/.jdy_writer && chmod 700 ~/.jdy_writer
nano ~/.jdy_writer/.env  # 然后自己粘贴：
# WECHAT_APP_ID=wx...
# WECHAT_APP_SECRET=...
chmod 600 ~/.jdy_writer/.env
```

凭据来自：公众号后台 → 设置与开发 → 基本配置 → AppID + AppSecret。

**发布前自检**（每次 Phase 6.3 自动执行，不可跳过）：

```bash
# 检查凭据文件
[ -s ~/.jdy_writer/.env ] || { echo "缺凭据，先按 Phase 6.0 配置 ~/.jdy_writer/.env"; exit 1; }

# 获取当前公网 IP
IP=$(curl -s https://api.ipify.org)
echo "当前公网 IP：$IP"
echo "→ 继续发布；如公众号 API 返回 40164 invalid ip，再提示用户把该 IP 加入白名单"
```

**执行规则**：不要在发布前询问用户 IP 是否已加入白名单。直接进入 Phase 6.3 调用发布 API；只有实际报错 `40164: invalid ip` 时，才停下来提示用户把错误信息中的 IP 加入公众号后台白名单后重试。

**Secret 泄露应急流程**（如果 secret 已经出现在对话/transcript/任何日志里）：

1. 立即去公众号后台重置 AppSecret
2. 用户自己 `nano ~/.jdy_writer/.env` 改新值
3. AI 不参与读写

---

### 6.1 文章配图

**生成器固定为 codex companion + 内置 image_gen 工具**。不调用 jdy-imagine、不调 baoyu-* fallback。

#### 6.1.1 Analyze：判断是否需要 AI 插图

读取已保存的公众号 md，先看正文是否已有 Phase 4.5 同步的 daily 真实图片：

- 已有 2+ 张真实图片：默认不加 AI 插图，除非有抽象核心概念
- 已有 1 张真实图片：最多补 1 张概念/隐喻图
- 没有真实图片：1-3 张，按文章长度和概念密度

只给"理解文章有帮助"的位置配图——核心论点、抽象概念、流程、时间线。**不**给纯情绪段落、生活叙事段落、已有真实照片的场景。文章用隐喻时画背后的概念关系，不字面画隐喻。

#### 6.1.2 Plan：每张图必须有 4 项

```markdown
## Illustration N
Position: 放在哪个小节/哪一段后
Purpose: 为什么这张图能帮助理解
Visual Content: 画什么，避免画什么
Filename: NN-short-slug.png
```

写不清 Purpose 就删掉这张图。

#### 6.1.3 Prompt 规则

prompt 必须包含文章里的**具体词**或**判断**（"断更十天"、"让 agent 替我决定"），不能只写抽象情绪。

固定禁区（每张图 prompt 末尾必须包含）：
> No text, no logos, no watermarks, no realistic faces, no robots, no humanoid AI figures, no neon, no cyberpunk aesthetic, no marketing-poster vibe.

#### 6.1.4 调用方式

通过 codex companion 调内置 image_gen：

```bash
COMPANION="$(ls -t ~/.claude/plugins/cache/openai-codex/codex/*/scripts/codex-companion.mjs 2>/dev/null | head -1)"
node "$COMPANION" task --write '使用你内置的 image_gen 工具生成图片。

Prompt: <完整的英文 prompt，按 6.1.3 规则>

输出：cp 到 /tmp/jdy-writer-illustrations/<topic-slug>/NN-<slug>.png
（不写入 vault，符合 D5 全面 R2 化；调用前先 mkdir -p /tmp/jdy-writer-illustrations/<topic-slug>）
确认：ls -la 报告文件大小'
```

**禁区**：
- 不调用 `jdy-imagine` skill（CLI 默认无凭据，会失败）
- 不调用 `$imagegen` placeholder（不是真实可调用工具）
- 不调用 `baoyu-image-gen` / `baoyu-article-illustrator`（已不依赖）

#### 6.1.5 插入

- 生成路径：codex 生成的 PNG 落 `/tmp/jdy-writer-illustrations/<topic-slug>/NN-<slug>.png`（不再落到 vault 内的 `illustrations/` 目录）
- 立即上传 R2（必须先 source env 文件加载 5 个变量）：
  ```bash
  # `~/.config/r2-pipeline/env` 含 5 个变量：
  #   R2_ACCESS_KEY_ID / R2_SECRET_ACCESS_KEY / IMG_SUBDOMAIN / R2_BUCKET / R2_ACCOUNT_ID
  # 这些变量 *不在* shell startup config 中——必须显式 source；不要尝试读取 env 文件内容（含密钥）
  set -a && source /Users/jdy/.config/r2-pipeline/env && set +a
  R2_URL="$(bash /Users/jdy/Documents/obsidian/scripts/r2-upload.sh \
    "/tmp/jdy-writer-illustrations/<topic-slug>/NN-<slug>.png" \
    "illustrations/<YYYYMMDD>-<topic-slug>-NN-<slug>")"
  ```
- 文章内引用：直接用 `$R2_URL`（`https://img.jdy.systems/illustrations/<YYYYMMDD>-<topic-slug>-NN-<slug>.webp`）
- 紧跟对应段落后，不堆到文末
- 文件名冲突：`-v2` 后缀（k2 = key + 后缀）
- 检查：URL HEAD 200、内容对应场景、无隐私/账户/地址/logo/水印
- **vault 内不创建 `60_Output/公众号/<YYYYMM>/illustrations/` 目录**（D5 全面 R2 化）

---

### 6.2 封面图

**框架引用**：见 [`cover-design-framework.md`](../cover-design-framework.md)（5 维度自动选型 rubric、prompt 生成规则、与正文配图关系）。

#### 6.2.1 自动选型

按 cover-design-framework.md 决策树，根据文章模式（A/B/C/D）和主话题自动选 5 维度。**不询问用户，直接生成**——除非用户主动指定某个维度。

#### 6.2.2 生成

通过 codex companion 调内置 image_gen，prompt 必须包含 cover-design-framework.md 「Prompt 生成规则」7 条要素。

```bash
mkdir -p /tmp/jdy-writer-cover
node "$COMPANION" task --write '使用你内置的 image_gen 工具生成封面图。

Prompt: <按 cover-design-framework.md 规则的英文 prompt，含 16:9>

输出：cp 到 /tmp/jdy-writer-cover/<YYYYMMDD>-cover.png
（不写入 vault，符合 D5 全面 R2 化；如已存在用 <YYYYMMDD>-cover-v2.png）
确认：ls -la 报告文件大小'
```

#### 6.2.3 R2 上传 + 正文嵌入

```bash
# r2-upload.sh 需要 5 个 env vars，必须先 source（参考 6.1.5）
set -a && source /Users/jdy/.config/r2-pipeline/env && set +a
COVER_URL="$(bash /Users/jdy/Documents/obsidian/scripts/r2-upload.sh \
  "/tmp/jdy-writer-cover/<YYYYMMDD>-cover.png" \
  "illustrations/<YYYYMMDD>-cover")"
# r2-upload.sh: cwebp q=90 + wrangler put + 删 /tmp/.../cover.png 本地副本
# stdout: https://img.jdy.systems/illustrations/<YYYYMMDD>-cover.webp（已捕获到 $COVER_URL）
# 注意：r2-upload.sh 上传成功后会删本地 cover.png；如果后续 Phase 6.3 需要本地路径，
#       必须从 R2 重新下载到 /tmp/jdy-writer-cover/<YYYYMMDD>-cover.webp
```

R2 公网 URL：`$COVER_URL`（已由 r2-upload.sh stdout 捕获，格式为 `https://img.jdy.systems/illustrations/<YYYYMMDD>-cover.webp`）

封面 URL 必须插入正文开头——紧跟 `# 标题` 后，空一行：

```markdown
# 文章标题

![]($COVER_URL)

正文第一段……
```

封面同时作为 Phase 6.3 发布参数 `--cover` 使用。Phase 7.1 生成 X Article 时**自动剥离开头封面图行**（X 通过 `--cover` 单独传）。

---

### 6.3 发布到公众号（API）

#### 6.3.1 标题计数

格式：`N. 标题`。计数器：`/Users/jdy/Documents/skills/jdy_writer/article-counter.txt`（git 仓库 `git@github.com:ken-zy/jdy_writer.git`）。

发布前先同步远端：

```bash
SKILL_DIR=/Users/jdy/Documents/skills/jdy_writer
git -C "$SKILL_DIR" pull --rebase --autostash origin main
```

读取当前 N，发布标题为 `{N+1}. 原标题`。

异常处理：
- rebase 冲突 → 停下问 jdy
- 网络失败 → 告知 jdy 是否继续；继续则用本地值，最终 push 可能被 reject
- 文件不存在/为空 → **必须询问用户当前序号**，禁止从 vault 文件数推断（vault 不含全部历史）

#### 6.3.2 创建发布版本文件 `-publish.md`

- 文件名：`{原文件名}-publish.md`
- 内容：原始 md 全文，并剥离以下 **vault-only** 内容（公众号读者不需要看到）：
  - **去掉末尾的发布链接行**（`> 发布链接：...`）
  - **去掉 `## 关联` 小节**（vault 内部双链区，含 `[[K-xxx]]` / `[[A-xxx]]` 等，对外读者无意义且渲染异常）
  - **去掉主话题键 HTML 注释**（`<!-- 主话题: ... -->`，仅 vault 去重用）
- 发布完后删除（避免污染 vault）

**剥离实现参考**（bash/sed）：
```bash
# 从原文件复制时一并剥离
awk '
  /^## 关联$/ { skip=1; next }
  /^<!-- 主话题:.*-->$/ { next }
  /^> 发布链接：/ { next }
  skip && /^## / { skip=0 }      # 遇到下一个 ## 标题恢复
  !skip { print }
' "$SRC" > "$DST"
```
注：如 `## 关联` 是文件最后一节（无后续 `##`），awk 会一直 skip 到 EOF，符合预期。

#### 6.3.3 调用内化发布器

**强制走 API 模式，不再有浏览器 fallback**（浏览器模式已从 wechat-publisher 中剥离）。

```bash
SKILL_DIR=/Users/jdy/Documents/skills/jdy_writer
# wechat-api.ts 的 --cover **只接受本地路径**，传 URL 会被当成相对路径解析报 "Image not found"。
# 如果 cover 已被 r2-upload.sh 删除本地副本，先从 R2 下载回来：
#   curl -sSL -o /tmp/jdy-writer-cover/<YYYYMMDD>-cover.webp \
#     "$COVER_URL"   # 或显式 https://img.jdy.systems/illustrations/<YYYYMMDD>-cover.webp
# wechat-api.ts 会自动把 .webp 转 JPEG (q=82) 后上传 material API。
LOCAL_COVER=/tmp/jdy-writer-cover/<YYYYMMDD>-cover.webp
cd "$SKILL_DIR/wechat-publisher" && npx -y bun wechat-api.ts \
  "<vault-path>/<YYYYMM>/<原文件名>-publish.md" \
  --title "{N+1}. 原标题" \
  --author "泽永" \
  --summary "正文前 1-2 句（不含标题）" \
  --cover "$LOCAL_COVER"
```

（**正文图** URL 会被 wechat-publisher 自动 fetch + WebP→JPEG 转换 + 上传 material API；**封面图** 不走这个路径，必须本地。）

**首次运行需安装依赖**（一次性）：

```bash
cd "$SKILL_DIR/wechat-publisher" && npx -y bun install
```

**常见错误诊断**：

| 错误码 / 信息 | 含义 | 修复 |
|--------------|------|------|
| `Missing WECHAT_APP_ID` | `~/.jdy_writer/.env` 缺凭据 | Phase 6.0 首次设置流程 |
| `40164: invalid ip` | 当前公网 IP 不在白名单 | 复制错误信息中的 IP 去公众号后台白名单加上 |
| `40001: invalid credential` | App Secret 错误或被改 | 公众号后台重置 AppSecret，更新 `~/.jdy_writer/.env` |
| `40003: invalid openid` | media_id 失效（极少见） | 重新发布 |

**格式修正后的草稿替换**：

- API 只创建草稿，不更新既有草稿。公众号后台发现格式问题（如表格对齐）时，不要在后台手改后再让本地状态漂移。
- 先改原始 md，再重新创建同标题草稿；计数器不变。
- 新草稿创建成功后，用 `draft/delete` 删除上一版草稿，避免后台同时存在多个同标题版本。
- 如果创建新草稿失败，不删除旧草稿；先保留可用版本，再处理错误。

#### 6.3.4 末尾引流段落

默认不追加任何固定引流段落。

如果 jdy 在本次发布中明确要求追加引流、二维码或固定 CTA，才按当次指令加入发布版本文件。不要自动加入任何历史固定引流内容。

#### 6.3.5 计数器递增 + 清理

发布成功后：

```bash
echo "$((N+1))" > "$SKILL_DIR/article-counter.txt"
rm "<vault-path>/<YYYYMM>/<原文件名>-publish.md"
git -C "$SKILL_DIR" add article-counter.txt
git -C "$SKILL_DIR" commit -m "chore: bump article counter to $((N+1))"
git -C "$SKILL_DIR" push origin main
```

- 不加 Co-Authored-By（遵守 jdy 全局规则）
- push 被拒 → 停下询问 jdy，**禁止** `--force`；WeChat 已发布、本地号已对，需手动 rebase 解决冲突再 push
- 网络失败 → 告知 jdy 不阻塞 vault 流程，下次 pull 会带出 commit

---

### 6.4 补充发布链接 ⛔ BLOCKING

**此步骤必须在进入 Phase 7 之前完成，不可跳过。**

API 发布只创建草稿。用户需要去公众号后台 review + 群发，然后提供 URL：

1. 用户去公众号后台群发文章
2. 提供已发布的公众号文章 URL（`https://mp.weixin.qq.com/s/xxx`）
3. 追加到原始 md 文件末尾：

```
> 发布链接：https://mp.weixin.qq.com/s/xxx
```

**如果用户暂时没有 URL**（如还没群发），回复"稍后补充"即可跳过，但**必须明确询问**，不能默认跳过。

---
