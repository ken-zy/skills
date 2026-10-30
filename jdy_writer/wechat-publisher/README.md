# wechat-publisher

jdy_writer skill 内置的微信公众号发布器。**API 模式独占**——已剥离浏览器/CDP 模式以降低维护成本。

## 来源

Fork from [baoyu-skills/baoyu-post-to-wechat](https://github.com/JimLiu/baoyu-skills) at 2026-05-07，后续独立维护。原始项目 MIT License。

## 何时调用

**仅由 jdy_writer SKILL.md Phase 6.3 调用**。不直接给用户用。

## 凭据

读取顺序：
1. 进程 env vars `WECHAT_APP_ID` / `WECHAT_APP_SECRET`
2. `<cwd>/.jdy_writer/.env`
3. `~/.jdy_writer/.env` ← **用户标准位置**

凭据由用户用 `nano ~/.jdy_writer/.env` 自己写入，AI 永不读、永不写。

## 用法

```bash
# 使用本 Skill 的已安装 Bun 和依赖，不临时安装运行时
bun <SKILL_DIR>/wechat-publisher/wechat-api.ts <markdown-file> \
  --title "N. 文章标题" \
  --author "泽永" \
  --summary "..." \
  --cover /path/to/cover.png
```

## 与 baoyu-post-to-wechat 的差异

| 项 | baoyu | 本 fork |
|---|---|---|
| 凭据搜索路径 | `~/.baoyu-skills/.env` 等 | `~/.jdy_writer/.env` 等 |
| 浏览器模式 | 支持 (`wechat-article.ts` + cdp) | **删除**（API only） |
| Multi-account | 完整支持 | 保留代码但简化使用 |
| Vendor deps | `baoyu-md` + `baoyu-chrome-cdp` | 仅 `baoyu-md`（CDP 删除） |

## 输出

本发布器只创建或更新公众号草稿，不调用正式发表接口。已有视频号内容和本地视频上传分别走[官方网页流程](../references/workflow-wechat.md#65-文章内视频视频号插入与本地视频上传)；后台已有原生播放器或视频号卡片时，API Markdown 覆盖会停止。

```json
{
  "success": true,
  "media_id": "...",
  "title": "..."
}
```

回读有差异时，命令输出分类诊断而不宣称成功。`--inspect-only` 保存私有原始／远端快照；实际审阅后用 `--reconcile-receipt --readback-sha256 ... --review-note ...` 仅核实本地回执，不写远端。精确校验仍用 `--verify-only`；图片展示地址的有限兼容不会放行正文、链接或样式变化。

用户明确确认发表后，使用 `--record-published --state-file ... --expected-media-id ... --expected-title ... --confirmation-note ...` 做本地收尾；该模式不读取凭据或网络配置。原 pending 完整备份，结果标为 `publication_user_confirmed`，不冒充独立发表／播放验收，关闭后不能用此回执继续写草稿。命令、取号语义及边界见[公众号流程 §6.3–6.4](../references/workflow-wechat.md#633-调用内化发布器)。
