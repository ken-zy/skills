import type { QualityResult } from "./types";

const ANTI_SCRAPING_MARKERS = [
  /access denied/i,
  /403 forbidden/i,
  /请完成验证/,
  /captcha/i,
  /just a moment/i,
  /checking your browser/i,
];

const LOGIN_WALL_MARKERS = [
  /请登录.{0,6}(?:查看|访问|继续|阅读)/,
  /sign in to continue/i,
  /log in to (?:view|access|continue|read|see)/i,
  /Become a .* Member to (?:read|access|view|continue)/i,
  /Subscribe to (?:read|access|view|continue|unlock)/i,
];

function stripMarkdownMarkers(text: string): string {
  return text
    .replace(/^#{1,6}\s+/gm, "")
    .replace(/\*\*|__/g, "")
    .replace(/\*|_/g, "")
    .replace(/!\[.*?\]\(.*?\)/g, "")
    .replace(/\[([^\]]*)\]\(.*?\)/g, "$1")
    .replace(/`[^`]*`/g, "")
    .replace(/^[-*+]\s+/gm, "")
    .replace(/^\d+\.\s+/gm, "")
    .trim();
}

function countChineseChars(text: string): number {
  const matches = text.match(/[\u4e00-\u9fff]/g);
  return matches ? matches.length : 0;
}

function isUsefulParagraph(line: string): boolean {
  const trimmed = line.trim();
  if (!trimmed) return false;
  if (/^#{1,6}\s+/.test(trimmed)) return false;
  if (/^!\[.*?\]\(.*?\)\s*$/.test(trimmed)) return false;
  const withoutLinks = trimmed.replace(/\[([^\]]*)\]\([^)]*\)/g, "").trim();
  const linkCount = (trimmed.match(/\[([^\]]*)\]\([^)]*\)/g) || []).length;
  if (linkCount >= 3 && withoutLinks.length < 20) return false;
  const chineseCount = countChineseChars(trimmed);
  if (chineseCount >= 15) return true;
  const words = trimmed.split(/\s+/).filter(w => w.length > 0);
  return words.length >= 8;
}

export function qualityCheck(markdown: string): QualityResult {
  const plainText = stripMarkdownMarkers(markdown);
  const charCount = plainText.length;

  if (charCount < 120) {
    return { pass: false, reason: `content too short: ${charCount} chars (min 120)`, stats: { charCount, usefulParagraphs: 0 } };
  }

  for (const marker of ANTI_SCRAPING_MARKERS) {
    if (marker.test(markdown)) {
      return { pass: false, reason: `anti-scraping marker detected: ${marker.source}`, stats: { charCount, usefulParagraphs: 0 } };
    }
  }

  for (const marker of LOGIN_WALL_MARKERS) {
    if (marker.test(markdown)) {
      return { pass: false, reason: `login wall marker detected: ${marker.source}`, stats: { charCount, usefulParagraphs: 0 } };
    }
  }

  const lines = markdown.split(/\n\n+/);
  const usefulParagraphs = lines.filter(isUsefulParagraph).length;

  if (usefulParagraphs < 2) {
    return { pass: false, reason: `insufficient useful paragraphs: ${usefulParagraphs} (min 2)`, stats: { charCount, usefulParagraphs } };
  }

  return { pass: true, stats: { charCount, usefulParagraphs } };
}
