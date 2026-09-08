---
name: merge-check
description: 检查当前开发分支是否基于最新 main；未包含最新 main 时先 rebase，已包含则不重复操作，不自动 push 或合并。
---

# merge-check

确保当前开发分支基于最新 main：先检查提交关系，未包含最新 main 时执行 rebase。用户请求本流程时，检查和必要的 rebase 属于同一任务；沿用已有授权，不重复询问。用户明确要求“只检查、不修改”时，只报告差距。

## 检查与同步步骤

1. 读取项目约定，确认目标仓库、远端与 main 分支；默认使用 `origin/main`。检查 `git status --short --branch`，记录当前分支与 HEAD。当前为 main、detached HEAD、工作区不干净或处于 merge/rebase 中间状态时停止并报告；不自动 stash、清理或切换分支。
2. 成功执行 `git fetch origin` 后，解析并记录 `BASE_SHA=$(git rev-parse --verify 'origin/main^{commit}')` 与 `HEAD_SHA=$(git rev-parse --verify 'HEAD^{commit}')`。fetch 或引用解析失败时报告“无法确认最新 main”，不得拿旧缓存宣称检查通过。
3. 使用固定提交检查包含关系：

   ```bash
   git merge-base --is-ancestor "$BASE_SHA" "$HEAD_SHA"
   ```

   - 返回 0：当前提交已包含本次获取的最新 main，无需 rebase；功能分支可以有自己的额外提交，不要求两个 SHA 相等。
   - 返回 1：当前提交未包含该 main，进入 rebase 步骤；用户明确只读时则报告需要同步并结束。
   - 其他返回值：检查出错，停止并报告原因，不当作“需要同步”或“通过”。

4. 需要 rebase 时，先确认当前分支、HEAD 和干净工作区仍与检查时一致，再执行 `git rebase "$BASE_SHA"`。遇到冲突或其他失败立即停止，报告状态与冲突文件；不跳过提交、强行继续或覆盖用户改动。
5. rebase 成功后重新记录 HEAD，确认工作区干净、分支未变且 `git merge-base --is-ancestor "$BASE_SHA" HEAD` 返回 0。已包含基线而未执行 rebase 时，也确认 HEAD 未被并发改变。任一检查失败都不能报告同步成功。

## 结果与职责边界

- 报告当前分支、`BASE_SHA`、同步前后 HEAD、是否执行 rebase 及结果。没有需要同步的提交时直接报告“已基于本次获取的最新 main，无需 rebase”。
- “基于最新 main”按最新 main 是否为当前 HEAD 的祖先判断，检查的是当前基线关系，不追溯分支最初创建日期。检查后 main 仍可能更新。
- 本流程不自动 push、merge 或删除分支。rebase 后推送须沿用单独的 push 授权与项目安全流程；仅同步分支不附带推送。
- rebase 成功不等于测试通过或可合并。合并到 main 由 `merge-to-main` 完成版本绑定验证与合并前复核；不得用同步成功替代合并门禁。
