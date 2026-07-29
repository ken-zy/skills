import { describe, expect, test } from "bun:test";
import { qualityCheck } from "../scripts/quality";
import { waitForValidContent } from "../scripts/wait";

describe("waitForValidContent", () => {
  test("returns the first page that passes validation", async () => {
    const blocked = "# 微信文章\n\n微信扫一扫可打开此内容，使用完整服务。".repeat(10);
    const valid = [
      "# 微信文章",
      "",
      "这是第一段真正的微信文章正文，包含足够多的信息供读者理解文章讨论的问题和主要结论。",
      "",
      "这是第二段真正的微信文章正文，继续解释背景、证据和作者给出的具体建议。",
      "",
      "这是第三段补充内容，用于确保页面已经完成加载，而不是仍然停留在微信客户端引导页面。",
    ].join("\n");
    const pages = [blocked, valid];
    let index = 0;

    const result = await waitForValidContent({
      read: async () => pages[Math.min(index++, pages.length - 1)],
      validate: qualityCheck,
      timeoutMs: 1000,
      intervalMs: 0,
      sleep: async () => {},
    });

    expect(result).toBe(valid);
  });
});
