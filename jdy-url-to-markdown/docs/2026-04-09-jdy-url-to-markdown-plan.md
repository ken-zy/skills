# jdy-url-to-markdown Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Claude Code skill that fetches any URL and converts it to clean Markdown with YAML front matter, using a two-level fetch cascade (local fetch -> CDP) with quality gating.

**Architecture:** Router dispatches URLs via domain pattern matching to either the generic Fetcher (two-level cascade with quality checks) or specialized Adapters (YouTube, X/Twitter). Parser (Readability + Turndown) is a shared library. CDP daemon provides persistent Chrome connection via Unix socket.

**Tech Stack:** Bun (runtime), TypeScript, @mozilla/readability, turndown, linkedom, turndown-plugin-gfm. CDP layer is zero-dependency (native WebSocket).

**Design Spec:** `docs/2026-04-09-jdy-url-to-markdown-design.md`

---

## File Structure

```
jdy-url-to-markdown/
├── scripts/
│   ├── main.ts              # CLI entry, arg parsing, router, orchestration
│   ├── fetcher.ts           # Two-level fetch cascade + quality check
│   ├── parser.ts            # Readability + Turndown + metadata extraction
│   ├── quality.ts           # Quality check function (shared by fetcher)
│   ├── writer.ts            # Slug generation, YAML front matter, file output
│   ├── types.ts             # Shared type definitions
│   ├── cdp/
│   │   ├── client.ts        # CDP WebSocket client (port discovery, connection, protocol)
│   │   └── daemon.ts        # Persistent daemon (Unix socket, NDJSON, mutex, auto-exit)
│   ├── adapters/
│   │   ├── youtube.ts       # YouTube transcript + chapters extraction
│   │   └── x-twitter.ts     # Tweet/thread extraction via CDP network interception
│   └── rules/
│       ├── site-rules.json  # Domain pattern -> config mapping
│       └── cleaners.ts      # Named cleaner functions (wechat, zhihu, xiaohongshu)
├── tests/
│   ├── quality.test.ts
│   ├── writer.test.ts
│   ├── router.test.ts
│   ├── parser.test.ts
│   ├── cleaners.test.ts
│   └── fixtures/            # HTML samples for parser/cleaner tests
│       ├── simple-article.html
│       ├── wechat-article.html
│       └── zhihu-article.html
├── package.json
├── tsconfig.json
├── .claude-plugin/
│   └── plugin.json
├── SKILL.md
├── CLAUDE.md
├── .gitignore
└── README.md
```

**Design note:** `quality.ts` is extracted from `fetcher.ts` as a separate module because it's independently testable and the quality check logic is non-trivial (5 criteria, Chinese character handling). `types.ts` holds shared interfaces used across modules.

---

### Task 1: Project Scaffolding & Dependencies

**Files:**
- Create: `package.json`
- Create: `tsconfig.json`
- Create: `scripts/types.ts`

- [ ] **Step 1: Initialize package.json**

```json
{
  "name": "jdy-url-to-markdown",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "scripts": {
    "start": "bun run scripts/main.ts",
    "test": "bun test"
  },
  "dependencies": {
    "@mozilla/readability": "0.6.0",
    "turndown": "7.2.4",
    "linkedom": "0.18.12",
    "turndown-plugin-gfm": "1.0.2"
  },
  "devDependencies": {
    "@types/turndown": "5.0.5"
  }
}
```

- [ ] **Step 2: Create tsconfig.json**

```json
{
  "compilerOptions": {
    "target": "ESNext",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "outDir": "dist",
    "rootDir": ".",
    "types": ["bun-types"]
  },
  "include": ["scripts/**/*.ts", "tests/**/*.ts"]
}
```

- [ ] **Step 3: Create shared type definitions**

Create `scripts/types.ts`:

```typescript
export interface Metadata {
  url: string;
  title: string;
  author?: string;
  published?: string;
  site_name?: string;
  description?: string;
}

export interface ParseResult {
  markdown: string;
  metadata: Metadata;
}

export interface QualityResult {
  pass: boolean;
  reason?: string;
  stats?: {
    charCount: number;
    usefulParagraphs: number;
  };
}

export interface SiteRule {
  startLevel?: number;
  adapter?: string;
  aliases?: string[];
  cdpActions?: string[];
  cleaners?: string[];
}

export type SiteRules = Record<string, SiteRule>;

export type Cleaner = (markdown: string) => string;
```

- [ ] **Step 4: Install dependencies**

Run: `bun install`
Expected: lockfile created, node_modules populated, no errors.

- [ ] **Step 5: Verify Bun + TypeScript works**

Run: `echo 'console.log("ok")' > /tmp/test-bun.ts && bun run /tmp/test-bun.ts`
Expected: `ok`

- [ ] **Step 6: Create test fixtures directory**

Run: `mkdir -p tests/fixtures`

- [ ] **Step 7: Commit**

```bash
git add package.json tsconfig.json scripts/types.ts tests/fixtures/.gitkeep .gitignore
git commit -m "feat(init): project scaffolding with dependencies and shared types"
```

---

### Task 2: Quality Check Module

**Files:**
- Create: `scripts/quality.ts`
- Create: `tests/quality.test.ts`

This is the core gating logic -- determines whether extracted content is "good enough" or should fall through to the next fetch level. 5 criteria from spec S3.2.

- [ ] **Step 1: Write failing tests for quality check**

Create `tests/quality.test.ts`:

```typescript
import { describe, expect, test } from "bun:test";
import { qualityCheck } from "../scripts/quality";

describe("qualityCheck", () => {
  test("passes for content with sufficient length and paragraphs", () => {
    const markdown = [
      "# Article Title",
      "",
      "This is the first paragraph with enough words to be considered useful content for the quality check.",
      "",
      "This is the second paragraph that also contains enough words to pass the useful paragraph threshold.",
      "",
      "And a third paragraph for good measure with plenty of words inside it to meet requirements.",
    ].join("\n");
    const result = qualityCheck(markdown);
    expect(result.pass).toBe(true);
    expect(result.stats!.usefulParagraphs).toBeGreaterThanOrEqual(2);
  });

  test("fails for content shorter than 120 chars", () => {
    const result = qualityCheck("Short text.");
    expect(result.pass).toBe(false);
    expect(result.reason).toContain("too short");
  });

  test("fails for anti-scraping markers", () => {
    const markdown = "# Page\n\nAccess Denied\n\nYou do not have permission to access this resource.";
    const result = qualityCheck(markdown);
    expect(result.pass).toBe(false);
    expect(result.reason).toContain("anti-scraping");
  });

  test("fails for login wall markers", () => {
    const markdown = "# Welcome\n\n请登录后查看完整内容。\n\n更多精彩内容等你来看。";
    const result = qualityCheck(markdown);
    expect(result.pass).toBe(false);
    expect(result.reason).toContain("login wall");
  });

  test("fails for content with only 1 useful paragraph", () => {
    // One real paragraph + image-only + heading-only lines
    const markdown = [
      "# Title",
      "",
      "This is the only real paragraph with enough words to be considered useful.",
      "",
      "![image](https://example.com/img.png)",
      "",
      "## Another heading",
    ].join("\n");
    const result = qualityCheck(markdown);
    expect(result.pass).toBe(false);
    expect(result.reason).toContain("paragraph");
  });

  test("counts Chinese characters correctly for useful paragraph", () => {
    // 15+ Chinese chars = useful paragraph
    const markdown = [
      "# 标题",
      "",
      "这是一段足够长的中文段落，包含了超过十五个中文字符，应该被认为是有用的段落。",
      "",
      "另一段中文内容，同样包含了足够多的中文字符，可以通过质量检查。",
    ].join("\n");
    const result = qualityCheck(markdown);
    expect(result.pass).toBe(true);
    expect(result.stats!.usefulParagraphs).toBeGreaterThanOrEqual(2);
  });

  test("rejects navigation fragments (link lists without prose)", () => {
    const markdown = [
      "# Site",
      "",
      "This is a paragraph with enough words to be considered potentially useful for content.",
      "",
      "[Home](/) [About](/about) [Contact](/contact) [Blog](/blog)",
    ].join("\n");
    const result = qualityCheck(markdown);
    expect(result.pass).toBe(false);
    expect(result.reason).toContain("paragraph");
  });

  test("detects Cloudflare challenge page", () => {
    const markdown = "# Checking your browser\n\nJust a moment...\n\nPlease wait while we verify your connection.";
    const result = qualityCheck(markdown);
    expect(result.pass).toBe(false);
    expect(result.reason).toContain("anti-scraping");
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/jdy/Documents/skills/jdy-url-to-markdown && bun test tests/quality.test.ts`
Expected: FAIL -- module `../scripts/quality` not found.

- [ ] **Step 3: Implement quality check**

Create `scripts/quality.ts`:

```typescript
import type { QualityResult } from "./types";

const ANTI_SCRAPING_MARKERS = [
  /access denied/i,
  /403 forbidden/i,
  /请完成验证/,
  /captcha/i,
  /just a moment/i,
  /checking your browser/i,
];

const LOGIN_WALL_MARKERS = [
  /请登录/,
  /sign in to continue/i,
  /log in to/i,
  /Become a .* Member/i,
  /Subscribe to/i,
];

function stripMarkdownMarkers(text: string): string {
  return text
    .replace(/^#{1,6}\s+/gm, "")       // headings
    .replace(/\*\*|__/g, "")            // bold
    .replace(/\*|_/g, "")              // italic
    .replace(/!\[.*?\]\(.*?\)/g, "")   // images
    .replace(/\[([^\]]*)\]\(.*?\)/g, "$1") // links -> text
    .replace(/`[^`]*`/g, "")          // inline code
    .replace(/^[-*+]\s+/gm, "")       // list markers
    .replace(/^\d+\.\s+/gm, "")       // ordered list markers
    .trim();
}

function countChineseChars(text: string): number {
  const matches = text.match(/[\u4e00-\u9fff]/g);
  return matches ? matches.length : 0;
}

function isUsefulParagraph(line: string): boolean {
  const trimmed = line.trim();
  if (!trimmed) return false;

  // heading-only line
  if (/^#{1,6}\s+/.test(trimmed)) return false;

  // image-only line
  if (/^!\[.*?\]\(.*?\)\s*$/.test(trimmed)) return false;

  // navigation fragment: mostly links, little prose
  const withoutLinks = trimmed.replace(/\[([^\]]*)\]\([^)]*\)/g, "").trim();
  const linkCount = (trimmed.match(/\[([^\]]*)\]\([^)]*\)/g) || []).length;
  if (linkCount >= 3 && withoutLinks.length < 20) return false;

  // word count check: >=8 English words OR >=15 Chinese characters
  const chineseCount = countChineseChars(trimmed);
  if (chineseCount >= 15) return true;

  const words = trimmed.split(/\s+/).filter(w => w.length > 0);
  return words.length >= 8;
}

export function qualityCheck(markdown: string): QualityResult {
  const plainText = stripMarkdownMarkers(markdown);
  const charCount = plainText.length;

  // Criterion 1: minimum length
  if (charCount < 120) {
    return { pass: false, reason: `content too short: ${charCount} chars (min 120)`, stats: { charCount, usefulParagraphs: 0 } };
  }

  // Criterion 2: anti-scraping markers
  for (const marker of ANTI_SCRAPING_MARKERS) {
    if (marker.test(markdown)) {
      return { pass: false, reason: `anti-scraping marker detected: ${marker.source}`, stats: { charCount, usefulParagraphs: 0 } };
    }
  }

  // Criterion 3: login wall markers
  for (const marker of LOGIN_WALL_MARKERS) {
    if (marker.test(markdown)) {
      return { pass: false, reason: `login wall marker detected: ${marker.source}`, stats: { charCount, usefulParagraphs: 0 } };
    }
  }

  // Criterion 4 & 5: useful paragraphs
  const lines = markdown.split(/\n\n+/);
  const usefulParagraphs = lines.filter(isUsefulParagraph).length;

  if (usefulParagraphs < 2) {
    return { pass: false, reason: `insufficient useful paragraphs: ${usefulParagraphs} (min 2)`, stats: { charCount, usefulParagraphs } };
  }

  return { pass: true, stats: { charCount, usefulParagraphs } };
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/jdy/Documents/skills/jdy-url-to-markdown && bun test tests/quality.test.ts`
Expected: All 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/quality.ts tests/quality.test.ts
git commit -m "feat(quality): quality check module with 5-criteria gating"
```

---

### Task 3: Writer Module (Slug Generation, YAML Front Matter, File Output)

**Files:**
- Create: `scripts/writer.ts`
- Create: `tests/writer.test.ts`

- [ ] **Step 1: Write failing tests for slug and YAML generation**

Create `tests/writer.test.ts`:

```typescript
import { describe, expect, test } from "bun:test";
import { generateSlug, buildFrontMatter, buildOutputPath } from "../scripts/writer";

describe("generateSlug", () => {
  test("converts English title to kebab-case", () => {
    expect(generateSlug("How to Build a CLI Tool")).toBe("how-to-build-a-cli-tool");
  });

  test("preserves Chinese characters", () => {
    expect(generateSlug("如何构建命令行工具")).toBe("如何构建命令行工具");
  });

  test("strips special characters", () => {
    expect(generateSlug("Title: With / Special? Chars*")).toBe("title-with-special-chars");
  });

  test("collapses consecutive hyphens", () => {
    expect(generateSlug("hello---world")).toBe("hello-world");
  });

  test("trims leading and trailing hyphens", () => {
    expect(generateSlug("--hello world--")).toBe("hello-world");
  });

  test("returns 'untitled' for empty result", () => {
    expect(generateSlug("🎉🎊🎈")).toBe("untitled");
  });

  test("truncates to 50 chars", () => {
    const long = "a".repeat(60);
    expect(generateSlug(long).length).toBeLessThanOrEqual(50);
  });

  test("handles mixed Chinese and English", () => {
    expect(generateSlug("Vue3 响应式原理详解")).toBe("vue3-响应式原理详解");
  });
});

describe("buildFrontMatter", () => {
  test("produces valid YAML with double-quoted strings", () => {
    const fm = buildFrontMatter({
      url: "https://example.com",
      title: "Test Article",
      author: "John",
    }, 1);
    expect(fm).toContain('url: "https://example.com"');
    expect(fm).toContain('title: "Test Article"');
    expect(fm).toContain('fetch_level: 1');
    expect(fm).toStartWith("---\n");
    expect(fm).toEndWith("\n---\n");
  });

  test("escapes internal double quotes", () => {
    const fm = buildFrontMatter({
      url: "https://example.com",
      title: 'He said "hello"',
    }, 1);
    expect(fm).toContain('title: "He said \\"hello\\""');
  });

  test("replaces newlines in values with space", () => {
    const fm = buildFrontMatter({
      url: "https://example.com",
      title: "Line1\nLine2",
      description: "Desc\nwith\nnewlines",
    }, 2);
    expect(fm).toContain('title: "Line1 Line2"');
    expect(fm).toContain('description: "Desc with newlines"');
  });

  test("omits undefined optional fields", () => {
    const fm = buildFrontMatter({
      url: "https://example.com",
      title: "Test",
    }, 1);
    expect(fm).not.toContain("author:");
    expect(fm).not.toContain("published:");
  });
});

describe("buildOutputPath", () => {
  test("generates correct path structure", () => {
    const path = buildOutputPath("Article Title", "/out", new Date("2026-04-09T12:00:00Z"));
    expect(path).toBe("/out/20260409/article-title.md");
  });

  test("uses untitled for empty slug", () => {
    const path = buildOutputPath("🎉", "/out", new Date("2026-04-09T12:00:00Z"));
    expect(path).toBe("/out/20260409/untitled.md");
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/jdy/Documents/skills/jdy-url-to-markdown && bun test tests/writer.test.ts`
Expected: FAIL -- module not found.

- [ ] **Step 3: Implement writer module**

Create `scripts/writer.ts`:

```typescript
import { existsSync, mkdirSync, writeFileSync } from "fs";
import { dirname, join } from "path";
import type { Metadata } from "./types";

export function generateSlug(title: string): string {
  let slug = title
    .toLowerCase()
    .replace(/[^a-z0-9\u4e00-\u9fff\s-]/g, "")  // keep alphanumeric, Chinese, spaces, hyphens
    .replace(/\s+/g, "-")                          // spaces -> hyphens
    .replace(/-{2,}/g, "-")                        // collapse consecutive hyphens
    .replace(/^-+|-+$/g, "");                      // trim leading/trailing hyphens

  if (!slug) return "untitled";
  if (slug.length > 50) slug = slug.slice(0, 50).replace(/-+$/, "");
  return slug || "untitled";
}

function yamlString(value: string): string {
  const cleaned = value.replace(/\n/g, " ");
  const escaped = cleaned.replace(/"/g, '\\"');
  return `"${escaped}"`;
}

export function buildFrontMatter(metadata: Metadata, fetchLevel: number): string {
  const now = new Date().toISOString();
  const lines: string[] = ["---"];

  lines.push(`url: ${yamlString(metadata.url)}`);
  lines.push(`title: ${yamlString(metadata.title)}`);
  if (metadata.author) lines.push(`author: ${yamlString(metadata.author)}`);
  if (metadata.published) lines.push(`published: ${yamlString(metadata.published)}`);
  if (metadata.site_name) lines.push(`site_name: ${yamlString(metadata.site_name)}`);
  if (metadata.description) lines.push(`description: ${yamlString(metadata.description)}`);
  lines.push(`captured_at: ${yamlString(now)}`);
  lines.push(`fetch_level: ${fetchLevel}`);

  lines.push("---");
  return lines.join("\n") + "\n";
}

export function buildOutputPath(title: string, baseDir: string, date: Date = new Date()): string {
  const dateStr = [
    date.getUTCFullYear(),
    String(date.getUTCMonth() + 1).padStart(2, "0"),
    String(date.getUTCDate()).padStart(2, "0"),
  ].join("");

  const slug = generateSlug(title);
  return join(baseDir, dateStr, `${slug}.md`);
}

export function resolveConflict(filePath: string): string {
  if (!existsSync(filePath)) return filePath;
  const now = new Date();
  const suffix = [
    String(now.getHours()).padStart(2, "0"),
    String(now.getMinutes()).padStart(2, "0"),
    String(now.getSeconds()).padStart(2, "0"),
  ].join("");
  const base = filePath.replace(/\.md$/, "");
  return `${base}-${suffix}.md`;
}

export function writeMarkdown(
  filePath: string,
  metadata: Metadata,
  markdown: string,
  fetchLevel: number,
): string {
  const resolvedPath = resolveConflict(filePath);
  const dir = dirname(resolvedPath);
  mkdirSync(dir, { recursive: true });

  const frontMatter = buildFrontMatter(metadata, fetchLevel);
  writeFileSync(resolvedPath, frontMatter + "\n" + markdown, "utf-8");
  return resolvedPath;
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/jdy/Documents/skills/jdy-url-to-markdown && bun test tests/writer.test.ts`
Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/writer.ts tests/writer.test.ts
git commit -m "feat(writer): slug generation, YAML front matter, and file output"
```

---

### Task 4: Router (Domain Pattern Matching)

**Files:**
- Create: `scripts/router.ts`
- Create: `scripts/rules/site-rules.json`
- Create: `tests/router.test.ts`

- [ ] **Step 1: Create site-rules.json**

Create `scripts/rules/site-rules.json` with the content from spec S3.1 (the revised version with `*.zhihu.com` patterns and aliases).

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

- [ ] **Step 2: Write failing tests for route matching**

Create `tests/router.test.ts`:

```typescript
import { describe, expect, test } from "bun:test";
import { matchSiteRule } from "../scripts/router";

describe("matchSiteRule", () => {
  test("exact match: mp.weixin.qq.com", () => {
    const rule = matchSiteRule("https://mp.weixin.qq.com/s/abc123");
    expect(rule).not.toBeNull();
    expect(rule!.startLevel).toBe(2);
    expect(rule!.cleaners).toEqual(["wechat"]);
  });

  test("suffix match: zhuanlan.zhihu.com matches *.zhihu.com", () => {
    const rule = matchSiteRule("https://zhuanlan.zhihu.com/p/12345");
    expect(rule).not.toBeNull();
    expect(rule!.cleaners).toEqual(["zhihu"]);
  });

  test("suffix match: www.zhihu.com matches *.zhihu.com", () => {
    const rule = matchSiteRule("https://www.zhihu.com/question/12345");
    expect(rule).not.toBeNull();
  });

  test("alias match: youtu.be resolves to youtube adapter", () => {
    const rule = matchSiteRule("https://youtu.be/abc123");
    expect(rule).not.toBeNull();
    expect(rule!.adapter).toBe("youtube");
  });

  test("alias match: twitter.com resolves to x-twitter adapter", () => {
    const rule = matchSiteRule("https://twitter.com/user/status/123");
    expect(rule).not.toBeNull();
    expect(rule!.adapter).toBe("x-twitter");
  });

  test("www prefix is stripped: www.youtube.com matches *.youtube.com", () => {
    const rule = matchSiteRule("https://www.youtube.com/watch?v=abc");
    expect(rule).not.toBeNull();
    expect(rule!.adapter).toBe("youtube");
  });

  test("m.youtube.com matches *.youtube.com", () => {
    const rule = matchSiteRule("https://m.youtube.com/watch?v=abc");
    expect(rule).not.toBeNull();
    expect(rule!.adapter).toBe("youtube");
  });

  test("returns null for unmatched domain", () => {
    const rule = matchSiteRule("https://example.com/blog/post");
    expect(rule).toBeNull();
  });

  test("host is lowercased before matching", () => {
    const rule = matchSiteRule("https://MP.WEIXIN.QQ.COM/s/abc");
    expect(rule).not.toBeNull();
  });
});
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd /Users/jdy/Documents/skills/jdy-url-to-markdown && bun test tests/router.test.ts`
Expected: FAIL -- module not found.

- [ ] **Step 4: Implement router**

Create `scripts/router.ts`:

```typescript
import siteRulesJson from "./rules/site-rules.json";
import type { SiteRule, SiteRules } from "./types";

const siteRules: SiteRules = siteRulesJson as SiteRules;

// Pre-build alias lookup: alias domain -> pattern key
const aliasMap = new Map<string, string>();
for (const [pattern, rule] of Object.entries(siteRules)) {
  if (rule.aliases) {
    for (const alias of rule.aliases) {
      aliasMap.set(alias.toLowerCase(), pattern);
    }
  }
}

function normalizeHost(host: string): string {
  let h = host.toLowerCase();
  if (h.startsWith("www.")) h = h.slice(4);
  return h;
}

export function matchSiteRule(url: string): SiteRule | null {
  const parsed = new URL(url);
  const host = normalizeHost(parsed.hostname);

  // 1. Exact match (also try with www. stripped)
  if (siteRules[host]) return siteRules[host];
  if (siteRules[parsed.hostname.toLowerCase()]) return siteRules[parsed.hostname.toLowerCase()];

  // 2. Suffix match: *.domain.com
  for (const [pattern, rule] of Object.entries(siteRules)) {
    if (!pattern.startsWith("*.")) continue;
    const suffix = pattern.slice(2); // remove "*."
    if (host === suffix || host.endsWith("." + suffix)) {
      return rule;
    }
  }

  // 3. Alias match
  const aliasKey = aliasMap.get(host) || aliasMap.get(parsed.hostname.toLowerCase());
  if (aliasKey) return siteRules[aliasKey];

  return null;
}

export function getDefaultRule(): SiteRule {
  return { startLevel: 1 };
}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /Users/jdy/Documents/skills/jdy-url-to-markdown && bun test tests/router.test.ts`
Expected: All 9 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add scripts/router.ts scripts/rules/site-rules.json tests/router.test.ts
git commit -m "feat(router): domain pattern matching with suffix and alias support"
```

---

### Task 5: Parser Module (Readability + Turndown + Metadata)

**Files:**
- Create: `scripts/parser.ts`
- Create: `tests/parser.test.ts`
- Create: `tests/fixtures/simple-article.html`

**Important:** This task includes the linkedom compatibility validation mentioned in spec S9. If Readability + linkedom produces poor results, we switch to jsdom.

- [ ] **Step 1: Create test fixture**

Create `tests/fixtures/simple-article.html`:

```html
<!DOCTYPE html>
<html>
<head>
  <meta property="og:title" content="Test Article Title">
  <meta property="og:description" content="A test article description">
  <meta property="og:site_name" content="Test Site">
  <meta property="article:author" content="Test Author">
  <meta property="article:published_time" content="2026-04-09">
  <title>Test Article Title - Test Site</title>
</head>
<body>
  <header><nav><a href="/">Home</a><a href="/about">About</a></nav></header>
  <article>
    <h1>Test Article Title</h1>
    <p>This is the first paragraph of the test article. It contains enough words to pass the useful paragraph check in quality gating.</p>
    <p>This is the second paragraph with more content. It discusses the implications of testing and why automated testing is important for software quality.</p>
    <h2>Section Two</h2>
    <p>The third paragraph covers additional topics and provides more context about the article subject matter and related concepts.</p>
    <figure>
      <img src="https://example.com/image.jpg" alt="Test image">
      <figcaption>A test image</figcaption>
    </figure>
    <p>Final paragraph wraps up the article with conclusions and next steps for the reader to consider.</p>
  </article>
  <footer><p>Copyright 2026</p></footer>
  <script>console.log("noise");</script>
  <style>.hidden { display: none; }</style>
</body>
</html>
```

- [ ] **Step 2: Write failing tests**

Create `tests/parser.test.ts`:

```typescript
import { describe, expect, test } from "bun:test";
import { readFileSync } from "fs";
import { resolve } from "path";
import { parse } from "../scripts/parser";

const fixtureDir = resolve(import.meta.dir, "fixtures");

describe("parse", () => {
  const html = readFileSync(resolve(fixtureDir, "simple-article.html"), "utf-8");

  test("extracts article content as markdown", () => {
    const result = parse(html, "https://example.com/article");
    expect(result.markdown).toContain("# Test Article Title");
    expect(result.markdown).toContain("first paragraph");
    expect(result.markdown).toContain("## Section Two");
  });

  test("strips script and style tags from output", () => {
    const result = parse(html, "https://example.com/article");
    expect(result.markdown).not.toContain("console.log");
    expect(result.markdown).not.toContain(".hidden");
  });

  test("extracts OG metadata", () => {
    const result = parse(html, "https://example.com/article");
    expect(result.metadata.title).toBe("Test Article Title");
    expect(result.metadata.description).toBe("A test article description");
    expect(result.metadata.site_name).toBe("Test Site");
    expect(result.metadata.author).toBe("Test Author");
    expect(result.metadata.published).toBe("2026-04-09");
  });

  test("preserves image markdown", () => {
    const result = parse(html, "https://example.com/article");
    expect(result.markdown).toContain("![Test image]");
  });

  test("falls back to <title> when OG tags missing", () => {
    const minimalHtml = `<html><head><title>Fallback Title</title></head>
    <body><article><p>Paragraph one with enough words to be useful for testing purposes in this test.</p>
    <p>Paragraph two also with enough words to pass the useful paragraph threshold in quality checks.</p></article></body></html>`;
    const result = parse(minimalHtml, "https://example.com/page");
    expect(result.metadata.title).toBe("Fallback Title");
  });

  test("applies cleaners when provided", () => {
    const result = parse(html, "https://example.com/article", [(md) => md.replace(/Final paragraph.*/, "CLEANED")]);
    expect(result.markdown).toContain("CLEANED");
  });
});
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd /Users/jdy/Documents/skills/jdy-url-to-markdown && bun test tests/parser.test.ts`
Expected: FAIL.

- [ ] **Step 4: Implement parser**

Create `scripts/parser.ts`:

```typescript
import { parseHTML } from "linkedom";
import { Readability } from "@mozilla/readability";
import TurndownService from "turndown";
import { gfm } from "turndown-plugin-gfm";
import type { Metadata, ParseResult, Cleaner } from "./types";

function createTurndown(): TurndownService {
  const td = new TurndownService({
    headingStyle: "atx",
    codeBlockStyle: "fenced",
    bulletListMarker: "-",
    emDelimiter: "_",
  });
  td.use(gfm);
  td.remove(["script", "style", "iframe", "noscript", "template", "svg", "path"]);

  // Drop invisible anchors: <a> with no text and no child media
  td.addRule("dropInvisibleAnchors", {
    filter(node) {
      if (node.nodeName !== "A") return false;
      const text = (node.textContent || "").trim();
      if (text) return false;
      const hasMedia = node.querySelector("img, video, audio, picture");
      return !hasMedia;
    },
    replacement() {
      return "";
    },
  });

  // Collapse <figure> to prevent excessive blank lines
  td.addRule("collapseFigure", {
    filter: "figure",
    replacement(_content, node) {
      const img = node.querySelector("img");
      const caption = node.querySelector("figcaption");
      if (!img) return _content;
      const alt = caption?.textContent?.trim() || img.getAttribute("alt") || "";
      const src = img.getAttribute("src") || "";
      return `\n\n![${alt}](${src})\n\n`;
    },
  });

  return td;
}

function extractMetadata(doc: Document, url: string): Metadata {
  const get = (sel: string, attr: string) => doc.querySelector(sel)?.getAttribute(attr)?.trim();
  const getMeta = (name: string) => get(`meta[property="${name}"]`, "content") || get(`meta[name="${name}"]`, "content");

  // Try JSON-LD
  let jsonLd: any = null;
  const ldScript = doc.querySelector('script[type="application/ld+json"]');
  if (ldScript?.textContent) {
    try { jsonLd = JSON.parse(ldScript.textContent); } catch {}
  }

  const title =
    getMeta("og:title") ||
    jsonLd?.headline ||
    doc.querySelector("title")?.textContent?.trim() ||
    "Untitled";

  const author =
    getMeta("article:author") ||
    (typeof jsonLd?.author === "string" ? jsonLd.author : jsonLd?.author?.name) ||
    getMeta("author") ||
    undefined;

  const published =
    getMeta("article:published_time") ||
    jsonLd?.datePublished ||
    getMeta("date") ||
    undefined;

  const site_name =
    getMeta("og:site_name") ||
    undefined;

  const description =
    getMeta("og:description") ||
    getMeta("description") ||
    undefined;

  return { url, title, author, published, site_name, description };
}

export function parse(html: string, url: string, cleaners?: Cleaner[]): ParseResult {
  const { document } = parseHTML(html);

  // Extract metadata before Readability modifies the DOM
  const metadata = extractMetadata(document as unknown as Document, url);

  // Re-parse for Readability (it mutates the DOM)
  const { document: readDoc } = parseHTML(html);
  const reader = new Readability(readDoc as any, {
    charThreshold: 120,
    nbTopCandidates: 10,
  });
  const article = reader.parse();

  const td = createTurndown();

  let markdown: string;
  if (article?.content) {
    markdown = td.turndown(article.content);
  } else {
    // Fallback: convert body directly
    markdown = td.turndown(html);
  }

  // Apply cleaners
  if (cleaners) {
    for (const cleaner of cleaners) {
      markdown = cleaner(markdown);
    }
  }

  return { markdown, metadata };
}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /Users/jdy/Documents/skills/jdy-url-to-markdown && bun test tests/parser.test.ts`
Expected: All tests PASS. If linkedom causes Readability failures (null article), investigate and potentially swap to jsdom.

- [ ] **Step 6: Commit**

```bash
git add scripts/parser.ts tests/parser.test.ts tests/fixtures/simple-article.html
git commit -m "feat(parser): Readability + Turndown pipeline with metadata extraction"
```

---

### Task 6: Cleaners (WeChat, Zhihu, Xiaohongshu)

**Files:**
- Create: `scripts/rules/cleaners.ts`
- Create: `tests/cleaners.test.ts`

- [ ] **Step 1: Write failing tests**

Create `tests/cleaners.test.ts`:

```typescript
import { describe, expect, test } from "bun:test";
import { getCleaner } from "../scripts/rules/cleaners";

describe("wechat cleaner", () => {
  const clean = getCleaner("wechat")!;

  test("removes content after 预览时标签不可点", () => {
    const md = "Article content here.\n\n预览时标签不可点\n\nFooter noise";
    expect(clean(md)).toBe("Article content here.");
  });

  test("removes 微信扫一扫赞赏作者 block", () => {
    const md = "Article content.\n\n微信扫一扫赞赏作者\n\nMore noise";
    expect(clean(md)).toBe("Article content.");
  });

  test("removes duplicate title", () => {
    const md = "# My Title\n\nMy Title\n\nActual content starts here with enough words.";
    expect(clean(md)).not.toMatch(/^# My Title\n\nMy Title/);
  });

  test("strips 原创 author line", () => {
    const md = "原创 张三 公众号名称\n\n# Title\n\nContent here.";
    expect(clean(md)).not.toContain("原创");
  });
});

describe("zhihu cleaner", () => {
  const clean = getCleaner("zhihu")!;

  test("removes 登录后你可以 prompts", () => {
    const md = "Content.\n\n登录后你可以关注作者\n\nMore content.";
    expect(clean(md)).not.toContain("登录后你可以");
    expect(clean(md)).toContain("Content.");
    expect(clean(md)).toContain("More content.");
  });

  test("removes 发布于/编辑于 footer", () => {
    const md = "Content.\n\n发布于 2026-04-09";
    expect(clean(md)).not.toContain("发布于");
  });
});

describe("xiaohongshu cleaner", () => {
  const clean = getCleaner("xiaohongshu")!;

  test("removes app download prompts", () => {
    const md = "Content.\n\n打开APP查看更多精彩内容\n\nMore content.";
    expect(clean(md)).not.toContain("打开APP");
  });
});

describe("getCleaner", () => {
  test("returns null for unknown cleaner", () => {
    expect(getCleaner("nonexistent")).toBeNull();
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/jdy/Documents/skills/jdy-url-to-markdown && bun test tests/cleaners.test.ts`
Expected: FAIL.

- [ ] **Step 3: Implement cleaners**

Create `scripts/rules/cleaners.ts`:

```typescript
import type { Cleaner } from "../types";

function wechat(markdown: string): string {
  let md = markdown;

  // Remove everything after "预览时标签不可点"
  const previewIdx = md.indexOf("预览时标签不可点");
  if (previewIdx !== -1) md = md.slice(0, previewIdx).trimEnd();

  // Remove "微信扫一扫赞赏作者" and everything below
  const rewardIdx = md.indexOf("微信扫一扫赞赏作者");
  if (rewardIdx !== -1) md = md.slice(0, rewardIdx).trimEnd();

  // Remove duplicate title: if line 2 (after "# Title\n\n") repeats the heading text
  const lines = md.split("\n");
  if (lines[0]?.startsWith("# ")) {
    const headingText = lines[0].slice(2).trim();
    // Find next non-empty line
    let nextIdx = 1;
    while (nextIdx < lines.length && !lines[nextIdx].trim()) nextIdx++;
    if (nextIdx < lines.length && lines[nextIdx].trim() === headingText) {
      lines.splice(nextIdx, 1);
      md = lines.join("\n");
    }
  }

  // Strip "原创 <author> <account>" line
  md = md.replace(/^原创\s+.+$/gm, "").replace(/^\n+/, "");

  return md.trimEnd();
}

function zhihu(markdown: string): string {
  let md = markdown;
  // Remove "登录后你可以..." lines
  md = md.replace(/^.*登录后你可以.*$/gm, "");
  // Remove sidebar recommendation blocks (lines starting with "推荐阅读")
  md = md.replace(/^.*推荐阅读.*$/gm, "");
  // Remove "发布于 / 编辑于" footer
  md = md.replace(/^.*(发布于|编辑于)\s+\d{4}-?\d{2}-?\d{2}.*$/gm, "");
  // Clean up excessive blank lines
  md = md.replace(/\n{3,}/g, "\n\n");
  return md.trim();
}

function xiaohongshu(markdown: string): string {
  let md = markdown;
  // Remove app download prompts
  md = md.replace(/^.*打开APP.*$/gm, "");
  md = md.replace(/^.*下载小红书.*$/gm, "");
  // Remove footer navigation
  md = md.replace(/^.*小红书App.*$/gm, "");
  md = md.replace(/\n{3,}/g, "\n\n");
  return md.trim();
}

const registry: Record<string, Cleaner> = { wechat, zhihu, xiaohongshu };

export function getCleaner(name: string): Cleaner | null {
  return registry[name] || null;
}

export function getCleaners(names: string[]): Cleaner[] {
  return names.map(n => getCleaner(n)).filter((c): c is Cleaner => c !== null);
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/jdy/Documents/skills/jdy-url-to-markdown && bun test tests/cleaners.test.ts`
Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/rules/cleaners.ts tests/cleaners.test.ts
git commit -m "feat(cleaners): site-specific cleanup rules for WeChat, Zhihu, Xiaohongshu"
```

---

### Task 7: Fetcher (Two-Level Cascade)

**Files:**
- Create: `scripts/fetcher.ts`

The Fetcher ties together Parser + Quality + Cleaners into the two-level cascade. It depends on the CDP client (Task 8) for Level 2, so we implement Level 1 fully and stub Level 2 for now.

- [ ] **Step 1: Implement fetcher with Level 1 and Level 2 interface**

Create `scripts/fetcher.ts`:

```typescript
import { parse } from "./parser";
import { qualityCheck } from "./quality";
import { getCleaners } from "./rules/cleaners";
import type { ParseResult, SiteRule } from "./types";

const USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36";

interface FetchOptions {
  rule: SiteRule;
  timeout?: number;
  forceCdp?: boolean;
  cdpFetch?: (url: string, rule: SiteRule, timeout: number) => Promise<string>;
}

export async function fetchAndParse(url: string, options: FetchOptions): Promise<ParseResult & { fetchLevel: number }> {
  const { rule, timeout = 30000, forceCdp = false, cdpFetch } = options;
  const startLevel = forceCdp ? 2 : (rule.startLevel || 1);
  const cleaners = rule.cleaners ? getCleaners(rule.cleaners) : [];

  // Level 1: local fetch
  if (startLevel <= 1) {
    try {
      const response = await fetch(url, {
        headers: {
          "User-Agent": USER_AGENT,
          "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        },
        signal: AbortSignal.timeout(timeout),
      });

      if (response.ok) {
        const html = await response.text();
        const result = parse(html, url, cleaners);
        const qc = qualityCheck(result.markdown);

        if (qc.pass) {
          return { ...result, fetchLevel: 1 };
        }
        console.error(`[L1] Quality check failed: ${qc.reason}`);
      } else {
        console.error(`[L1] HTTP ${response.status}`);
      }
    } catch (err) {
      console.error(`[L1] Fetch error: ${(err as Error).message}`);
    }
  }

  // Level 2: CDP
  if (!cdpFetch) {
    throw new Error("CDP fetch not available. Install Chrome and ensure remote debugging is enabled.");
  }

  console.error("[L2] Falling through to CDP...");
  const html = await cdpFetch(url, rule, timeout);
  const result = parse(html, url, cleaners);
  const qc = qualityCheck(result.markdown);

  if (qc.pass) {
    return { ...result, fetchLevel: 2 };
  }

  throw new Error(`Quality check failed at Level 2: ${qc.reason} (${qc.stats?.charCount} chars, ${qc.stats?.usefulParagraphs} useful paragraphs)`);
}
```

- [ ] **Step 2: Commit**

```bash
git add scripts/fetcher.ts
git commit -m "feat(fetcher): two-level fetch cascade with quality gating"
```

---

### Task 8: CDP Client & Daemon

**Files:**
- Create: `scripts/cdp/client.ts`
- Create: `scripts/cdp/daemon.ts`
- Create: `scripts/cdp/daemon-entry.ts`

This is the most complex task. Forked from chrome-cdp-skill's architecture but simplified to a global single-daemon model with request mutex. Key additions: network journal (for X adapter), Unix socket IPC.

- [ ] **Step 1: Implement CDP client (port discovery + WebSocket)**

Create `scripts/cdp/client.ts`:

```typescript
import { readFileSync, existsSync } from "fs";
import { homedir } from "os";
import { resolve } from "path";

const TIMEOUT = 15000;

export function getWsUrl(): string {
  const home = homedir();
  const macBrowsers = [
    "Google/Chrome", "Google/Chrome Beta", "Google/Chrome for Testing",
    "Chromium", "BraveSoftware/Brave-Browser", "Microsoft Edge",
  ];
  const linuxBrowsers = [
    "google-chrome", "google-chrome-beta", "chromium",
    "BraveSoftware/Brave-Browser", "microsoft-edge",
  ];

  const candidates: (string | undefined)[] = [
    process.env.CDP_PORT_FILE,
    ...macBrowsers.flatMap(b => [
      resolve(home, "Library/Application Support", b, "DevToolsActivePort"),
    ]),
    ...linuxBrowsers.flatMap(b => [
      resolve(home, ".config", b, "DevToolsActivePort"),
    ]),
  ];

  const portFile = candidates.filter(Boolean).find(p => existsSync(p!));
  if (!portFile) {
    throw new Error(
      "No DevToolsActivePort found. Start Chrome with remote debugging:\n" +
      "  chrome --remote-debugging-port=0\n" +
      "Or enable at chrome://flags/#allow-remote-debugging"
    );
  }

  const lines = readFileSync(portFile, "utf-8").trim().split("\n");
  if (lines.length < 2 || !lines[0] || !lines[1]) {
    throw new Error(`Invalid DevToolsActivePort: ${portFile}`);
  }

  const host = process.env.CDP_HOST || "127.0.0.1";
  return `ws://${host}:${lines[0]}${lines[1]}`;
}

export class CDPConnection {
  private ws!: WebSocket;
  private nextId = 1;
  private pending = new Map<number, { resolve: (v: any) => void; reject: (e: Error) => void }>();
  private eventHandlers = new Map<string, ((params: any) => void)[]>();

  async connect(wsUrl: string): Promise<void> {
    return new Promise((resolve, reject) => {
      this.ws = new WebSocket(wsUrl);
      this.ws.onopen = () => resolve();
      this.ws.onerror = (e) => reject(new Error(`CDP WebSocket error: ${e}`));
      this.ws.onmessage = (event) => {
        const msg = JSON.parse(String(event.data));
        if (msg.id !== undefined) {
          const p = this.pending.get(msg.id);
          if (p) {
            this.pending.delete(msg.id);
            if (msg.error) p.reject(new Error(msg.error.message));
            else p.resolve(msg.result);
          }
        } else if (msg.method) {
          const handlers = this.eventHandlers.get(msg.method) || [];
          for (const h of handlers) h(msg.params);
        }
      };
      this.ws.onclose = () => {
        for (const p of this.pending.values()) {
          p.reject(new Error("CDP connection closed"));
        }
        this.pending.clear();
      };
    });
  }

  async send(method: string, params: any = {}): Promise<any> {
    const id = this.nextId++;
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pending.delete(id);
        reject(new Error(`CDP timeout: ${method}`));
      }, TIMEOUT);

      this.pending.set(id, {
        resolve: (v) => { clearTimeout(timer); resolve(v); },
        reject: (e) => { clearTimeout(timer); reject(e); },
      });

      this.ws.send(JSON.stringify({ id, method, params }));
    });
  }

  on(event: string, handler: (params: any) => void): void {
    const list = this.eventHandlers.get(event) || [];
    list.push(handler);
    this.eventHandlers.set(event, list);
  }

  close(): void {
    this.ws.close();
  }
}
```

- [ ] **Step 2: Implement CDP daemon**

Create `scripts/cdp/daemon.ts`:

```typescript
import { existsSync, mkdirSync, unlinkSync } from "fs";
import { homedir } from "os";
import { resolve } from "path";
import net from "net";
import { CDPConnection, getWsUrl } from "./client";

const CACHE_DIR = resolve(homedir(), ".cache", "jdy-url-to-markdown");
const SOCK_PATH = resolve(CACHE_DIR, "daemon.sock");
const IDLE_TIMEOUT = 30 * 60 * 1000; // 30 minutes

// Ensure cache dir exists with restricted permissions
try { mkdirSync(CACHE_DIR, { recursive: true, mode: 0o700 }); } catch {}

export class CDPDaemon {
  private cdp!: CDPConnection;
  private busy = false;
  private idleTimer: ReturnType<typeof setTimeout> | null = null;
  private networkResponses = new Map<string, { url: string; requestId: string }>();
  private server: net.Server | null = null;

  async start(): Promise<void> {
    // Connect to Chrome
    const wsUrl = getWsUrl();
    this.cdp = new CDPConnection();

    // Retry connection (Chrome "Allow debugging" modal)
    let lastErr: Error | null = null;
    for (let i = 0; i < 20; i++) {
      try {
        await this.cdp.connect(wsUrl);
        lastErr = null;
        break;
      } catch (e) {
        lastErr = e as Error;
        await new Promise(r => setTimeout(r, 300));
      }
    }
    if (lastErr) throw lastErr;

    // Start Unix socket server
    if (existsSync(SOCK_PATH)) unlinkSync(SOCK_PATH);
    this.server = net.createServer(this.handleConnection.bind(this));
    this.server.listen(SOCK_PATH);
    this.resetIdleTimer();
    console.error(`[daemon] Listening on ${SOCK_PATH}`);
  }

  private resetIdleTimer(): void {
    if (this.idleTimer) clearTimeout(this.idleTimer);
    this.idleTimer = setTimeout(() => {
      console.error("[daemon] Idle timeout, shutting down");
      this.shutdown();
    }, IDLE_TIMEOUT);
  }

  private handleConnection(socket: net.Socket): void {
    let buffer = "";
    socket.on("data", (chunk) => {
      buffer += chunk.toString();
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";
      for (const line of lines) {
        if (!line.trim()) continue;
        this.handleRequest(JSON.parse(line), socket);
      }
    });
  }

  private async handleRequest(req: any, socket: net.Socket): Promise<void> {
    this.resetIdleTimer();

    // Mutex check
    if (this.busy) {
      socket.write(JSON.stringify({ error: "busy" }) + "\n");
      return;
    }

    this.busy = true;
    try {
      let result: any;
      switch (req.method) {
        case "health":
          result = { ok: true };
          break;
        case "navigate":
          result = await this.navigate(req.params.url, req.params.timeout);
          break;
        case "getHTML":
          result = await this.getHTML(req.params);
          break;
        case "evaluate":
          result = await this.evaluate(req.params.expression);
          break;
        case "enableNetwork":
          result = await this.enableNetwork();
          break;
        case "getNetworkResponses":
          result = this.getNetworkResponsesByPattern(req.params.urlPattern);
          break;
        case "getResponseBody":
          result = await this.getResponseBody(req.params.requestId);
          break;
        case "setCookies":
          result = await this.setCookies(req.params.cookies);
          break;
        case "getCookies":
          result = await this.getCookies(req.params.domain);
          break;
        default:
          result = { error: `Unknown method: ${req.method}` };
      }
      socket.write(JSON.stringify(result) + "\n");
    } catch (e) {
      socket.write(JSON.stringify({ error: (e as Error).message }) + "\n");
    } finally {
      this.busy = false;
    }
  }

  private async navigate(url: string, timeout = 30000): Promise<{ ok: true }> {
    // Create new tab
    const { targetId } = await this.cdp.send("Target.createTarget", { url: "about:blank" });
    const { sessionId } = await this.cdp.send("Target.attachToTarget", { targetId, flatten: true });

    // Navigate
    await this.cdp.send("Page.enable", {});
    await this.cdp.send("Page.navigate", { url });

    // Wait for load
    await new Promise<void>((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error("Navigation timeout")), timeout);
      this.cdp.on("Page.loadEventFired", () => {
        clearTimeout(timer);
        // Extra wait for network idle
        setTimeout(resolve, 1500);
      });
    });

    return { ok: true };
  }

  private async getHTML(params?: { waitForSelector?: string }): Promise<{ html: string }> {
    if (params?.waitForSelector) {
      const [selector, timeoutStr] = params.waitForSelector.split(":");
      const timeout = timeoutStr ? parseInt(timeoutStr) : 5000;
      await this.cdp.send("Runtime.evaluate", {
        expression: `new Promise((resolve, reject) => {
          const el = document.querySelector('${selector}');
          if (el) return resolve(true);
          const observer = new MutationObserver(() => {
            if (document.querySelector('${selector}')) { observer.disconnect(); resolve(true); }
          });
          observer.observe(document.body, { childList: true, subtree: true });
          setTimeout(() => { observer.disconnect(); reject(new Error('timeout')); }, ${timeout});
        })`,
        awaitPromise: true,
      });
    }

    const { result } = await this.cdp.send("Runtime.evaluate", {
      expression: "document.documentElement.outerHTML",
      returnByValue: true,
    });
    return { html: result.value };
  }

  private async evaluate(expression: string): Promise<any> {
    const { result } = await this.cdp.send("Runtime.evaluate", {
      expression,
      returnByValue: true,
      awaitPromise: true,
    });
    return result.value;
  }

  private async enableNetwork(): Promise<{ ok: true }> {
    await this.cdp.send("Network.enable", {});
    this.networkResponses.clear();
    this.cdp.on("Network.responseReceived", (params: any) => {
      this.networkResponses.set(params.requestId, {
        url: params.response.url,
        requestId: params.requestId,
      });
    });
    return { ok: true };
  }

  private getNetworkResponsesByPattern(urlPattern: string): { responses: { url: string; requestId: string }[] } {
    const regex = new RegExp(urlPattern);
    const matches = [...this.networkResponses.values()].filter(r => regex.test(r.url));
    return { responses: matches };
  }

  private async getResponseBody(requestId: string): Promise<{ body: string }> {
    const { body, base64Encoded } = await this.cdp.send("Network.getResponseBody", { requestId });
    return { body: base64Encoded ? Buffer.from(body, "base64").toString() : body };
  }

  private async setCookies(cookies: any[]): Promise<{ ok: true }> {
    for (const cookie of cookies) {
      await this.cdp.send("Network.setCookie", cookie);
    }
    return { ok: true };
  }

  private async getCookies(domain: string): Promise<{ cookies: any[] }> {
    const { cookies } = await this.cdp.send("Network.getCookies", { urls: [`https://${domain}`] });
    return { cookies };
  }

  shutdown(): void {
    if (this.idleTimer) clearTimeout(this.idleTimer);
    if (this.server) {
      this.server.close();
      try { unlinkSync(SOCK_PATH); } catch {}
    }
    this.cdp.close();
    process.exit(0);
  }
}

// CDP daemon client: connects to running daemon or starts one
export async function connectDaemon(): Promise<net.Socket> {
  return new Promise((resolve, reject) => {
    const sock = net.connect(SOCK_PATH);
    sock.on("connect", () => resolve(sock));
    sock.on("error", () => reject(new Error("Daemon not running")));
  });
}

export function sendDaemonRequest(sock: net.Socket, method: string, params: any = {}): Promise<any> {
  return new Promise((resolve, reject) => {
    let buffer = "";
    const onData = (chunk: Buffer) => {
      buffer += chunk.toString();
      const idx = buffer.indexOf("\n");
      if (idx !== -1) {
        sock.off("data", onData);
        const line = buffer.slice(0, idx);
        const result = JSON.parse(line);
        if (result.error) reject(new Error(result.error));
        else resolve(result);
      }
    };
    sock.on("data", onData);
    sock.write(JSON.stringify({ method, params }) + "\n");
  });
}

// Start daemon as background process if not running
export async function ensureDaemon(): Promise<net.Socket> {
  try {
    return await connectDaemon();
  } catch {
    // Start daemon using Bun.spawn (safer than shell execution)
    const daemonScript = resolve(import.meta.dir, "daemon-entry.ts");
    const proc = Bun.spawn(["bun", "run", daemonScript], {
      stdio: ["ignore", "ignore", "ignore"],
    });
    proc.unref();

    // Wait for daemon to be ready
    for (let i = 0; i < 20; i++) {
      await new Promise(r => setTimeout(r, 300));
      try {
        const sock = await connectDaemon();
        await sendDaemonRequest(sock, "health");
        return sock;
      } catch {}
    }
    throw new Error("Failed to start CDP daemon");
  }
}
```

- [ ] **Step 3: Create daemon entry point**

Create `scripts/cdp/daemon-entry.ts`:

```typescript
import { CDPDaemon } from "./daemon";

const daemon = new CDPDaemon();
daemon.start().catch((e) => {
  console.error(`[daemon] Fatal: ${e.message}`);
  process.exit(1);
});
```

- [ ] **Step 4: Commit**

```bash
git add scripts/cdp/client.ts scripts/cdp/daemon.ts scripts/cdp/daemon-entry.ts
git commit -m "feat(cdp): CDP client and daemon with Unix socket IPC and request mutex"
```

---

### Task 9: CLI Entry Point (main.ts)

**Files:**
- Create: `scripts/main.ts`

Ties everything together: arg parsing, routing, fetcher dispatch (or adapter dispatch), writer output.

- [ ] **Step 1: Implement main.ts**

Create `scripts/main.ts`:

```typescript
import { matchSiteRule, getDefaultRule } from "./router";
import { fetchAndParse } from "./fetcher";
import { buildOutputPath, writeMarkdown } from "./writer";
import { ensureDaemon, sendDaemonRequest } from "./cdp/daemon";
import type { SiteRule } from "./types";

function printUsage(): void {
  console.error(`Usage: bun run scripts/main.ts <url> [options]
Options:
  --cdp           Force CDP (skip Level 1)
  --wait          Wait mode for login-required pages
  --timeout <ms>  Page load timeout (default: 30000)
  -o <path>       Output file path`);
}

function parseArgs(args: string[]): { url: string; cdp: boolean; wait: boolean; timeout: number; output?: string } {
  const positional: string[] = [];
  let cdp = false;
  let wait = false;
  let timeout = 30000;
  let output: string | undefined;

  for (let i = 0; i < args.length; i++) {
    switch (args[i]) {
      case "--cdp": cdp = true; break;
      case "--wait": wait = true; break;
      case "--timeout": timeout = parseInt(args[++i]); break;
      case "-o": output = args[++i]; break;
      case "--help": case "-h": printUsage(); process.exit(0);
      default:
        if (args[i].startsWith("-")) {
          console.error(`Unknown option: ${args[i]}`);
          process.exit(1);
        }
        positional.push(args[i]);
    }
  }

  if (positional.length !== 1) {
    printUsage();
    process.exit(1);
  }

  return { url: positional[0], cdp, wait, timeout, output };
}

async function cdpFetch(url: string, rule: SiteRule, timeout: number): Promise<string> {
  const sock = await ensureDaemon();
  try {
    await sendDaemonRequest(sock, "navigate", { url, timeout });

    // Execute cdpActions if any
    if (rule.cdpActions) {
      for (const action of rule.cdpActions) {
        if (action.startsWith("waitForSelector:")) {
          const selectorAndTimeout = action.slice("waitForSelector:".length);
          await sendDaemonRequest(sock, "getHTML", { waitForSelector: selectorAndTimeout });
        } else if (action.startsWith("removeOverlays:")) {
          const selectors = action.slice("removeOverlays:".length);
          await sendDaemonRequest(sock, "evaluate", {
            expression: `document.querySelectorAll('${selectors}').forEach(el => el.remove())`,
          });
        } else if (action === "autoScroll") {
          await sendDaemonRequest(sock, "evaluate", {
            expression: `(async () => {
              for (let i = 0; i < 5; i++) {
                window.scrollBy(0, window.innerHeight);
                await new Promise(r => setTimeout(r, 500));
              }
              window.scrollTo(0, 0);
            })()`,
          });
        } else if (action === "expandContent") {
          await sendDaemonRequest(sock, "evaluate", {
            expression: `document.querySelectorAll('[class*="expand"], [class*="more"]').forEach(el => el.click())`,
          });
        }
      }
    }

    const { html } = await sendDaemonRequest(sock, "getHTML", {});
    return html;
  } finally {
    sock.destroy();
  }
}

async function main(): Promise<void> {
  const args = parseArgs(process.argv.slice(2));
  const { url, cdp: forceCdp, timeout, output } = args;

  // Validate URL
  try {
    new URL(url);
  } catch {
    console.error(`Invalid URL: ${url}`);
    process.exit(1);
  }

  // Route
  const rule = matchSiteRule(url) || getDefaultRule();

  // Check if adapter is needed
  if (rule.adapter) {
    try {
      const adapterModule = await import(`./adapters/${rule.adapter}.ts`);
      const result = await adapterModule.extract(url, { timeout, ensureDaemon, sendDaemonRequest });
      const filePath = output || buildOutputPath(result.metadata.title, "40_Reference/Articles");
      const written = writeMarkdown(filePath, result.metadata, result.markdown, 2);
      console.log(written);
      process.exit(0);
    } catch (e) {
      console.error(`[adapter:${rule.adapter}] Failed: ${(e as Error).message}`);
      console.error("Falling back to generic CDP extraction...");
      // Fall through to generic fetcher
    }
  }

  try {
    const result = await fetchAndParse(url, {
      rule,
      timeout,
      forceCdp,
      cdpFetch,
    });

    const filePath = output || buildOutputPath(result.metadata.title, "40_Reference/Articles");
    const written = writeMarkdown(filePath, result.metadata, result.markdown, result.fetchLevel);
    console.log(written);
    process.exit(0);
  } catch (e) {
    const err = e as Error;
    console.error(`Error: ${err.message}`);
    if (err.message.includes("Quality check failed")) process.exit(2);
    if (err.message.includes("CDP")) process.exit(3);
    process.exit(1);
  }
}

main();
```

- [ ] **Step 2: Test basic Level 1 fetch manually**

Run: `cd /Users/jdy/Documents/skills/jdy-url-to-markdown && bun run scripts/main.ts "https://en.wikipedia.org/wiki/Markdown" -o /tmp/test-markdown.md`
Expected: File written to `/tmp/test-markdown.md` with YAML front matter and article content. Check stderr for `[L1]` pass/fail messages.

- [ ] **Step 3: Verify output quality**

Run: `head -20 /tmp/test-markdown.md`
Expected: Valid YAML front matter with title, url, captured_at, fetch_level: 1.

- [ ] **Step 4: Commit**

```bash
git add scripts/main.ts
git commit -m "feat(cli): main entry point with arg parsing, routing, and fetch orchestration"
```

---

### Task 10: YouTube Adapter

**Files:**
- Create: `scripts/adapters/youtube.ts`

- [ ] **Step 1: Implement YouTube adapter**

Create `scripts/adapters/youtube.ts`:

```typescript
import type { ParseResult } from "../types";

interface AdapterContext {
  timeout: number;
  ensureDaemon: () => Promise<import("net").Socket>;
  sendDaemonRequest: (sock: import("net").Socket, method: string, params?: any) => Promise<any>;
}

function extractVideoId(url: string): string | null {
  const parsed = new URL(url);
  if (parsed.searchParams.has("v")) return parsed.searchParams.get("v");
  if (parsed.hostname === "youtu.be") return parsed.pathname.slice(1);
  const match = parsed.pathname.match(/\/(embed|shorts|v)\/([^/?]+)/);
  return match ? match[2] : null;
}

function parseTimestamp(ts: string): number {
  const parts = ts.split(":").map(Number);
  if (parts.length === 3) return parts[0] * 3600 + parts[1] * 60 + parts[2];
  if (parts.length === 2) return parts[0] * 60 + parts[1];
  return parts[0];
}

function formatTimestamp(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  if (h > 0) return `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  return `${m}:${String(s).padStart(2, "0")}`;
}

function extractChapters(description: string): { time: number; title: string }[] {
  const chapters: { time: number; title: string }[] = [];
  const regex = /(\d{1,2}:\d{2}(?::\d{2})?)\s+(.+)/g;
  let match;
  while ((match = regex.exec(description)) !== null) {
    chapters.push({ time: parseTimestamp(match[1]), title: match[2].trim() });
  }
  return chapters;
}

function parseTranscriptXml(xml: string): { start: number; text: string }[] {
  const entries: { start: number; text: string }[] = [];

  // Format 1: <text start="1.23" dur="4.56">content</text>
  const textRegex = /<text\s+start="([\d.]+)"[^>]*>([\s\S]*?)<\/text>/g;
  let match;
  while ((match = textRegex.exec(xml)) !== null) {
    entries.push({
      start: parseFloat(match[1]),
      text: match[2]
        .replace(/<[^>]+>/g, "")
        .replace(/&amp;/g, "&").replace(/&lt;/g, "<").replace(/&gt;/g, ">")
        .replace(/&#39;/g, "'").replace(/&quot;/g, '"')
        .trim(),
    });
  }
  if (entries.length > 0) return entries;

  // Format 2: <p t="1230" d="4560">content</p>
  const pRegex = /<p\s+t="(\d+)"[^>]*>([\s\S]*?)<\/p>/g;
  while ((match = pRegex.exec(xml)) !== null) {
    entries.push({
      start: parseInt(match[1]) / 1000,
      text: match[2].replace(/<[^>]+>/g, "").trim(),
    });
  }
  return entries;
}

export async function extract(url: string, ctx: AdapterContext): Promise<ParseResult> {
  const videoId = extractVideoId(url);
  if (!videoId) throw new Error(`Cannot extract video ID from URL: ${url}`);

  const sock = await ctx.ensureDaemon();
  try {
    await ctx.sendDaemonRequest(sock, "navigate", {
      url: `https://www.youtube.com/watch?v=${videoId}`,
      timeout: ctx.timeout,
    });

    // Extract metadata and API key from page
    const pageData = await ctx.sendDaemonRequest(sock, "evaluate", {
      expression: `JSON.stringify({
        title: document.querySelector('meta[property="og:title"]')?.content || document.title,
        channel: document.querySelector('link[itemprop="name"]')?.content || document.querySelector('#channel-name a')?.textContent?.trim() || '',
        published: document.querySelector('meta[itemprop="datePublished"]')?.content || '',
        description: document.querySelector('meta[property="og:description"]')?.content || '',
        apiKey: window.ytcfg?.data_?.INNERTUBE_API_KEY || '',
      })`,
    });
    const meta = JSON.parse(pageData);

    // Try to get transcript via InnerTube API
    let transcript: { start: number; text: string }[] = [];
    if (meta.apiKey) {
      try {
        const playerResp = await fetch(`https://www.youtube.com/youtubei/v1/player?key=${meta.apiKey}`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            videoId,
            context: {
              client: { clientName: "ANDROID", clientVersion: "17.31.35", hl: "en" },
            },
          }),
        });
        const playerData = await playerResp.json();
        const captionTracks = playerData?.captions?.playerCaptionsTracklistRenderer?.captionTracks;
        if (captionTracks?.length > 0) {
          const transcriptResp = await fetch(captionTracks[0].baseUrl);
          transcript = parseTranscriptXml(await transcriptResp.text());
        }
      } catch (e) {
        console.error(`[youtube] InnerTube API failed: ${(e as Error).message}`);
      }
    }

    // Fallback: try ytInitialPlayerResponse
    if (transcript.length === 0) {
      try {
        const iprData = await ctx.sendDaemonRequest(sock, "evaluate", {
          expression: `(() => {
            const scripts = document.querySelectorAll('script');
            for (const s of scripts) {
              const m = s.textContent?.match(/ytInitialPlayerResponse\\s*=\\s*({.+?});/);
              if (m) return m[1];
            }
            return null;
          })()`,
        });
        if (iprData) {
          const ipr = JSON.parse(iprData);
          const tracks = ipr?.captions?.playerCaptionsTracklistRenderer?.captionTracks;
          if (tracks?.length > 0) {
            const resp = await fetch(tracks[0].baseUrl);
            transcript = parseTranscriptXml(await resp.text());
          }
        }
      } catch {
        console.error("[youtube] ytInitialPlayerResponse fallback also failed");
      }
    }

    // Extract chapters from description
    const fullDescription = await ctx.sendDaemonRequest(sock, "evaluate", {
      expression: `document.querySelector('#description-inner, ytd-text-inline-expander .content')?.textContent || ''`,
    });
    const chapters = extractChapters(fullDescription || "");

    // Build markdown
    const lines: string[] = [];
    lines.push(`# ${meta.title}`);
    lines.push("");
    lines.push(`**Channel:** ${meta.channel}`);
    if (meta.published) lines.push(`**Published:** ${meta.published}`);
    lines.push(`**URL:** https://www.youtube.com/watch?v=${videoId}`);
    lines.push("");

    if (chapters.length > 0) {
      lines.push("## Chapters");
      lines.push("");
      for (const ch of chapters) {
        lines.push(`- [${formatTimestamp(ch.time)}] ${ch.title}`);
      }
      lines.push("");
    }

    if (transcript.length > 0) {
      lines.push("## Transcript");
      lines.push("");
      let currentChapter = 0;
      for (const entry of transcript) {
        if (chapters.length > 0 && currentChapter < chapters.length - 1) {
          if (entry.start >= chapters[currentChapter + 1].time) {
            currentChapter++;
            lines.push("");
            lines.push(`### ${chapters[currentChapter].title}`);
            lines.push("");
          }
        }
        lines.push(`[${formatTimestamp(entry.start)}] ${entry.text}`);
      }
    } else {
      lines.push("_No transcript available for this video._");
    }

    return {
      markdown: lines.join("\n"),
      metadata: {
        url: `https://www.youtube.com/watch?v=${videoId}`,
        title: meta.title,
        author: meta.channel,
        published: meta.published || undefined,
        site_name: "YouTube",
        description: meta.description || undefined,
      },
    };
  } finally {
    sock.destroy();
  }
}
```

- [ ] **Step 2: Commit**

```bash
git add scripts/adapters/youtube.ts
git commit -m "feat(adapter): YouTube transcript and chapters extraction"
```

---

### Task 11: X/Twitter Adapter

**Files:**
- Create: `scripts/adapters/x-twitter.ts`

- [ ] **Step 1: Implement X/Twitter adapter**

Create `scripts/adapters/x-twitter.ts`:

```typescript
import { existsSync, readFileSync, writeFileSync, unlinkSync, chmodSync } from "fs";
import { resolve } from "path";
import { homedir } from "os";
import type { ParseResult } from "../types";

const CACHE_DIR = resolve(homedir(), ".cache", "jdy-url-to-markdown");
const COOKIE_FILE = resolve(CACHE_DIR, "x-session-cookies.json");

interface AdapterContext {
  timeout: number;
  ensureDaemon: () => Promise<import("net").Socket>;
  sendDaemonRequest: (sock: import("net").Socket, method: string, params?: any) => Promise<any>;
}

function extractTweetId(url: string): string | null {
  const match = url.match(/(?:twitter\.com|x\.com)\/\w+\/status\/(\d+)/);
  return match ? match[1] : null;
}

function loadCookies(): any[] | null {
  if (!existsSync(COOKIE_FILE)) return null;
  try {
    const data = JSON.parse(readFileSync(COOKIE_FILE, "utf-8"));
    return data.cookies || null;
  } catch {
    return null;
  }
}

function saveCookies(cookies: any[]): void {
  console.error(`[x-twitter] Saving X session cookies to ${COOKIE_FILE}`);
  writeFileSync(COOKIE_FILE, JSON.stringify({ cookies, savedAt: new Date().toISOString() }), { mode: 0o600 });
  try { chmodSync(COOKIE_FILE, 0o600); } catch {}
}

function deleteCookies(): void {
  try { unlinkSync(COOKIE_FILE); } catch {}
}

function extractTweetData(graphqlPayload: any): { tweets: any[]; author: any } {
  const tweets: any[] = [];
  let author: any = null;

  function walk(obj: any): void {
    if (!obj || typeof obj !== "object") return;
    if (obj.__typename === "Tweet" || obj.legacy?.full_text) {
      const legacy = obj.legacy || obj;
      const user = obj.core?.user_results?.result?.legacy || {};
      if (!author) author = user;
      tweets.push({
        text: legacy.full_text || "",
        created_at: legacy.created_at || "",
        favorite_count: legacy.favorite_count || 0,
        retweet_count: legacy.retweet_count || 0,
        media: (legacy.entities?.media || []).map((m: any) => m.media_url_https || m.url),
        quoted: obj.quoted_status_result?.result,
      });
    }
    for (const val of Object.values(obj)) {
      if (typeof val === "object") walk(val);
    }
  }

  walk(graphqlPayload);
  return { tweets, author };
}

export async function extract(url: string, ctx: AdapterContext): Promise<ParseResult> {
  const tweetId = extractTweetId(url);
  if (!tweetId) throw new Error(`Cannot extract tweet ID from URL: ${url}`);

  const sock = await ctx.ensureDaemon();
  try {
    // Enable network interception
    await ctx.sendDaemonRequest(sock, "enableNetwork");

    // Restore cookies if available
    const savedCookies = loadCookies();
    if (savedCookies) {
      await ctx.sendDaemonRequest(sock, "setCookies", { cookies: savedCookies });
    }

    // Navigate to tweet
    await ctx.sendDaemonRequest(sock, "navigate", { url, timeout: ctx.timeout });

    // Check for login wall
    const loginCheck = await ctx.sendDaemonRequest(sock, "evaluate", {
      expression: `!!document.querySelector('[data-testid="loginButton"], [href="/login"]')`,
    });

    if (loginCheck && !savedCookies) {
      // Need login -- prompt user
      console.error("[x-twitter] Login required. Please log in to X in the Chrome window, then press Enter.");
      await new Promise<void>((resolve) => {
        process.stdin.once("data", () => resolve());
      });

      // Re-navigate after login
      await ctx.sendDaemonRequest(sock, "navigate", { url, timeout: ctx.timeout });

      // Save cookies
      const { cookies } = await ctx.sendDaemonRequest(sock, "getCookies", { domain: "x.com" });
      const authCookies = cookies.filter((c: any) => ["auth_token", "ct0"].includes(c.name));
      if (authCookies.length >= 2) {
        saveCookies(cookies);
      }
    } else if (loginCheck && savedCookies) {
      // Cookies expired
      console.error("[x-twitter] Saved cookies expired, clearing...");
      deleteCookies();
      throw new Error("X session cookies expired. Please re-run to log in again.");
    }

    // Wait for GraphQL responses
    await new Promise(r => setTimeout(r, 3000));

    const { responses } = await ctx.sendDaemonRequest(sock, "getNetworkResponses", {
      urlPattern: "graphql.*/TweetDetail|TweetResultByRestId",
    });

    if (responses.length === 0) {
      throw new Error("No GraphQL responses captured. The tweet may require authentication.");
    }

    // Get the most relevant response
    const { body: bodyStr } = await ctx.sendDaemonRequest(sock, "getResponseBody", {
      requestId: responses[responses.length - 1].requestId,
    });
    const payload = JSON.parse(bodyStr);
    const { tweets, author } = extractTweetData(payload);

    if (tweets.length === 0) {
      throw new Error("No tweet data found in GraphQL response.");
    }

    // Build markdown
    const authorName = author?.name || "Unknown";
    const authorHandle = author?.screen_name || "unknown";
    const lines: string[] = [];

    lines.push(`# @${authorHandle} (${authorName})`);
    lines.push("");

    for (let i = 0; i < tweets.length; i++) {
      const tweet = tweets[i];
      if (tweets.length > 1) {
        lines.push(`**[${i + 1}/${tweets.length}]**`);
        lines.push("");
      }
      lines.push(tweet.text);
      lines.push("");

      if (tweet.media.length > 0) {
        for (const mediaUrl of tweet.media) {
          lines.push(`![](${mediaUrl})`);
        }
        lines.push("");
      }

      if (tweet.quoted) {
        const qLegacy = tweet.quoted.legacy || tweet.quoted;
        const qUser = tweet.quoted.core?.user_results?.result?.legacy || {};
        lines.push(`> **@${qUser.screen_name || "unknown"}:** ${qLegacy.full_text || ""}`);
        lines.push("");
      }
    }

    // Engagement
    const mainTweet = tweets[0];
    lines.push("---");
    lines.push(`Likes: ${mainTweet.favorite_count} | Retweets: ${mainTweet.retweet_count}`);
    lines.push(`Date: ${mainTweet.created_at}`);

    return {
      markdown: lines.join("\n"),
      metadata: {
        url,
        title: `@${authorHandle}: ${tweets[0].text.slice(0, 80)}${tweets[0].text.length > 80 ? "..." : ""}`,
        author: `${authorName} (@${authorHandle})`,
        site_name: "X (Twitter)",
      },
    };
  } finally {
    sock.destroy();
  }
}
```

- [ ] **Step 2: Commit**

```bash
git add scripts/adapters/x-twitter.ts
git commit -m "feat(adapter): X/Twitter thread extraction via GraphQL interception"
```

---

### Task 12: SKILL.md & Plugin Manifest

**Files:**
- Create: `SKILL.md`
- Create: `.claude-plugin/plugin.json`
- Create: `CLAUDE.md`

- [ ] **Step 1: Create SKILL.md**

Create `SKILL.md`:

```markdown
---
name: baoyu-url-to-markdown
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

    # Wait mode for login-required pages
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
```

- [ ] **Step 2: Create plugin.json**

Run: `mkdir -p /Users/jdy/Documents/skills/jdy-url-to-markdown/.claude-plugin`

Create `.claude-plugin/plugin.json`:

```json
{
  "name": "jdy-url-to-markdown",
  "version": "0.1.0",
  "description": "Fetch URLs and convert to clean Markdown with YAML front matter",
  "skills": [
    {
      "name": "baoyu-url-to-markdown",
      "path": "../SKILL.md"
    }
  ]
}
```

- [ ] **Step 3: Create CLAUDE.md**

Create `CLAUDE.md`:

```markdown
# jdy-url-to-markdown

URL to Markdown tool, used as a Claude Code skill.

## Development

- Runtime: Bun
- Test: `bun test`
- Entry: `bun run scripts/main.ts <url>`

## Architecture

- `scripts/main.ts` -- CLI entry, arg parsing, routing
- `scripts/fetcher.ts` -- two-level fetch cascade (local fetch -> CDP)
- `scripts/parser.ts` -- Readability + Turndown parsing
- `scripts/quality.ts` -- content quality check (5 criteria)
- `scripts/writer.ts` -- slug generation, YAML front matter, file output
- `scripts/cdp/` -- CDP client and daemon
- `scripts/adapters/` -- YouTube, X/Twitter adapters
- `scripts/rules/` -- site rules and cleaner functions
```

- [ ] **Step 4: Commit**

```bash
git add SKILL.md .claude-plugin/plugin.json CLAUDE.md
git commit -m "feat(skill): SKILL.md, plugin manifest, and CLAUDE.md"
```

---

### Task 13: Integration Test (End-to-End Level 1 Fetch)

**Files:**
- Create: `tests/integration.test.ts`

- [ ] **Step 1: Write integration test for Level 1 fetch**

Create `tests/integration.test.ts`:

```typescript
import { describe, expect, test, afterAll } from "bun:test";
import { existsSync, readFileSync, unlinkSync, rmdirSync } from "fs";

const OUTPUT_PATH = "/tmp/jdy-url-to-markdown-test/test-output.md";
const PROJECT_DIR = import.meta.dir.replace("/tests", "");

describe("end-to-end Level 1 fetch", () => {
  test("fetches Wikipedia article via Level 1", async () => {
    try { unlinkSync(OUTPUT_PATH); } catch {}

    const proc = Bun.spawn(
      ["bun", "run", "scripts/main.ts", "https://en.wikipedia.org/wiki/Markdown", "-o", OUTPUT_PATH],
      { cwd: PROJECT_DIR, stdout: "pipe", stderr: "pipe" },
    );

    const exitCode = await proc.exited;
    expect(exitCode).toBe(0);
    expect(existsSync(OUTPUT_PATH)).toBe(true);

    const content = readFileSync(OUTPUT_PATH, "utf-8");
    // Has YAML front matter
    expect(content).toStartWith("---\n");
    expect(content).toContain("fetch_level: 1");
    // Has actual content
    expect(content).toContain("Markdown");
    expect(content.length).toBeGreaterThan(500);
  }, 30000);

  afterAll(() => {
    try { unlinkSync(OUTPUT_PATH); } catch {}
    try { rmdirSync("/tmp/jdy-url-to-markdown-test"); } catch {}
  });
});
```

- [ ] **Step 2: Run integration test**

Run: `cd /Users/jdy/Documents/skills/jdy-url-to-markdown && bun test tests/integration.test.ts`
Expected: PASS -- Wikipedia article fetched and saved with front matter.

- [ ] **Step 3: Commit**

```bash
git add tests/integration.test.ts
git commit -m "test(integration): end-to-end Level 1 fetch of Wikipedia article"
```

---

## Self-Review Checklist

**Spec coverage:**
- [x] Two-level fetch cascade (Task 7)
- [x] Quality gating with 5 criteria (Task 2)
- [x] Router with suffix + alias matching (Task 4)
- [x] Parser: Readability + Turndown + metadata (Task 5)
- [x] CDP daemon with mutex (Task 8)
- [x] Cleaners: WeChat, Zhihu, Xiaohongshu (Task 6)
- [x] Writer: slug sanitization, YAML safety (Task 3)
- [x] YouTube adapter (Task 10)
- [x] X/Twitter adapter with cookie security (Task 11)
- [x] CLI with --cdp, --wait, --timeout, -o (Task 9)
- [x] SKILL.md + EXTEND.md support (Task 12)
- [x] linkedom compatibility validation (Task 5 Step 5 note)
- [x] Exit codes 0/1/2/3 (Task 9)
- [x] Integration test (Task 13)

**Type consistency:**
- `ParseResult` used consistently: `{ markdown: string, metadata: Metadata }`
- `QualityResult` used in quality.ts and fetcher.ts
- `SiteRule` used in router.ts, fetcher.ts, main.ts
- `Cleaner` type used in cleaners.ts and parser.ts
- Adapter `extract()` returns `ParseResult` -- matches in youtube.ts and x-twitter.ts

**No placeholders found.**
