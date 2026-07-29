import { describe, expect, test } from "bun:test";
import { fetchAndParse } from "../scripts/fetcher";

describe("fetchAndParse", () => {
  test("applies site-specific quality options to CDP content", async () => {
    const paragraph = "这是微信编辑器生成的一整块正文，内容真实且足够长，但转换后没有空行分隔。".repeat(30);
    const html = `<html>
      <head><meta property="og:title" content="微信单段文章"></head>
      <body><section id="js_content"><p>${paragraph}</p></section></body>
    </html>`;

    const result = await fetchAndParse("https://mp.weixin.qq.com/s/test", {
      rule: {
        startLevel: 2,
        contentSelector: "#js_content",
        quality: { singleParagraphMinChars: 600 },
      },
      forceCdp: true,
      cdpFetch: async () => html,
    });

    expect(result.fetchLevel).toBe(2);
  });
});
