---
name: merge-to-main
description: Use when merging the current feature branch into main. Synchronize with the latest main and validate the resulting revision before either a GitHub PR merge or an explicitly authorized local merge.
---

# merge-to-main

将当前分支合并到 main。两条路径都必须先基于最新 main 完成验证；验证失败、缺失或过期时不得合并。

流程：确认目标和授权 → 同步 main → 验证 → 合并前复核 → 合并 → 核实结果。

## 1. 前置检查与路径选择

- 读取目标仓库的 Agent 指令、测试与合并门禁。沿用当前会话已有授权；本 Skill 不额外授予 rebase、push、merge、删除分支或修改 GitHub 规则的权限。
- 检查 `git status --short --branch`。工作区须干净、当前须为功能分支；main、detached HEAD 或未完成的 merge/rebase 均停止。保留用户和并发改动。
- 确认目标仓库、远端与目标分支。以下示例以 `origin/main` 为目标；PR 必须属于已确认的仓库、base 为 main，head 对应当前分支及其来源仓库，避免误选同名分支。
- 查询 PR 时保留错误输出。找到唯一 open PR 才走路径 A；查询失败或结果不明确时停止，不能当作“没有 PR”。成功查询确认无 PR 时，只有仓库规则或用户明确允许本地合并才走路径 B，否则报告缺少 PR。
- 执行下列步骤时逐步检查结果；任何命令失败都不得继续执行后续写操作。

## 2. 共同步骤：同步最新 main 并验证

`merge-check` 负责检查当前分支是否包含最新 main，未包含时先 rebase，已包含时不重复操作，也不自动推送。本 Skill 复用其 fetch、固定 SHA 祖先判断与必要的 rebase 方法，并按下列顺序完成验证、推送及合并。基线已同步不能替代验证或合并前复核；需要改写已发布分支时，须先完成下列远端 head 记录与提交包含检查，再 rebase。

1. 成功执行 `git fetch origin`，记录 `BASE_SHA=$(git rev-parse origin/main)`。若需要更新已发布的功能分支，在 rebase 前记录其远端 head，并确认本地已包含远端提交；否则停止，不能覆盖远端独有改动。保留该 head 供后续明确的 lease 检查使用。
2. 检查 `git merge-base --is-ancestor "$BASE_SHA" HEAD`。返回 0 表示已包含最新 main，不做无意义的 rebase；返回 1 时，在已有授权范围内执行 `git rebase "$BASE_SHA"`；其他错误停止。冲突时停止并报告，不跳过提交或强行继续。
3. 再次确认上述祖先检查成功，记录 `VALIDATED_HEAD=$(git rev-parse HEAD)`。
4. 针对该版本执行仓库要求的测试、lint、构建及改动相关验证。记录 `BASE_SHA`、`VALIDATED_HEAD`、验证命令与结果。rebase 前的通过记录不能代替本次验证；“没有冲突”也不是验证通过。
5. 验证后确认 HEAD 仍为 `VALIDATED_HEAD` 且工作区干净。代码变化、验证失败、必要环境不可用或必需检查未运行时停止，不进入合并。

## 3. 路径 A：GitHub PR 合并

1. 如 PR head 尚未对应 `VALIDATED_HEAD`，在已有 push 授权范围内更新准确的 PR 来源分支。改写已发布历史时使用绑定 rebase 前远端 head 的 `--force-with-lease=<ref>:<expected-sha>`，不能覆盖别人新推送的提交；不得向 main 强推。
2. 重新读取 PR，确认 open、非 draft、base 为 main，且 `headRefOid` 等于 `VALIDATED_HEAD`。等待该版本的必需 CI 和仓库要求的其他检查通过；旧 head 的绿色结果不能复用。对 PR 合成提交运行的检查，应确认其对应当前 head/base。必需检查缺失、仍在运行或失败时不得合并。
3. 不把分支保护或 ruleset API 查询作为合并前置；这些接口的套餐限制或 403 不阻止已授权且验证通过的普通 PR 合并。
4. 提交合并请求前执行第 5 节复核，再按仓库允许的方式合并。例如允许 merge commit 时：

   ```bash
   gh pr merge "$PR" --merge --match-head-commit "$VALIDATED_HEAD"
   ```

   `--match-head-commit` 锁定 PR head，不锁定远端 main。禁止使用 `--admin` 绕过检查。若合并请求被 GitHub 拒绝，读取实际原因；需要同步时返回第 2 节，不强行重试。若 GitHub 明确要求 merge queue，按其队列流程提交；入队不等于已合并，须等队列检查通过并核实最终状态。

## 4. 路径 B：明确允许的本地合并

1. 必须已完成第 2 节全部验证以及第 5 节复核。切换前记录功能分支名；切到 main 后，只允许快进同步，且确认本地 main **恰好等于 `BASE_SHA`**。本地 main 有额外提交或目标已变化时停止，不把未验证内容一并合入。
2. 合并已验证的固定版本，而非可能被并发更新的分支名：

   ```bash
   git merge --no-ff "$VALIDATED_HEAD" -m "merge: $BRANCH into main"
   ```

3. 确认合并结果的文件树与 `VALIDATED_HEAD` 相同，工作区干净；记录 `MERGED_SHA=$(git rev-parse HEAD)`。若 hooks 等改变了文件树，不得复用旧验证。仓库若要求对最终 merge commit 另跑检查，完成后才能推送。
4. 推送前再次 fetch，确认 `origin/main` 仍为 `BASE_SHA`、本地 HEAD 仍为 `MERGED_SHA` 且工作区干净。随后仅普通推送固定提交：`git push origin "$MERGED_SHA:refs/heads/main"`。远端若在最后窗口新增了未包含的提交，非快进推送会被拒绝。
5. main 更新或推送被拒绝时，保留本地状态、报告原因。重新同步并验证后才可再次尝试；禁止为完成推送而把新 main 直接混入未验证结果，禁止强推 main 或重置用户工作。

## 5. 合并前复核与验收

合并请求或本地合并前，必须重新成功 fetch 并确认：

- `origin/main` 仍等于 `BASE_SHA`；本地 HEAD 仍等于 `VALIDATED_HEAD`，工作区干净；路径 A 的 PR head 也等于该值。
- 第 2 节验证成功，路径 A 的当前版本必需 CI 已通过。

main 或功能分支有变化时，旧验证失效，返回第 2 节同步并重跑要求的验证。版本未变且证据完整时复用本轮结果，不重复跑相同检查。持续并发更新导致无法完成时报告并暂停，不无限重试。

合并后核实远端实际结果：路径 A 确认 PR 为 MERGED 并记录 merge commit，路径 B 确认推送提交已进入远端 main。未完成时报告“等待 CI / 已入队 / 合并受阻”，不能报告成功。

仅在确认远端合并成功后，才按已有授权快进同步本地 main、清理本地分支；删除远端分支须有明确授权。最终报告目标、基线 SHA、已验证 head、验证结果与实际合并状态。

依据：[Merge queue](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/configuring-pull-request-merges/managing-a-merge-queue)、[gh pr merge](https://cli.github.com/manual/gh_pr_merge)。
