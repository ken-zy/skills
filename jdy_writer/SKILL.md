---
name: jdy_writer
description: "撰写或修改公众号文章、X 中文内容，或执行明确要求的发布任务。"
---

# 自媒体内容创作

交付符合作者风格的公众号文章或 X 中文内容。按请求选择下面的部分，不把改字、写稿或保存自动扩展为完整发布流程。

## 保留约束

- 作者决定方向；保留真实语气和观点，不编造经历，不公开私人账户、地址或聊天信息。
- 新写作参考 `writing-style-profile.md`；简单措辞修改不重新扫描历史文章。
- 凭据零接触：不读写 `~/.jdy_writer/.env`；凭据操作由用户在独立终端完成。
- 公众号和 X 发布使用本 Skill 的 `wechat-publisher/`、`x-publisher/`；图片按已配置的 codex companion/image_gen 流程生成。
- Vault 图片仅引用分类 R2 WebP URL；上传成功后再写入，临时图片放 Vault 外。
- 对外发布须有明确授权和已确定的内容；已有授权与选择继续有效。只完成用户要求的渠道与步骤。

## 按任务读取

| 任务 | 参考 |
|---|---|
| 首次写稿或更新风格档案 | [风格校准](references/workflow-style.md) |
| 从日志选题、选择写作模式 | [选题与模式](references/workflow-planning.md) |
| 日志反思材料不足、需要作者补充判断 | [反思引导](references/workflow-reflection.md) |
| 写初稿 | [成稿约束](references/workflow-draft.md)；需要观点技法时读 [技法](references/workflow-techniques.md) |
| B/C/D 模式的读者理解检查 | [读者检查](references/workflow-reader-check.md) |
| 定稿、同步日志配图或保存 | [保存规则](references/workflow-save.md)，保留主话题去重键与内部链接 |
| 公众号配图、封面、发布及链接回填 | [公众号流程](references/workflow-wechat.md)，只读对应小节 |
| 生成或发布 X 中文内容 | [X 流程](references/workflow-x.md) |

解释或保存后无需固定询问下一轮服务。完成已请求产物、必要验证和结果说明后结束；缺少关键输入时再提问。
