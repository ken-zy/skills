---
name: jdy-url-to-markdown
description: Fetch URLs and convert them to markdown using local HTTP or Chrome CDP, with optional PicList-to-R2 image persistence. Supports site-specific cleanup for WeChat, Zhihu, and Xiaohongshu, plus YouTube transcripts and X/Twitter threads. Use when the user asks to read, extract, archive, or save a webpage or article.
metadata:
  openclaw:
    requires:
      anyBins:
        - bun
---

# URL to Markdown

Fetches any URL and converts it to clean Markdown with YAML front matter.

## CLI Setup

**Agent Execution Instructions:**
1. Determine this SKILL.md file's directory path as `{baseDir}`
2. CLI entry point = `{baseDir}/scripts/main.ts`
3. Verify `bun` is on PATH. If not, tell user to install Bun: `curl -fsSL https://bun.sh/install | bash`
4. `${CMD}` = `bun run {baseDir}/scripts/main.ts`

## Preferences (EXTEND.md)

Check EXTEND.md existence (priority order):

    test -f .jdy-url-to-markdown/EXTEND.md && echo "project"
    test -f "${XDG_CONFIG_HOME:-$HOME/.config}/jdy-url-to-markdown/EXTEND.md" && echo "xdg"
    test -f "$HOME/.jdy-url-to-markdown/EXTEND.md" && echo "user"

### Supported Keys

| Key | Default | Values | Description |
|-----|---------|--------|-------------|
| `default_output_dir` | `40_Reference/Articles` | path | Default output directory |
| `default_timeout` | `30000` | ms | Default page load timeout |
| `default_image_mode` | `remote` | `remote`, `piclist`, `none` | Default image handling mode |
| `piclist_endpoint` | `http://127.0.0.1:36677/upload` | local URL | PicList-compatible upload endpoint |
| `persistent_image_hosts` | `img.jdy.systems` | comma-separated hosts | Hosts that do not need re-uploading |

If EXTEND.md not found, use defaults. No blocking setup flow required.

## Usage

    # Auto-detect best fetch method
    ${CMD} <url>

    # Force CDP (skip Level 1 local fetch)
    ${CMD} <url> --cdp

    # Save to specific path
    ${CMD} <url> -o /path/to/output.md

    # Force CDP and poll until the quality check passes or timeout expires
    ${CMD} <url> --wait

    # Custom page-load and --wait timeout
    ${CMD} <url> --timeout 60000

    # Persist article images through PicList -> WebP -> R2 before writing
    ${CMD} <url> --images piclist

    # Save text only
    ${CMD} <url> --images none

## How It Works

1. **Router** checks URL against site-rules.json for domain-specific config
2. **Level 1** (default): local fetch() + Readability + Turndown -> quality check
3. **Level 2** (fallback or forced): CDP daemon -> full JS rendering -> same pipeline
4. **Adapters** (WeChat, YouTube, X/Twitter, ZSXQ): bypass generic extraction when platform-specific DOM/API handling is required
5. **Media persistence** optionally downloads unique images, uploads them through PicList, verifies public WebP URLs, and rewrites Markdown
6. **Writer** generates YAML front matter and saves to output path

The WeChat adapter normalizes lazy-loaded `data-src` images, removes structural
QR/reward noise and placeholder media before reusing the shared parser and
quality gate. File output remains centralized in the writer.

Use `--images piclist` for a durable archive when the user authorizes image
uploads and PicList is running. Keep adapters limited to extraction and cleanup;
do not add PicList logic to a site adapter. The media stage runs only after the
quality gate and before the writer. If any download, upload, or public WebP
verification fails, do not write the Markdown file; retain temporary images for
diagnosis and report the path. PicList may have uploaded a successful prefix of
the image set, so do not attempt automatic R2 deletion.

## Agent Quality Gate

After every run, verify:
1. Markdown title matches expected page content
2. Body contains meaningful article text, not just navigation/errors
3. No obvious failure signs (login walls, empty content, framework shells)
4. With `--images piclist`, all image URLs use a configured persistent host and return `image/webp`

If quality is poor:
- Try `--cdp` to force browser rendering
- Try `--wait` for login-required pages
- Check stderr for quality check diagnostics

## Exit Codes

- 0: success (stdout = output file path)
- 1: fetch failed
- 2: quality check failed (content too short or garbled)
- 3: CDP daemon connection failed
- 4: image persistence failed; Markdown was not written
