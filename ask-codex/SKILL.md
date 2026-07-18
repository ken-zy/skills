---
name: ask-codex
description: Use when jdy explicitly invokes /ask-codex to consult Codex (GPT-5.5, high effort) for diagnosis, review, second opinions, or any task where jdy wants Codex's raw response back in the main context. Auto-detects tmux: if running in tmux with a codex CLI pane in the same cwd, sends prompt to that pane (preserves codex's session memory); otherwise falls back to direct Bash bridge to companion.mjs.
---

# ask-codex

让 codex 对一段 prompt 给出原话回答。**双通道自动选择**：

- **tmux 模式**（首选）：当前在 tmux 中，且找到同 cwd 的 codex CLI pane → 直接把 prompt paste 到那个 pane。
  优势：复用 codex pane 已经积累的 session 记忆（可达 800k+ tokens cached），无冷启动延迟。
- **companion 模式**（回退）：不在 tmux 中 → Bash 直调 codex companion.mjs。

不经 subagent，不做总结改写，原文回主对话上下文。

## 触发条件

仅在 jdy 显式输入 `/ask-codex <prompt>` 时使用。Claude 不主动调用——
"我觉得该问 codex"的判断仍走 codex:rescue 通道（如果适用）。

## 调用方式

**三步走**：检测模式 → prompt 落临时文件 → 按模式发送。

### Step 0：检测模式

用一次 Bash 调用判断：

```bash
if [ -n "$TMUX" ]; then
  # 找符合条件的 codex pane：跑着 codex 进程 AND 在同一个 cwd
  # 用 pipe '|' 作为字段分隔符 —— tmux list-panes -F 不解析 \t 转义（会输出字面 \t）
  CODEX_PANE=$(tmux list-panes -a \
    -F '#{pane_id}|#{pane_current_command}|#{pane_current_path}' \
    | awk -F'|' -v cwd="$PWD" '$2 ~ /codex/ && $3 == cwd {print $1; exit}')
  if [ -n "$CODEX_PANE" ]; then
    echo "MODE=tmux PANE=$CODEX_PANE"
  else
    echo "MODE=error"
    echo "[ask-codex] 在 tmux 中但没找到匹配的 codex pane"
    echo "           条件: pane_current_command ~ /codex/ AND pane_current_path == $PWD"
    echo "           请在另一 pane 启动 codex CLI（同目录），或退出 tmux 走 companion 路径。"
  fi
else
  echo "MODE=companion"
fi
```

> **分隔符注意**：`tmux list-panes -F` 的 format string **不识别 `\t` 转义**——若直接写 `'#{pane_id}\t#{pane_current_command}'`，tmux 输出的是字面 `\t`（反斜杠 + t）而不是 tab，awk `-F'\t'` 会把整行当成 `$1` 导致探测失败。改用 pipe `|`（pane 字段值里不会出现 pipe，安全）。

- `MODE=tmux` → Step 2A
- `MODE=companion` → Step 2B
- `MODE=error` → 退出，不静默 fallback

> **判定理由**：`pane_current_command ~ /codex/` 抓住 codex CLI 进程；`pane_current_path == $PWD` 防止把 prompt 发到别的项目的 codex pane。两条件必须同时成立。

### Step 1：把 prompt 写到临时文件

用 Write 工具（**不要**用 Bash 的 echo/heredoc）把 jdy 在 `/ask-codex` 后输入的
全部内容（保留原样换行和特殊字符）写到：

```
/tmp/ask-codex-<unix_timestamp>.txt
```

### Step 2A：tmux 模式

```bash
PROMPT_FILE="/tmp/ask-codex-<上一步的 timestamp>.txt"
TARGET="<Step 0 拿到的 CODEX_PANE，如 %1>"

LOG_DIR="$HOME/.codex/logs/$(date +%Y%m%d)"
LOG_FILE="$LOG_DIR/$(date +%H%M%S)-tmux.md"
mkdir -p "$LOG_DIR"

# 写日志骨架（prompt 全文 + 元数据，响应留空待 done 注入）
{
  printf '# ask-codex (tmux) %s\n\n' "$(date '+%Y-%m-%d %H:%M:%S')"
  printf -- '- **cwd**: %s\n' "$PWD"
  printf -- '- **codex pane**: %s\n' "$TARGET"
  printf -- '- **branch**: %s\n\n' "$(git branch --show-current 2>/dev/null || echo 'n/a')"
  printf '## Prompt\n\n```\n'
  cat "$PROMPT_FILE"
  printf '\n```\n\n## Response\n\n_pending — 由 jdy signal "done" 后 capture 注入_\n'
} > "$LOG_FILE"

# 用具名 buffer 避免污染默认 buffer，paste 后清理
tmux load-buffer -b ask-codex "$PROMPT_FILE"
tmux paste-buffer -b ask-codex -p -t "$TARGET"
tmux delete-buffer -b ask-codex 2>/dev/null || true

# 提交（codex CLI 用 Enter 触发 inference）
tmux send-keys -t "$TARGET" Enter

rm -f "$PROMPT_FILE"

echo ""
echo "[ask-codex] prompt 已发到 codex pane $TARGET"
echo "[ask-codex] 请在 pane $TARGET 查看 codex 回复；完成后告诉 Claude:"
echo "             - 'done' → 我用 tmux capture-pane 抓内容附加到日志 + 进上下文"
echo "             - 粘贴一段关键结果 → 我用你提供的内容"
echo "             - 直接给下一指令 → 我跳过 codex 响应"
echo "[ask-codex] 日志骨架: $LOG_FILE (响应待 done 后注入)"
echo "[ask-codex] 记住的 pane / 日志: PANE=$TARGET LOG=$LOG_FILE"
```

**技术关键点**：
- `tmux load-buffer <file>`：直接从文件读取原始字节进 buffer，**完全绕过 shell 转义**。PoC 验证 22 KB + 特殊字符 + 中文 + emoji 完整无损。
- `paste-buffer -p`：`-p` 启用 bracketed paste mode（向终端发 `ESC[200~ ... ESC[201~` 包裹），让 codex CLI 把整段识别为"粘贴"而非"逐字符键入"——multi-line prompt 的换行不会被误解为提交信号。
- `-b ask-codex`：用具名 buffer，避免污染 jdy 的默认 tmux paste buffer。
- `send-keys Enter`：codex CLI v0.134.0 用 Enter 提交输入并开始 inference。
- 不轮询 codex 完成状态，半自动等 jdy signal。

### Step 2B：companion 模式

```bash
PROMPT_FILE="/tmp/ask-codex-<timestamp>.txt"

COMPANION="$(ls -t ~/.claude/plugins/cache/openai-codex/codex/*/scripts/codex-companion.mjs 2>/dev/null | head -1)"
[ -z "$COMPANION" ] && { echo "[ask-codex] codex 插件未安装，请 jdy 先安装 codex 插件"; exit 1; }

LOG_DIR="$HOME/.codex/logs/$(date +%Y%m%d)"
LOG_FILE="$LOG_DIR/$(date +%H%M%S).md"
mkdir -p "$LOG_DIR"

# 写日志头（prompt 全文）
{
  printf '# ask-codex (companion) %s\n\n' "$(date '+%Y-%m-%d %H:%M:%S')"
  printf -- '- **cwd**: %s\n' "$PWD"
  printf -- '- **branch**: %s\n\n' "$(git branch --show-current 2>/dev/null || echo 'n/a')"
  printf '## Prompt\n\n```\n'
  cat "$PROMPT_FILE"
  printf '\n```\n\n## Response\n\n'
} > "$LOG_FILE"

# 调 codex companion —— 用 --prompt-file 让 codex 自己读，不经 shell argv
set -o pipefail
node "$COMPANION" task --prompt-file "$PROMPT_FILE" 2>&1 | tee -a "$LOG_FILE"
STATUS=${PIPESTATUS[0]}

rm -f "$PROMPT_FILE"
echo ""
echo "[ask-codex] 日志: $LOG_FILE"
exit $STATUS
```

**companion 模式不变**，关键点：
- `--prompt-file <path>`：codex 从文件读 prompt，不受 shell 转义影响
- 不传 `--model`：走 `~/.codex/config.toml` 默认（当前 GPT-5.5 + high effort + 中文）
- 不传 `--write`：默认 read-only，codex 只回答不改文件
- 不传 `--background`：foreground 阻塞，stdout 一次性返回
- `2>&1`：stderr 也进日志
- `tee -a`：stdout 同时回主对话和日志
- `${PIPESTATUS[0]}`：拿 node 的真实退出码（不是 tee 的）

## Done Signal 处理（tmux 模式后续）

skill 在 tmux 模式发完 prompt 就退出，**响应处理发生在主对话流中**。

Step 2A 输出里包含两条状态信息供 Claude 在后续对话中调用：
- `PANE=<codex pane id>`
- `LOG=<日志文件路径>`

当 jdy 后续说 "done" / "codex done" / 任何表达"codex 答完了"的话：

```bash
PANE="<从 Step 2A 输出记住的 pane id>"
LOG_FILE="<从 Step 2A 输出记住的日志路径>"

# 抓 codex pane scrollback 最近内容（纯文本，无 ANSI 转义；history-limit 默认 2000 行）
tmux capture-pane -p -t "$PANE" -S -1000 > /tmp/codex-response.txt

# 追加到日志
{
  echo ""
  echo "## Response (captured at $(date '+%H:%M:%S'))"
  echo ""
  echo '```'
  cat /tmp/codex-response.txt
  echo '```'
} >> "$LOG_FILE"

# 内容回到 Claude 主对话上下文
cat /tmp/codex-response.txt
rm -f /tmp/codex-response.txt

echo ""
echo "[ask-codex] codex 响应已抓取并追加到 $LOG_FILE"
```

**抓取范围**：默认 `-S -1000`（往上 1000 行）。codex 长响应（200+ 行）也覆盖。

**注意 capture-pane 会包含 jdy 发送的 prompt + codex 之前的 historical messages**——Claude 在向 jdy 转述/总结时应该截取最近一次响应（从本次 prompt 末尾标记之后），而不是 dump 全部历史。

**状态丢失兜底**：如果对话上下文被 compact 等原因丢了 PANE/LOG，Claude 可以：
- 重新探测：用 Step 0 的逻辑找当前 codex pane
- 找日志：`ls -t ~/.codex/logs/$(date +%Y%m%d)/*-tmux.md | head -1` 取最新

**jdy 直接粘贴响应**：不抓 pane，直接用 jdy 提供的内容。可以选择性追加到日志。

## 输出处理

- **companion 模式**：stdout 原样回到主对话上下文（含 codex 完整回答）。
- **tmux 模式**：skill 退出后由 jdy 控制下一步。Claude 在 done signal 时主动 capture 并消化。

无论哪种模式：不做总结、不做改写、不做摘要。
如果 jdy 想要总结，他会在收到原话后再让 Claude 处理。

## 历史日志

每次调用自动写到 `~/.codex/logs/YYYYMMDD/HHmmss-{tmux|companion}.md`，含 prompt + response 全文。

- 路径会在调用结束后回显给 jdy
- markdown 格式，便于回溯 / 拷贝到 obsidian vault
- jdy 可以 `ls ~/.codex/logs/` 查看历史，或 `grep -r "关键词" ~/.codex/logs/` 检索
- 日志不会自动清理；如需清理可手动 `rm -rf ~/.codex/logs/<date>/`
- tmux 模式的日志在 prompt 写入时就创建（含 pending 占位），响应通过 done signal 追加

## 失败处理

不做主动重试。

- **companion 模式**：codex 卡住时 jdy 自行 Ctrl+C。第一次冷启动 30-60 秒（sessionRuntime 是 direct mode），是一次性代价。
- **tmux 模式**：codex pane 不响应时 jdy 在 pane 里观察/重试，skill 不介入。
- **tmux 中没找到 codex pane**：退出报错，**不**静默 fallback 到 companion——避免你以为用了 pane 实际开了新 session。

## 与 codex:rescue 的对比

| 维度 | /ask-codex | codex:rescue |
|---|---|---|
| 触发 | jdy 显式 | Claude 自动判断 |
| 通道 | tmux pane (优先) / Bash companion (回退) | subagent → Bash |
| 默认 | read-only | write-capable |
| 结果 | codex 原话 | subagent 可能改写 |
| 历史 | 自动写日志 | 不写 |
| 上下文 | tmux 模式复用 codex pane session 记忆 | 每次新 session |
