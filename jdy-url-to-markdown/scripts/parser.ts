import { parseHTML } from "linkedom";
import { Readability } from "@mozilla/readability";
import TurndownService from "turndown";
import { gfm } from "turndown-plugin-gfm";
import type { Metadata, ParseResult, Cleaner } from "./types";

function createTurndown(): TurndownService {
  const td = new TurndownService({
    headingStyle: "atx",
    codeBlockStyle: "fenced",
    bulletListMarker: "-",
    emDelimiter: "_",
  });
  td.use(gfm);
  td.remove(["script", "style", "iframe", "noscript", "template", "svg", "path"]);

  td.addRule("dropInvisibleAnchors", {
    filter(node) {
      if (node.nodeName !== "A") return false;
      const text = (node.textContent || "").trim();
      if (text) return false;
      const hasMedia = node.querySelector("img, video, audio, picture");
      return !hasMedia;
    },
    replacement() {
      return "";
    },
  });

  td.addRule("collapseFigure", {
    filter: "figure",
    replacement(_content, node) {
      const img = node.querySelector("img");
      const caption = node.querySelector("figcaption");
      if (!img) return _content;
      const alt = caption?.textContent?.trim() || img.getAttribute("alt") || "";
      const src = img.getAttribute("src") || "";
      return `\n\n![${alt}](${src})\n\n`;
    },
  });

  return td;
}

function extractMetadata(doc: any, url: string): Metadata {
  const get = (sel: string, attr: string) => doc.querySelector(sel)?.getAttribute(attr)?.trim();
  const getMeta = (name: string) => get(`meta[property="${name}"]`, "content") || get(`meta[name="${name}"]`, "content");

  let jsonLd: any = null;
  const ldScript = doc.querySelector('script[type="application/ld+json"]');
  if (ldScript?.textContent) {
    try { jsonLd = JSON.parse(ldScript.textContent); } catch {}
  }

  const title = getMeta("og:title") || jsonLd?.headline || doc.querySelector("title")?.textContent?.trim() || "Untitled";
  const author = getMeta("article:author") || (typeof jsonLd?.author === "string" ? jsonLd.author : jsonLd?.author?.name) || getMeta("author") || undefined;
  const published = getMeta("article:published_time") || jsonLd?.datePublished || getMeta("date") || undefined;
  const site_name = getMeta("og:site_name") || undefined;
  const description = getMeta("og:description") || getMeta("description") || undefined;

  return { url, title, author, published, site_name, description };
}

export function parse(html: string, url: string, cleaners?: Cleaner[]): ParseResult {
  const { document } = parseHTML(html);
  const metadata = extractMetadata(document, url);

  const { document: readDoc } = parseHTML(html);
  const reader = new Readability(readDoc as any, {
    charThreshold: 120,
    nbTopCandidates: 10,
  });
  const article = reader.parse();

  const td = createTurndown();
  let markdown: string;
  if (article?.content) {
    markdown = td.turndown(article.content);
    // Readability sometimes strips the <h1> title; prepend it if missing
    const titleText = article.title?.trim() || metadata.title;
    if (titleText && !markdown.includes(titleText)) {
      markdown = `# ${titleText}\n\n${markdown}`;
    }
  } else {
    markdown = td.turndown(html);
  }

  if (cleaners) {
    for (const cleaner of cleaners) {
      markdown = cleaner(markdown);
    }
  }

  return { markdown, metadata };
}
