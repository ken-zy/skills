import { createHash } from "crypto";
import { resolve } from "path";

export interface R2ScriptOptions {
  scriptPath: string;
  cwd?: string;
  extension?: "webp" | "mp4";
}

function canonicalSourceUrl(sourceUrl: string): string {
  const parsed = new URL(sourceUrl);
  parsed.hash = "";
  parsed.searchParams.sort();
  return parsed.toString();
}

function asciiSlug(value: string): string {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 48)
    .replace(/-+$/g, "");
}

export function buildR2ArticleKeyPrefix(sourceUrl: string): string {
  const canonicalUrl = canonicalSourceUrl(sourceUrl);
  const digest = createHash("sha256").update(canonicalUrl).digest("hex").slice(0, 12);
  const parsed = new URL(canonicalUrl);
  const host = parsed.hostname.toLowerCase().replace(/^www\./, "") || "unknown-host";
  const rawPathLeaf = parsed.pathname.split("/").filter(Boolean).at(-1) ?? "";
  let decodedPathLeaf = rawPathLeaf;
  try {
    decodedPathLeaf = decodeURIComponent(rawPathLeaf);
  } catch {}
  const pathSlug = asciiSlug(decodedPathLeaf);
  const articleId = pathSlug ? `${pathSlug}-${digest}` : digest;
  return `web-articles/${host}/${articleId}`;
}

function parseUploadUrl(stdout: string, key: string, extension = "webp"): string {
  const lines = stdout.split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
  if (lines.length !== 1) {
    throw new Error("r2-upload.sh must output exactly one URL");
  }

  let parsed: URL;
  try {
    parsed = new URL(lines[0]);
  } catch {
    throw new Error("r2-upload.sh returned an invalid URL");
  }
  if (parsed.protocol !== "https:" || parsed.pathname !== `/${key}.${extension}` || parsed.search || parsed.hash || parsed.username || parsed.password) {
    throw new Error(`r2-upload.sh returned an unexpected object URL for ${key}`);
  }
  return parsed.toString();
}

export async function uploadWithR2Script(
  filePath: string,
  key: string,
  options: R2ScriptOptions,
): Promise<string> {
  const cwd = options.cwd ?? process.cwd();
  const scriptPath = resolve(cwd, options.scriptPath);
  const child = Bun.spawn(["bash", scriptPath, filePath, key], {
    cwd,
    stdout: "pipe",
    stderr: "pipe",
  });
  const [exitCode, stdout, stderr] = await Promise.all([
    child.exited,
    new Response(child.stdout).text(),
    new Response(child.stderr).text(),
  ]);
  if (exitCode !== 0) {
    throw new Error(`r2-upload.sh failed with exit ${exitCode}: ${stderr.trim() || "unknown error"}`);
  }
  return parseUploadUrl(stdout, key, options.extension);
}
