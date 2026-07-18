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
