# 解锁窗口核验：实现验证

实施提交：`86650fecab0c82572722a838c61fcf1847c9f639`。基线：`3cecdc25021419e8d947697b28f7768b903e78e4`。仅三个有效规则/入口文件修改；本记录及相邻材料是验证证据，不是运行时采集程序。

## 重要证据更正

批准方案保留了审查时的原始正文及指纹。方案第 12 行所称 ENA Foundation 分项来自展开 tooltip 的 DOM；后续截图确认该区域有登录模糊遮罩，因而不是可接受的公开字段证据。方案中的这一调查描述由本记录及更新后的共享规则样本更正：**公开卡片未给接收方，展开分项受限，FAQ 仅为待核线索，不能认定已核实的 Foundation/Core Contributors 冲突。** 不改写已批准方案的历史指纹，也不在有效规则中沿用错误事实。站内字段差异仍由 E 案例中设定为公开的合成字段验证。

原日历的 SUI 漏采与 ENA 接收方结论也已更正；其他事件保留原核验截止，未将本次操作冒充全日历重跑。

## 实际内置浏览器核查

2026-09-30 北京时间下午通过 `iab` 实际操作，两站网页而非隐藏接口；资料反映当次可见状态，不保证之后数值不变。

- 窗口：北京时间 `[2026-10-01 00:00, 2026-10-15 00:00)`，即 10/1–14 含末日。UTC 为 `[2026-09-30 16:00, 2026-10-14 16:00)`。
- [DefiLlama SUI](https://defillama.com/unlocks/sui-foundation)：连续读 59、60、61、62/147 页，事件升序且相邻页一致。59 页为 UTC 9/1，62 页为 UTC 10/31；两侧边界之间 60–61 页均读。60 页 UTC 9/30 16:02 Mysten Labs Treasury 2.07M、17:56 Community Reserve 4M；61 页 UTC 10/1 19:19 Early Contributors 7.37M、21:51 Stake Subsidies 7.35M。北京时间分别 10/1 00:02、01:56，10/2 03:19、05:51；互不重复的四项模型 cliff 小计 20.79M，纳入 Stake Subsidies。仅这个公开 cliff 组件目标范围已检查，不声称覆盖受限数据/其他类型。Notes 明示由官方图表近似建模，分钟级时间不是官方精确安排。
- [Tokenomist SUI](https://tokenomist.ai/sui)：真实字段加载后公开 Upcoming 卡片 10/1、13.26M、3 Allocations、0.32% of released supply、Pending verification，Version 9 更新时间 2025-07-01。展开 tooltip 后截图可见登录模糊遮罩，即使 DOM 可读也不引用受限数量/分组/UTC。覆盖：卡片已读，分项受限；与 DefiLlama 四项窗口小计未完成匹配，不认定同事件数量冲突。
- [DefiLlama ENA](https://defillama.com/unlocks/ethena)：1–6 页公开 Unlock Events 实际全部读取。包括 2024–2026 历史周速率变化，例如 2026-04-05 Ecosystem 12.58M ENA/week、2025-04-05 Investors 17.97M/week 与 Team 21.56M/week。Notes 使用项目 2024 CSV 与空投估计。全部速率节点页已读并不证明 10/2 单次 cliff 或窗口累计释放覆盖；不从这些周速率外推总量，不据此宣布无事件。
- [Tokenomist ENA](https://tokenomist.ai/ethena)：公开 Upcoming 卡片 10/2、40.63M、1 Allocation、0.45% of released supply、Pending verification，Version 9 更新时间 2026-09-29；未提供接收方或可核实的卡片时区。展开 tooltip 截图确认登录遮罩，不使用其 DOM 字段。公开 FAQ 指向 Core Contributors，仅是待核线索；不能与受限字段构成已核实冲突。读到页面并不等于取得完整事件日历。
- [Sui 官方](https://www.sui.io/token-schedule)：读取正文说明曲线为估计，释放安排与基金会部署计划有关，不能裁定精确分项字段。
- [Ethena 官方](https://docs.ethena.fi/overview/ena/tokenomics)：读取正文给出贡献者/投资者一年 25% cliff、之后三年月度归属，自 2024-03-05 TGE 起算；这些通用计划不确认 2026-10-02 精确数量/接收方或实际执行。

本次验证没有取当前行情、计算实际当前流通比例、解除登录/付费遮罩、访问隐藏接口、确认链上执行或部署代码。

## 初轮静态检查（原基线与实施文件指纹）

实施 subagent 与 root 均确认：

- `git diff origin/main...HEAD --check` 与实施提交的 cached whitespace 检查通过。
- Ruby 标准库 `YAML.safe_load` 解析两个入口 frontmatter，检查字典结构、description 及相应 name/allowed-tools 字段类型，通过。
- Python 标准库逐个检查三文件全部 33 个 Markdown 链接：相对路径存在、HTTP(S) URL 有合法主机，通过。未声称对所有外链做在线可达性测试。
- 三文件 LF、UTF-8 及批准方案 9,853 字节/SHA256 保持不变，通过。
- 通用 `quick_validate.py` 因环境缺 PyYAML 无法启动（`ModuleNotFoundError: No module named 'yaml'`），没有运行成功，没有安装依赖。上面是实际执行的替代检查，范围仅覆盖此次入口结构、链接与内容卫生，不宣称完整复制通用验证器所有规则。

| 文件 | UTF-8 bytes | SHA256 |
|---|---:|---|
| `commands/catalyst.md` | 7327 | `3c09a80dadbb16dc234e434973ad8c0abd6dee14e617022c69ff9a52d62e714d` |
| `skills/catalyst-calendar/SKILL.md` | 10136 | `576863727004aae2ae90bcf6ca129ce329fdba5be87b7072dcca6196c6debdf9` |
| `references/token-unlocks-browser.md` | 12972 | `965533de95717e41efcaabef3ed939fd330de5e4ce514d042ecb472b8ee7f6dd` |

以上路径均在 `jdy_finance_skills/macro/` 下，对应共享规则完整路径为 `skills/macro-dashboard/references/token-unlocks-browser.md`。

## 独立行为验证

独立 subagent 只收到更新后的共享规则、九例原始合成材料及可读关联页；未收到预期答案、方案、原日历、调查记录或其他 agent 结论。没有公网、仓库写入或提交权限。原始材料归档于 [fixtures](2026-09-30-catalyst-unlock-behavior-fixtures.json)，其中 pages map 保存验证时的独立页文件，可按 key 还原；结果归档于 [独立结果](2026-09-30-catalyst-unlock-behavior-results.md)。这些案例验证规则应用行为，不是自动化浏览器回归测试，也不能保证所有未来模型都遵守规则。


root 依据原始材料独立复核结果，九例满足本次验收：

| 案例 | 已验证的实际行为 |
|---|---|
| A | 连续双向补页、起点纳入/终点排除、不重复；300 TOK 窗口数量与同窗口源一致，明确窗口前5000分母，6%累计筛选；官方确认限于明示字段。 |
| B | 补采可读缺页后500 TOK；有效起点与右边界代替两侧范围外记录，未因初始屏缺项认定冲突。 |
| C | Premium/示例行排除；匹配Team100可比较，但缺第二接收方，未冒充完整卡片/窗口总量。 |
| D | 历史70 TOK/week不外推10月总量；已读40 TOK单次cliff线索保留，不误判冲突。 |
| E | 结构化事件40 TOK跨站一致，同时保留合成材料中设定为公开的卡片Foundation/FAQ Team站内字段差异，未升级跨站冲突。 |
| F | 同事件F1数量40/50冲突待核，不平均、不选值、不由官方估计图裁定。 |
| G | 日期精度/未知时区保留边界待核，不套图表UTC；翻页返回旧页判采集失败，Fetching空表不作零。 |
| H | 确认生效、已加载的两源筛选组件零结果，可记组件范围0，不外推全项目或链上零活动。 |
| I | 加载失败与登录限制分开；两站未取得明确无法核实，不填零。 |

被测agent也指出端点最低证明格式、项目筛选粒度、展开完整性的记录格式等实采界限。规则已要求有效加载、控件状态、项目/窗口和相关分项读取；本次不新增通用分页框架。A/B/H原始材料的loaded/全行/筛选声明属于合成给定证据，不能充当真实浏览器截图的替代。G重复读文件不是刷新浏览器，G-b/I-a未提供新状态，结果没有虚构重试。九例通过不等于运行时自动化或所有未来执行者保证。


## 最新 main 同步后的验证

审查期间 main 合并 PR30，推进至 `a5ff9d27922cbba72bb91b07dd0143266ab945c0`。本分支从干净状态无冲突 rebase 到这一固定基线，保留其 catalyst 技能第16行的 CoinGecko/Binance 共享失败处理路由。同步后的阶段 HEAD 为 `4b053210b34dacdb370b2fc29795bdd239ecaa71`；最终 HEAD 会在固定审查包及 PR 正文中另行绑定，旧 HEAD 的 LGTM 不能自动当新版本批准。

- 重新执行两个入口 Ruby YAML/schema、全部33链接、UTF-8/LF、方案原指纹与 `git diff a5ff9d2...HEAD --check`；全部通过。固定新 main 是当前 HEAD 的祖先。
- command 与共享解锁规则字节未变；catalyst 技能因保留 main 的行情段变成 10,325 bytes，SHA256 `7cc18ac9f6b2434da3c10acec5a5e6f57f7478413878395cc6b6c69b45eedcc0`。上表是初轮指纹，不能冒充同步后的技能指纹。
- root 阅读最新共享行情规则及同入口整合内容：行情连接/追加预算/等待要求针对行情请求；解锁网页仍走原公共浏览器规则。没有当前价格需求时无需拉行情，重算当前美元估值才走行情规则；解锁数量比较与价格告警不混用，两条路径兼容。
- 九例原始材料和盲测结果、共享解锁规则、命令入口字节不变，原行为结果对这些未变内容复用；没有声称在本阶段重新实测网页或重跑盲测。因 main 改变了同入口，最终 Pro 审查仍需阅读整合后的完整技能及相关行情规则背景。
