# 催化剂可读性：静态验证记录

本记录验证文档结构、入口及引用；不充当独立生成行为验收或实际市场重新采集证据。实现前已取得[冻结方案的 PLAN LGTM](../reviews/2026-10-06-catalyst-readable-plan.md)。基线为 `c9ec96f3c96edc2f5bd071f24b070b4160763238`；本轮在实现内容提交前的工作树运行，六个交付内容文件的字节指纹见[结构结果](2026-10-06-catalyst-readable-structural.json)，最终提交须由后续审查单独绑定。

## 已实际执行

- 用 `git archive` 将固定基线的 `jdy_finance_skills` 提取到临时目录，在那里运行既有 `scripts/validate_plugin.py`，再对实现后的完整插件树运行同一脚本。完整 stdout、stderr、退出码逐字比较相同；两次均 exit 1、FAIL、4 errors、4 warnings，**没有新增错误或警告，不是全仓 PASS**。[完整结果](2026-10-06-catalyst-readable-plugin-results.json)保留两次输出。
- 基线错误为四个子插件 `.mcp.json` 缺失；警告为 tradfi/crypto/macro 的 setup 命令映射，以及 crypto airdrop 命名。没有为了消除无关状态新增配置或修改其他入口。既有 skill_frontmatter、command_metadata 等四项检查均 PASS。
- Ruby 标准库 `YAML.safe_load` 实际解析 skill 与 command frontmatter；两者为字典且 description 为字符串，skill 的 name、command 的 allowed-tools 为字符串，通过。未新增依赖。
- Python 标准库对六个交付内容文件验证 UTF-8、LF、末尾换行、Markdown 围栏成对、全部 60 个 Markdown 链接的本地路径存在或 HTTP(S) 主机合法，通过。不是外链在线可达性或全部 Markdown 语法验证；合成 `.example` 地址仅展示字段。
- 与固定基线逐字比较 macro-dashboard/references 中全部文件，未改变共享解锁、IR、FOMC、X 及其他来源规则。冻结方案仍为 10,030 bytes、SHA256 `c2811b167912982f9e431d9c6e53fc67e90b51d290310aa974bd027babccfff3`。
- 六个交付内容文件没有机器绝对路径或私密 ChatGPT 审查会话地址。prompt 只含一个 `{{CATALYST_SKILL_PATH}}` 占位符；实际安装路径不公开提交。
- `git diff --check` 通过；提交前还须运行 staged whitespace 检查，仅 stage 本需求文件。

## 展示与验证边界

[三层规范](../../jdy_finance_skills/macro/skills/catalyst-calendar/references/readable-preview.md)是 skill、command 和拟部署 prompt 的共同依据；两入口移除了旧六列表、持仓模板、颜色要求和全年默认 EST/UTC。收集类别、浏览器及双源约束继续保留。主表最多四列，摘要最多三项重点；少事件不凑数，多于两项重大限制不得被字数预算删掉。核验附录仍需同会话完整输出。

[合成教学样例](../examples/catalyst-readable-preview-synthetic.md)展示事件编号、银行两种时刻、源时区未知、同日叠加、第三方小计、历史速率不可比、日期分歧、资格截止及缺基线。它不是实际用户报告，不能当公开网站核验结果或自动生成测试。

独立三入口、多案例生成验收由另一 agent 在读取本轮冻结交付内容后完成，结果须另附，并与本记录静态检查区分。此记录不预先宣称行为验收成功、不证明所有未来模型遵循规范，不证明远端 CI/PR/合并完成，也不证明自动化已经更新。实际任务 prompt 的更新、回读及原调度字段核对在 Git 交付之外。

## 独立生成初轮反馈后的修正

初轮生成验收实际发现来源身份升级和机构身份推断：三个变化案例把只有公告日期/首次纳入核验的活动标成官方计划，另一个命令入口密集事件案例把未明示机构身份的代号称为银行。初轮 FAIL 证据由独立验收记录保留，不用静态检查掩盖生成问题。

本轮仅在三层规范明确两项证据约束：官方计划/预计需核实来源身份并有对应字段原文明示；未知身份仍待核，不从链接、发布日期或首次纳入推导。机构/板块身份不得由代号或关注理由猜定，必要推断须标明且不能作为事实或来源核验依据。其他入口、prompt 和明示合成身份的教学样例未改。

修正后再次实际运行完整插件验证器，与此前归档的固定基线 stdout/stderr/exit code 完全相同，仍 FAIL 4 errors/4 warnings、无新增；再次检查六内容文件的 UTF-8/LF/围栏和全部 60 链接、共享 references 与固定基线字节相同，并更新三层规范的结构指纹，通过。提交前再次运行 `git diff --check` 及 staged whitespace 检查。受影响四份报告须由独立验收者重新生成，本记录不提前宣布复验通过。
