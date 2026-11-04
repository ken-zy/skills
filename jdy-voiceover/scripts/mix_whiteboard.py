"""Voice Studio sound helper; use its existing venv. Never install dependencies here."""
import argparse
import hashlib
import json
import math
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--narration', type=Path, required=True)
    parser.add_argument('--events', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--narration-sha256')
    parser.add_argument('--events-sha256')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    for path in [args.narration, args.events, args.output_dir]:
        if not path.is_absolute():
            raise ValueError('输入与输出须使用绝对路径')
    if args.output_dir.exists() or args.output_dir.is_symlink():
        raise ValueError('拒绝覆盖已有输出目录')
    if not args.output_dir.parent.is_dir():
        raise ValueError('输出父目录须先存在')
    profile_path = Path(__file__).resolve().parents[1] / 'assets/whiteboard-pen-soft-v1.json'
    profile = json.loads(profile_path.read_text())
    texture_path = Path(profile['texture_path'])
    if sha(texture_path) != profile['texture_sha256']:
        raise ValueError('基准笔声素材哈希不符；不得替换素材或再次处理已柔化音轨')
    narration_hash, events_hash = sha(args.narration), sha(args.events)
    for expected, actual in [(args.narration_sha256, narration_hash),
                             (args.events_sha256, events_hash)]:
        if expected and expected != actual:
            raise ValueError('输入哈希不符')
    import numpy as np
    import soundfile as sf
    from scipy.signal import butter, sosfiltfilt
    voice_info = sf.info(args.narration)
    if voice_info.subtype not in {'PCM_16', 'PCM_24'}:
        raise ValueError('旁白须为PCM16或PCM24；不静默量化浮点或PCM32旁白')
    voice, sr = sf.read(args.narration, dtype='int32')
    texture, tsr = sf.read(texture_path, dtype='int32')
    if sr != profile['sample_rate'] or sr != tsr or voice.ndim != 1 or texture.ndim != 1:
        raise ValueError('当前已确认预设使用48kHz单声道旁白和笔声')
    if len(texture) < 128 or not len(voice):
        raise ValueError('音轨为空或笔声素材过短')
    raw_events = json.loads(args.events.read_text())
    if raw_events.get('narration_sha256') not in (None, narration_hash):
        raise ValueError('绘画事件绑定了另一版旁白，不能仅凭时长相同复用')
    duration = raw_events.get('duration_seconds', len(voice) / sr)
    if (isinstance(duration, bool) or not isinstance(duration, (int, float)) or
            not math.isfinite(duration) or abs(duration - len(voice) / sr) > 1 / sr):
        raise ValueError('绘画事件时长与实际旁白不符')
    contacts = raw_events.get('contacts')
    if not isinstance(contacts, list):
        raise ValueError('缺少contacts数组')
    prepared, last_end = [], 0.0
    for event in contacts:
        a, b = event['start_seconds'], event['end_seconds']
        if (isinstance(a, bool) or isinstance(b, bool) or
                not isinstance(a, (int, float)) or not isinstance(b, (int, float)) or
                not math.isfinite(a) or not math.isfinite(b) or
                not 0 <= a < b <= len(voice) / sr + .5 / sr or a < last_end):
            raise ValueError('触笔区间须有限、有序、不重叠且落在旁白时间轴内')
        start, end = round(a * sr), round(b * sr)
        if end <= start or end > len(voice):
            raise ValueError('触笔区间取样后为空或越界')
        prepared.append((start, end))
        last_end = b
    if args.dry_run:
        print(json.dumps({'profile': profile['id'], 'contacts': len(prepared),
                          'narration_sha256': narration_hash, 'events_sha256': events_hash}))
        return
    n = len(texture)
    sos = butter(profile['pen_lowpass_order'], profile['pen_only_lowpass_hz'], fs=sr,
                 btype='lowpass', output='sos')
    soft = sosfiltfilt(sos, np.tile(texture.astype(float), 5))[2*n:3*n]
    soft *= 10 ** (profile['pen_gain_db_relative_to_texture'] / 20)
    pen = np.zeros(len(voice), dtype=np.int64)
    audible = np.zeros(len(voice), dtype=bool)
    kept = phase = 0
    for a, b in prepared:
        count = b - a
        if count < round(profile['minimum_audible_contact_ms'] * sr / 1000):
            continue
        value = soft[(np.arange(count) + phase) % n]
        phase += count
        attack = min(round(profile['attack_ms_max'] * sr / 1000), count // 3)
        release = min(round(profile['release_ms_max'] * sr / 1000), count // 3)
        env = np.ones(count)
        env[:attack] = .5 - .5 * np.cos(np.linspace(0, np.pi, attack))
        env[-release:] = .5 + .5 * np.cos(np.linspace(0, np.pi, release))
        pen[a:b] += np.rint(value * env / 256).astype(np.int64) * 256
        audible[a:b] = True
        kept += 1
    mixed = voice.astype(np.int64) + pen
    if np.abs(mixed).max() >= 2**31:
        raise ValueError('混音削波；停止，不调低已确认旁白或做自动归一化')
    assert not np.any(pen[~audible])
    args.output_dir.mkdir()
    for stem, data in [('pen-only', pen), ('mix', mixed)]:
        sf.write(args.output_dir / f'{stem}.wav', data.astype(np.int32), sr, subtype='PCM_24')
    back, _ = sf.read(args.output_dir / 'mix.wav', dtype='int32')
    pb, _ = sf.read(args.output_dir / 'pen-only.wav', dtype='int32')
    assert np.array_equal(back.astype(np.int64) - pb, voice.astype(np.int64))
    assert sha(args.narration) == narration_hash and sha(args.events) == events_hash
    manifest = {
        'owner': 'Voice Studio', 'status': 'pending_user_mix_review',
        'profile': profile, 'profile_sha256': sha(profile_path),
        'producer_path': str(Path(__file__).resolve()), 'producer_sha256': sha(Path(__file__)),
        'narration_path': str(args.narration), 'narration_sha256': narration_hash,
        'events_path': str(args.events), 'events_sha256': events_hash,
        'sample_rate': sr, 'frames': len(voice), 'duration_seconds': len(voice) / sr,
        'contacts': {'all': len(prepared), 'audible': kept, 'silent_short_details': len(prepared)-kept},
        'validation': {'voice_integer_pcm_unchanged': True, 'no_clipping': True,
                       'silent_outside_audible_contacts': True, 'timeline_unchanged': True},
        'files': {name: sha(args.output_dir / name) for name in ['mix.wav', 'pen-only.wav']}}
    (args.output_dir / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    print(json.dumps({'output': str(args.output_dir), 'contacts': manifest['contacts']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
