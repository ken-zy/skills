import { existsSync, mkdirSync, writeFileSync } from "fs";
import { dirname, join } from "path";
import type { Metadata } from "./types";

export function generateSlug(title: string): string {
  let slug = title
    .toLowerCase()
    .replace(/[^a-z0-9\u4e00-\u9fff\s-]/g, "")
    .replace(/\s+/g, "-")
    .replace(/-{2,}/g, "-")
    .replace(/^-+|-+$/g, "");

  if (!slug) return "untitled";
  if (slug.length > 50) slug = slug.slice(0, 50).replace(/-+$/, "");
  return slug || "untitled";
}

function yamlString(value: string): string {
  const cleaned = value.replace(/\n/g, " ");
  const escaped = cleaned.replace(/"/g, '\\"');
  return `"${escaped}"`;
}

export function buildFrontMatter(metadata: Metadata, fetchLevel: number): string {
  const now = new Date().toISOString();
  const lines: string[] = ["---"];

  lines.push(`url: ${yamlString(metadata.url)}`);
  lines.push(`title: ${yamlString(metadata.title)}`);
  if (metadata.author) lines.push(`author: ${yamlString(metadata.author)}`);
  if (metadata.published) lines.push(`published: ${yamlString(metadata.published)}`);
  if (metadata.site_name) lines.push(`site_name: ${yamlString(metadata.site_name)}`);
  if (metadata.description) lines.push(`description: ${yamlString(metadata.description)}`);
  lines.push(`captured_at: ${yamlString(now)}`);
  lines.push(`fetch_level: ${fetchLevel}`);

  lines.push("---");
  return lines.join("\n") + "\n";
}

export function buildOutputPath(title: string, baseDir: string, date: Date = new Date()): string {
  const dateStr = [
    date.getUTCFullYear(),
    String(date.getUTCMonth() + 1).padStart(2, "0"),
    String(date.getUTCDate()).padStart(2, "0"),
  ].join("");

  const slug = generateSlug(title);
  return join(baseDir, dateStr, `${slug}.md`);
}

export function resolveConflict(filePath: string): string {
  if (!existsSync(filePath)) return filePath;
  const now = new Date();
  const suffix = [
    String(now.getHours()).padStart(2, "0"),
    String(now.getMinutes()).padStart(2, "0"),
    String(now.getSeconds()).padStart(2, "0"),
  ].join("");
  const base = filePath.replace(/\.md$/, "");
  return `${base}-${suffix}.md`;
}

export function writeMarkdown(
  filePath: string,
  metadata: Metadata,
  markdown: string,
  fetchLevel: number,
): string {
  const resolvedPath = resolveConflict(filePath);
  const dir = dirname(resolvedPath);
  mkdirSync(dir, { recursive: true });

  const frontMatter = buildFrontMatter(metadata, fetchLevel);
  writeFileSync(resolvedPath, frontMatter + "\n" + markdown, "utf-8");
  return resolvedPath;
}
