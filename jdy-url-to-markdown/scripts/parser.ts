import { parseHTML } from "linkedom";
import { Readability } from "@mozilla/readability";
import TurndownService from "turndown";
import { gfm } from "turndown-plugin-gfm";
import type { Metadata, ParseResult, Cleaner } from "./types";

interface ParsedTableRow {
  cells: string[];
  nextIndex: number;
}

interface NormalizedTable {
  lines: string[];
  nextIndex: number;
}

function countUnescapedPipes(line: string): number {
  let count = 0;
  for (let index = 0; index < line.length; index++) {
    if (line[index] !== "|") continue;
    let backslashes = 0;
    for (let cursor = index - 1; cursor >= 0 && line[cursor] === "\\"; cursor--) {
      backslashes += 1;
    }
    if (backslashes % 2 === 0) count += 1;
  }
  return count;
}

function splitUnescapedPipes(line: string): string[] {
  const parts = [""];
  for (let index = 0; index < line.length; index++) {
    const character = line[index];
    if (character !== "|") {
      parts[parts.length - 1] += character;
      continue;
    }

    let backslashes = 0;
    for (let cursor = index - 1; cursor >= 0 && line[cursor] === "\\"; cursor--) {
      backslashes += 1;
    }
    if (backslashes % 2 === 1) {
      parts[parts.length - 1] += character;
    } else {
      parts.push("");
    }
  }
  return parts;
}

function separatorColumnCount(line: string): number | undefined {
  const stripped = line.trim();
  if (!/^\|(?:\s*:?-{3,}:?\s*\|)+$/.test(stripped)) return undefined;
  return countUnescapedPipes(stripped) - 1;
}

function parseTableRow(
  lines: string[],
  startIndex: number,
  columnCount: number,
): ParsedTableRow | undefined {
  const cells: string[] = [];
  let current: string[] = [];
  let index = startIndex;
  let firstLine = true;

  while (index < lines.length) {
    let stripped = lines[index].trim();
    if (firstLine) {
      if (!stripped.startsWith("|")) return undefined;
      stripped = stripped.replace(/^\|\s*/, "");
      firstLine = false;
    }

    if (stripped) {
      const parts = splitUnescapedPipes(stripped);
      for (let partIndex = 0; partIndex < parts.length; partIndex++) {
        const text = parts[partIndex].trim();
        if (text) current.push(text);
        if (partIndex === parts.length - 1) continue;

        cells.push(current.join(" ").trim());
        current = [];
        if (cells.length === columnCount) {
          const remainder = parts.slice(partIndex + 1).join("").trim();
          if (remainder) return undefined;
          return { cells, nextIndex: index + 1 };
        }
      }
    }
    index += 1;
  }

  return undefined;
}

function renderTableRow(cells: string[]): string {
  return `| ${cells.join(" | ")} |`;
}

function normalizeTableAt(lines: string[], startIndex: number): NormalizedTable | undefined {
  const searchLimit = Math.min(startIndex + 200, lines.length);
  let separatorIndex: number | undefined;
  let columnCount: number | undefined;
  let header: ParsedTableRow | undefined;

  for (let candidate = startIndex; candidate < searchLimit; candidate++) {
    const candidateColumns = separatorColumnCount(lines[candidate]);
    if (candidateColumns === undefined) continue;
    const candidateHeader = parseTableRow(lines, startIndex, candidateColumns);
    if (!candidateHeader) continue;
    const between = lines.slice(candidateHeader.nextIndex, candidate);
    if (!between.every((line) => !line.trim())) continue;
    separatorIndex = candidate;
    columnCount = candidateColumns;
    header = candidateHeader;
    break;
  }

  if (separatorIndex === undefined || columnCount === undefined || !header) return undefined;

  const normalized = [
    renderTableRow(header.cells),
    lines[separatorIndex].trim(),
  ];
  let index = separatorIndex + 1;

  while (index < lines.length) {
    let nextContent = index;
    while (nextContent < lines.length && !lines[nextContent].trim()) nextContent += 1;
    if (nextContent >= lines.length) return { lines: normalized, nextIndex: index };

    const nextLine = lines[nextContent].trim();
    if (!nextLine.startsWith("|") || separatorColumnCount(nextLine) !== undefined) {
      return { lines: normalized, nextIndex: index };
    }

    const row = parseTableRow(lines, nextContent, columnCount);
    if (!row) return undefined;
    normalized.push(renderTableRow(row.cells));
    index = row.nextIndex;
  }

  return { lines: normalized, nextIndex: index };
}

export function normalizeMarkdownTables(markdown: string): string {
  const lines = markdown.split("\n");
  const output: string[] = [];
  let index = 0;

  while (index < lines.length) {
    const candidate = lines[index].trim();
    if (candidate.startsWith("|") && separatorColumnCount(candidate) === undefined) {
      const table = normalizeTableAt(lines, index);
      if (table) {
        output.push(...table.lines);
        index = table.nextIndex;
        continue;
      }
    }
    output.push(lines[index]);
    index += 1;
  }

  return output.join("\n");
}

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

function expandTableColspans(document: any): void {
  document.querySelectorAll("table tr").forEach((row: Element) => {
    const cells = [...row.children] as Element[];
    for (const cell of cells) {
      const colspan = Number.parseInt(cell.getAttribute("colspan") || "1", 10);
      if (!Number.isFinite(colspan) || colspan <= 1) continue;
      cell.removeAttribute("colspan");

      let anchor = cell;
      for (let index = 1; index < colspan; index++) {
        const filler = document.createElement(cell.tagName.toLowerCase());
        row.insertBefore(filler, anchor.nextSibling);
        anchor = filler;
      }
    }
  });
}

const MAX_METADATA_TITLE_LENGTH = 180;

function normalizeMetadataTitle(value: unknown): string | undefined {
  if (typeof value !== "string") return undefined;
  const title = value.replace(/\u00a0/g, " ").trim();
  if (
    !title
    || title.length > MAX_METADATA_TITLE_LENGTH
    || /[\r\n]/.test(title)
    || /\\[rn]/.test(title)
  ) {
    return undefined;
  }
  return title.replace(/[ \t]+/g, " ");
}

function usableMetadataTitle(title: string): string | undefined {
  return title === "Untitled" ? undefined : normalizeMetadataTitle(title);
}

function extractMetadata(doc: any, url: string): Metadata {
  const get = (sel: string, attr: string) => doc.querySelector(sel)?.getAttribute(attr)?.trim();
  const getMeta = (name: string) => get(`meta[property="${name}"]`, "content") || get(`meta[name="${name}"]`, "content");

  let jsonLd: any = null;
  const ldScript = doc.querySelector('script[type="application/ld+json"]');
  if (ldScript?.textContent) {
    try { jsonLd = JSON.parse(ldScript.textContent); } catch {}
  }

  const title = [
    getMeta("og:title"),
    jsonLd?.headline,
    doc.querySelector("title")?.textContent,
  ].map(normalizeMetadataTitle).find(Boolean) || "Untitled";
  const author = getMeta("article:author") || (typeof jsonLd?.author === "string" ? jsonLd.author : jsonLd?.author?.name) || getMeta("author") || undefined;
  const published = getMeta("article:published_time") || jsonLd?.datePublished || getMeta("date") || undefined;
  const site_name = getMeta("og:site_name") || undefined;
  const description = getMeta("og:description") || getMeta("description") || undefined;

  return { url, title, author, published, site_name, description };
}

export function parse(
  html: string,
  url: string,
  cleaners?: Cleaner[],
  contentSelector?: string,
): ParseResult {
  const { document } = parseHTML(html);
  const metadata = extractMetadata(document, url);

  const { document: readDoc } = parseHTML(html);
  expandTableColspans(readDoc);
  const td = createTurndown();
  let markdown: string;

  const selectedContent = contentSelector
    ? readDoc.querySelector(contentSelector)
    : null;

  if (selectedContent?.textContent?.trim()) {
    markdown = td.turndown(selectedContent.innerHTML);
    const titleText = usableMetadataTitle(metadata.title);
    if (titleText && !markdown.includes(titleText)) {
      markdown = `# ${titleText}\n\n${markdown}`;
    }
  } else {
    const reader = new Readability(readDoc as any, {
      charThreshold: 120,
      nbTopCandidates: 10,
    });
    const article = reader.parse();

    if (article?.content) {
      markdown = td.turndown(article.content);
      // Readability sometimes strips the <h1> title; prepend it if missing
      const titleText = normalizeMetadataTitle(article.title)
        || usableMetadataTitle(metadata.title);
      if (titleText && !markdown.includes(titleText)) {
        markdown = `# ${titleText}\n\n${markdown}`;
      }
    } else {
      markdown = td.turndown(html);
    }
  }

  if (cleaners) {
    for (const cleaner of cleaners) {
      markdown = cleaner(markdown);
    }
  }

  markdown = normalizeMarkdownTables(markdown);

  return { markdown, metadata };
}
