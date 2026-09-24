# style

本文件中的脚本、风格档案及资源相对路径，均以 Skill 根目录（上一级）为基准。仅执行本次请求的部分；沿用已给出的选择和授权，不重复确认。

## Phase 1: 风格校准（自动，无需用户参与）

### 1.1 加载风格档案

读取技能目录下的风格档案 `writing-style-profile.md`（与 SKILL.md 同目录）。

如果文件不存在，执行完整风格分析（见 1.3）。

### 1.2 增量吸收新文章

每次调用时，检查是否有新的公众号文章尚未被分析：

```bash
# 获取所有公众号文章，按文件名排序（YYYYMMDD 开头，即时间顺序）
find 60_Output/公众号/ -name "*.md" -not -path "*/attachments/*" -not -path "*/illustrations/*" -not -path "*/prompts/*" -not -name "*-publish.md" | sort

# 与风格档案中的 last_analyzed_file 对比，排在其后的即为新文章
```

**判断是否有新文章**：
- 风格档案中维护 `last_analyzed_file`（最后分析的文件名，如 `20260322 标题.md`）
- `find | sort` 获取全部文章列表，排在 `last_analyzed_file` 之后的即为新文章
- 文件名以 `YYYYMMDD` 开头，按名称排序即为时间顺序，不依赖文件修改时间

**如果有新文章**：
1. 仅读取排在 `last_analyzed_file` 之后的文章
2. 分析是否有风格变化（新的话题类型、语气转变、新的常用词汇）
3. 更新 `writing-style-profile.md`（追加新发现，修正过时描述）
4. 更新档案中的 `last_analyzed_file` 为最新文件名

**如果没有新文章**：直接使用现有档案。

### 1.3 首次完整分析（仅风格档案不存在时）

**用户提示**：首次分析前输出一句提示——"首次校准风格档案，正在分析 N 篇历史文章..."（N 为实际文章数）。

用 subagent 并行阅读所有历史文章，归纳：
- 4 种风格模式（日记体/深度思考/框架教程/长叙事）
- 通用特征（语言、结构、开头结尾模式）
- 高频词汇/黑话
- 写作检查清单

保存到 `writing-style-profile.md`。

---
