# 工程参考与保护

本机参考项目：`/Users/jdy/Code/ai-ip-business-plan`。先检查实际存在；路径缺失时仍可用本 skill 组织流程，不伪称已有渲染后端，也不无提示地安装整套第三方项目。

## 只读参考入口

- `docs/2026-10-31-handdraw-video-production-workflow-v1.md`：首片流程和试错。
- `docs/videos/01-01-republic/README.md`：当前文件布局及清理记录。
- `docs/videos/01-01-republic/animation/portrait-calendar-v1/render.py`：人工语义路径样片；其 `remix-foley.py` 展示只替换音轨。
- `docs/videos/01-01-republic/animation/full-film-v1/engine.py`：骨架路径、局部揭示、手部合成；仍有笔画不顺问题。
- `docs/videos/01-01-republic/animation/full-film-v1/film.py`：首片专用对象、时间表和混音，并非加载通用 scene-plan.json 的引擎。
- `docs/videos/01-01-republic/synthesize-cloud-yunxi.py`：仅作语音编排参考，内含首片文本校验与样音复用，不直接运行来合成新文章。
- `docs/videos/01-01-republic/animation/whiteboard-v3/CREDITS.md` 和 `LEMO-LICENSE.txt`：复用相关实现时保留技术来源及许可。

本机声音工具使用过隔离安装的 edge-tts；不是本地语音模型。版本和服务可用性会变，按实际环境核查；不要把首片的免费调用或版本豁免变成长期保证。

## 适配新视频

1. 在新集目录开发。旧工程只读，先列需要的模块和素材，再复制必要依赖到新集内部；不要复制整个 1 月 1 日故事当已完成的新集。
2. 首片存在 `full-film → whiteboard-v3 → whiteboard-v2` 的导入，以及人物、持笔手、字体和声音路径依赖。导入可能加载旧图，缺配乐时的回退可能写旧样片 WAV。复制后逐一重定向读取／输出路径，禁止指向旧集可写路径。
3. 替换新旁白、分段、角色、镜头、字幕和所有语义时点；不得让新主题播放旧旁白。asset ID 与新故事一致。JSON 工作表是编排与审核记录，需要 Agent 实现适配代码，不是声称现有 renderer 已能消费这些 JSON。
4. 输出目录必须按版本新建，拒绝覆盖已有视频；预览也只能写新集目录。先用计划中的最终引擎做代表片段，经过用户审核再扩展。
5. 现有本机可用过 Python 3.14 的 Pillow／NumPy 环境；默认 python3 可能不是它。先探测已装解释器和 ffmpeg，不为导入失败立即重装或升级。辅助脚本只用标准库；实际渲染依赖需按机器政策核查。

## 保护首片

绝不原地运行首片的 `film.py` 或 `--preview-only`：两者会写回文件。只读查看、核对哈希允许。

首片定稿：`docs/videos/01-01-republic/animation/full-film-v1/jan01-full-v1.mp4`

SHA-256：`52a2cc166039c20fab3188431742c80d4a007d45c3c88a41640be9064e9adf9e`

如果这份文件的值不同，停止任何会触及旧片的工作，报告差异，不自动用旧版本覆盖。新集工作与该文件无关时继续在新目录制作。

制作 WAV 和中间文件已归档至项目 `.archives/jan01-video-2026-11-02/`，私有 GitHub 备份：
https://github.com/ken-zy/ai-ip-business-plan/releases/tag/archive-jan01-video-2026-11-02

正常新片不必下载归档或恢复旧音轨；确需读取时校验清单，解压到隔离目录，不回填旧定稿目录。用户本人声线和数字形象尚未接通，需另行验证。
