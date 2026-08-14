import {
  existsSync,
  mkdirSync,
  readFileSync,
  readdirSync,
  renameSync,
  statSync,
  unlinkSync,
  writeFileSync,
} from "fs";
import { basename, dirname, join } from "path";
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

function canonicalSourceUrl(value: string): string {
  try {
    const parsed = new URL(value);
    parsed.hash = "";
    parsed.searchParams.sort();
    return parsed.toString();
  } catch {
    return value.split("#", 1)[0];
  }
}

function frontMatterUrl(filePath: string): string | undefined {
  try {
    const content = readFileSync(filePath, "utf-8");
    const match = content.match(/^url:\s*("(?:\\.|[^"])*")\s*$/m);
    if (!match) return undefined;
    return JSON.parse(match[1]);
  } catch {
    return undefined;
  }
}

function findExistingByUrl(filePath: string, sourceUrl: string): string | undefined {
  const dir = dirname(filePath);
  if (!existsSync(dir)) return undefined;
  const canonical = canonicalSourceUrl(sourceUrl);

  for (const name of readdirSync(dir).filter((entry) => entry.endsWith(".md")).sort()) {
    const candidate = join(dir, name);
    const candidateUrl = frontMatterUrl(candidate);
    if (candidateUrl && canonicalSourceUrl(candidateUrl) === canonical) return candidate;
  }
  return undefined;
}

function atomicWrite(filePath: string, content: string): void {
  const dir = dirname(filePath);
  const mode = existsSync(filePath) ? statSync(filePath).mode & 0o777 : 0o644;
  const tempPath = join(
    dir,
    `.${basename(filePath)}.${process.pid}.${Date.now()}.${Math.random().toString(16).slice(2)}.tmp`,
  );
  try {
    writeFileSync(tempPath, content, { encoding: "utf-8", mode });
    renameSync(tempPath, filePath);
  } catch (error) {
    try { unlinkSync(tempPath); } catch {}
    throw error;
  }
}

export function writeMarkdown(
  filePath: string,
  metadata: Metadata,
  markdown: string,
  fetchLevel: number,
): string {
  const dir = dirname(filePath);
  mkdirSync(dir, { recursive: true });
  const resolvedPath = findExistingByUrl(filePath, metadata.url)
    ?? resolveConflict(filePath);

  const frontMatter = buildFrontMatter(metadata, fetchLevel);
  atomicWrite(resolvedPath, frontMatter + "\n" + markdown);
  return resolvedPath;
}
