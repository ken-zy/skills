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
