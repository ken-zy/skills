#!/usr/bin/env python3
"""Turn narration rows (row_type=line) of storyboard.csv plus word timings (word_timings.json from align_words.py)
into the episode's UTF-8 .srt and check it automatically; no video needed. Run once, after the storyboard is
final (step 7), then locked by recording its SHA-256 in episode.json. A "|" (or "｜") in the narration forces a break there. Each line is cut at "|" and punctuation; a clause
longer than --max-chars is cut between words into pieces as even as possible, not next to function
words (warning if unavoidable); a cue shorter than 0.8 s joins its neighbour when it fits (inner
punctuation shown as a space), never across a "|": a too-short cue at a "|" is an error. Cue times are the first/last word's real times. Punctuation counts only between words; characters inside a word
(3.5, 10:30) are kept. Checks: cue text equals the narration (punctuation between words aside, words intact), every
word inside its line, words in time order without overlap, every word used by exactly one line, no overlap, length,
minimum duration, plausible speed. Any problem: lists it, writes nothing,
exit 1 (do not burn). Reads inputs only; refuses to overwrite unless --force.
Burn time (--check): never re-cuts. Checks the .srt still has the SHA-256 recorded at lock time and
ends within the clean video's video stream (all cues for the full film); with --start (sample cut from the full narration at that second) it also
writes the sample's slice shifted to 0, refusing if the sample starts or ends inside a cue."""
import argparse
import csv
import hashlib
import json
import math
import re
import sys
from pathlib import Path

BREAK = '，。！？；：、,.!?;:…—'
KEEP = '？！?!'  # kept at the end of a cue; other trailing punctuation is dropped
MARK = '|｜'  # forced break, placed in the narration where a picture beat must start
OPEN, CLOSE = '“‘《（(「', '”’》）)」'
SKIP = set(BREAK + MARK + OPEN + CLOSE + ' \u3000·"\'-')
TOL, MIN_DUR, MAX_SPEED, GAP = 0.1, 0.8, 12, 0.02  # seconds, seconds, chars per second, word overlap allowed
NO_END = set('在把被将对从向和与及或但而')  # a cue may not end with these words (prepositions, conjunctions)
NO_START = set('的地得了着过')  # nor may the next cue start with these particles


def stamp(t):
    ms = round(t * 1000)
    return f'{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}'


def number(raw):
    try:
        value = float(str(raw).strip())
    except ValueError:
        return None
    return value if math.isfinite(value) and value >= 0 else None


def bare(s):
    return ''.join(c for c in s if c not in SKIP)


def balanced(spans, max_chars, text):
    """Cut one clause into the fewest pieces <= max_chars (a single long word stays whole); among those, avoid
    cutting next to function words, then as even as possible. Returns (pieces, number of bad cuts)."""
    word = lambda k: text[spans[k][0]:spans[k][1]]
    bad = lambda j: j < len(spans) and (word(j - 1) in NO_END or word(j) in NO_START)
    n, best = len(spans), {0: (0, 0, 0, 0)}
    for j in range(1, n + 1):
        best[j] = min((best[i][0] + 1, best[i][1] + bad(j), best[i][2] + (spans[j - 1][1] - spans[i][0]) ** 2, i)
                      for i in range(j) if i == j - 1 or spans[j - 1][1] - spans[i][0] <= max_chars)
    cuts, j = [], n
    while j:
        cuts.append(spans[best[j][3]:j])
        j = best[j][3]
    return cuts[::-1], best[n][1]


def split_line(text, words, max_chars, warnings):
    """[(start, end, shown)] or raises ValueError. words: [(text, start, end)] in time order."""
    spans, pos = [], 0
    for word, start, end in words:
        at = text.find(word, pos)
        if at < 0 or not set(text[pos:at]) <= SKIP:
            raise ValueError(f'词“{word}”与旁白文字对不上' + ('（断点“|”不能放在词中间）' if set(text) & set(MARK) else ''))
        spans.append([at, at + len(word), start, end, bool(set(text[pos:at]) & set(MARK)) and pos > 0])
        pos = at + len(word)
    if not set(text[pos:]) <= SKIP:
        raise ValueError(f'旁白末尾“{text[pos:]}”没有词时间')
    cues, clause = [], []
    for i, span in enumerate(spans):
        clause.append(span)
        after = text[span[1]:spans[i + 1][0] if i + 1 < len(spans) else len(text)]
        if set(after) & set(BREAK + MARK) or i + 1 == len(spans):
            pieces, bad = balanced(clause, max_chars, text)
            cues += pieces
            if bad:
                warnings.append(f'“{text[clause[0][0]:clause[-1][1]]}”只能在虚词旁断开')
            clause = []
    i = 0
    while i < len(cues):  # a cue too short to read joins its neighbour in the line if the result still fits
        until = cues[i + 1][0][2] if i + 1 < len(cues) else cues[i][-1][3]
        a, b = sorted((i, i + 1 if i + 1 < len(cues) else i - 1))
        if (round(until - cues[i][0][2], 3) < MIN_DUR and a >= 0 and not cues[b][0][4]
                and cues[b][-1][1] - cues[a][0][0] <= max_chars):
            cues[a:b + 1] = [cues[a] + cues[b]]
            i = a
        else:
            i += 1
    for n, cue in enumerate(cues):
        until = cues[n + 1][0][2] if n + 1 < len(cues) else cue[-1][3]
        if round(until - cue[0][2], 3) < MIN_DUR and (cue[0][4] or n + 1 < len(cues) and cues[n + 1][0][4]):
            raise ValueError(f'断点“|”使“{text[cue[0][0]:cue[-1][1]]}”显示不足 {MIN_DUR} 秒，请移动或去掉这个断点')
    out = []
    for n, cue in enumerate(cues):
        a, b = cue[0][0], cue[-1][1]
        while a > 0 and text[a - 1] in OPEN:
            a -= 1
        tail = text[b:cues[n + 1][0][0] if n + 1 < len(cues) else len(text)]
        b += next((i for i, c in enumerate(tail) if c not in CLOSE), len(tail))
        inside = {i for s in cue for i in range(s[0], s[1])}  # characters of the words themselves stay as they are
        shown = ''.join(text[i] if i in inside else ' ' if text[i] in BREAK and text[i] not in KEEP else text[i]
                        for i in range(a, b) if text[i] not in MARK).replace('  ', ' ')
        shown += ''.join(c for c in tail if c in KEEP)[:1]
        end = cues[n + 1][0][2] if n + 1 < len(cues) else cue[-1][3]  # stay up through pauses inside the line
        out.append([cue[0][2], end, shown.strip()])
        at = 0
        for s in cue:  # every word must appear in the cue unchanged, in order
            at = out[-1][2].find(text[s[0]:s[1]], at)
            if at < 0:
                raise ValueError(f'字幕文字与旁白不一致（词“{text[s[0]:s[1]]}”被改动）')
    if ''.join(bare(c[2]) for c in out) != bare(text):
        raise ValueError('字幕文字与旁白不一致')
    return out


def duration(video):
    """End of the video stream, not the container (same as check_timing.py)."""
    sys.dont_write_bytecode = True  # 不在技能目录留 __pycache__
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from check_timing import probe_video_end
    return number(probe_video_end(video)[0])


def seconds(h, m, s, ms):
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000


def guard(out, inputs, force):
    if out.exists() and out.resolve() in {Path(x).resolve() for x in inputs if x}:
        sys.exit('拒绝: 输出路径是输入文件')
    if out.exists() and not force:
        sys.exit(f'拒绝覆盖已有文件: {out}（确认要覆盖再加 --force）')


def check(args):
    """Burn-time check of the locked subtitles.srt; optionally write the sample's slice. Never re-cuts."""
    if args.start is not None:
        guard(Path(args.output), [args.check, args.video], args.force)
    try:
        data = Path(args.check).read_bytes()
    except OSError as exc:
        sys.exit(f'无法读取字幕: {exc}')
    problems = [] if hashlib.sha256(data).hexdigest() == args.sha256.strip().lower() else [
        '字幕文件的 SHA-256 与锁定时登记的不符（被改过或不是同一个文件）']
    cues = [(seconds(*m[0:4]), seconds(*m[4:8]), m[8]) for m in re.findall(
        r'(\d+):(\d\d):(\d\d),(\d{3}) --> (\d+):(\d\d):(\d\d),(\d{3})\r?\n([^\r\n]*)', data.decode('utf-8', 'replace'))]
    total, t0 = duration(args.video), args.start or 0.0
    if not cues:
        problems.append('字幕里没有可读的条目')
    if total is None:
        problems.append(f'无法读取视频时长: {args.video}')
    elif args.start is None:  # full film: every cue, no filtering
        if cues and max(e for s, e, t in cues) > total + TOL:
            problems.append(f'最后一条字幕结束于 {max(e for s, e, t in cues):.2f} 秒，超出视频时长 {total:.2f} 秒')
    else:
        problems += [f'“{t}”跨在样片起点上，样片要从两条字幕之间开始' for s, e, t in cues if s < t0 < e]
        cues = [c for c in cues if c[0] >= t0 and c[0] < t0 + total]
        if cues and cues[-1][1] - t0 > total + TOL:
            problems.append(f'最后一条字幕结束于 {cues[-1][1] - t0:.2f} 秒，超出视频时长 {total:.2f} 秒（样片要在两条字幕之间结束）')
    if problems:
        sys.exit('烧入前检查未通过，不得烧入:\n' + '\n'.join(problems))
    if args.start is None:
        print(f'烧入前检查通过（{len(cues)} 条，原样烧入）: {args.check}')
        return
    out = Path(args.output)
    out.write_text('\n'.join(f'{i}\n{stamp(s - t0)} --> {stamp(e - t0)}\n{t}\n' for i, (s, e, t) in enumerate(cues, 1)),
                   encoding='utf-8')
    print(f'烧入前检查通过，已截出样片字幕 {len(cues)} 条（未重新切分）: {out}')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--storyboard', help='storyboard.csv（旁白行已填实测时间；“|”为强制断点）')
    p.add_argument('--words', help='word_timings.json（与镜头表同一时间轴的词时间，秒）')
    p.add_argument('--output', help='要写出的 .srt 路径（--check 时为样片字幕）')
    p.add_argument('--max-chars', type=int, default=16, help='每条字幕最多字数（单行）')
    p.add_argument('--check', help='烧入前检查：第 7 步切好并锁定的 subtitles.srt')
    p.add_argument('--sha256', help='--check 用：锁定时登记在 episode.json 的 subtitles.sha256')
    p.add_argument('--video', help='--check 用：未烧字幕的样片或成片')
    p.add_argument('--start', type=float, help='--check 用：样片在整条旁白里的起点（秒）；给出时写出截好的样片字幕')
    p.add_argument('--force', action='store_true', help='允许覆盖已有文件')
    args = p.parse_args()
    if args.check:
        if not (args.sha256 and args.video) or (args.start is not None and not args.output):
            p.error('--check 需要 --sha256 和 --video；给 --start 时还要 --output')
        if args.start is not None and number(args.start) is None:
            p.error('拒绝: --start 须为非负有限秒数')
        return check(args)
    if not (args.storyboard and args.words and args.output):
        p.error('生成字幕需要 --storyboard、--words 和 --output')
    out = Path(args.output)
    guard(out, [args.storyboard, args.words], args.force)
    try:
        with open(args.storyboard, encoding='utf-8-sig', newline='') as f:
            rows = list(csv.DictReader(f))
        words = [(w['text'], number(w['start']), number(w['end']))
                 for w in json.loads(Path(args.words).read_text(encoding='utf-8'))['words']]
    except (OSError, ValueError, KeyError, TypeError, csv.Error) as exc:
        sys.exit(f'无法读取输入: {exc}')
    warnings = []
    problems = [f'词时间无效: {w}' for w in words if None in w or w[1] > w[2] or not w[0]]
    for a, b in zip(words, words[1:]):  # words in time order, no overlap beyond 0.02 s
        if not problems and (b[1] < a[1] or b[1] < a[2] - GAP):
            problems.append(f'词时间顺序颠倒或重叠: “{a[0]}”{a[1]}–{a[2]} 与“{b[0]}”{b[1]}–{b[2]}')
    bad_words = bool(problems)
    used = [0] * len(words)
    cues, size = [], max(args.max_chars, 1)
    for n, row in enumerate(rows, start=2):
        if (row.get('row_type') or '').strip() != 'line' or bad_words:
            continue
        text = (row.get('text') or '').strip()
        start, end = number(row.get('audio_start') or ''), number(row.get('audio_end') or '')
        if not text or start is None or end is None or start >= end:
            problems.append(f'第 {n} 行: 旁白文字为空，或 audio_start／audio_end 不是有效起止')
            continue
        picked = [i for i, w in enumerate(words) if start <= (w[1] + w[2]) / 2 <= end]
        mine = [words[i] for i in picked]
        for i in picked:
            used[i] += 1
        if not mine:
            problems.append(f'第 {n} 行: 缺少词时间，未生成（不按字数估算）')
            continue
        try:
            line = split_line(text, mine, size, warnings)
        except ValueError as exc:
            problems.append(f'第 {n} 行: {exc}')
            continue
        if any(w[1] < start - TOL or w[2] > end + TOL for w in mine):
            problems.append(f'第 {n} 行: 词时间超出本句 audio_start～audio_end')
        cues += [c + [n] for c in line]
    if not bad_words:  # every word is used by exactly one narration row
        problems += [f'词“{w[0]}”{w[1]}–{w[2]} 没有对应的旁白行（镜头表漏了旁白行？）' for w, k in zip(words, used) if k == 0]
        problems += [f'词“{w[0]}”{w[1]}–{w[2]} 落在多句旁白行里' for w, k in zip(words, used) if k > 1]
    cues.sort()
    for i, c in enumerate(cues):
        say = f'第 {c[3]} 行“{c[2]}”'
        nxt = cues[i + 1][0] if i + 1 < len(cues) else math.inf  # the video length is checked at burn time
        if round(c[1] - c[0], 3) < MIN_DUR:  # in ms, as in the .srt; too short to read: stay up a little longer if the gap allows
            if round(c[0] + MIN_DUR, 3) <= round(nxt, 3):
                c[1] = c[0] + MIN_DUR
            else:
                problems.append(f'{say}: 显示不足 {MIN_DUR} 秒，又没有空隙可延长')
        if len(bare(c[2])) > size:
            problems.append(f'{say}: 超过 {size} 字')
        if len(bare(c[2])) / max(c[1] - c[0], 1e-3) > MAX_SPEED:
            problems.append(f'{say}: 每秒超过 {MAX_SPEED} 字，对齐可疑')
        if i + 1 < len(cues) and c[1] > cues[i + 1][0] + 1e-6:
            problems.append(f'{say}与第 {cues[i + 1][3]} 行时间重叠')
    if not cues and not problems:
        problems.append('镜头表没有可用的旁白行（row_type=line）')
    for w in warnings:
        print(f'提醒: {w}', file=sys.stderr)
    if problems:
        sys.exit('字幕检查未通过，未写出、不得烧入:\n' + '\n'.join(problems))
    out.write_text('\n'.join(f'{i}\n{stamp(s)} --> {stamp(e)}\n{t}\n' for i, (s, e, t, _) in enumerate(cues, 1)),
                   encoding='utf-8')
    print(f'字幕检查通过，已写出 {len(cues)} 条: {out}')
    print(f'sha256: {hashlib.sha256(out.read_bytes()).hexdigest()}（登记到 episode.json 的 subtitles.sha256 即锁定）')


if __name__ == '__main__':
    main()
