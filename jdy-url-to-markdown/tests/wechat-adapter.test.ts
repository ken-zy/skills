import { describe, expect, test } from "bun:test";
import type { Socket } from "net";
import {
  extract,
  parseWechatHtml,
  prepareWechatHtml,
} from "../scripts/adapters/wechat";

const ARTICLE_URL = "https://mp.weixin.qq.com/s/test";

function buildWechatHtml(body: string): string {
  return `<html>
    <head>
      <meta property="og:title" content="微信 Adapter 测试文章">
      <meta name="author" content="测试作者">
    </head>
    <body>
      <div class="js_wechat_qrcode">二维码提示</div>
      <section id="js_content" class="rich_media_content">
        ${body}
      </section>
    </body>
  </html>`;
}

describe("prepareWechatHtml", () => {
  test("promotes lazy-loaded image URLs and removes placeholders and structural noise", () => {
    const html = buildWechatHtml(`
      <p>这是第一段完整正文，用来验证微信公众号 Adapter 可以保留有意义的文章内容。</p>
      <img alt="销量截图" src="data:image/svg+xml,placeholder" data-src="//mmbiz.qpic.cn/example/640?wx_fmt=png">
      <img alt="透明占位图" src="data:image/svg+xml,placeholder">
      <div class="reward_area">微信扫一扫赞赏作者</div>
      <p>这是第二段完整正文，用来确认清理结构噪声后不会误删正常文章段落。</p>
    `);

    const prepared = prepareWechatHtml(html);

    expect(prepared).toContain("https://mmbiz.qpic.cn/example/640?wx_fmt=png");
    expect(prepared).not.toContain("data:image/svg+xml");
    expect(prepared).not.toContain("二维码提示");
    expect(prepared).not.toContain("微信扫一扫赞赏作者");
  });
});

describe("parseWechatHtml", () => {
  test("reuses the shared parser and produces compact markdown", () => {
    const html = buildWechatHtml(`
      <p>这是第一段完整正文，包含足够多的中文字符，用于确认共享解析器可以正确转换微信公众号正文。</p>
      <p>&nbsp;</p>
      <img alt="产品截图" data-src="https://mmbiz.qpic.cn/example/product.png" src="data:image/svg+xml,placeholder">
      <p>这是第二段完整正文，同样包含足够多的中文字符，用于确认输出具有多个可用正文段落。</p>
    `);

    const result = parseWechatHtml(html, ARTICLE_URL);

    expect(result.metadata.title).toBe("微信 Adapter 测试文章");
    expect(result.markdown).toContain("![产品截图](https://mmbiz.qpic.cn/example/product.png)");
    expect(result.markdown).not.toMatch(/\n{3,}/);
  });

  test("recovers a short title when a WeChat special page puts the body in title metadata", () => {
    const title = "微信贴图号：我半个月做出百万爆款，现在入场还在红利早期";
    const firstParagraph = "微信公众号最近悄悄上线了一个新功能，贴图，也就是大家说的微信版小绿书。";
    const secondParagraph = "很多人以为这只是内容形式的变化，但背后其实是一个尚未被多数人发现的流量红利。";
    const html = `<html>
      <head>
        <meta property="og:title" content="${title}\\n\\n${firstParagraph}\\n\\n${secondParagraph}">
        <title>${title} ${firstParagraph} ${secondParagraph}</title>
      </head>
      <body>
        <section id="js_content" class="rich_media_content">
          <p>${title}</p>
          <p>${firstParagraph}</p>
          <p>${secondParagraph}</p>
        </section>
      </body>
    </html>`;

    const result = parseWechatHtml(html, ARTICLE_URL);

    expect(result.metadata.title).toBe(title);
    expect(result.metadata.title.length).toBeLessThanOrEqual(180);
    expect(result.markdown.split("\n", 1)[0]).toBe(`# ${title}`);
    expect(result.markdown).toContain(firstParagraph);
    expect(result.markdown).toContain(secondParagraph);
  });
});

describe("extract", () => {
  test("returns parsed content after the shared quality gate passes", async () => {
    const html = buildWechatHtml(`
      <p>这是第一段完整正文，包含足够多的中文字符，用来验证微信公众号 Adapter 的成功抓取路径。</p>
      <img alt="正文截图" data-src="https://mmbiz.qpic.cn/example/success.png" src="data:image/svg+xml,placeholder">
      <p>这是第二段完整正文，同样包含足够多的中文字符，确保共享质量检查可以识别多个有效段落。</p>
      <p>这是第三段补充正文，用来让测试内容稳定超过最小字符数，并验证正常文章不会被错误拒绝。</p>
    `);
    let destroyed = false;
    const socket = { destroy() { destroyed = true; } } as Socket;
    const calls: string[] = [];
    const context = {
      timeout: 30000,
      ensureDaemon: async () => socket,
      sendDaemonRequest: async (_sock: Socket, method: string) => {
        calls.push(method);
        if (method === "navigate") return { ok: true };
        if (method === "getHTML") return { html };
        throw new Error(`unexpected method: ${method}`);
      },
      quality: { singleParagraphMinChars: 600 },
    };

    const result = await extract(ARTICLE_URL, context);

    expect(result.markdown).toContain("![正文截图](https://mmbiz.qpic.cn/example/success.png)");
    expect(calls).toEqual(["navigate", "getHTML"]);
    expect(destroyed).toBe(true);
  });

  test("rejects adapter output that fails the shared quality gate", async () => {
    const html = buildWechatHtml("<p>正文太短。</p>");
    const socket = { destroy() {} } as Socket;
    const context = {
      timeout: 30000,
      ensureDaemon: async () => socket,
      sendDaemonRequest: async (_sock: Socket, method: string) => {
        if (method === "navigate") return { ok: true };
        if (method === "getHTML") return { html };
        throw new Error(`unexpected method: ${method}`);
      },
      quality: { singleParagraphMinChars: 600 },
    };

    await expect(extract(ARTICLE_URL, context)).rejects.toThrow("Quality check failed");
  });

  test("rejects a WeChat page when no trustworthy title can be recovered", async () => {
    const body = "这是第一段完整正文，用于模拟标题元数据被正文污染且无法恢复标题的特殊页面。".repeat(8);
    const html = `<html><head><meta property="og:title" content="${body}"><title>${body}</title></head>
      <body><section id="js_content"><p>${body}</p><p>${body}</p></section></body></html>`;
    const socket = { destroy() {} } as Socket;
    const context = {
      timeout: 30000,
      ensureDaemon: async () => socket,
      sendDaemonRequest: async (_sock: Socket, method: string) => {
        if (method === "navigate") return { ok: true };
        if (method === "getHTML") return { html };
        throw new Error(`unexpected method: ${method}`);
      },
      quality: { singleParagraphMinChars: 600 },
    };

    await expect(extract(ARTICLE_URL, context)).rejects.toThrow("invalid or body-like title metadata");
  });
});
