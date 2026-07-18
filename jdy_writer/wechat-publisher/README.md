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
cd /Users/jdy/Documents/obsidian/.claude/skills/jdy_writer/wechat-publisher
npx -y bun install   # 首次
npx -y bun wechat-api.ts <markdown-file> \
  --title "191/1000 让 agent 替我决定" \
  --author "jdy" \
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

API 发布成功 = 创建公众号草稿。**用户需手动在公众号后台 review + 群发**——API 不允许直接群发。

```json
{
  "success": true,
  "media_id": "...",
  "title": "..."
}
```
