# wechat

本文件中的脚本、风格档案及资源相对路径，均以 Skill 根目录（上一级）为基准。仅执行本次请求的部分；沿用已给出的选择和授权，不重复确认。

## Phase 6: 公众号后续操作（按需）

按当前请求选择执行；只有用户要求 X 内容时才进入 X 流程。

**文件路径约定**：Phase 5.1 保存的文件路径（如 `60_Output/公众号/202603/20260323 标题.md`）作为后续所有步骤的输入。

**架构**：所有发布相关动作走 jdy_writer 内置工具链，**不再依赖 baoyu-skills 任何路径**。
- 图片生成：codex companion 调内置 `image_gen` 工具
- 公众号发布：`{SKILL_DIR}/wechat-publisher/wechat-api.ts`（自包含，已剥离浏览器模式）
- 凭据管理：`~/.jdy_writer/.env`（用户自管，AI 永不读取也永不写入）

---

### 6.0 凭据安全 ⛔ BLOCKING（每次发布前自检）

**核心规则（绝对不可违反）**：

1. **禁止用户在对话中粘贴 App ID / App Secret / 任何 token**——对话内容可能进入模型服务和本地 transcript（.jsonl），任何粘贴 = 泄露
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

# 固定出口由 wechat-api.ts 在读取凭据前自动检查。
# 不用普通 api.ipify.org 请求推断微信出口，分流网络下两者可能不同。
```

**执行规则**：不要在发布前询问用户 IP 是否已加入白名单。直接进入 Phase 6.3 调用发布 API；只有实际报错 `40164` 时，才停下来提示用户把经过脱敏提取的 `whitelist IP` 加入公众号后台白名单后重试。

**Secret 泄露应急流程**（如果 secret 已经出现在对话/transcript/任何日志里）：

1. 立即去公众号后台重置 AppSecret
2. 用户自己 `nano ~/.jdy_writer/.env` 改新值
3. AI 不参与读写

---

### 6.0.1 公众号专用固定出口

设备本地无密钥配置：`~/.config/jdy-writer/wechat-network.json`：

```json
{
  "proxy": "http://127.0.0.1:17993",
  "expectedEgressIp": "95.169.12.176"
}
```

本机 Clash 的 `wechat-publisher` HTTP listener 直接绑定实际节点“固定美国”。配置里的 IP 是本机预期值，不代表其他设备也已配置，换服务器时必须重新核实。

- 正常上传前自动检查国内、海外探针是否都为预期 IP，失败中止；不会回退家庭直连。
- 只有 token、正文图片上传、封面素材上传和草稿读写 API 使用专用出口；源图片下载、生成封面、上传 R2 和其他程序沿用原行为。
- 本机 Bun 1.3.11 会让 NO_PROXY 覆盖显式代理，因此专用请求使用私有 stdio 子进程，在子进程内清除代理绕过变量。父进程/全局环境不变；请求 URL、凭据和响应 token 不进入命令行参数或诊断日志。
- `--dry-run` 不加载此网络配置、不执行探针、不调用 loadCredentials；保留原有 EXTEND 元数据解析。
- 未配置本文件的设备保持原有行为；配置文件存在但错误时必须修复或回滚，不能自动忽略。
- 网络失败只显示受控阶段/错误类型；微信白名单错误显示数字错误码和校验过的 IPv4，不显示原始 errmsg、完整 URL 或凭据。

配置、激活与回滚由 `wechat-publisher/wechat-egress-setup.ts` 分阶段执行。安装清单包含草稿模块；激活时先用安装目标的 `--help` 检查完整发布器能否启动，再重载网络配置，启动检查失败则回滚。`prepare` 只生成私有候选与备份，审查通过才执行 `apply`。私有 manifest 位于 `~/.local/state/jdy-writer/fixed-egress/install-*/`，不得上传仓库。回滚按 manifest 恢复原文件；仅当原先不存在且当前哈希仍匹配本次安装时删除新文件。Clash 重载可能短暂影响连接。

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
- 使用现有已配置的 R2 上传脚本；先阅读 Vault 的 `docs/agents/media.md`，不读取或输出凭据：
  ```bash
  R2_URL="$(bash /Users/jdy/Code/obsidian/scripts/r2-upload.sh \
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
# 使用现有 R2 认证配置；不要读取或输出秘密（参考 6.1.5）
COVER_URL="$(bash /Users/jdy/Code/obsidian/scripts/r2-upload.sh \
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

封面同时作为 Phase 6.3 草稿参数 `--cover` 使用。若用户另行要求 X Article，按 X 流程单独传封面并剥离正文开头封面行。

---

### 6.3 发布到公众号（API）

#### 6.3.1 标题计数

格式：`N. 标题`。计数器：`/Users/jdy/Documents/skills/jdy_writer/article-counter.txt`，仓库根目录 `/Users/jdy/Documents/skills`（远端 `git@github.com:ken-zy/skills.git`）。

- 新文章先获取最新 `origin/main`，读取远端计数器 N，拟用 `{N+1}. 原标题`；缺失或为空时询问当前序号，不从 Vault 数量推断。
- 使用独立 worktree 处理计数器，遵守机器级 Git 交付规则；不要在包含用户改动的活动目录执行 `pull --rebase --autostash`。
- 已有草稿沿用其标题和序号，不再次递增。先查看私有回执，避免把重试误当新文章。
- 无法同步或有并行文章占用同一序号时，先协调编号再创建草稿；不猜值或强制覆盖。

#### 6.3.2 创建发布版本文件 `-publish.md`

- 文件名：`{原文件名}-publish.md`
- 内容：原始 md 全文，并剥离以下 **vault-only** 内容（公众号读者不需要看到）：
  - **去掉末尾的发布链接行**（`> 发布链接：...`）
  - **去掉 `## 关联` 小节**（vault 内部双链区，含 `[[K-xxx]]` / `[[A-xxx]]` 等，对外读者无意义且渲染异常）
  - **保留 `<!-- 公众号阅读原文: URL -->` 元数据**，发布器据此设置原文链接，渲染不可见；从原始文件单独用 `--source-url` 传入也可以。位于 `## 关联` 后的元数据不能被整段剥离误删。
  - **去掉主话题键 HTML 注释**（`<!-- 主话题: ... -->`，仅 vault 去重用）
- 发布完后删除（避免污染 vault）

**剥离实现参考**（bash/sed）：
```bash
# 从原文件复制时一并剥离
awk '
  /^<!--[[:space:]]*公众号阅读原文[[:space:]]*[:：]/ { print; next }
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
# 首次草稿明确指定稳定的私有回执路径；同一篇文章更新时复用此路径和输入文件路径。
# --cover 可用本地路径或 R2 URL，WebP 会转换为微信接受的格式。
# 日常更新省略 --cover，会保留后台现有文章封面及裁剪。
bun "$SKILL_DIR/wechat-publisher/wechat-api.ts" \
  "<vault-path>/<YYYYMM>/<原文件名>-publish.md" \
  --title "{N+1}. 原标题" --author "泽永" \
  --summary "正文前 1-2 句（不含标题）" \
  --cover "$COVER_URL" \
  --state-file "$HOME/.local/state/jdy-writer/drafts/<文章唯一键>.json"
```

先 `--dry-run` 检查渲染和原文 URL；这一步不加载凭据、不探测网络、不写回执。实际保存时才经过专用出口。

运行环境应使用已安装的 Bun 和依赖，不通过 `npx -y` 临时下载运行时。依赖缺失时按机器级依赖规则处理。

**常见错误诊断**：

| 错误码 / 信息 | 含义 | 修复 |
|--------------|------|------|
| `Missing WECHAT_APP_ID` | `~/.jdy_writer/.env` 缺凭据 | Phase 6.0 首次设置流程 |
| `40164: invalid ip` | 当前公网 IP 不在白名单 | 复制错误信息中的 IP 去公众号后台白名单加上 |
| `40001: invalid credential` | App Secret 错误或被改 | 公众号后台重置 AppSecret，更新 `~/.jdy_writer/.env` |
| `40007` | 素材 ID 不合法，需结合失败阶段判断 | 核对永久封面 ID；不要盲目重建草稿 |
| `40113` | 文件类型不被接受 | 检查实际格式、文件名扩展名及对应素材接口 |

**原位更新及重试**：

- 回执按账号和输入文件绑定，包含草稿 ID、最近一次远端正文/封面/裁剪快照、图片上传缓存及未确认操作。默认放 `~/.local/state/jdy-writer/drafts/`，文件权限 0600，不提交到仓库。
- 同一路径重跑自动读取已有草稿，使用 `draft/update` 原位修改，不新建、不删除旧草稿。已有草稿尚无回执时，用 `--update-media-id <ID>` 首次接管；此操作替换正文，先确认本地正文已合并后台修改。
- 更新默认保留远端标题、作者、摘要、评论设置、阅读原文和封面裁剪；只有显式参数/原文元数据才覆盖对应字段。正文以当前输入文件为准。
- 后台或手机编辑造成快照不同，停止覆盖。先读取远端与本地合并正文，再显式用 `--accept-remote` 接受最新元数据；会保留接管前私有备份。不能只为消除报错自动加此参数。
- 写入前再读取一次，检查准备图片期间是否发生编辑；微信接口不提供条件写入，最后检查与写入之间仍存在短暂竞争窗口。操作期间避免同时编辑。
- 上传缓存按图片字节及用途区分；同图重试不重复上传。缓存素材被后台删除时，核实错误后仅清理对应缓存项，不删除整个草稿回执。源图片下载仍需联网。
- 手机端可能返回空 `thumb_media_id`。仅当已知原封面与当前图片 URL 相同，才允许复用已验证的原永久 ID；否则明确提供 `--cover-media-id <原图永久ID>`，或用 `--cover` 更换图片。不得把裁剪后的 `thumb_url` 再上传并套用旧裁剪。
- 更换封面时不沿用旧图的裁剪参数，实际裁剪需在官方编辑器核实；重复指定同一封面仍保留当前裁剪。文章封面和视频封面分别管理，不相互兜底。
- API JSON 明确返回非零数值错误码时，本次写入已被拒绝：清除该次 pending，保留草稿快照和图片缓存；修正对应参数后可重试，不创建替代草稿。HTTP 错误、传输异常及畸形错误码不能据此判定写入被拒绝。
- 请求超时、响应不完整或回读不一致，保留 pending 记录，报告“结果待核实”；不自动重建或删除草稿。已知 ID 时重试先回读，匹配待写内容才恢复；创建结果未知时，人工核实草稿箱并提供实际 ID，不能猜测。
- 若进程崩溃遗留 `.lock` 或 `.tmp`，先根据锁中的 PID 确认没有活动进程、备份回执并核实远端，再清理残留；不自动抢锁或丢弃 pending。多篇图文草稿暂交官方编辑器处理。

#### 6.3.4 末尾引流段落

默认不追加任何固定引流段落。

如果 jdy 在本次发布中明确要求追加引流、二维码或固定 CTA，才按当次指令加入发布版本文件。不要自动加入任何历史固定引流内容。

#### 6.3.5 计数器递增 + 清理

仅新文章首次确认创建草稿后更新计数器；`updated` / `unchanged` 不递增。计数器记录已分配的文章序号，不代表正式发表。故障恢复时对照实际草稿标题和远端计数器，确保同一序号只记一次。

在独立 worktree 提交计数器改动，允许按机器级规则推送和创建 PR；合并仍需明确授权。冲突时读取最新计数器并协调，不 `--force`，不提交其他技能或风格改动。推送失败不重传公众号草稿。

保存并核对草稿成功后清理临时 `-publish.md`，保留原稿、回执及媒体原件。

---

### 6.4 交付状态与发表链接

发布器只保存草稿，不调用正式发表接口。输出的 `status: draft_verified` 表示草稿字段已回读核对；`published: false` 表示没有执行正式发表。`operation` 区分 `created`、`updated` 和 `unchanged`。

- 素材上传成功、素材可读取、草稿保存、视频审核通过、预览可播放、正式发表成功分别记录。没有状态字段或没有验证时写“未知/未验证”。
- 不用草稿 ID、HTML 标签保留或播放按钮证明可正式发表；不为验证功能擅自发表测试文章。
- 只有获得正式发表结果或可核实的文章地址，才能称为“已发表”。“视频状态非法”不等于已证明内容违规，应区分引用格式、素材可用性和审核状态。
- 任务只要求上传草稿时，到草稿交付即完成，不追问发表链接、不自动转入 X。
- 用户明确要求回填发表链接，或之后提供链接时，再追加到原始 md：`> 发布链接：https://mp.weixin.qq.com/s/...`。

### 6.5 视频：默认引用链接＋阅读原文

- 先确认用户要的是外链、公众号正文内播放还是视频号。沿用已明确的选择；“上传视频到 R2”不等于要求原生播放器。
- 默认保留正文 `[观看宣传片](公开视频URL)`，使用渲染器的引用编号及“引用链接”列表，并写一句“点击文末‘阅读原文’观看完整视频”。普通外链在微信正文能否直接点击，不作保证。
- 在原稿写 `<!-- 公众号阅读原文: https://... -->`，发布器自动设置 `content_source_url`；显式 `--source-url` 优先，`--clear-source-url` 才清除。没有元数据或参数时，更新保留原有值。只有一个阅读原文入口，按用户确定的目的地设置。
- R2 视频与图片走不同处理流程：`r2-upload.sh` 是图片转 WebP 管线，不能传入 MP4。视频按媒体托管规则使用已有工具上传，保留原件；确认 HTTP 200、Content-Type、长度和可访问性后再写 URL。
- 此发布器暂不支持原生视频发表，遇到 iframe/video/mpvideo 会在写入前拒绝。禁止手写播放器、猜测或改写 `apiv_` / `wxv_` 标识冒充兼容性。用户明确要求正文播放时，可在官方编辑器从素材库插入，并如实说明发表验收尚未完成；工具不可用或访问被安全策略阻止时，交付素材和说明，不绕过限制。
- 原生视频若以后获验证支持，应分别记录视频素材 ID、平台视频 ID和独立视频封面；以明确指定图片或核实过的视频画面为封面，不回退到文章封面。压缩/转码仅操作副本，并按实际接口核实大小、编码等约束。
- 用户要求删除视频引用时，同步处理正文标签、编号、对应脚注及空的“引用链接”标题；有其他引用则保留。明确保留或清除阅读原文，不误改文章其他内容。
- 视频号是独立渠道，本 skill 没有视频号发布器；明确说明能力边界。若官方工具无法操作，准备视频、独立封面和文案，报告“未发布”，不把公众号素材上传当作视频号完成。
