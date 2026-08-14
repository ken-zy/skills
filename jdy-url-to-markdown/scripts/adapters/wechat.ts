import type { Socket } from "net";
import { parseHTML } from "linkedom";
import { parse } from "../parser";
import { qualityCheck } from "../quality";
import type { ParseResult, QualityOptions } from "../types";

const CONTENT_SELECTOR = "#js_content, .rich_media_content";
const CONTENT_WAIT = `${CONTENT_SELECTOR}:4500`;
const MAX_WECHAT_TITLE_LENGTH = 180;

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
  ".wx_bottom_modal_group",
  ".rich_media_meta_list_combine",
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

function compactWechatTitle(value: string): string {
  return value
    .replace(/\u00a0/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function trustworthyWechatTitle(value: string | null | undefined): string | undefined {
  if (!value) return undefined;
  const title = compactWechatTitle(value);
  if (!title || title.length > MAX_WECHAT_TITLE_LENGTH) return undefined;
  return title;
}

function recoverWechatTitle(document: any, content: Element): string | undefined {
  const platformTitle = [
    document.querySelector("#activity-name")?.textContent,
    document.querySelector(".rich_media_title")?.textContent,
  ].map(trustworthyWechatTitle).find(Boolean);
  if (platformTitle) return platformTitle;

  const metadataCandidates = [
    document.querySelector('meta[property="og:title"]')?.getAttribute("content"),
    document.querySelector('meta[name="og:title"]')?.getAttribute("content"),
    document.querySelector("title")?.textContent,
  ].filter((value): value is string => typeof value === "string" && value.trim().length > 0);

  for (const value of metadataCandidates) {
    const hasDelimiter = /[\r\n]|\\[rn]/.test(value);
    if (!hasDelimiter) {
      const title = trustworthyWechatTitle(value);
      if (title) return title;
    }
    if (!hasDelimiter) continue;
    const firstSegment = value
      .replace(/\\r\\n|\\n|\\r/g, "\n")
      .split(/[\r\n]+/)
      .map((segment) => segment.trim())
      .find(Boolean);
    const title = trustworthyWechatTitle(firstSegment);
    if (title) return title;
  }

  const firstHeading = content.querySelector("h1, h2")?.textContent;
  return trustworthyWechatTitle(firstHeading);
}

function normalizeWechatTitleMetadata(document: any, content: Element): void {
  const title = recoverWechatTitle(document, content);
  if (!title) return;

  let ogTitle = document.querySelector('meta[property="og:title"]');
  if (!ogTitle) {
    ogTitle = document.createElement("meta");
    ogTitle.setAttribute("property", "og:title");
    document.head?.appendChild(ogTitle);
  }
  ogTitle.setAttribute("content", title);
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

  normalizeWechatTitleMetadata(document, content);

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

function ensureWechatTitleHeading(markdown: string, title: string): string {
  if (!title || title === "Untitled") return markdown;
  const lines = markdown.split("\n");
  const firstContentLine = lines.findIndex((line) => line.trim().length > 0);
  if (firstContentLine < 0) return markdown;

  const firstLine = lines[firstContentLine].trim();
  if (firstLine === title) lines[firstContentLine] = `# ${title}`;
  return lines.join("\n");
}

export function parseWechatHtml(html: string, url: string): ParseResult {
  const preparedHtml = prepareWechatHtml(html);
  const result = parse(preparedHtml, url, undefined, CONTENT_SELECTOR);
  const compacted = compactWechatMarkdown(result.markdown);
  return {
    ...result,
    markdown: ensureWechatTitleHeading(compacted, result.metadata.title),
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
    if (result.metadata.title === "Untitled") {
      throw new Error("Quality check failed: invalid or body-like title metadata");
    }
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
