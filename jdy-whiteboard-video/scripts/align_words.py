#!/usr/bin/env python3
"""Force-align the known narration (row_type=line rows of storyboard.csv, in order) to the narration
audio with stable-ts (Whisper), regroup into jieba words, and write word_timings.json for make_srt.py. Subtitle text always comes
from the storyboard, never from speech recognition. Times are seconds on the audio's own timeline, so
pass the full narration track, which starts at 0. Forced subtitle breaks "|" are dropped first. Times may
still be blank (rows written at step 2). Forced alignment returns the text it was given, so this only checks
the returned text is complete; it cannot catch misread or skipped words (the user's listening at step 4 does).
Reads inputs only; writes only --output; refuses to overwrite unless --force."""
import argparse
import csv
import json
import sys
from pathlib import Path

PUNCT = '，。！？；：、,.!?;:…—“”‘’《》（）()「」 \u3000·"\'-'


def to_words(text, tokens, cuts):
    """Map aligner tokens [(text, start, end)] onto the known text and regroup them into the words of
    `cuts` (jieba segmentation of the same text), so a cue never breaks inside a word such as 袁世凯
    or 1911. Returns [{text, start, end}] without punctuation."""
    bounds, n = {0}, 0
    for c in cuts:
        n += len(c)
        bounds.add(n)
    words, pos = [], 0
    for tok, start, end in tokens:
        tok = ''.join(tok.split())
        if not tok:
            continue
        at = text.find(tok, pos)
        if at < 0 or text[pos:at].strip():
            raise ValueError(f'对齐返回的文字“{tok}”与旁白文字对不上')
        a, b, pos = at, at + len(tok), at + len(tok)
        while a < b and text[a] in PUNCT:
            a += 1
        while b > a and text[b - 1] in PUNCT:
            b -= 1
        if a == b:
            continue
        if words and words[-1]['_b'] not in bounds and not text[words[-1]['_b']:a].strip(PUNCT):
            words[-1].update(text=text[words[-1]['_a']:b], end=round(end, 3), _b=b)
        else:
            words.append({'text': text[a:b], 'start': round(start, 3), 'end': round(end, 3), '_a': a, '_b': b})
    rest = ''.join(c for c in text[pos:] if c not in PUNCT and not c.isspace())
    if rest:
        raise ValueError(f'旁白末尾“{rest[:20]}”没有对齐结果')
    return [{k: w[k] for k in ('text', 'start', 'end')} for w in words]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--storyboard', required=True, help='storyboard.csv（旁白文字以它为准）')
    p.add_argument('--audio', required=True, help='旁白音轨（与视频同一 0 秒起点）')
    p.add_argument('--output', required=True, help='要写出的 word_timings.json')
    p.add_argument('--model', default='small', help='Whisper 模型（默认 small）')
    p.add_argument('--force', action='store_true', help='允许覆盖已有文件')
    args = p.parse_args()
    out = Path(args.output)
    if out.exists() and out.resolve() in (Path(args.storyboard).resolve(), Path(args.audio).resolve()):
        sys.exit('拒绝: 输出路径是输入文件')
    if out.exists() and not args.force:
        sys.exit(f'拒绝覆盖已有文件: {out}（确认要覆盖再加 --force）')
    with open(args.storyboard, encoding='utf-8-sig', newline='') as f:
        text = ''.join((r.get('text') or '').strip() for r in csv.DictReader(f)
                       if (r.get('row_type') or '').strip() == 'line')
    text = text.replace('|', '').replace('｜', '')  # forced subtitle breaks are not spoken
    if not text:
        sys.exit('镜头表没有旁白行（row_type=line）')
    import jieba  # pip install stable-ts jieba
    import stable_whisper
    result = stable_whisper.load_model(args.model, device='cpu').align(args.audio, text, language='zh')
    try:
        words = to_words(text, [(w.word, w.start, w.end) for s in result.segments for w in s.words],
                         list(jieba.cut(text)))
    except ValueError as exc:
        sys.exit(f'未写出: {exc}')
    out.write_text(json.dumps({'words': words}, ensure_ascii=False, indent=0), encoding='utf-8')
    print(f'已写出 {len(words)} 个词: {out}（只核对返回文字完整；读错、漏读靠第 4 步听审）')


if __name__ == '__main__':
    main()
