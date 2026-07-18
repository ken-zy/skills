---
name: jdy-url-to-markdown
description: Fetch any URL and convert to markdown using Chrome CDP. Supports two-level fetch (local -> CDP), site-specific cleanup (WeChat, Zhihu, Xiaohongshu), YouTube transcripts, and X/Twitter threads. Use when user wants to save a webpage as markdown.
version: 0.1.0
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

If EXTEND.md not found, use defaults. No blocking setup flow required.

## Usage

    # Auto-detect best fetch method
    ${CMD} <url>

    # Force CDP (skip Level 1 local fetch)
    ${CMD} <url> --cdp

    # Save to specific path
    ${CMD} <url> -o /path/to/output.md

    # Force CDP (alias, reserved for future login-wait mode)
    ${CMD} <url> --wait

    # Custom timeout
    ${CMD} <url> --timeout 60000

## How It Works

1. **Router** checks URL against site-rules.json for domain-specific config
2. **Level 1** (default): local fetch() + Readability + Turndown -> quality check
3. **Level 2** (fallback or forced): CDP daemon -> full JS rendering -> same pipeline
4. **Adapters** (YouTube, X/Twitter): bypass generic pipeline with specialized extraction
5. **Writer** generates YAML front matter and saves to output path

## Agent Quality Gate

After every run, verify:
1. Markdown title matches expected page content
2. Body contains meaningful article text, not just navigation/errors
3. No obvious failure signs (login walls, empty content, framework shells)

If quality is poor:
- Try `--cdp` to force browser rendering
- Try `--wait` for login-required pages
- Check stderr for quality check diagnostics

## Exit Codes

- 0: success (stdout = output file path)
- 1: fetch failed
- 2: quality check failed (content too short or garbled)
- 3: CDP daemon connection failed
