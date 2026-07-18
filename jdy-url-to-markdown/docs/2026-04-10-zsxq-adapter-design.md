# zsxq adapter design

Add a Knowledge Planet (知识星球) adapter to jdy-url-to-markdown for extracting single posts from zsxq.com.

## URL patterns

| Pattern | Type | Extraction |
|---------|------|------------|
| `wx.zsxq.com/group/{gid}/topic/{tid}` | topic | API via CDP evaluate |
| `articles.zsxq.com/id_{slug}.html` | article | CDP navigate + Readability |
| `t.zsxq.com/{code}` | shortlink | CDP redirect follow, then dispatch |

## Architecture

Single adapter file `scripts/adapters/zsxq.ts` exporting `extract(url, ctx)`.

### Flow

```
extract(url, ctx)
  parseZsxqUrl(url) -> { type, groupId?, topicId?, slug? }
  |
  +-- shortlink: CDP navigate -> get redirected URL -> recursive extract()
  +-- topic:     CDP navigate to wx.zsxq.com -> evaluate fetch API -> parse
  +-- article:   CDP navigate to articles.zsxq.com -> getHTML -> Readability
```

### URL parser: parseZsxqUrl(url)

Extract structured info from three URL formats:

- `wx.zsxq.com/group/{gid}/topic/{tid}` -> `{ type: 'topic', groupId: gid, topicId: tid }`
- `articles.zsxq.com/id_{slug}.html` -> `{ type: 'article', slug }`
- `t.zsxq.com/{code}` -> `{ type: 'shortlink' }`

### Topic extraction

1. Ensure browser is on `wx.zsxq.com` (navigate if needed)
2. CDP evaluate: `fetch('/v2/groups/{gid}/topics/{tid}', {credentials:'include'})` to get topic JSON
3. If direct topic API fails (error 1007), fall back to listing API with `end_time` pagination to locate the topic by ID
4. Extract from response: `talk.text`, `talk.article`, `talk.images`, `talk.owner`, `likes_count`, `comments_count`, `create_time`
5. Run `cleanZsxqMarkup()` on text
6. If topic has `article_url`, fetch article content and append below topic text

### Article extraction

1. CDP navigate to `articles.zsxq.com/id_{slug}.html`
2. Wait for content to render
3. `getHTML` -> strip `<script>` and `<style>` -> Readability parse -> Turndown to markdown
4. Extract title from `<title>` tag, author and date from page metadata

### Shortlink resolution

1. CDP navigate to `t.zsxq.com/{code}`
2. Read final URL after redirect
3. Call `parseZsxqUrl()` on resolved URL
4. Dispatch to topic or article handler

### Markup cleaner: cleanZsxqMarkup(text)

Knowledge Planet uses custom inline XML tags in topic text. Transform them to markdown:

| Input | Output |
|-------|--------|
| `<e type="text_bold" title="{encoded}"/>` | `**{decoded}**` |
| `<e type="hashtag" title="{encoded}"/>` | `#{decoded}` |
| `<e type="mention" name="{encoded}"/>` | `@{decoded}` |
| `<e type="web" href="{encoded}" title="{encoded}"/>` | `[{decoded_title}]({decoded_href})` |
| `<e type="web" href="{encoded}"/>` | `{decoded_href}` |
| Any other `<e .../>` | remove |

All `title`, `name`, `href` attribute values are URI-encoded and must be decoded.

## Output format

Standard `ParseResult` with YAML front matter:

```yaml
---
url: "https://wx.zsxq.com/group/{gid}/topic/{tid}"
title: "{article_title or first 50 chars of text}"
author: "{owner.name}"
published: "{create_time as YYYY-MM-DD}"
site_name: "知识星球"
description: "{first 100 chars of cleaned text}"
---
```

Body: cleaned markdown text. For topics with article_url, article full text is appended after a `---` separator.

Image URLs from `talk.images` are included as `![](url)` at the end.

## site-rules.json

Add one entry:

```json
"wx.zsxq.com": {
  "adapter": "zsxq",
  "aliases": ["t.zsxq.com", "articles.zsxq.com"]
}
```

## Error handling

- **Not logged in**: API returns 401. Adapter logs error and exits with code 3 (CDP connection issue equivalent — user needs to log in via Chrome).
- **Topic not found**: API returns empty or error. Exit with code 1.
- **Shortlink invalid**: redirect fails or lands on non-topic page. Exit with code 1.
- **Article page empty**: Readability returns no content. Exit with code 2.

## Scope exclusions

- No batch/bulk scraping (separate skill)
- No login flow handling (depends on existing Chrome session cookies)
- No standalone cleaner in cleaners.ts (markup logic is zsxq-specific, stays in adapter)

## Files to create/modify

| File | Action |
|------|--------|
| `scripts/adapters/zsxq.ts` | Create — adapter implementation |
| `scripts/rules/site-rules.json` | Modify — add wx.zsxq.com entry |
| `tests/zsxq-adapter.test.ts` | Create — unit tests for URL parser and markup cleaner |
