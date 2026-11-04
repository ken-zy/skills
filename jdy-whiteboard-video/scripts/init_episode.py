#!/usr/bin/env python3
"""Create an isolated episode scaffold; standard library only, never overwrite.

Protection guards against mistakes, not deliberate bypass: every docs/videos/PROTECTED.json
found above the output (walking up both the path as typed and its real path), plus an
optional --protected manifest, is read before anything is written. All of them apply; if any
is broken or protects the output, nothing is created.
"""
import argparse
import hashlib
import json
import os
import re
from pathlib import Path, PurePosixPath

MANIFEST = Path('docs') / 'videos' / 'PROTECTED.json'
SHA256 = re.compile(r'^[0-9a-f]{64}$')
STORYBOARD_COLUMNS = ['shot_id', 'row_id', 'row_type', 'line_id', 'text', 'audio_start', 'audio_end',
                      'draw_start', 'draw_end', 'recognizable_at', 'character_ids', 'keyframe_id',
                      'transition', 'pen_sound', 'note']


class Refused(ValueError):
    pass


def expect(condition, message):
    if not condition:
        raise Refused(message)


def lexical(path):
    """Absolute path without following symlinks (the path as typed)."""
    return Path(os.path.normpath(os.path.abspath(os.path.expanduser(str(path)))))


def relative(value, where):
    pure = PurePosixPath(value) if isinstance(value, str) and value.strip() else None
    expect(pure is not None and not pure.is_absolute() and not value.startswith('~') and '..' not in pure.parts,
           f'{where}: path 须为相对项目根、不含 .. 的路径: {value!r}')
    return value


def load(manifest, root):
    """Read one manifest and check only what protection relies on; returns (manifest, root, data)."""
    expect(manifest.is_file(), f'保护清单不是可读文件（悬空软链接或目录？）: {manifest}')
    try:
        data = json.loads(manifest.read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        raise Refused(f'保护清单无法解析: {manifest}: {exc}')
    where = str(manifest)
    expect(isinstance(data, dict) and data.get('schema_version') == 1 and type(data['schema_version']) is int,
           f'{where}: schema_version 须为整数 1')
    expect(isinstance(data.get('protected'), list), f'{where}: protected 须为列表')
    for index, item in enumerate(data['protected']):
        at = f'{where}: protected[{index}]'
        expect(isinstance(item, dict), f'{at} 须为对象')
        relative(item.get('path'), at)
        files = item.get('files', [])
        expect(isinstance(files, list), f'{at}: files 须为列表')
        for j, entry in enumerate(files):
            expect(isinstance(entry, dict), f'{at}.files[{j}] 须为对象')
            relative(entry.get('path'), f'{at}.files[{j}]')
            expect(isinstance(entry.get('sha256'), str) and SHA256.match(entry['sha256']),
                   f'{at}.files[{j}]: sha256 须为 64 位小写十六进制')
    if root is None:  # --protected manifest outside <project>/docs/videos/
        expect(isinstance(data.get('project_root'), str) and Path(data['project_root']).is_absolute(),
               f'清单不在 <项目>/docs/videos/ 下，且没有绝对路径 project_root: {manifest}')
        root = Path(data['project_root'])
    return manifest, root, data


def create(output, title, manifest=None):
    expect('..' not in PurePosixPath(str(output)).parts,
           f'输出路径不能含 .. 段，请写出完整目录: {output}')
    typed = lexical(output)
    real = typed.resolve()
    forms = {typed, real}

    # 1) read every applicable manifest before any write; --protected only adds
    entries = [(folder / MANIFEST, folder) for start in (typed, real) for folder in [start, *start.parents]
               if os.path.lexists(folder / MANIFEST)]
    if manifest:
        given = lexical(manifest)
        under_docs = given.parent.name == 'videos' and given.parent.parent.name == 'docs'
        entries.append((given, given.parents[2] if under_docs else None))
    seen, loaded = set(), []
    for path, root in entries:
        if (path.resolve(), root) not in seen:
            seen.add((path.resolve(), root))
            loaded.append(load(path, root))

    # 2) any manifest protecting the output (typed or real form) refuses
    for path, root, data in loaded:
        for item in data['protected']:
            for rel in [item['path']] + [entry['path'] for entry in item.get('files', [])]:
                target = lexical(root / rel)
                for form in forms:
                    if any(t == form or t in form.parents for t in {target, target.resolve()}):
                        raise Refused(f'{rel} 在保护清单 {path} 中为只读，不能在其中创建新集。')

    # 3) generic guards
    expect(not os.path.lexists(typed) and not real.exists(),
           '目录已存在；继续已有集请先读取记录，新版本请使用新的同级目录。')
    expect(not any((p / 'episode.json').exists() for f in forms for p in f.parents),
           '不能在已有集内嵌套新集；请选择新的同级目录。')
    expect(title.strip(), '标题不能为空。')

    # 4) write
    real.parent.mkdir(parents=True, exist_ok=True)
    real.mkdir()
    for folder in ['sources', 'audio', 'art', 'render', 'reviews']:
        (real / folder).mkdir()
    (real / 'narration.txt').write_text('', encoding='utf-8')
    (real / 'storyboard.csv').write_text(','.join(STORYBOARD_COLUMNS) + '\n', encoding='utf-8')
    data = {
        'schema_version': 1, 'title': title, 'state': 'draft',
        'source_policy': '以用户提供的内容为准；用户未要求时不另查资料或核查',
        'voice': {'owner': 'Voice Studio', 'engine': 'voice studio（jdy-voiceover）',
                  'voice_config': None, 'selection_evidence': '',
                  'note': '从用户当前选择或 Voice Studio 记录确定 voice_config，再显式调用；不回退默认声线。'
                          '本集只保存版本化交付音轨、参数和清单，完整听审后对齐；不继承上一集音频。'},
        'subtitles': {'path': 'subtitles.srt', 'sha256': ''},
        'character_ids': [], 'keyframe_ids': [], 'known_issues': [],
        'resources': [{
            'id': 'narration', 'kind': 'narration_text', 'path': 'narration.txt',
            'sha256': hashlib.sha256(b'').hexdigest(), 'dependencies': [],
            'review': {'status': 'pending', 'reviewed_sha256': '', 'evidence': ''}
        }],
    }
    (real / 'episode.json').write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return real


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    parser.add_argument('--title', required=True)
    parser.add_argument('--protected', help='额外的保护清单；只会增加保护，不会替代向上查找到的清单')
    args = parser.parse_args()
    try:
        print(create(args.output, args.title, args.protected))
    except (ValueError, OSError) as exc:
        parser.exit(1, f'拒绝建集: {exc}\n')
