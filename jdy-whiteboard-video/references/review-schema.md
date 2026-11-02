# 工作表和审核记录

初始化命令：

```sh
python3 /Users/jdy/.codex/skills/jdy-whiteboard-video/scripts/init_episode.py --output /你的项目/docs/videos/新集ID --title '新视频标题'
```

输出 `episode.json`、空 `narration.txt`、带字段头的 `storyboard.csv` 以及素材目录。空文件表示尚未创作，不是已完成稿。脚本不调用云服务，不修改旧工程。继续已有集直接读取文件，不重复初始化。

## episode.json

- `schema_version` 为 1；`title` 是本集标题。
- `state` 为 `draft`、`final` 或 `provisional_final`。后两者只在用户明确决定后填写，修订须建立新的同级目录。
- `voice` 记录实际声线选择和参数；初始化的云希配置是继承建议，用户要求优先。
- `source_policy` 写本集的来源及是否核查要求；不要继承其他故事的特殊豁免。
- `character_ids` 与 `keyframe_ids` 列本集使用的全部固定角色和关键镜头资源 ID；不要因不想等审核而漏列角色。没有人物的解释板可以没有角色，整片至少有一个关键镜头。
- `known_issues` 是问题列表。暂定定稿记录用户保留的问题，不自动清空。
- `resources` 登记每项可审核文件。全部路径相对本集目录；批准的外部参考需要复用时，将对应文件复制到新集，并保留原审核证据，不指向旧集可写路径。

资源示例（字段值必须替换为实际文件和真实证据）：

```json
{
  "id": "style-current",
  "kind": "style_sample",
  "path": "render/style-v1.mp4",
  "sha256": "文件的实际SHA256",
  "dependencies": [
    {"path": "render/engine.py", "sha256": "生成样片时的代码SHA256"},
    {"path": "render/scene.json", "sha256": "生成样片时的配置SHA256"}
  ],
  "review": {
    "status": "pending",
    "reviewed_sha256": "",
    "evidence": ""
  }
}
```

`kind` 可选：`narration_text`、`narration_audio`、`character`、`keyframe`、`style_sample`、`avatar_sample`、`final_video`。角色板与关键镜头可以用图片或可读审核文件；实际出图仍要展示给用户。

SHA-256 可用 `shasum -a 256 文件` 读取。文件或其依赖修改后，不要更新旧审核的哈希来“让检查变绿”：先重新生成受影响产物、清除旧审核状态，再按需要让用户复核。样片和成片依赖应列实际使用的代码、配置、声音和素材；不能登记无关文件来敷衍检查。

`review.status` 初始 `pending`；用户要求修改可写 `changes_requested`；真实确认后写 `approved`，`reviewed_sha256` 填用户看到的文件校验值，`evidence` 写用户原意见、日期／对话回合或可核对记录。成片暂定定稿可用 `provisional`。已确认且文件相同的复用保留原证据，无须重问；不能沿用其他角色或不同声音文本的确认。

## 阶段检查

```sh
python3 /Users/jdy/.codex/skills/jdy-whiteboard-video/scripts/check_episode.py /本集目录 --stage full
```

| stage | 检查用途 |
| --- | --- |
| plan | 工作表及文件路径／哈希完整性，不要求审核完成 |
| sample | 声明的旁白文本、完整旁白音频、角色及数字人样片已获对应审核；允许待审关键构图及动态样片供本轮审核 |
| full | 文本、音频、人物、关键镜头、最终实现的动态样片及已使用数字人样片通过；关键镜头清单不能空 |
| final | 上述检查加定稿视频本身的确认、定稿状态和对应版本；暂定定稿须保留问题 |

此工具为只读门槛检查，不生成审批、不验证是否真的收到用户意见、不解码媒体、不判断笔声可闻性，也不能识别工作表里漏列的角色。Agent 仍须核对聊天证据及真实画面、完成音视频验收，并遵守用户当次授权。

`storyboard.csv` 用于沟通和排时，不是首片 renderer 已支持的输入格式。旁白尚未生成时，秒数留空；拿到实际音频后再填写。新片不必照抄首片十二段结构。
