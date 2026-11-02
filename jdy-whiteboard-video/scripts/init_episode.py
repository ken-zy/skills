#!/usr/bin/env python3
"""Create an isolated episode scaffold; standard library only, never overwrite."""
import argparse
import hashlib
import json
from pathlib import Path

PROTECTED = Path('/Users/jdy/Code/ai-ip-business-plan/docs/videos/01-01-republic')


def create(output, title):
    output = Path(output).expanduser().resolve()
    protected = PROTECTED.resolve()
    if output == protected or protected in output.parents:
        raise ValueError('首片是只读参考，不能在其中创建新集。')
    if output.exists():
        raise ValueError('目录已存在；继续已有集请先读取记录，新版本请使用新的同级目录。')
    if any((p / 'episode.json').exists() for p in output.parents):
        raise ValueError('不能在已有集内嵌套新集；请选择新的同级目录。')
    if not title.strip():
        raise ValueError('标题不能为空。')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.mkdir()  # atomic refusal if another process created it
    for folder in ['sources', 'audio', 'art', 'render', 'reviews']:
        (output / folder).mkdir()
    (output / 'narration.txt').write_text('', encoding='utf-8')
    (output / 'storyboard.csv').write_text(
        'shot_id,narration_segment,concept,objects,character_ids,keyframe_id,'
        'audio_start,recognizable_at,draw_end,hold_end,transition,pen_sound,avatar_layout\n',
        encoding='utf-8')
    data = {
        'schema_version': 1, 'title': title, 'state': 'draft',
        'source_policy': '按本集用户要求确定来源与核查范围',
        'voice': {'mode': 'inherit-yunxi-unless-user-specifies',
                  'voice_id': 'zh-CN-YunxiNeural', 'rate': '+10%',
                  'note': '继承配置，不继承上一集音频；本人声线按用户当前要求处理'},
        'character_ids': [], 'keyframe_ids': [], 'known_issues': [],
        'resources': [{
            'id': 'narration', 'kind': 'narration_text', 'path': 'narration.txt',
            'sha256': hashlib.sha256(b'').hexdigest(), 'dependencies': [],
            'review': {'status': 'pending', 'reviewed_sha256': '', 'evidence': ''}
        }],
    }
    (output / 'episode.json').write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    parser.add_argument('--title', required=True)
    args = parser.parse_args()
    try:
        print(create(args.output, args.title))
    except (ValueError, OSError) as exc:
        parser.exit(1, f'{exc}\n')
