# 发表核验与媒体回执

只处理用户已要求的核对、回填和媒体交接。命令不执行正式发表，不读取公众号凭据，也不替用户声明视频已播放。私有 JSON、HTML、截图和视频均放 Vault 外；知识库保留原正文、R2 图片、内部双链及正式链接。

## 公众号正式文章核对

原草稿回执的 `--record-published` 继续记录用户确认，不改变其证据含义。下面的新回执独立记录正式文章读取与比较，不修改原草稿回执。

```bash
SKILL_DIR=/Users/jdy/Documents/skills/jdy_writer
bun "$SKILL_DIR/publishing/wechat-publication.ts" \
  --source "<Vault绝对路径>/<文章>.md" \
  --draft-receipt "<原私有草稿回执>.json" \
  --state-file "$HOME/.local/state/jdy-writer/publications/<本次文章>.json" \
  --url "https://mp.weixin.qq.com/s/<已核实文章ID>"
```

- 默认从官方 URL 只读 HTTP 获取 HTML，再调用相邻 jdy-url-to-markdown 的 `prepareWechatHtml` / `parseWechatHtml`，保留懒加载图片。技能不相邻时用 `--url-skill <实际技能目录>`，不猜测不存在的安装路径。
- 标题和正文不可用、登录/验证码、HTTP 或解析失败时停止。不得为了读到内容绕过已遇到的浏览器访问策略。允许的浏览器已获得 HTML 时可用 `--html <私有快照>`，证据标为 `provided-html`，不冒称本次 live fetch；快照内 canonical/og:url 不匹配正式 URL 时只比较，不自动回填链接。
- 以原草稿回执中已渲染的文章作为基线；旧回执收尾后只剩备份时，仅从同目录、文件名及草稿身份均匹配的发表备份中读取快照。核对标题、规范化空白后的正文、图片身份/顺序和可点击链接；新增的视频卡片须用下节 ledger 声明身份和位置，并传 `--media-ledger <私有JSON>`。
- 相同内容返回 `article_compared`；只给明确指定笔记追加正式链接，不替换正文或上传媒体。回填时源文件改变则停止，手工合并同一链接后可重跑收尾。
- 有差异时退出码为 2，返回 `differences`、私有 `.comparison-<哈希>.json` 及其哈希，不回填链接。报告含正文，不能发到公开日志或 PR。读取并审查实际差异；若是后台已有的合理修改，保留这些改动，并按知识库规则合并正文和媒体。随后在原命令中加 `--accept-report <刚审查的哈希> --review-note <接受原因>`。命令再次读取，哈希变化即拒绝；成功标为 `article_reviewed`，不伪称精确一致。
- 核验不下载原生视频，不存储或打印签名播放地址；卡片身份/位置匹配不代表能播放。正文改动需单独合并，不能将报告里的微信图片地址直接替换知识库 R2 引用。

## 视频插入的交接与验收

实际网页操作继续遵循 [视频流程](workflow-wechat.md#65-文章内视频视频号插入与本地视频上传)。为每个视频建立稳定 key，绑定目标草稿 ID、文章标题、原素材身份和插入段落。交接时给出这些信息，让用户只处理未完成步骤。

```bash
MEDIA="$HOME/.local/state/jdy-writer/media/<本次文章>.json"
bun "$SKILL_DIR/publishing/media-ledger.ts" --state-file "$MEDIA" \
  --action add --key fish --draft-id "<已知草稿ID>" --article-title "<含序号的完整标题>" \
  --type channels --source "https://weixin.qq.com/sph/<原分享ID>" \
  --author "<视频号作者>" --media-title "<视频标题>" --after "<插入点前的准确正文>"

bun "$SKILL_DIR/publishing/media-ledger.ts" --state-file "$MEDIA" \
  --action record --key fish --event inserted --result pass \
  --evidence user-confirmed --note "<用户对同一篇文章完成插入的明确确认>"
```

本地视频使用 `--type local --source <原文件绝对路径>`；记录在私有回执，不写进知识库正文。

- `inserted`、`playback`、`published` 独立记录 `pass/fail/unknown`。没有记录的项为 unknown，插入成功不自动填为播放/发表成功。
- 用户确认用 `user-confirmed`；agent 实际检查用 `inspected`，须提供已查看的 `--evidence-file <本地截图/记录>`，脚本保存其路径和哈希。脚本仅保存证据，不代替 agent 实际观察。
- 每次记录追加到事件历史，不能覆盖原素材身份、换用另一个草稿 ID，也不能用“上传完成”充当“已插入”。出现失败保留已完成环节。
- 正式文章核对时读取 ledger 中声明的作者、标题及正文锚点；用户确认、网页解析和实际播放的证据保持独立。
