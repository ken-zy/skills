# jdy-url-to-markdown

URL to Markdown tool, used as a Claude Code skill.

## Development

- Runtime: Bun
- Test: `bun test`
- Entry: `bun run scripts/main.ts <url>`

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
- `scripts/media/` -- site-independent image download, classified R2-script/PicList upload, WebP verification, and Markdown URL rewrite
- `scripts/rules/` -- site rules and cleaner functions
