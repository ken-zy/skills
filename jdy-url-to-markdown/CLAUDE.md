# jdy-url-to-markdown

URL to Markdown tool, used as a Claude Code skill.

## Development

- Runtime: Bun
- Test: `bun test`
- Media adapter tests: `python3 -m unittest discover -s tests -p 'test_media_download.py'`
- Native backend tests: `python3 -m unittest discover -s tests -p 'test_native_media.py'`
- Media tests including real synthetic files (run on the selected execution host): `python3 -m unittest discover -s tests -p 'test_*media*.py'`
- Entry: `bun run scripts/main.ts <url>`
- Platform media entry: `python3 scripts/download_media.py doctor|probe|subtitles|audio|video|bundle ...`

## Architecture

- `scripts/main.ts` -- CLI entry, arg parsing
- `scripts/router.ts` -- domain pattern matching, site rule dispatch
- `scripts/fetcher.ts` -- two-level fetch cascade (local fetch -> CDP)
- `scripts/parser.ts` -- Readability + Turndown parsing
- `scripts/quality.ts` -- content quality check (5 criteria)
- `scripts/writer.ts` -- slug generation, YAML front matter, file output
- `scripts/types.ts` -- shared TypeScript interfaces
- `scripts/cdp/` -- CDP client (auto-launches Chrome profile_1) and daemon
- `scripts/adapters/` -- WeChat, YouTube, X/Twitter, ZSXQ adapters
- `scripts/adapters/media_platforms.py` -- media platform routing, share-URL handling and explicit backend limits
- `scripts/download_media.py` -- bounded yt-dlp invocation, original subtitles/audio, ffprobe checks and JSON manifests; independent of Bun/article/R2 paths
- `scripts/adapters/native_media.py` -- requested-photo Apollo state, bounded HTTPS MP4 transfers and opt-in fixed WeChat resolver
- `scripts/browser_media.ts` -- Deno/CDP fixed browser reads for selected Reddit/Douyin/Xiaohongshu pages and Vimeo official download dialogs; no cookie/storage APIs
- `scripts/media/` -- site-independent image download, classified R2-script/PicList upload, WebP verification, and Markdown URL rewrite
- `scripts/media/video-nodes.ts` -- preserve embedded MP4 players and unresolved video positions before HTML cleanup
- `scripts/media/persist-videos.ts` -- bounded MP4 download, ffprobe validation, R2 upload and public verification
- `scripts/media/r2-upload-video.sh` -- bundled non-converting MP4 uploader; preserves local input until caller verification
- `scripts/rules/` -- site rules and cleaner functions
