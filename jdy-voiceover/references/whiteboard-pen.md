# 白板柔和笔声与混音

## 采用范围

用户在2026-11-05确认柔和笔声和完整影片，随后要求把该方案固定到skill，供以后白板视频复用。白板任务无另选音效时采用此预设；保留项目已有明确选择。认可的是固定原始纹理与这套处理的组合，不表示任意素材降低相同分贝都能得到相同听感。

声音制作由本skill使用Voice Studio环境完成，白板项目只交绘画事件并接收音轨。`voice speak`仍只负责旁白；以下是实际存在的独立辅助脚本，不虚构`voice mix`命令。它只输出旁白＋笔声，无既定配乐时不新增配乐；已要求的配乐需另由Voice Studio接入，不能静默丢掉。

## 固定预设

可执行配置：[whiteboard-pen-soft-v1.json](../assets/whiteboard-pen-soft-v1.json)。

| 项目 | 已确认值／做法 |
| --- | --- |
| 原始纹理 | Voice Studio管理的`approved/whiteboard-pen-soft-v1/source-texture.wav`，以配置中的SHA256钉住 |
| 频率处理 | 只对笔声做1800Hz、6阶Butterworth低通；周期扩展5份，双向滤波后截中间1份，避免纹理重复边界突变 |
| 笔声音量 | 相对上述**未经过本预设处理**的纹理降低6dB，不能对成品`pen-only.wav`再降一轮或反复低通 |
| 发声选择 | 原始单笔触时间先取48kHz样本区间；少于40ms的细笔触静音，不先合并碎笔再绕过门槛 |
| 起落 | 半余弦起音最多12ms、收音最多15ms，各不超过当前笔触样本数的三分之一 |
| 触笔同步 | 仅在选中笔触内发声；先处理纹理再截取／包络，滤波尾声不能漏到提笔区间 |
| 旁白 | 增益1，原始样本和时间轴不变；不重配、不滤波、不变速、不做自动归一化 |

失败经验：旧版给10,576个笔触全部发声，其中9,361个不足20ms，用户反馈“笔刷的声音太刺耳了”；认可版只为620个至少40ms的笔触发声。计数和总体响度来自该集，不应成为新片目标；有多少长笔触取决于实际绘画事件。频谱下降也不等于已经听审通过。

## 实际调用

使用Voice Studio已审核环境中的NumPy／SciPy／SoundFile，不安装模型或依赖。默认基准纹理留在Voice Studio，不复制到视频工程或Git；它缺失或哈希不符时报告缺口，不从其他声音素材悄悄替换。

```sh
/Users/jdy/Code/voice-studio/.local-voice/venv/bin/python \
  /Users/jdy/Documents/skills/jdy-voiceover/scripts/mix_whiteboard.py \
  --narration /所属项目/audio/已确认旁白.wav \
  --events /所属项目/绘画事件.json \
  --output-dir /所属项目/audio/新的混音版本
```

支持同参加`--dry-run`先核对。可加`--narration-sha256`和`--events-sha256`绑定本次验收输入。路径必须为绝对路径，输出父目录须存在，版本目录不得已存在。当前预设接受48kHz单声道PCM16／PCM24；不偷偷转换其他输入或缩放人声来避免削波。

事件沿用本次实际交付格式，片头为0，单位秒：

```json
{"contacts": [{"stroke_id": "实际笔画ID", "object_id": "实际对象ID", "start_seconds": 1.2, "end_seconds": 1.32}]}
```

`contacts`按时间顺序、不重叠、落在完整旁白时长内，不能用对象的大时间框代替真实触笔。输出`mix.wav`、`pen-only.wav`、`manifest.json`；需要MP3时从交付WAV编码另存，不再处理其音色或响度。脚本是本skill的声音实现，白板renderer不能复制后再维护另一套DSP。

## 验证与复用

- 验证整数PCM的混音分解、笔声在提笔／跳过细笔时为零、无削波、源文件哈希及旁白样本数不变。脚本遇到削波停止，不调低已确认人声。
- 新内容直接使用预设，不重新做声线或参数海选；完整音轨仍随最终编码样片和整片审核。若改素材或参数，先做同段原版／候选对照，明确新候选，保留用户对旧版的否定记录。
- 只改混音且旁白时间轴未动：视频侧可复用词时间、锁定字幕与视频流；用实际样本数、哈希和解码检查证明，而不只写“仅改混音”。
- 用户说试听1.25倍速且不要重新出视频，只设置播放器`playbackRate`；不把倍速烘焙进音轨，也不将该集的播放速度推广为所有新视频的默认。

## 基准证据（只读）

- 原始处理实现与参数：`/Users/jdy/Code/voice-studio/.local-voice/experiments/republic-v3-pen-soft-20261104-v1/soften_pen.py`及`manifest.json`，不直接复跑旧输出目录。
- 原始纹理来源与裁切区间：Voice Studio `approved/whiteboard-pen-soft-v1/source.json`；素材是原始片段，不含任何人的参考录音。
- 用户确认：`/Users/jdy/Code/ai-ip-business-plan/docs/videos/01-01-republic-v3/reviews/pen-soft-v1/pen-approval.json`及该集`FINAL.md`。生成清单里的`pending_user_pen_audition`是当时导出状态；后来确认记录独立保存，不改冻结文件来伪装当时已通过。
- 已确认混音SHA256：`c10815d13ac513c9df70976bfa54629e58acb6868874f1e73f26d9d6432c3d6b`。该文件只用于回归验证，不将其整个旁白或笔声轨用作下一集的循环纹理。
