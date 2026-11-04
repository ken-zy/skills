#!/usr/bin/env python3
"""Read-only rhythm check for the storyboard (step 6, storyboard only), sample and full stages: per-row storyboard rules and video freezes
(the full stage turns missing data into errors). Reports only; never edits any file or video.
Run --video on the clean render, before subtitles are burned in, so they cannot hide a static board.

status: passed (exit 0) only when everything required was checked and nothing failed;
failed (exit 1) when any rule is broken; incomplete (exit 3) when something could not be
checked (missing data, missing input, unknown duration). incomplete is never a pass.
"""
import argparse
import csv
import json
import math
import re
import shutil
import subprocess
from pathlib import Path

REQUIRED = ['shot_id', 'row_id', 'row_type', 'line_id', 'text', 'audio_start', 'audio_end',
            'draw_start', 'draw_end', 'recognizable_at']
END_TOLERANCE = 0.1  # seconds a storyboard time may exceed the video stream end


def clock(seconds):
    minutes, rest = divmod(max(seconds, 0.0), 60)
    return f'{int(minutes):02d}:{rest:04.1f}'


class Report:
    def __init__(self, stage):
        self.stage = stage
        self.errors, self.warnings, self.checked, self.unchecked = [], [], [], []

    def missing(self, message):
        """Data that should exist but does not: never a pass; an error at full stage."""
        self.unchecked.append(message)
        if self.stage == 'full':
            self.errors.append(message)

    def status(self):
        return 'failed' if self.errors else ('incomplete' if self.unchecked else 'passed')


def seconds(raw, column):
    """(value, problem); value None and problem None means blank or 'none'."""
    text = (raw or '').strip()
    if not text or text.lower() == 'none':
        return None, None
    try:
        value = float(text)
    except ValueError:
        return None, f'{column} 不是秒数: {text}'
    if not math.isfinite(value) or value < 0:
        return None, f'{column} 须为非负有限秒数: {text}'
    return value, None


def check_storyboard(path, max_recognize, max_static, video_end, report):
    try:
        with Path(path).open(encoding='utf-8-sig', newline='') as stream:
            reader = csv.DictReader(stream)
            reader.fieldnames = [c.strip() for c in (reader.fieldnames or [])]
            rows = list(reader)
            columns = reader.fieldnames
    except (OSError, UnicodeDecodeError, csv.Error) as exc:
        report.errors.append(f'镜头表无法读取: {exc}')
        report.unchecked.append('镜头表: 未检查（无法读取）')
        return {'rows': 0}
    absent = [c for c in REQUIRED if c not in columns]
    if absent:
        report.missing(f'镜头表缺少列 {", ".join(absent)}（须为每行一个对象或一句旁白的新格式），整表未检查')
        return {'rows': len(rows)}
    if not rows:
        report.missing('镜头表没有任何行，节奏未检查')
        return {'rows': 0}

    lines, objects, object_ids, latest, seen = {}, [], set(), 0.0, set()
    for row in rows:  # every non-empty row_id is unique across the whole table
        row_id = (row.get('row_id') or '').strip()
        if row_id and row_id in seen:
            report.errors.append(f'row_id {row_id} 重复（全表唯一）')
        seen.add(row_id)
    for number, row in enumerate(rows, start=2):
        kind = (row.get('row_type') or '').strip().lower()
        row_id = (row.get('row_id') or '').strip()
        line_id = (row.get('line_id') or '').strip() if kind == 'object' else row_id
        label = f'第{number}行 {(row.get("shot_id") or "?").strip()}/{kind or "?"}/{(row.get("text") or "?").strip()}'
        t, bad = {}, []
        for column in REQUIRED[5:]:
            t[column], problem = seconds(row.get(column), column)
            bad += [problem] if problem else []
        latest = max([latest] + [v for v in t.values() if v is not None])
        need = {'line': ['audio_start', 'audio_end'],
                'object': ['audio_start', 'draw_start', 'draw_end', 'recognizable_at']}.get(kind)
        if need is None:
            report.errors.append(f'{label}: row_type 须为 object 或 line: {kind or "空"}')
            continue
        if kind == 'object' and row_id:
            object_ids.add(row_id)
        if not line_id:
            bad.append('旁白行缺少 row_id' if kind == 'line' else '缺少 line_id（须指向所属旁白行的 row_id）')
        if kind == 'line' and (t['draw_start'] is None) != (t['draw_end'] is None):
            bad.append('draw_start 和 draw_end 须同时填写，或同时留空／写 none（本句无新绘制）')
        empty = [c for c in need if t[c] is None and not any(m.startswith(c + ' ') for m in bad)]
        for problem in bad:
            report.errors.append(f'{label}: {problem}')
        if empty:
            report.missing(f'{label}: {", ".join(empty)} 为空，本行未检查')
        if bad or empty:
            if kind == 'line' and line_id:
                lines.setdefault(line_id, None)  # the sentence exists but its times are unusable
            continue
        if kind == 'object':
            objects.append({'label': label, 'line_id': line_id, **t})
            continue
        if not t['audio_start'] < t['audio_end']:
            report.errors.append(f'{label}: audio_start 须早于 audio_end')
        if t['draw_start'] is not None:
            if not t['draw_start'] < t['draw_end']:
                report.errors.append(f'{label}: draw_start 须早于 draw_end')
            elif t['draw_end'] > t['audio_end']:
                report.errors.append(f'{label}: 本句绘制 {t["draw_end"]:.2f} 秒画完，晚于句子结束 {t["audio_end"]:.2f} 秒')
        lines[line_id] = {'label': label, **t}

    checked = len([l for l in lines.values() if l])
    for obj in objects:
        label = obj['label']
        if not obj['draw_start'] < obj['draw_end']:
            report.errors.append(f'{label}: draw_start 须早于 draw_end（相等即“直接出现”，违反逐笔绘制）')
            continue
        if not obj['draw_start'] <= obj['recognizable_at'] <= obj['draw_end']:
            report.errors.append(f'{label}: recognizable_at 须在 draw_start 与 draw_end 之间')
            continue
        gap = obj['recognizable_at'] - obj['audio_start']  # drawing may start before the mention
        if gap > max_recognize:
            report.errors.append(f'{label}: 提到后 {gap:.2f} 秒才可辨认，超过 {max_recognize} 秒')
        if obj['line_id'] not in lines:
            kind = '对象行' if obj['line_id'] in object_ids else '不存在的句子'
            report.errors.append(f'{label}: line_id {obj["line_id"]} 指向{kind}，须指向旁白行')
            continue
        owner = lines.get(obj['line_id'])
        if owner is None:
            report.unchecked.append(f'{label}: 所属句子 {obj["line_id"]} 本身未通过检查，截止时间未核对')
            continue
        checked += 1
        if not owner['audio_start'] <= obj['audio_start'] <= owner['audio_end']:
            report.errors.append(f'{label}: 提到时刻 {obj["audio_start"]:.2f} 秒不在所属句子 {obj["line_id"]} '
                                 f'{owner["audio_start"]:.2f}–{owner["audio_end"]:.2f} 秒之内')
        if obj['draw_end'] > owner['audio_end']:
            report.errors.append(f'{label}: 画完 {obj["draw_end"]:.2f} 秒，晚于所属句子 {obj["line_id"]} 结束 {owner["audio_end"]:.2f} 秒')

    if video_end is not None and latest > video_end + END_TOLERANCE:
        report.errors.append(f'镜头表时间到 {latest:.2f} 秒，超出视频流结束 {video_end:.2f} 秒'
                             '（样片的镜头表时间以样片自身 0 秒为起点）')

    # coarse hint only; the video freeze check decides
    spans = sorted((r['draw_start'], r['draw_end']) for r in [*objects, *[l for l in lines.values() if l]]
                   if r['draw_start'] is not None and r['draw_end'] is not None)
    reach = None
    for start, end in spans:
        if reach is not None and start - reach > max_static:
            report.warnings.append(f'{clock(reach)}–{clock(start)} 镜头表无任何绘制（{start - reach:.1f} 秒），以视频静止检测为准')
        reach = end if reach is None else max(reach, end)
    report.checked.append(f'镜头表: {checked}/{len(rows)} 行已逐行检查')
    return {'rows': len(rows), 'rows_checked': checked, 'latest_time': latest}


def probe_video_end(path):
    """End time of the video stream itself (not the container): (seconds, None) or (None, reason)."""
    ffprobe = shutil.which('ffprobe')
    if not ffprobe:
        return None, '未找到 ffprobe'
    base = [ffprobe, '-v', 'error', '-select_streams', 'v:0', '-of', 'csv=p=0']
    try:
        out = subprocess.run(base + ['-show_entries', 'stream=start_time,duration', str(path)],
                             capture_output=True, text=True, check=True).stdout.strip().split(',')
        if len(out) == 2 and 'N/A' not in out and all(out):
            return float(out[0]) + float(out[1]), None
        out = subprocess.run(base + ['-show_entries', 'packet=pts_time,duration_time', str(path)],
                             capture_output=True, text=True, check=True).stdout
        ends = []
        for line in out.splitlines():
            parts = (line.strip().split(',') + ['0'])[:2]
            try:
                ends.append(float(parts[0]) + (0.0 if parts[1] in ('', 'N/A') else float(parts[1])))
            except ValueError:
                continue
        if ends:
            return max(ends), None
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        return None, f'ffprobe 失败: {exc}'
    return None, '视频流没有可用的结束时间'


def check_video(path, max_static, noise, report):
    result = {'freezes': []}
    if not Path(path).is_file():
        report.errors.append(f'视频不存在: {path}')
        report.unchecked.append('视频静止检测: 未运行（文件不存在）')
        return result, None
    video_end, why = probe_video_end(path)
    result['video_stream_end'] = None if video_end is None else round(video_end, 3)
    if video_end is None:
        report.unchecked.append(f'视频流结束时间未知（{why}），镜头表是否超出视频未检查')
    ffmpeg = shutil.which('ffmpeg')
    if not ffmpeg:
        report.unchecked.append('视频静止检测: 未运行（未找到 ffmpeg），不算通过')
        return result, video_end
    detect = f'freezedetect=n={noise}:d={max_static}'
    run = subprocess.run([ffmpeg, '-hide_banner', '-nostats', '-i', str(path), '-map', '0:v:0',
                          '-vf', detect, '-f', 'null', '-'], capture_output=True, text=True, errors='replace')
    if run.returncode != 0:
        report.errors.append(f'ffmpeg 退出码 {run.returncode}: {(run.stderr.strip().splitlines() or [""])[-1]}')
        report.unchecked.append('视频静止检测: 未完成')
        return result, video_end
    freezes, start = [], None
    for key, value in re.findall(r'freeze_(start|duration):\s*([-\d.eE+]+)', run.stderr):
        if key == 'start':
            start = float(value)
        elif start is not None:
            freezes.append((start, float(value), False))
            start = None
    if start is not None:  # freezedetect prints no end when the freeze lasts until EOF
        freezes.append((start, None if video_end is None else video_end - start, True))
    for start, duration, to_end in freezes:
        result['freezes'].append({'start': clock(start), 'duration': None if duration is None else round(duration, 3),
                                  'to_end': to_end})
        if duration is None:
            report.unchecked.append(f'{clock(start)} 起静止至片尾，时长未知')
        elif duration > max_static:
            report.errors.append(f'{clock(start)} 起静止 {duration:.1f} 秒，超过 {max_static} 秒'
                                 + ('（至视频流结束）' if to_end else ''))
    report.checked.append('视频静止检测（整幅画面）')
    return result, video_end


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--storyboard', help='storyboard.csv（每行一个对象或一句旁白）')
    parser.add_argument('--video', help='未烧字幕的样片或成片视频（需要 ffmpeg／ffprobe）')
    parser.add_argument('--stage', choices=['sample', 'full'], default='sample')
    parser.add_argument('--max-recognize', type=float, default=1.5, help='提到对象到可辨认的最长秒数')
    parser.add_argument('--max-static', type=float, default=3.0, help='画面静止的最长秒数')
    parser.add_argument('--freeze-noise', type=float, default=0.003, help='freezedetect 噪声阈值 n')
    args = parser.parse_args()
    report = Report(args.stage)
    output = {'stage': args.stage, 'thresholds': {'max_recognize': args.max_recognize, 'max_static': args.max_static,
                                                  'freeze_noise': args.freeze_noise}}
    limits = [args.max_recognize > 0, args.max_static > 0, 0 < args.freeze_noise < 1]
    if not all(limits) or not all(map(math.isfinite, output['thresholds'].values())):
        report.errors.append(f'门槛无效（须为有限正数，噪声 < 1）: {output["thresholds"]}')
        report.unchecked.append('全部检查: 门槛无效，未运行')
    else:
        if args.max_recognize > 1.5 or args.max_static > 3.0:
            report.warnings.append('门槛比默认（1.5／3 秒）宽：放宽须经用户同意并记录')
        video_end = None
        if args.video:
            output['video'], video_end = check_video(args.video, args.max_static, args.freeze_noise, report)
        else:
            report.unchecked.append('视频静止检测: 未提供 --video，未检查')
        if args.storyboard:
            output['storyboard'] = check_storyboard(args.storyboard, args.max_recognize, args.max_static,
                                                    video_end, report)
        else:
            report.unchecked.append('镜头表: 未提供 --storyboard，未检查')
    status = report.status()
    print(json.dumps({'status': status, 'passed': status == 'passed', **output,
                      'checked': report.checked, 'unchecked': report.unchecked,
                      'errors': report.errors, 'warnings': report.warnings,
                      'scope': '只读：只报告，不改片、不改文件；不代替人看片。静止检测须用未烧字幕的视频，仍可能被手部移动掩盖'},
                     ensure_ascii=False, indent=2))
    return {'passed': 0, 'failed': 1, 'incomplete': 3}[status]


if __name__ == '__main__':
    raise SystemExit(main())
