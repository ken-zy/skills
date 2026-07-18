# jdy-url-to-markdown Design Spec

> Date: 2026-04-09 | Status: Draft (rev.1) | Replaces: baoyu-url-to-markdown
>
> **Rev.1 changes (2026-04-09):** Codex review 修订 — 路由改为域名后缀匹配 + 别名、daemon 加请求互斥锁、X cookie 持久化加安全约束、slug 生成加字符白名单、YAML 字段加引号策略、运行时改为要求预装 Bun

## 1. Overview

A Claude Code skill (independent plugin repo) that fetches any URL and converts it to clean Markdown with YAML front matter. Core differentiators vs existing solutions:

- **Two-level fetch with quality gating** — local fetch first, CDP only when needed
- **Persistent CDP daemon** — reuses Chrome connection across calls (~200ms vs ~2s)
- **Content quality detection** — never silently returns garbage
- **Site-specific cleanup rules + adapters** — extensible without changing core

## 2. Decisions Log

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Project location | Independent repo (Claude plugin) | Reusable across projects |
| Runtime | Bun (requires preinstall) | Native TS, fast, precedent in ecosystem; skill validates `bun` on PATH at startup |
| Jina Reader | Excluded | Privacy, adds external dependency, doesn't help with top use case (WeChat) |
| CDP implementation | Fork chrome-cdp-skill daemon | Proven, zero-dep, persistent connection |
| Content extraction | Readability + Turndown | Local-only, no remote API (Defuddle removed) |
| Architecture | Modular (方案 B) | Balanced: maintainable without over-engineering |
| Dependencies | 4 npm packages, pinned versions | Minimal, trusted, auditable |

## 3. Architecture

```
URL Input
    │
    ▼
┌──────────┐     ┌───────────────────────────────┐     ┌──────────┐
│  Router  │────▶│          Fetcher              │────▶│  Writer  │
│ site-rules│     │ fetch → parse → clean → QA   │     │ output   │
└──────────┘     │  (calls Parser internally)    │     └──────────┘
                 └───────────────────────────────┘
                          or
                 ┌───────────────────────────────┐
                 │         Adapter               │
                 │ (YouTube/X: own extract logic) │
                 └───────────────────────────────┘
```

Note: Parser (parser.ts) is a library module called by Fetcher and Adapters, not an independent pipeline stage. Fetcher needs parsed markdown to run quality checks before deciding whether to fall through to the next level.

### 3.1 Router (main.ts → site-rules.json)

Reads `site-rules.json` to determine:
- Which fetch level to start at (skip L1 for known JS-heavy sites)
- Which adapter to use (youtube, x-twitter, or generic)
- Which post-processing cleaners to apply

**Host matching:** Each key in `site-rules.json` is a domain pattern. Matching order:
1. Exact match: `mp.weixin.qq.com`
2. Suffix match: `*.zhihu.com` matches `www.zhihu.com`, `zhuanlan.zhihu.com`, etc.
3. Short-link aliases listed in `"aliases"` array (e.g. `youtu.be` → youtube adapter)

Router normalizes the input URL host before matching: strip `www.` prefix, lowercase, then check exact → suffix → alias in order.

```json
{
  "mp.weixin.qq.com": {
    "startLevel": 2,
    "cdpActions": ["waitForSelector:#js_content,.rich_media_content:4500", "removeOverlays:.js_wechat_qrcode,.wx_tips,.rich_media_global_msg", "autoScroll"],
    "cleaners": ["wechat"]
  },
  "*.zhihu.com": {
    "startLevel": 2,
    "cleaners": ["zhihu"]
  },
  "*.xiaohongshu.com": {
    "startLevel": 2,
    "cdpActions": ["expandContent"],
    "cleaners": ["xiaohongshu"]
  },
  "*.youtube.com": {
    "adapter": "youtube",
    "aliases": ["youtu.be"]
  },
  "x.com": {
    "adapter": "x-twitter",
    "aliases": ["twitter.com"]
  }
}
```

Unlisted domains start at Level 1 with generic processing.

### 3.2 Fetcher (fetcher.ts)

Two-level cascade with quality gating after each level:

```
Level 1: Local fetch + Readability + Turndown
  │  Native fetch() with browser User-Agent → HTML → Readability extract → Turndown convert
  │  Headers: User-Agent (Chrome macOS), Accept-Language: zh-CN,zh;q=0.9,en;q=0.8
  │  For: public pages, blogs, news, static content
  │
  │── qualityCheck() ──▶ pass → Parser
  │                      fail ↓
  │
Level 2: CDP daemon
  │  Connect to running Chrome via persistent daemon
  │  Full JS rendering → extract HTML → Readability + Turndown
  │  For: JS-heavy SPAs, login walls, anti-scraping sites
  │
  └── qualityCheck() ──▶ pass → Parser
                         fail → error with diagnostics
```

**Quality check criteria:**
1. Text length after stripping markdown markers: ≥ 120 chars
2. No anti-scraping markers: "access denied", "403 forbidden", "请完成验证", "captcha", "just a moment", "checking your browser"
3. No login wall markers: "请登录", "sign in to continue", "log in to", "Become a .* Member", "Subscribe to"
4. Has at least one "useful paragraph" — a paragraph is useful only if it:
   - Contains ≥ 8 words (or ≥ 15 Chinese characters)
   - Is not an image-only line
   - Is not a heading-only line
   - Is not a navigation fragment (link list without prose)
5. Total useful paragraph count ≥ 2 (single-paragraph results are usually extraction artifacts)

The quality check function returns `{ pass: boolean, reason?: string, stats?: { charCount, usefulParagraphs } }` for logging and debugging.

### 3.3 CDP Layer (cdp/)

Forked from chrome-cdp-skill's architecture:

**client.ts:**
- Direct WebSocket connection to Chrome's CDP endpoint
- Port discovery via `DevToolsActivePort` file (macOS: `~/Library/Application Support/Google/Chrome/`, Linux: `~/.config/google-chrome/`)
- No TCP port scanning — `DevToolsActivePort` is the only reliable source
- Session management via `Target.attachToTarget`

**daemon.ts:**
- **Global single-daemon model** (not per-tab like chrome-cdp-skill) — simpler for our use case since we process one URL at a time
- **Request mutex:** daemon holds at most one active request; concurrent callers receive NDJSON `{"error":"busy"}` and should retry with backoff. This prevents network journal cross-contamination between requests (especially X adapter's `Network.responseReceived` events)
- Creates a new tab for each request via `Target.createTarget`, closes it after extraction
- Spawns as detached background process on first CDP request
- Listens on Unix socket (`~/.cache/jdy-url-to-markdown/daemon.sock`) for subsequent requests
- NDJSON request/response protocol
- Health check endpoint for connection reuse
- Auto-exit after 30 minutes idle
- **"Allow debugging" modal handling**: on first connect, Chrome shows a permission dialog. Daemon retries connection for up to 6 seconds (20 retries × 300ms) to allow user to click "Allow". This is normal, not an error.
- Key operations exposed:
  - `navigate(url)` — navigate and wait for network idle
  - `getHTML()` — extract full page HTML after optional `waitForSelector`
  - `evaluate(expression)` — run JS in page context
  - `getAccessibilityTree()` — AX tree extraction (fallback for Readability failures)
  - `enableNetwork()` — enable `Network.enable` and start buffering XHR responses
  - `getNetworkResponses(urlPattern)` — return buffered responses matching pattern
  - `getResponseBody(requestId)` — get body of a specific network response
  - `setCookies(cookies)` — inject cookies via `Network.setCookie`
  - `getCookies(domain)` — export cookies for persistence

Note: The network journal operations (enableNetwork, getNetworkResponses, getResponseBody) are additions beyond chrome-cdp-skill's original scope, required by the X/Twitter adapter.

### 3.4 Parser (parser.ts)

Pipeline:

```
HTML input
    │
    ▼
linkedom.parseHTML(html)          ← create DOM from HTML string
    │
    ▼
new Readability(doc, {           ← extract article content
  charThreshold: 120,            ← lowered from default 500 for Chinese content
  nbTopCandidates: 10
}).parse()
    │
    ├─ success → article.content (HTML)
    │                │
    │                ▼
    │         TurndownService.turndown(html)  ← convert to Markdown
    │                │
    │                ▼
    │         Apply cleaners (if any)
    │                │
    │                ▼
    │         Return { markdown, metadata }
    │
    └─ failure (null result, e.g. SPA shell) →
              │
              ▼
         [If CDP level] getAccessibilityTree()
              │
              ▼
         Map AX roles to Markdown structure
         (heading → #, paragraph → text, link → [](), list → -)
              │
              ▼
         Return { markdown, metadata }
```

**Metadata extraction priority (from HTML before Readability strips it):**

```
1. Open Graph tags: og:title, og:description, og:site_name, article:author, article:published_time
2. schema.org JSON-LD: headline, author.name, datePublished
3. HTML meta tags: author, description, date
4. Fallback: <title>, URL-derived site name
```

**Turndown configuration:**
- GitHub Flavored Markdown plugin (tables, strikethrough)
- Heading style: ATX (`#`)
- Code block style: fenced (```)
- Link style: inlined
- Bullet list marker: `-`
- Emphasis delimiter: `_`
- Image alt text preserved
- **Remove rules** (critical — without these, scripts/SVGs pollute output):
  `turndown.remove(["script", "style", "iframe", "noscript", "template", "svg", "path"])`
- **Custom rules:**
  - `dropInvisibleAnchors`: remove `<a>` tags with no text content and no child media
  - `collapseFigure`: prevent `<figure>` from producing excessive blank lines

### 3.5 Adapters (adapters/)

Adapters bypass the normal fetch→parse pipeline entirely. They implement their own extraction logic and return `{ markdown: string, metadata: Metadata }`.

**youtube.ts:**
- Extract video ID from URL
- Always uses CDP (YouTube requires JS rendering):
  1. Navigate to video page via CDP daemon
  2. Extract `INNERTUBE_API_KEY` from `window.ytcfg.data_.INNERTUBE_API_KEY`
  3. POST to `/youtubei/v1/player` with `clientName: "ANDROID"` to get `captionTracks`
  4. Fetch transcript XML from the `baseUrl` in `captionTracks[0]` (URL is signed, cannot be constructed manually)
  5. Parse transcript XML: handle both `<text start="" dur="">` and `<p t="" d="">` formats
  - Fallback: if InnerTube API fails, extract from `ytInitialPlayerResponse` embedded in page HTML
- Extract chapters from description (timestamp patterns like `0:00`, `1:23:45`)
- Extract video metadata: title, channel, duration, publish date from page
- Build markdown: metadata header, chapters with timestamps, full transcript text
- Metadata: video URL, channel name, duration, publish date

Note: The old `timedtext` API endpoint is deprecated and returns empty/403 for most videos. Must use InnerTube player API.

**x-twitter.ts:**
- Requires CDP with network interception (X uses GraphQL, DOM polling is unreliable)
- Extraction strategy: intercept XHR responses, not scrape DOM
  1. Enable `Network.enable` on CDP session
  2. Navigate to tweet URL via daemon
  3. Listen for `Network.responseReceived` matching `/graphql/*/TweetDetail` or `TweetResultByRestId`
  4. Extract structured tweet data from GraphQL JSON payload
  5. For threads: scroll page + click "Show replies" to trigger additional GraphQL requests, collect all
  6. For quoted tweets: extract from nested `quoted_status_result` in payload
- Cookie persistence for login state:
  - On first use: detect login wall → prompt user to log in in Chrome → wait → verify `auth_token` + `ct0` cookies present
  - **First-time save:** print explicit notice to stderr ("Saving X session cookies to ~/.cache/...") so user is aware credentials are being persisted
  - Save cookies to `~/.cache/jdy-url-to-markdown/x-session-cookies.json` with `chmod 0600` (owner-only read/write)
  - On subsequent use: restore cookies from file → inject via `Network.setCookie` → proceed
  - If restored cookies expired (HTTP 401/403 or login wall re-detected): delete stale file, re-prompt login flow
  - **Cookie file contains long-lived session tokens** — treat as sensitive. Parent directory `~/.cache/jdy-url-to-markdown/` should also be `0700`
- Build markdown: author info, tweet text, image URLs, thread structure, engagement metrics
- CDP daemon requirements: must expose `Network.enable`, `Network.responseReceived` event listener, and `Network.getResponseBody` in addition to basic navigate/getHTML

Note: This means the CDP daemon needs network journal capability beyond what chrome-cdp-skill provides. See Section 3.3 for required additions.

### 3.6 Cleanup Rules (rules/)

**site-rules.json** defines which cleaners to apply per domain.

**cleaners.ts** exports named cleaner functions:

```typescript
type Cleaner = (markdown: string) => string;

wechat:
  - Remove everything after "预览时标签不可点" (WeChat UI noise)
  - Remove "微信扫一扫赞赏作者" block and all content below
  - Remove duplicate title (WeChat often renders title twice)
  - Strip "原创 <author> <account>" line → preserve as metadata only

zhihu:
  - Remove "登录后你可以" prompts
  - Remove sidebar recommendation blocks
  - Remove "发布于 / 编辑于" footer noise, preserve dates as metadata

xiaohongshu:
  - Remove app download prompts and footer navigation
  - Extract image gallery URLs into markdown image list
  Note: "查看更多" expansion is a fetch-time CDP action, not a post-process cleaner.
  site-rules.json should specify a `cdpActions` field for this:
  "www.xiaohongshu.com": { "startLevel": 2, "cdpActions": ["expandContent"], "cleaners": ["xiaohongshu"] }
```

### 3.7 Writer (writer.ts)

**Output path:** `40_Reference/Articles/YYYYMMDD/<title-slug>.md`

- `YYYYMMDD`: capture date
- `<title-slug>`: from extracted title, kebab-case, max 50 chars, Chinese preserved
- **Slug sanitization:** strip characters outside `[a-zA-Z0-9\u4e00-\u9fff-]` (alphanumeric, Chinese, hyphens), collapse consecutive hyphens, trim leading/trailing hyphens. If slug is empty after sanitization, use `untitled`. Emoji and special chars (`/ : ? * | " < >`) are stripped, not replaced.
- Conflict: append `-HHmmss` suffix

**YAML front matter format:**

```yaml
---
url: "https://example.com/article"
title: "Article Title"
author: "Author Name"
published: "2026-04-09"
site_name: "Example Site"
description: "Brief description"
captured_at: "2026-04-09T12:00:00Z"
fetch_level: 1
---
```

**YAML safety:** All string values are double-quoted. Internal double quotes are escaped as `\"`. Newlines in description/title are replaced with a single space. Values containing `---` are safe inside double quotes (no special YAML meaning).

`fetch_level` records which level actually succeeded (1 or 2), useful for debugging and tuning site-rules.

**Output directory is configurable** via SKILL.md EXTEND.md mechanism (same as baoyu's pattern — check project-level, then user-level, then default).

## 4. CLI Interface

```bash
# Basic usage — auto-detect everything
bun run scripts/main.ts <url>

# Force CDP (skip Level 1)
bun run scripts/main.ts <url> --cdp

# Specify output path
bun run scripts/main.ts <url> -o /path/to/output.md

# Wait mode for login-required pages (CDP only)
bun run scripts/main.ts <url> --wait

# Page load timeout (default 30000ms)
bun run scripts/main.ts <url> --timeout 60000
```

**Exit codes:**
- 0: success
- 1: fetch failed (all levels exhausted)
- 2: quality check failed (content extracted but below threshold)
- 3: CDP daemon connection failed

**Stdout:** path to generated markdown file (for script chaining)
**Stderr:** progress messages, diagnostics, quality check reasons

## 5. SKILL.md Integration

The SKILL.md will register as a Claude Code skill with:
- Trigger: user wants to save a webpage as markdown, mentions "抓取", "fetch", "save page", "url to markdown"
- Usage: `bun run ${SKILL_DIR}/scripts/main.ts <url> [options]`
- EXTEND.md support for: default output directory, default timeout, default fetch level

## 6. Data Flow Example

**Scenario: User says "save this WeChat article"**

```
1. main.ts receives URL: mp.weixin.qq.com/s/abc123
2. Router checks site-rules.json → match: startLevel=2, cdpActions=[waitForSelector, removeOverlays, autoScroll], cleaners=["wechat"]
3. Fetcher skips Level 1, goes directly to Level 2 (CDP)
4. CDP daemon connects (or reuses existing connection), creates new tab
5. daemon.navigate(url) → waits for network idle
6. Execute cdpActions: wait for #js_content (4.5s max) → remove overlay elements → scroll to trigger lazy-load images
7. daemon.getHTML() → returns full rendered HTML
8. Parser: linkedom.parseHTML → Readability.parse(charThreshold=120) → Turndown.turndown
9. Cleaner: wechat() strips bottom noise (below "预览时标签不可点")
10. Quality check: 800 chars, 5 useful paragraphs → pass
11. Writer: generates front matter, writes to 40_Reference/Articles/20260409/article-title.md
12. CDP daemon closes tab
13. Stdout: /path/to/article-title.md
```

**Scenario: User says "save this blog post"**

```
1. URL: example.com/blog/some-post
2. Router: no match in site-rules → startLevel=1, no adapter, no cleaners
3. Fetcher Level 1: fetch(url) → HTML → Readability → Turndown
4. Quality check: 2000 chars, clean content → pass
5. Writer: generates front matter, writes file
6. (CDP never touched — fast path, < 1 second)
```

**Scenario: User says "save this YouTube video"**

```
1. URL: youtube.com/watch?v=xyz
2. Router: match → adapter="youtube"
3. YouTube adapter: extract video ID → CDP navigate to page
4. Extract INNERTUBE_API_KEY from page JS
5. POST /youtubei/v1/player → get captionTracks → fetch transcript XML from baseUrl
6. Parse transcript XML, extract chapters from description
7. Build markdown: title + chapters + transcript
8. Writer: writes file
```

## 7. Error Handling

| Error | Behavior |
|-------|----------|
| Network unreachable | Fail immediately, exit 1, clear error message |
| Level 1 fetch returns non-200 | Log reason, fall through to Level 2 |
| Level 1 quality check fails | Log reason (e.g. "content too short: 45 chars"), fall through to Level 2 |
| CDP daemon not running, Chrome not found | Attempt to start daemon; if Chrome not found, exit 3 with setup instructions |
| CDP timeout | Retry once with 2x timeout; if still fails, exit 1 |
| Level 2 quality check fails | Exit 2 with diagnostic: what was extracted, why it failed, suggestion (try --wait?) |
| Adapter-specific failure (e.g. no YouTube transcript) | Fall back to generic CDP extraction for that URL |
| File write permission error | Exit 1, print path and error |

## 8. Scope Boundaries

**In scope (v1):**
- Two-level fetch cascade with quality gating
- Readability + Turndown parsing with AX Tree fallback
- CDP daemon (forked from chrome-cdp-skill)
- YAML front matter from OG/schema.org/meta
- Adapters: YouTube (transcript), X/Twitter (threads)
- Cleanup rules: WeChat, Zhihu, Xiaohongshu
- Configurable output directory via EXTEND.md
- CLI with --cdp, --wait, --timeout, -o flags

**Out of scope (v1):**
- Batch URL processing (one URL per invocation)
- Image downloading / local image caching
- PDF/EPUB conversion
- B站 adapter (v2)
- Search engine over collected articles
- MCP server interface
- Web UI

## 9. Dependencies

All pinned to exact versions, no `^` or `~`:

```json
{
  "dependencies": {
    "@mozilla/readability": "0.6.0",
    "turndown": "7.2.4",
    "linkedom": "0.18.12",
    "turndown-plugin-gfm": "1.0.2"
  }
}
```

CDP layer: zero dependencies (Node 22 native WebSocket, forked from chrome-cdp-skill).

**linkedom compatibility note:** Readability depends on DOM APIs (TreeWalker, getComputedStyle) that linkedom implements incompletely. baoyu-skills uses jsdom instead. Implementation plan should include a Step 1 validation: test Readability + linkedom against WeChat and Zhihu HTML samples. If extraction quality is significantly worse than jsdom, replace linkedom with jsdom (adds ~3MB but guarantees compatibility). This is a known trade-off: linkedom is lighter/faster but less DOM-complete.

## 10. Project Structure

```
jdy-url-to-markdown/
├── scripts/
│   ├── main.ts              # CLI entry, arg parsing, orchestration
│   ├── fetcher.ts           # Two-level fetch + quality check
│   ├── parser.ts            # Readability + Turndown + metadata extraction
│   ├── writer.ts            # Output path generation + file writing
│   ├── cdp/
│   │   ├── client.ts        # CDP WebSocket client (port discovery, connection)
│   │   └── daemon.ts        # Persistent daemon (Unix socket, NDJSON, auto-exit)
│   ├── adapters/
│   │   ├── index.ts         # Adapter registry (URL → adapter mapping)
│   │   ├── youtube.ts       # Transcript + chapters extraction
│   │   └── x-twitter.ts     # Tweet/thread extraction via CDP
│   └── rules/
│       ├── site-rules.json  # Domain → config mapping
│       └── cleaners.ts      # Named cleaner functions
├── package.json
├── bun.lockb
├── .claude-plugin/
│   └── plugin.json          # Claude plugin manifest
├── SKILL.md                 # Claude Code skill definition
├── CLAUDE.md
├── LICENSE
└── README.md
```

## 11. Testing Strategy

- **Unit tests:** quality check function, cleaners, metadata extraction, URL routing
- **Integration tests:** end-to-end fetch of known stable URLs (e.g. Wikipedia article)
- **Manual verification:** WeChat, YouTube, X — these require real browser state and change frequently, automated testing is brittle
