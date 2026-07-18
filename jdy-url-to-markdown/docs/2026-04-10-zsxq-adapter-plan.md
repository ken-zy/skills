# zsxq Adapter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Knowledge Planet (知识星球) adapter to jdy-url-to-markdown for single-post extraction from wx.zsxq.com, articles.zsxq.com, and t.zsxq.com short links.

**Architecture:** Single adapter file following the existing pattern (youtube.ts, x-twitter.ts). URL parser identifies three URL types and dispatches to topic API extraction, article page extraction, or short link redirect resolution. zsxq-specific XML markup is cleaned to standard markdown.

**Tech Stack:** TypeScript, Bun, CDP daemon (existing infrastructure)

---

## File Structure

| File | Responsibility |
|------|---------------|
| `scripts/adapters/zsxq.ts` | Create — adapter: URL parsing, API extraction, article extraction, markup cleaning |
| `scripts/rules/site-rules.json` | Modify — add wx.zsxq.com entry with aliases |
| `tests/zsxq-adapter.test.ts` | Create — unit tests for URL parser and markup cleaner |

---

### Task 1: URL Parser and Markup Cleaner (Pure Functions)

**Files:**
- Create: `scripts/adapters/zsxq.ts`
- Create: `tests/zsxq-adapter.test.ts`

- [ ] **Step 1: Write failing tests for URL parser**

```typescript
// tests/zsxq-adapter.test.ts
import { describe, expect, test } from "bun:test";

// We'll test the exported helpers directly
// For now, import from adapter file
import { parseZsxqUrl, cleanZsxqMarkup } from "../scripts/adapters/zsxq";

describe("parseZsxqUrl", () => {
  test("parses topic URL", () => {
    const result = parseZsxqUrl("https://wx.zsxq.com/group/1824528822/topic/22255512548581550");
    expect(result).toEqual({ type: "topic", groupId: "1824528822", topicId: "22255512548581550" });
  });

  test("parses article URL", () => {
    const result = parseZsxqUrl("https://articles.zsxq.com/id_d108rkca7zzl.html");
    expect(result).toEqual({ type: "article", slug: "d108rkca7zzl" });
  });

  test("parses short link", () => {
    const result = parseZsxqUrl("https://t.zsxq.com/uKZso");
    expect(result).toEqual({ type: "shortlink", code: "uKZso" });
  });

  test("returns null for unrecognized zsxq URL", () => {
    const result = parseZsxqUrl("https://wx.zsxq.com/settings");
    expect(result).toBeNull();
  });

  test("handles topic URL without www", () => {
    const result = parseZsxqUrl("https://wx.zsxq.com/group/88514228512542/topic/111821114882522");
    expect(result).toEqual({ type: "topic", groupId: "88514228512542", topicId: "111821114882522" });
  });
});

describe("cleanZsxqMarkup", () => {
  test("converts bold tags", () => {
    expect(cleanZsxqMarkup('<e type="text_bold" title="%E5%8A%A0%E7%B2%97" />')).toBe("**加粗**");
  });

  test("converts hashtag tags", () => {
    expect(cleanZsxqMarkup('<e type="hashtag" title="%E9%A1%B9%E7%9B%AE%E5%AE%9E%E6%93%8D" />')).toBe("#项目实操");
  });

  test("converts mention tags", () => {
    expect(cleanZsxqMarkup('<e type="mention" name="%E4%BA%A6%E4%BB%81" />')).toBe("@亦仁");
  });

  test("converts web link with title", () => {
    expect(cleanZsxqMarkup('<e type="web" href="https%3A%2F%2Fexample.com" title="%E9%93%BE%E6%8E%A5" />')).toBe("[链接](https://example.com)");
  });

  test("converts web link without title", () => {
    expect(cleanZsxqMarkup('<e type="web" href="https%3A%2F%2Fexample.com%2Fpath" />')).toBe("https://example.com/path");
  });

  test("strips unknown e tags", () => {
    expect(cleanZsxqMarkup('hello <e type="unknown" /> world')).toBe("hello  world");
  });

  test("handles mixed content", () => {
    const input = '这是<e type="text_bold" title="%E6%B5%8B%E8%AF%95" />文本，来自<e type="mention" name="%E4%BA%A6%E4%BB%81" />';
    expect(cleanZsxqMarkup(input)).toBe("这是**测试**文本，来自@亦仁");
  });

  test("passes through plain text unchanged", () => {
    expect(cleanZsxqMarkup("普通文本没有标签")).toBe("普通文本没有标签");
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/jdy/.claude/skills/jdy-url-to-markdown && bun test tests/zsxq-adapter.test.ts`
Expected: FAIL — module not found

- [ ] **Step 3: Implement URL parser and markup cleaner**

```typescript
// scripts/adapters/zsxq.ts
import type { ParseResult } from "../types";

interface AdapterContext {
  timeout: number;
  ensureDaemon: () => Promise<import("net").Socket>;
  sendDaemonRequest: (sock: import("net").Socket, method: string, params?: any) => Promise<any>;
}

type ZsxqUrl =
  | { type: "topic"; groupId: string; topicId: string }
  | { type: "article"; slug: string }
  | { type: "shortlink"; code: string };

export function parseZsxqUrl(url: string): ZsxqUrl | null {
  const parsed = new URL(url);
  const host = parsed.hostname.replace(/^www\./, "");

  if (host === "wx.zsxq.com") {
    const match = parsed.pathname.match(/^\/group\/(\d+)\/topic\/(\d+)/);
    if (match) return { type: "topic", groupId: match[1], topicId: match[2] };
    return null;
  }

  if (host === "articles.zsxq.com") {
    const match = parsed.pathname.match(/^\/id_([^.]+)\.html/);
    if (match) return { type: "article", slug: match[1] };
    return null;
  }

  if (host === "t.zsxq.com") {
    const code = parsed.pathname.slice(1);
    if (code) return { type: "shortlink", code };
    return null;
  }

  return null;
}

export function cleanZsxqMarkup(text: string): string {
  return text
    .replace(/<e type="text_bold" title="([^"]*)"[^/]*\/>/g, (_, t) => `**${decodeURIComponent(t)}**`)
    .replace(/<e type="hashtag"[^/]*title="([^"]*)"[^/]*\/>/g, (_, t) => `#${decodeURIComponent(t)}`)
    .replace(/<e type="mention"[^/]*name="([^"]*)"[^/]*\/>/g, (_, n) => `@${decodeURIComponent(n)}`)
    .replace(/<e type="web"[^/]*href="([^"]*)"[^/]*title="([^"]*)"[^/]*\/>/g, (_, h, t) => `[${decodeURIComponent(t)}](${decodeURIComponent(h)})`)
    .replace(/<e type="web"[^/]*href="([^"]*)"[^/]*\/>/g, (_, h) => decodeURIComponent(h))
    .replace(/<e [^/]*\/>/g, "");
}

// extract() will be added in Task 2
export async function extract(_url: string, _ctx: AdapterContext): Promise<ParseResult> {
  throw new Error("Not implemented yet");
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/jdy/.claude/skills/jdy-url-to-markdown && bun test tests/zsxq-adapter.test.ts`
Expected: All 13 tests PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/jdy/.claude/skills/jdy-url-to-markdown
git add scripts/adapters/zsxq.ts tests/zsxq-adapter.test.ts
git commit -m "feat(zsxq): add URL parser and markup cleaner with tests"
```

---

### Task 2: Topic Extraction via API

**Files:**
- Modify: `scripts/adapters/zsxq.ts`

- [ ] **Step 1: Implement topic extraction helper**

Add `extractTopic()` function above `extract()` in `scripts/adapters/zsxq.ts`:

```typescript
async function extractTopic(
  groupId: string,
  topicId: string,
  ctx: AdapterContext,
): Promise<ParseResult> {
  const sock = await ctx.ensureDaemon();
  try {
    // Navigate to wx.zsxq.com to ensure same-origin cookie access
    await ctx.sendDaemonRequest(sock, "navigate", {
      url: `https://wx.zsxq.com/group/${groupId}/topic/${topicId}`,
      timeout: ctx.timeout,
    });

    // Fetch topic data via API from page context
    const raw = await ctx.sendDaemonRequest(sock, "evaluate", {
      expression: `(async () => {
        const resp = await fetch('https://api.zsxq.com/v2/groups/${groupId}/topics/${topicId}', {
          credentials: 'include',
          headers: { 'Accept': 'application/json' }
        });
        const data = await resp.json();
        if (!data.succeeded) throw new Error('API error: ' + (data.code || 'unknown'));
        const t = data.resp_data.topic;
        return JSON.stringify({
          text: t.talk?.text || t.question?.text || '',
          author: t.talk?.owner?.name || t.question?.owner?.name || '',
          create_time: t.create_time,
          article_title: t.talk?.article?.title || null,
          article_url: t.talk?.article?.article_url || null,
          images: (t.talk?.images || []).map(i => i.large?.url || i.original?.url || '').filter(Boolean),
          likes: t.likes_count || 0,
          comments: t.comments_count || 0,
        });
      })()`,
    });

    const topic = JSON.parse(raw);
    const cleanedText = cleanZsxqMarkup(topic.text);
    const title = topic.article_title || cleanedText.replace(/\n/g, " ").slice(0, 50);
    const published = topic.create_time?.slice(0, 10) || "";

    const lines: string[] = [];
    lines.push(topic.article_title ? `# ${topic.article_title}` : "");
    lines.push(cleanedText);

    // If topic has article URL, fetch the full article content
    if (topic.article_url) {
      try {
        const articleResult = await extractArticle(topic.article_url.match(/id_([^.]+)\.html/)?.[1] || "", ctx, sock);
        lines.push("", "---", "", articleResult);
      } catch (e) {
        lines.push("", `[阅读全文](${topic.article_url})`);
      }
    }

    if (topic.images.length > 0) {
      lines.push("");
      for (const img of topic.images) lines.push(`![](${img})`);
    }

    return {
      markdown: lines.filter(Boolean).join("\n"),
      metadata: {
        url: `https://wx.zsxq.com/group/${groupId}/topic/${topicId}`,
        title,
        author: topic.author,
        published,
        site_name: "知识星球",
        description: cleanedText.slice(0, 100),
      },
    };
  } finally {
    sock.destroy();
  }
}
```

- [ ] **Step 2: Implement article extraction helper**

Add `extractArticle()` function above `extractTopic()`:

```typescript
async function extractArticle(
  slug: string,
  ctx: AdapterContext,
  existingSock?: import("net").Socket,
): Promise<string> {
  const sock = existingSock || (await ctx.ensureDaemon());
  const shouldDestroy = !existingSock;
  try {
    await ctx.sendDaemonRequest(sock, "navigate", {
      url: `https://articles.zsxq.com/id_${slug}.html`,
      timeout: ctx.timeout,
    });

    const html = await ctx.sendDaemonRequest(sock, "getHTML", {});
    const text = html
      .replace(/<script[\s\S]*?<\/script>/gi, "")
      .replace(/<style[\s\S]*?<\/style>/gi, "")
      .replace(/<[^>]+>/g, "\n")
      .replace(/&nbsp;/g, " ")
      .replace(/&lt;/g, "<")
      .replace(/&gt;/g, ">")
      .replace(/&amp;/g, "&")
      .replace(/\n{3,}/g, "\n\n")
      .trim();

    // Strip header boilerplate (title, "来自：", date line)
    const lines = text.split("\n");
    let startIdx = 0;
    for (let i = 0; i < Math.min(lines.length, 10); i++) {
      if (lines[i].includes("来自：") || /^\d{4}年\d{2}月\d{2}日/.test(lines[i].trim())) {
        startIdx = i + 1;
      }
    }
    return lines.slice(startIdx).join("\n").trim();
  } finally {
    if (shouldDestroy) sock.destroy();
  }
}
```

- [ ] **Step 3: Implement standalone article ParseResult wrapper**

Add `extractArticleFull()` for when articles.zsxq.com is the direct entry URL:

```typescript
async function extractArticleFull(slug: string, ctx: AdapterContext): Promise<ParseResult> {
  const sock = await ctx.ensureDaemon();
  try {
    await ctx.sendDaemonRequest(sock, "navigate", {
      url: `https://articles.zsxq.com/id_${slug}.html`,
      timeout: ctx.timeout,
    });

    // Extract title and meta from page
    const meta = await ctx.sendDaemonRequest(sock, "evaluate", {
      expression: `JSON.stringify({
        title: document.querySelector('title')?.textContent || '',
        author: document.querySelector('.author, .name')?.textContent?.trim() || '',
        date: document.querySelector('.date, time')?.textContent?.trim() || '',
      })`,
    });
    const pageMeta = JSON.parse(meta);

    const content = await extractArticle(slug, ctx, sock);

    return {
      markdown: `# ${pageMeta.title}\n\n${content}`,
      metadata: {
        url: `https://articles.zsxq.com/id_${slug}.html`,
        title: pageMeta.title,
        author: pageMeta.author || undefined,
        published: pageMeta.date || undefined,
        site_name: "知识星球",
        description: content.slice(0, 100),
      },
    };
  } finally {
    sock.destroy();
  }
}
```

- [ ] **Step 4: Wire up the extract() entry point**

Replace the placeholder `extract()` with the real implementation:

```typescript
export async function extract(url: string, ctx: AdapterContext): Promise<ParseResult> {
  const parsed = parseZsxqUrl(url);
  if (!parsed) throw new Error(`Unrecognized zsxq URL: ${url}`);

  switch (parsed.type) {
    case "topic":
      return extractTopic(parsed.groupId, parsed.topicId, ctx);

    case "article":
      return extractArticleFull(parsed.slug, ctx);

    case "shortlink": {
      // Resolve short link by following redirect via CDP
      const sock = await ctx.ensureDaemon();
      try {
        await ctx.sendDaemonRequest(sock, "navigate", { url, timeout: ctx.timeout });
        const resolvedUrl = await ctx.sendDaemonRequest(sock, "evaluate", {
          expression: "window.location.href",
        });
        sock.destroy();

        const resolvedParsed = parseZsxqUrl(resolvedUrl);
        if (!resolvedParsed || resolvedParsed.type === "shortlink") {
          throw new Error(`Short link resolved to unrecognized URL: ${resolvedUrl}`);
        }
        return extract(resolvedUrl, ctx);
      } catch (e) {
        sock.destroy();
        throw e;
      }
    }
  }
}
```

- [ ] **Step 5: Commit**

```bash
cd /Users/jdy/.claude/skills/jdy-url-to-markdown
git add scripts/adapters/zsxq.ts
git commit -m "feat(zsxq): implement topic, article, and shortlink extraction"
```

---

### Task 3: Site Rules and Integration

**Files:**
- Modify: `scripts/rules/site-rules.json`

- [ ] **Step 1: Add zsxq entry to site-rules.json**

Add after the `x.com` entry:

```json
  "wx.zsxq.com": {
    "adapter": "zsxq",
    "aliases": ["t.zsxq.com", "articles.zsxq.com"]
  }
```

- [ ] **Step 2: Verify router matches all three domains**

Run a quick check:

```bash
cd /Users/jdy/.claude/skills/jdy-url-to-markdown
bun -e "
const { matchSiteRule } = require('./scripts/router.ts');
console.log('wx.zsxq.com:', matchSiteRule('https://wx.zsxq.com/group/123/topic/456'));
console.log('articles:', matchSiteRule('https://articles.zsxq.com/id_abc.html'));
console.log('shortlink:', matchSiteRule('https://t.zsxq.com/uKZso'));
"
```

Expected: all three return `{ adapter: "zsxq", aliases: [...] }`

- [ ] **Step 3: Run all existing tests to verify no regression**

Run: `cd /Users/jdy/.claude/skills/jdy-url-to-markdown && bun test`
Expected: All existing tests pass, plus the 13 new zsxq tests

- [ ] **Step 4: Commit**

```bash
cd /Users/jdy/.claude/skills/jdy-url-to-markdown
git add scripts/rules/site-rules.json
git commit -m "feat(zsxq): register adapter in site-rules.json"
```

---

### Task 4: Manual Integration Test

**Files:** None (verification only)

- [ ] **Step 1: Test with a real topic URL**

```bash
cd /Users/jdy/.claude/skills/jdy-url-to-markdown
bun run scripts/main.ts "https://wx.zsxq.com/group/1824528822/topic/22255512548581550" -o /tmp/zsxq-test-topic.md
```

Verify: file created, contains frontmatter with `site_name: 知识星球`, has cleaned markdown body.

- [ ] **Step 2: Test with an article URL**

```bash
bun run scripts/main.ts "https://articles.zsxq.com/id_d108rkca7zzl.html" -o /tmp/zsxq-test-article.md
```

Verify: file created, contains full article text.

- [ ] **Step 3: Test with a short link (if available)**

```bash
bun run scripts/main.ts "https://t.zsxq.com/uKZso" -o /tmp/zsxq-test-shortlink.md
```

Verify: redirects and extracts content from the resolved URL.

- [ ] **Step 4: Clean up test files**

```bash
rm -f /tmp/zsxq-test-*.md
```

- [ ] **Step 5: Final commit if any fixes were needed**

```bash
cd /Users/jdy/.claude/skills/jdy-url-to-markdown
git add -A
git commit -m "fix(zsxq): adjustments from integration testing"
```
