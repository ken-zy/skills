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
    expect(generateSlug("\u{1F389}\u{1F38A}\u{1F388}")).toBe("untitled");
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
    const path = buildOutputPath("\u{1F389}", "/out", new Date("2026-04-09T12:00:00Z"));
    expect(path).toBe("/out/20260409/untitled.md");
  });
});
