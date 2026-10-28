# Platform media acquisition

Use this mode when the user requests local video/audio/subtitle downloads or a
format/subtitle probe. Article extraction remains in `scripts/main.ts`.

## Tools and scope

The standalone entrypoint is `python3 {baseDir}/scripts/download_media.py`.
It uses Python 3.9+ standard library only. `yt-dlp` is required for platform
extraction; `ffprobe` for media validation; `ffmpeg` for video/audio merging.
`doctor` checks tool paths and versions without network requests. It reports
missing tools and does not install, update, launch a browser, or read cookies.
Tool discovery includes Homebrew's `/opt/homebrew/bin`, `/usr/local/bin` and
`~/.local/bin` when an SSH session's PATH omits them. Video merging passes the
resolved FFmpeg location explicitly to yt-dlp.
Install fixed versions only under the host's dependency policy and user scope.
YouTube may additionally require an existing JS runtime or challenge components
according to the installed yt-dlp release; failures need diagnosis, not silent
runtime installation or third-party script downloads by this skill.

```bash
python3 {baseDir}/scripts/download_media.py doctor
python3 {baseDir}/scripts/download_media.py probe 'https://www.bilibili.com/video/BV_EXAMPLE/'
```

`probe` contacts the platform but does not save source media, subtitles or a
manifest. It returns title, author, description, duration, available formats,
chapters and separate lists for subtitle tracks and automatic captions. Metadata
without subtitle tracks means none were exposed to this request, not proof that
logged-in users cannot access captions. Nothing invokes ASR or an LLM API.

The optional Bun alias is `bun run {baseDir}/scripts/main.ts --media <action> ...`.
It takes the same arguments. Use the Python entrypoint on a host without Bun.

## Select outputs

Inspect the probe before deciding what to save. Honor explicit choices and
step-by-step confirmation. Avoid asking again for choices already specified.
Every download requires `--dir`; use the user's media storage outside the Vault
(normally `~/Downloads/资料/`), not the skill/repository directory.

```bash
# Original timestamped captions, no video/audio download or subtitle conversion
python3 {baseDir}/scripts/download_media.py subtitles 'URL' --dir ~/Downloads/资料/video-guide --sub-langs 'zh.*,ai-zh.*,en.*,-live_chat' --caption-kind both

# Preserve an original audio-only track, without lossy MP3 conversion
python3 {baseDir}/scripts/download_media.py audio 'URL' --dir ~/Downloads/资料/video-guide

# Video with sound, capped at 720p; fails rather than silently exceeding the cap
python3 {baseDir}/scripts/download_media.py video 'URL' --dir ~/Downloads/资料/video-guide --quality 720

# Video with sound plus requested caption tracks
python3 {baseDir}/scripts/download_media.py bundle 'URL' --dir ~/Downloads/资料/video-guide --quality 1080
```

`--quality` accepts `480`, `720` (default), `1080`, `2160`, `best`. Video merging
uses MKV without transcoding; the actual codecs and dimensions come from
ffprobe. `audio` requires an audio-only format and fails if none is exposed;
extracting from a combined file must be a subsequent explicit choice. To create
an ASR input, keep the original and separately convert with existing FFmpeg, e.g.
`ffmpeg -nostdin -n -i ORIGINAL -vn -ac 1 -ar 16000 asr-input.wav`.

Captions retain original formats and timing. `--caption-kind` accepts `manual`,
`auto`, `both` (default). Some extractors place AI tracks in `subtitles`; inspect
the language/name instead of assuming that field means human-authored. yt-dlp
may prefer manual over automatic tracks for the same language. No word-level
alignment, speaker identification or correction is claimed. A separate subtitles
request makes missing/unusable requested captions an error; `bundle` reports
`captions_status: not_downloaded` if no requested captions were saved.

Commands process one item only; Bilibili `/video/` URLs default to `p=1`, and a
provided `p=N` is preserved. Download other parts separately. Collection URLs
cannot authorize an entire series, profile, playlist or live recording. A
multi-clip result is limited to the first item by yt-dlp; report that selection.
Live/upcoming/still-processing streams are rejected.

## Platform adapters and evidence

These routes use the installed yt-dlp version. The existence of an upstream
extractor does not prove the current URL works; only a real successful run does.

| Adapter | URL hosts | Behavior / limitation |
|---|---|---|
| Bilibili | `bilibili.com`, `b23.tv` | One part; track and resolution access depends on the URL/account |
| YouTube | `youtube.com`, `youtu.be` | Existing JS runtime/login may be needed |
| X/Twitter | `x.com`, `twitter.com` | Video-bearing posts; article/thread extraction is separate |
| Douyin | `douyin.com`, `iesdouyin.com` | Upstream route; fresh cookies/verification or extractor failure possible |
| TikTok | `tiktok.com` | Short links forwarded intact to yt-dlp |
| Xiaohongshu | `xiaohongshu.com`, `xhslink.com` | Full share query retained during extraction, including `xsec_token` |
| Instagram / Facebook | `instagram.com`, `facebook.com`, `fb.watch` | Public access varies; no silent browser retry |
| Vimeo / Twitch / Reddit | `vimeo.com`, `twitch.tv`, `reddit.com`, `redd.it` | One item; live capture excluded |
| Weibo / AcFun | `weibo.com`, `weibo.cn`, `acfun.cn` | Upstream platform extractor |
| WeChat Channels | `weixin.qq.com`, `channels.weixin.qq.com` | Recognized, backend unavailable; fails before downloader execution |
| Kuaishou | `kuaishou.com`, `gifshow.com` | Recognized, backend unavailable; needs a separate share-page implementation |

Unknown hosts fail explicitly instead of accidentally scraping HTML and calling
it a completed video download. The WeChat article adapter's embedded MP4 support
does not imply WeChat Channels support. No online resolver, proxy change,
certificate installation, client automation or decryption backend is bundled.

## Credentials, errors and results

Default execution disables downloader config, netrc, cookie files and browser
cookie loading. No automatic retry with login or a different account is made.
If the user explicitly permits a named browser's cookies for this task, add
`--cookies-from-browser chrome` (also firefox/safari/edge/brave/chromium).
That invocation reads the local browser session; never export cookie contents
into chat/logs, and never treat a login prompt as permission to read a browser.
Network/fragment retries are disabled so denial/rate limits stop promptly.
`--timeout` is seconds per command, default 600, range 1–7200.

Each successful download gets a unique private subdirectory with media/subtitles
and `manifest.json`. The manifest includes source navigation URL (signed share
queries/tracking removed), selected video ID, platform, tool version, metadata,
actual file paths/sizes, SHA-256 and ffprobe duration/streams. Signed media URLs,
HTTP headers and raw downloader responses are not serialized. The original share
query is used in-memory for extraction; it is not preserved as a durable secret.

Success requires exit code 0, readable timed cues for subtitles, and positive
duration plus requested streams for media. Files are hashed. ffprobe validates
container/stream metadata; this is not full decoding or a transcript accuracy
check. Report missing captions, actual resolution and any unchecked quality.
Do not claim success based only on metadata, a downloader exit code or file
existence. On failure, retain the task directory for diagnosis, return
`ok: false`, and do not upload/archive/auto-delete anything. Repeating a request
creates a new directory; it does not reuse or overwrite another task's results.

## Design references (reviewed 2026-10-28)

The following are reference workflows, not dependencies or independently proven
performance claims. This implementation is original; their scripts are not
installed or executed.

- [MapleShaw/yt-dlp-downloader-skill](https://github.com/MapleShaw/yt-dlp-downloader-skill): broad platform routing, separate audio/subtitle/quality options. Its shell `eval`, implicit cookie advice and unpinned updates are not used here.
- [yaniv-golan/ytd-skill](https://github.com/yaniv-golan/ytd-skill): inspect formats/captions before download and inspect output files. Automatic installs and cookie export are not used here.
- [joeseesun/qiaomu-download](https://github.com/joeseesun/qiaomu-download): distinct platform backend status, verified-file results and explicit WeChat backend requirements. Its update, resolver and local-capture machinery is outside this adapter.
- [zyipeng/video-downloader](https://github.com/zyipeng/video-downloader): platform-specific share-link handling; custom Douyin/Kuaishou claims need separate review/live tests and are not copied.
- [yt-dlp supported sites](https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md) and [options](https://github.com/yt-dlp/yt-dlp#usage-and-options): actual backend contract. Upstream explicitly warns that listed sites can break.
