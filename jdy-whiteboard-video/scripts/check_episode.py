#!/usr/bin/env python3
"""Read-only approval and artifact integrity check; not an audiovisual reviewer."""
import argparse
import hashlib
import json
from pathlib import Path

KINDS = {'narration_text', 'narration_audio', 'character', 'keyframe',
         'style_sample', 'avatar_sample', 'final_video'}


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def check(folder, stage):
    root = Path(folder).resolve()
    data = json.loads((root / 'episode.json').read_text(encoding='utf-8'))
    errors = []
    if data.get('schema_version') != 1:
        errors.append('不支持的 schema_version')
    state = data.get('state')
    if state not in {'draft', 'final', 'provisional_final'}:
        errors.append('未知 state')
    if state != 'draft' and stage in {'sample', 'full'}:
        errors.append('定稿已冻结；修订须新建同级版本，不可继续覆盖本集')
    if stage == 'final' and state not in {'final', 'provisional_final'}:
        errors.append('尚未记录用户定稿或暂定定稿决定')
    # New handoffs must name the selected Voice Studio configuration; the
    # initializer deliberately leaves it unset rather than falling back to B.
    voice = data.get('voice', {})
    if stage != 'plan' and isinstance(voice, dict) and voice.get('owner') == 'Voice Studio':
        selected = voice.get('voice_config')
        if not isinstance(selected, str) or not selected.strip():
            errors.append('未明确 Voice Studio 声音配置；先记录实际选择，不得回退默认声线')
    required = set()
    if stage in {'sample', 'full', 'final'}:
        required |= {'narration_text', 'narration_audio', 'character', 'avatar_sample'}
    if stage in {'full', 'final'}:
        required |= {'keyframe', 'style_sample'}
    if stage == 'final':
        required.add('final_video')

    def local_file(relative):
        if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
            raise ValueError('资源路径须为本集内的非空相对路径')
        path = (root / relative).resolve()
        if root not in path.parents or not path.is_file():
            raise ValueError(f'文件缺失或越出本集目录: {relative}')
        return path

    resources = data.get('resources', [])
    if not isinstance(resources, list):
        return ['resources 须为数组']
    ids = {}
    duplicated = set()
    kinds = set()
    for item in resources:
        if not isinstance(item, dict):
            errors.append('资源须为对象')
            continue
        rid, kind = item.get('id'), item.get('kind')
        if not isinstance(rid, str) or not rid.strip():
            errors.append(f'缺失或无效资源 ID: {rid!r}（不登记）')
        elif rid in ids or rid in duplicated:
            errors.append(f'重复资源 ID: {rid}（所有同名条目均不登记）')
            ids.pop(rid, None)
            duplicated.add(rid)
        else:
            ids[rid] = kind
        kinds.add(kind)
        if kind not in KINDS:
            errors.append(f'{rid}: 未知资源类型')
        try:
            path = local_file(item.get('path'))
            actual = digest(path)
            if actual != item.get('sha256'):
                errors.append(f'{rid}: 文件已变化或 sha256 未更新')
            if stage != 'plan' and not path.stat().st_size:
                errors.append(f'{rid}: 文件为空')
            dependencies = item.get('dependencies', [])
            if not isinstance(dependencies, list):
                raise ValueError('dependencies 须为数组')
            if kind in {'style_sample', 'final_video'} and not dependencies:
                errors.append(f'{rid}: 必须登记产生样片/成片的代码、配置或输入依赖')
            for dep in dependencies:
                if digest(local_file(dep['path'])) != dep['sha256']:
                    errors.append(f'{rid}: 依赖已变化，旧样片/审核不能继续沿用: {dep["path"]}')
            if kind in required:
                review = item.get('review', {})
                allowed = {'approved'}
                if kind == 'final_video' and state == 'provisional_final':
                    allowed.add('provisional')
                if review.get('status') not in allowed:
                    errors.append(f'{rid}: 待用户审核')
                if review.get('reviewed_sha256') != actual:
                    errors.append(f'{rid}: 审核未绑定当前文件')
                if not isinstance(review.get('evidence'), str) or not review['evidence'].strip():
                    errors.append(f'{rid}: 缺少用户意见或确认出处')
        except (ValueError, OSError, KeyError, TypeError) as exc:
            errors.append(f'{rid}: {exc}')
    for field, expected in [('character_ids', 'character'), ('keyframe_ids', 'keyframe')]:
        declared = data.get(field, [])
        if not isinstance(declared, list):
            errors.append(f'{field} 须为数组')
            continue
        for rid in declared:
            if not isinstance(rid, str) or ids.get(rid) != expected:
                errors.append(f'{field}: 未登记对应资源: {rid}')
        if stage in {'full', 'final'} and field == 'keyframe_ids' and not declared:
            errors.append('需声明本集关键镜头，不得以空清单绕过审核')
    needed = {'narration_text'}
    if stage != 'plan':
        needed.add('narration_audio')
    if stage in {'full', 'final'}:
        needed |= {'style_sample', 'keyframe'}
    if stage == 'final':
        needed.add('final_video')
    for missing in sorted(needed - kinds):
        errors.append(f'缺少资源类型: {missing}')
    if stage == 'final' and state == 'provisional_final' and not data.get('known_issues'):
        errors.append('暂定定稿需记录已知问题或明确待确认项')
    return errors


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('episode')
    parser.add_argument('--stage', choices=['plan', 'sample', 'full', 'final'], default='plan')
    args = parser.parse_args()
    try:
        errors = check(args.episode, args.stage)
    except (OSError, ValueError, TypeError) as exc:
        errors = [str(exc)]
    print(json.dumps({'passed': not errors, 'stage': args.stage, 'errors': errors,
                      'scope': '仅核对声明资源、文件完整性及审核记录；不证明真实审批或音画质量'},
                     ensure_ascii=False, indent=2))
    raise SystemExit(1 if errors else 0)
