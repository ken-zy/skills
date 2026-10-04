# 晨报覆盖修复：结构验证

本记录只证明结构与配置保持性，不代替独立行为验收、ChatGPT Pro CODE LGTM 或实际自动化生效。

## 冻结方案与修改范围

基线 HEAD：f244741（docs: approve morning brief coverage plan）。冻结 R2 方案未修改，SHA256 为 537e322823f5ed21aca9af4c1ac20ebd6a8e62b2b6e688c74d0a92b7debfb598，已用 Python hashlib 实际核验。

实现新增一个领导晨报配置，接线 morning-note、morning 命令与 news-digest；新增自动化提示模板和九个离线合成原始场景。未新增依赖、采集程序、服务或持久状态；未调用网络、报价工具，未修改真实 automation.toml 或其他目录中的文件。生成模板只读现有 automation.toml。

## 实际运行检查

`git diff --check` 通过。对三处接线和新配置提取 Markdown 相对链接并解析文件路径，共 46 处，均指向实际存在文件。

Ruby 自带 YAML 解析三处 frontmatter，检查 skill 的 name/description 与 command 的 description/allowed-tools 均为非空字符串，三处通过。协调者尝试 skill-creator quick_validate.py 时，系统及 bundled Python 均缺 PyYAML（ModuleNotFoundError: yaml），未安装依赖，不将其记为通过；本次用 Ruby YAML 和仓库既有检查替代。

运行 `python3 jdy_finance_skills/scripts/validate_plugin.py` 返回 FAIL：四个子插件的 .mcp.json 在基线即缺失；四项既有 warning 为三个 setup 命令映射及 airdrop 命名。用 git archive 导出基线至临时目录并运行同脚本，完整 JSON 检查结果与本次逐项相同，确认没有新增错误或警告。plugin_json、skill_frontmatter、command_metadata、fallback_order 四项 PASS。没有为消除既有问题新增 MCP 配置或扩大本次范围。

Python stdlib JSON 解析 fixture 成功：F01–F09 九个独立场景；发现入口均有本地映射，页面只含保留域名 bulletin.test 和原始 HTML 或访问错误，未包含 expected 键或参考答案。ETF 场景初始候选为空，必须从发现入口沿页面链接读取相关报道；对应统计原表仍须实际读取才可使用。fixture 结构有效不等于模型执行已通过。

模板与只读现有提示按段落比较，仅第 2、5、6 段有预期变化（专用文件接线、覆盖/候选规则、正文取数与日期核验），其余七段逐字相同。全部路径占位仅 {SKILLS_ROOT}，每个展开对应的仓库规则文件均存在。指定 CoinGecko app、无代币报价/无指数点位/无 widget、标题格式、08:30、定时运行不改仓库、不交易/外发等边界保留。模板不是已应用配置；自动化 ID、线程、调度、状态与通知字段交由协调者应用并回读核对。

## 行为边界与交付限制

有效规则和 fixture 已冻结供独立评估者读取原始场景，评估记录由协调者另行保存；本实现者未给评估者参考输出或正确标签。九个场景包含七个方案要求的决策边界及两个模式控制，未执行实时晨报。行为验收和 Pro code review 完成前，不宣称整体修复已交付。

规则仍由模型执行，checked 仅代表指定来源/窗口检查，不保证全网无遗漏；受限来源可能使结论变窄。未选择进入短正文的候选须有排除理由，压缩不允许缩窄六类核心扫描。通用晨报报价能力与普通无报价短新闻仍保留原流程。

## 冻结内容 SHA256

| 文件 | SHA256 |
| --- | --- |
| morning-note/SKILL.md | 53f2f48fcf6d4dda2760fa0b8a8faf8695e15d7fd33bbb4efca571fb0b5fc44d |
| news-digest/SKILL.md | 8f62e71c978fde918014e9c43542fe9ca36a3ad089f2d0add9410edd3067ec29 |
| macro/commands/morning.md | b721edd57cc68906b01324bebfd1e4f272dccff595eee248001bb53edca37237 |
| morning-note/references/executive-brief.md | 20db787d5597298b1825b1029e11e1cd50d1c66777b31958224960df8b7830f2 |
| docs/validation/morning-note-fixtures.json | 8789b8c0add6bd74faf65a9e1f61b7508293b612c726179586e12ac821cf8239 |
| docs/automation/morning-note-prompt.txt | eb5ba3adea432ee2d940ed7213fe58b33df19a5dbddc6b360451c55b708174f7 |
