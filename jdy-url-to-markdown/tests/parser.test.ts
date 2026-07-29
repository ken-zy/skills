import { describe, expect, test } from "bun:test";
import { readFileSync } from "fs";
import { resolve } from "path";
import { parse } from "../scripts/parser";

const fixtureDir = resolve(import.meta.dir, "fixtures");

describe("parse", () => {
  const html = readFileSync(resolve(fixtureDir, "simple-article.html"), "utf-8");

  test("extracts article content as markdown", () => {
    const result = parse(html, "https://example.com/article");
    expect(result.markdown).toContain("Test Article Title");
    expect(result.markdown).toContain("first paragraph");
    expect(result.markdown).toContain("Section Two");
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
    expect(result.markdown).toContain("![");
  });

  test("falls back to title tag when OG tags missing", () => {
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

  test("uses a configured content selector before Readability", () => {
    const selectedContent = "这是微信正文第一段，用来验证站点专用正文选择器能够绕过通用 Readability 的错误判断。";
    const competingContent = "这是页面外围的推荐内容，不属于需要保存的文章正文。".repeat(40);
    const wechatHtml = `<html>
      <head><meta property="og:title" content="微信测试文章"></head>
      <body>
        <article><p>${competingContent}</p></article>
        <section id="js_content" class="rich_media_content">
          <p>${selectedContent}</p>
          <p>这是微信正文第二段，确保转换结果包含多个可用段落并可以通过内容质量检查。</p>
        </section>
      </body>
    </html>`;

    const result = parse(
      wechatHtml,
      "https://mp.weixin.qq.com/s/test",
      undefined,
      "#js_content, .rich_media_content",
    );

    expect(result.markdown).toContain(selectedContent);
    expect(result.markdown).not.toContain("页面外围的推荐内容");
  });

  test("falls back to Readability when the configured selector is missing", () => {
    const result = parse(
      html,
      "https://example.com/article",
      undefined,
      "#missing-content",
    );

    expect(result.markdown).toContain("first paragraph");
    expect(result.markdown).toContain("Section Two");
  });
});
