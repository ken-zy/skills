# 每周催化剂预告提示词模板

[纯文本模板](catalyst-calendar-prompt.txt)仅保存可审阅的 prompt，展示细则指向[三层规范](../../jdy_finance_skills/macro/skills/catalyst-calendar/references/readable-preview.md)。`{{CATALYST_SKILL_PATH}}` 由维护者替换为该安装环境中的 catalyst-calendar/SKILL.md 路径；提取方式是读取整个 `.txt`、替换这一占位符，不提取 Markdown 代码块或包含本说明。仓库不保存用户机器绝对路径或私密会话地址。

本需求只更新既有任务的 prompt。实际运行配置须在合并后用官方 automation_update 更新并回读核对，保持原任务标识、heartbeat 类型、名称、ACTIVE、周日 20:00、原会话及通知偏好。不得新建替代任务或手写调度文件。代码合并和运行配置切换是两项状态；更新或回读失败时写明“代码已合并、运行配置未完成”，仅重试同一任务。这个模板本身不证明任务已更新。
