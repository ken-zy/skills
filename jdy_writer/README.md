# jdy_writer

中文公众号文章与 X 单条图文帖的写作、草稿准备和明确授权的发布流程。公众号 API 只保存草稿；正式发表、视频插入及播放结果分别验收。

- [SKILL.md](SKILL.md)：按任务选择流程，不自动串行执行所有渠道。
- [X 图文帖](references/workflow-x.md)：定稿准备、专用账号核验、提交恢复及链接回填。
- [发表核验与媒体回执](references/workflow-publication.md)：公众号正式文章只读比较、差异报告及视频交接。
- `publishing/prepare-x.ts`：定稿生成正文、有序图片和来源哈希，供发布器 `--prepared` 直接使用。
- `publishing/wechat-publication.ts`：复用 jdy-url-to-markdown 的解析器；不读取公众号凭据，不写远端草稿。
- `publishing/media-ledger.ts`：独立保存媒体身份、插入位置及各项证据，不执行上传或发表。
- `writing-style-profile.md`：作者风格参考；本轮原话、事实和明确选择优先。

私有回执及媒体文件置于 Vault 外，知识库保留 Markdown、R2 图片引用和正式链接。已确认内容与授权在任务范围内持续有效。修改与验证见仓库 PR 检查；测试不连接真实账号发布。
