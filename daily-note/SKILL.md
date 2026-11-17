---
name: daily-note
description: 在 Obsidian 中按 T-Daily 模板创建每日笔记，或补充已有的每日笔记。
---

# Daily Note

1. 在目标 Obsidian vault 根目录执行命令。使用用户指定的日期，默认取本地当天。笔记路径为 `50_Daily/YYYY/MM/YYYY-MM-DD.md`。
2. 先检查该文件。已有笔记时，读取内容并按用户请求补充。
3. 创建前确认 Obsidian 正在运行、CLI 已启用且 `T-Daily` 模板可用。CLI 的首次调用可能启动 Obsidian。若用户要求避免启动应用，先确认运行状态。
4. 从 vault 根目录创建缺少的笔记。

   ```sh
   obsidian create path="50_Daily/YYYY/MM/YYYY-MM-DD.md" template="T-Daily"
   ```

   显式路径用于确保笔记落在月份目录。省略 `open` 和 `overwrite`。
5. 回读目标文件，确认它位于预期路径且包含模板内容。

[Obsidian CLI 文档](https://help.obsidian.md/cli)
