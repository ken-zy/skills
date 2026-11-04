# 工作表和审核记录

`/Users/jdy/.codex/skills/jdy-whiteboard-video` 是指向 `/Users/jdy/Documents/skills/jdy-whiteboard-video` 的符号链接，两处是同一份文件；改动只需改实际目录。

初始化命令：

```sh
python3 /Users/jdy/.codex/skills/jdy-whiteboard-video/scripts/init_episode.py --output /你的项目/docs/videos/新集ID --title '新视频标题'
```

输出 `episode.json`、空 `narration.txt`、带字段头的 `storyboard.csv` 以及素材目录。空文件表示尚未创作，不是已完成稿。脚本不调用云服务，不修改旧工程。写入任何文件之前，它从输出路径的输入形式和真实路径（解析软链接后）两边逐级向上查找所有 `docs/videos/PROTECTED.json`；`--protected <清单>` 只追加清单，不替代查到的清单。任一清单判定输出落在受保护路径内（用真实路径和输入形式两种形式比较）即拒绝；任一清单损坏（悬空软链接、无法解析、`schema_version` 不是 1、`protected`／`files` 不是列表、路径不是相对路径或含 `..`、`sha256` 格式不对）也拒绝；未知字段不拒绝。输出路径含 `..` 段、目录已存在、标题为空同样拒绝。拒绝时输出“拒绝建集: 原因”，退出码 1，不留下任何文件。清单格式见 [工程参考与保护](reference-engine.md)。继续已有集直接读取文件，不重复初始化。

## episode.json

- `schema_version` 为 1；`title` 是本集标题。
- `state` 为 `draft`、`final` 或 `provisional_final`。后两者只在用户明确决定后填写，修订须建立新的同级目录。
- `voice` 只记录 Voice Studio 调用与交付选择。初始化的 `voice_config` 为null，不能隐式落回任何声线；从用户当前选择／声音项目记录填入实际ID或配置路径，记录选择证据。完整交付音轨登记为 `narration_audio` 资源（`path`＋`sha256`），列 `params.json`、`manifest.json`、实际朗读输入依赖并核对哈希；声音能力与参数由声音项目维护，详见 [Voice Studio接口](voice-interface.md)。
- `subtitles` 是本集唯一字幕：`path`（默认 `subtitles.srt`）和 `sha256`。镜头表排定后切一次字幕，把 `make_srt.py` 打印的值填入 `sha256` 即锁定（为空表示还没切）；之后确需改字幕的做法见 [制作方法](production.md)。烧入前用它核对；样片和成片的 `dependencies` 也登记这个文件和哈希。
- `source_policy` 默认“以用户提供的内容为准”，不另查、不核查；仅当用户要求补查时写明范围。
- `character_ids` 与 `keyframe_ids` 列本集使用的全部固定角色和关键镜头资源 ID；不要因不想等审核而漏列角色。没有人物的解释板可以没有角色，整片至少有一个关键镜头。
- `known_issues` 是问题列表。暂定定稿记录用户保留的问题，不自动清空。短样选择、完整听审和质量稳定性分开记录；被后来反馈否定的版本更新为待修改，不把历史认可、旧B或同输入复现写成当前音质已通过。
- `resources` 登记每项可审核文件。全部路径相对本集目录；批准的外部参考需要复用时，将对应文件复制到新集，并保留原审核证据，不指向旧集可写路径。私有本人参考录音、模型和训练日志仍留在 Voice Studio，不复制到视频素材库或Git；本集只保存已授权交付的音轨与不含私密内容的参数清单。

定稿时`resources`只列当前采用的版本；已弃用的试验或拒绝成片可移到`historical_resources`保留原路径、哈希与否定意见，文件也保留。不把旧版改成approved来通过门槛，不把当前实际使用但未通过的资源移到历史来绕过审核。最终清单绑定选定成片、旁白、实际混音、字幕、工程和素材依赖；播放倍速单独登记，不当作已重新导出该速度的媒体。

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

## 图稿与实现对应

每个首次出现的画板对象都应对应具体确认图稿，可沿用本项目对象清单格式；登记图稿路径、SHA、对象区域／裁切和对应审核资源。显著展示具名人物与相关物品，简单日历、箭头、数字等不跳过图稿。动态资源依赖列实际采用的图稿、笔顺标注／路径、手部、已验收音轨、镜头表、SRT与字体样式；完成帧与确认来源比对。`check_episode.py`只验证声明内容，不自动判断对象是否漏列或图稿是否覆盖齐全。

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

新建集的 `voice.owner` 为 `Voice Studio` 时，`sample/full/final` 还会拒绝空的配置选择；`plan` 允许待选。这个检查不解析或批准声音参数，交付与实际选择的匹配仍按声音接口核对。旧集未声明该owner时保留兼容，不据此默认为任何声线。

此工具为只读门槛检查，不生成审批、不验证是否真的收到用户意见、不解码媒体、不判断笔声可闻性，也不能识别工作表里漏列的角色。Agent 仍须核对聊天证据及真实画面、完成音视频验收，并遵守用户当次授权。

`storyboard.csv` 用于沟通和排时，不是现有 renderer 已支持的输入格式。每行只写一个对象或一句旁白；画面规划时先逐句写好旁白行，秒数留空；对齐词时间后排镜头表时再填写。时间列均为从片头起的非负有限秒数。

| 字段 | `row_type=line`（一句旁白） | `row_type=object`（一个画板对象） |
| --- | --- | --- |
| `shot_id` | 所属镜头 | 所属镜头 |
| `row_id` | 必填，本句的 id（如 `L3`），全表唯一 | 可选（如 `O5`） |
| `line_id` | 不填 | 必填，所属旁白行的 `row_id` |
| `text` | 这句旁白原文，`\|` 为强制字幕断点 | 对象名称（如“袁世凯”“电报”） |
| `audio_start` | 这句开始 | 旁白真正提到它的时刻 |
| `audio_end` | 这句结束 | 留空（截止时间取所属句子的 `audio_end`） |
| `draw_start`／`draw_end` | 本句自身的新绘制起止，可留空或写 `none` | 第一笔与最后一笔（必填） |
| `recognizable_at` | 不检查 | 外轮廓画完、观众可认出的时刻（必填） |

其余列 `character_ids`、`keyframe_id`、`transition`、`pen_sound`、`note` 供沟通。字幕不进镜头表：镜头表排定后由旁白行（含 `|`）和词时间切一次 `subtitles.srt` 并锁定，最后原样烧入（见 [制作方法](production.md)）。缺 `row_id`／`line_id` 等列的旧表须改成新格式，否则检查报“未完成”。样片是整条旁白中从 T0 开始的连续一段，镜头表时间为整片时间减 T0，以样片自身的 0 秒为起点。新片不必照抄首片的段落结构。

## 交付与声音接口

样片截取需同时覆盖完整旁白句子和首个受审对象的绘制，不能从完整礼帽等已经画完的时刻才开始。字幕默认苹方SC常规、无描边／底栏／分隔线，记录实际字体face、字号、位置和使用的烧字实现；仅文字版式变化不重切已锁定字幕。

白板只输出绘画事件时点并调用 Voice Studio 的实际音轨交付，不登记白板自行实现的滤波／调速／合成配乐为默认管线。换旁白时间轴后重做词时间、镜头与字幕；只换混音须证实时点未变才可复用。交付报告说明步骤、版本、已查／未查、真实审核与下一节点，提供可播放文件，验证播放器功能不等于声音或整片已通过。

## 节奏检查

排镜头表时先只给 `--storyboard` 跑一次（没有视频，视频项记为未检查，看各行有无错误）；样片和整片阶段都必须连同视频运行，`--video` 用烧字幕之前的无字幕视频，结果随样片／成片提交：

```sh
python3 /Users/jdy/.codex/skills/jdy-whiteboard-video/scripts/check_timing.py --storyboard /本集目录/storyboard.csv
python3 /Users/jdy/.codex/skills/jdy-whiteboard-video/scripts/check_timing.py --storyboard /本集目录/storyboard.csv --video /本集目录/render/样片-无字幕.mp4 --stage sample
python3 /Users/jdy/.codex/skills/jdy-whiteboard-video/scripts/check_timing.py --storyboard /本集目录/storyboard.csv --video /本集目录/render/成片-无字幕.mp4 --stage full
```

- 镜头表（`--storyboard`）逐行检查：
  - 时间值必须是非负有限秒数；`nan`、`inf`、负数、非数字都报错。
  - 旁白行：`audio_start` < `audio_end`；有自身绘制时 `draw_start` < `draw_end` ≤ 本句 `audio_end`。不对旁白行算 1.5 秒。
  - 对象行：`draw_start` < `draw_end`（相等即“直接出现”，报错）；`draw_start` ≤ `recognizable_at` ≤ `draw_end`；`recognizable_at - audio_start` ≤ 1.5 秒（从真正提到它的时刻算，允许提前画）；`audio_start` 在所属句子（`line_id`）的 `audio_start`～`audio_end` 之内；`draw_end` ≤ 所属句子的 `audio_end`。`line_id` 缺失、指向不存在的句子或指向对象行都报错。
  - 非空 `row_id` 全表唯一（旁白行和对象行一起算），重复即报错。
  - 任何一行的时间超过视频流结束（容差 0.1 秒）即报错；需同时给 `--video`。
  - 相邻绘制之间空隙超过 3 秒记警告（以视频静止检测为准）。
  - 缺列（旧格式）、空表、时间格为空：记为“未检查”，状态为“未完成”；`full` 阶段同时记错误。
- 视频（`--video`）：调用 `ffmpeg -i <视频> -map 0:v:0 -vf freezedetect=n=0.003:d=3 -f null -`，逐条报告超过 3 秒的静止起点（mm:ss.s）和时长。静止持续到片尾时，用 `ffprobe` 读出的视频流结束时间（不是容器时长）计算；读不到时报“时长未知”，归入未检查。没有 ffmpeg 或运行失败时报告“未运行”，不算通过。
- 局限：静止检测比较整幅画面，所以要在烧字幕之前跑；手在动仍可能掩盖画板实际没在画，不能代替人工看片。
- 门槛可用 `--max-recognize`、`--max-static`、`--freeze-noise` 调整，默认 1.5／3／0.003；必须是正的有限数（噪声小于 1），否则不运行。放宽门槛须经用户同意，比默认宽时输出警告。
- 输出 JSON：`status`（`passed`／`failed`／`incomplete`）、`passed`、`checked`（已检查项）、`unchecked`（未检查项）、`errors`、`warnings`、`video`（含静止列表和视频流结束时间）、`scope`。退出码：通过 0，失败 1，未完成 3；只有 0 才算通过。
- 只报告不改片、不改任何文件，不代替人看片：有意的静止画面也会被列出，按硬门槛应改；确需保留由用户决定。
