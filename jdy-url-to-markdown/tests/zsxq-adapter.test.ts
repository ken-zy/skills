import { describe, expect, test } from "bun:test";
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
