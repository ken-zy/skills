import type { Socket } from "net";
import { parseHTML } from "linkedom";
import { parse } from "../parser";
import { qualityCheck } from "../quality";
import type { ParseResult, QualityOptions } from "../types";

const CONTENT_SELECTOR = "#js_content, .rich_media_content";
const CONTENT_WAIT = `${CONTENT_SELECTOR}:4500`;

const NOISE_SELECTORS = [
  "script",
  "style",
  "iframe",
  "noscript",
  "template",
  ".js_wechat_qrcode",
  ".wx_tips",
  ".rich_media_global_msg",
  ".qr_code_pc",
  ".reward_area",
];

interface AdapterContext {
  timeout: number;
  quality?: QualityOptions;
  ensureDaemon: () => Promise<Socket>;
  sendDaemonRequest: (sock: Socket, method: string, params?: any) => Promise<any>;
}

function resolveWechatImageSource(img: Element): string {
  const source = [
    "data-src",
    "data-original",
    "data-backup-src",
    "src",
  ]
    .map((attribute) => img.getAttribute(attribute)?.trim() || "")
    .find(Boolean) || "";

  if (source.startsWith("//")) return `https:${source}`;
  return source;
}

function isDiscardedImageSource(source: string): boolean {
  const normalized = source.trim().toLowerCase();
  return !normalized
    || normalized.startsWith("data:")
    || normalized.startsWith("about:")
    || normalized === "javascript:void(0)";
}

/**
 * Normalize WeChat's article DOM before the shared HTML-to-Markdown parser runs.
 * This is intentionally DOM-based: once Turndown has run, lazy-image attributes
 * and structural noise can no longer be distinguished reliably.
 */
export function prepareWechatHtml(html: string): string {
  const { document } = parseHTML(html);
  const content = document.querySelector(CONTENT_SELECTOR);
  if (!content) return html;

  for (const selector of NOISE_SELECTORS) {
    document.querySelectorAll(selector).forEach((element) => element.remove());
  }

  content.querySelectorAll("img").forEach((img) => {
    const source = resolveWechatImageSource(img);
    if (isDiscardedImageSource(source)) {
      img.remove();
      return;
    }

    img.setAttribute("src", source);
    img.removeAttribute("data-src");
    img.removeAttribute("data-original");
    img.removeAttribute("data-backup-src");
  });

  return document.documentElement?.outerHTML || html;
}

function compactWechatMarkdown(markdown: string): string {
  return markdown
    .replace(/\u00a0/g, " ")
    .replace(/^[ \t]+$/gm, "")
    .replace(/[ \t]+$/gm, "")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

export function parseWechatHtml(html: string, url: string): ParseResult {
  const preparedHtml = prepareWechatHtml(html);
  const result = parse(preparedHtml, url, undefined, CONTENT_SELECTOR);
  return {
    ...result,
    markdown: compactWechatMarkdown(result.markdown),
  };
}

export async function extract(url: string, ctx: AdapterContext): Promise<ParseResult> {
  const sock = await ctx.ensureDaemon();
  try {
    await ctx.sendDaemonRequest(sock, "navigate", { url, timeout: ctx.timeout });
    const { html } = await ctx.sendDaemonRequest(sock, "getHTML", {
      waitForSelector: CONTENT_WAIT,
    });

    const result = parseWechatHtml(html, url);
    const quality = qualityCheck(result.markdown, ctx.quality);
    if (!quality.pass) {
      throw new Error(
        `Quality check failed: ${quality.reason || "unknown reason"}`
        + ` (${quality.stats?.charCount || 0} chars, `
        + `${quality.stats?.usefulParagraphs || 0} useful paragraphs)`,
      );
    }

    return result;
  } finally {
    sock.destroy();
  }
}
