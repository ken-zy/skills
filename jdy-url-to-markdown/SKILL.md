---
name: jdy-url-to-markdown
description: Fetch URLs and convert them to markdown using local HTTP or Chrome CDP, with classified R2-script or PicList image persistence. Supports site-specific cleanup for WeChat, Zhihu, and Xiaohongshu, plus YouTube transcripts and X/Twitter threads. Use when the user asks to read, extract, archive, or save a webpage or article.
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
5. For persistent archives containing GIFs, verify `gif2webp` is on `PATH`. Do not
   install it automatically; report a missing converter as an image-persistence failure.

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
| `default_image_mode` | `remote` | `remote`, `piclist`, `r2`, `none` | Default image handling mode; set `r2` when Agent uploads require classified keys |
| `piclist_endpoint` | `http://127.0.0.1:36677/upload` | local URL | PicList-compatible upload endpoint |
| `r2_upload_script` | `scripts/r2-upload.sh` | path | Classified Agent uploader; relative paths resolve from the command working directory |
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

    # Persist article images through the classified R2 script before writing
    ${CMD} <url> --images r2

    # Use PicList's configured manual path policy instead
    ${CMD} <url> --images piclist

    # Save text only
    ${CMD} <url> --images none

## How It Works

1. **Router** checks URL against site-rules.json for domain-specific config
2. **Level 1** (default): local fetch() + Readability + Turndown -> quality check
3. **Level 2** (fallback or forced): CDP daemon -> full JS rendering -> same pipeline
4. **Adapters** (WeChat, YouTube, X/Twitter, ZSXQ): bypass generic extraction when platform-specific DOM/API handling is required
5. **Media persistence** optionally downloads unique images, uploads them through the classified R2 script or PicList, verifies public WebP URLs, and rewrites Markdown
6. **Writer** generates YAML front matter and atomically saves to the output path; reruns reuse an existing note with the same canonical source URL

The WeChat adapter normalizes lazy-loaded `data-src` images, removes structural
QR/reward noise and placeholder media before reusing the shared parser and
quality gate. It also rejects body-like title metadata and recovers a short,
single-line title from WeChat-specific title nodes or a clearly delimited first
title segment. If no trustworthy title can be recovered, fail without writing.
File output remains centralized in the writer.
When a site rule requires its adapter for persistent-image capture, an adapter or CDP failure is
fatal: do not downgrade to generic HTTP extraction because it may silently lose
lazy-loaded images.

Use `--images r2` for a durable Agent archive that must follow classified paths.
The uploader assigns stable keys under
`web-articles/<source-host>/<ascii-path>-<source-url-hash>/img-NNN.webp` (the
path portion is omitted when it has no ASCII slug); rerunning the same canonical
source URL reuses the same keys. Keep adapters limited to
extraction and cleanup. The media stage runs only after the quality gate and
before the writer. If any download, upload, or public WebP verification fails,
do not write the Markdown file; retain temporary images for diagnosis and report
the path. A successful prefix of the image set may already exist remotely, so do
not attempt automatic R2 deletion.

## Obsidian Vault Archives

When the target vault requires every image to use `https://img.jdy.systems/*.webp`:

1. Treat a request to save or archive an article as authorization to persist its
   meaningful article images through the configured `r2_upload_script`.
2. Set `default_image_mode: r2` in the vault's
   `.jdy-url-to-markdown/EXTEND.md`, or pass `--images r2` explicitly.
3. Do not use `remote`. Use `none` only when the user explicitly requests a
   text-only archive or the source contains no meaningful images.
4. Resolve relative image URLs against the source page before downloading them.
   Convert GIF sources to WebP with `gif2webp` before the first persistent write.
5. Reject Markdown containing Unicode replacement characters (`�`) or malformed
   GFM tables. Normalize block-heavy table cells before the quality gate.
6. Fail closed when the required site adapter or CDP is unavailable, the upload
   script fails, an upload response is ambiguous, or the public result is not an
   HTTPS WebP on a configured persistent host. Do not write or downgrade the
   article to text-only after these failures.
7. Treat reruns of the same canonical source URL as upgrades to the canonical
   raw archive note: replace that note atomically only after content and image
   verification succeed. Do not overwrite article analyses, summaries or other
   derivative notes merely because they share the source URL. Keep timestamp
   suffixes only for a different URL that collides on filename.
8. Do not retry or delete after an uploader returns an invalid/non-WebP URL
   because the remote write may already have happened. Retain temporary files
   and report the failure.

## Agent Quality Gate

After every run, verify:
1. Metadata title matches expected page content, is single-line, no longer than
   180 characters and is not copied from the body. WeChat pages without a
   trustworthy recoverable title must fail closed.
2. Body contains meaningful article text, not just navigation/errors
3. No obvious failure signs (login walls, empty content, framework shells)
4. Body contains no Unicode replacement characters and every GFM table has a
   single-line header and consistent single-line rows
5. With `--images r2` or `--images piclist`, all image URLs, including originally relative URLs,
   use a configured persistent host and return `image/webp`
6. Only one canonical raw archive note exists for the source URL after a rerun.
   Derived analyses may share the URL and must remain outside overwrite scope.

If quality is poor:
- Try `--cdp` to force browser rendering
- Try `--wait` for login-required pages
- Check stderr for adapter, Chrome launch, daemon, and quality diagnostics

## Exit Codes

- 0: success (stdout = output file path)
- 1: fetch failed
- 2: quality check failed (content too short or garbled)
- 3: CDP daemon connection failed
- 4: image persistence failed; Markdown was not written
