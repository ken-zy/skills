import fs from "node:fs";
import { createHash } from "node:crypto";
import { DraftSession, DraftReadbackError, defaultReceiptPath, readOriginalMetadata, validateSourceUrl, assertSupportedMedia, type DraftArticle } from "./wechat-draft.ts";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { loadWechatExtendConfig, resolveAccount, loadCredentials } from "./wechat-extend-config.ts";
import {
  type WechatUploadAsset,
  prepareWechatBodyImageUpload,
  needsWechatBodyImageProcessing,
  detectImageFormatFromBuffer,
} from "./wechat-image-processor.ts";

import { createWechatApiClient, loadWechatNetworkConfig, verifyWechatEgress, type WechatApiClient } from "./wechat-network.ts";

const defaultWechatClient = createWechatApiClient();

interface AccessTokenResponse {
  access_token?: string;
  errcode?: number;
  errmsg?: string;
}

interface UploadResponse {
  media_id: string;
  url: string;
  errcode?: number;
  errmsg?: string;
}

interface PublishResponse {
  media_id?: string;
  errcode?: number;
  errmsg?: string;
}

interface ImageInfo {
  placeholder: string;
  localPath: string;
  originalPath: string;
}

interface MarkdownRenderResult {
  title: string;
  author: string;
  summary: string;
  htmlPath: string;
  contentImages: ImageInfo[];
}

type ArticleType = "news" | "newspic";

interface ArticleOptions {
  title: string;
  author?: string;
  digest?: string;
  content: string;
  thumbMediaId: string;
  articleType: ArticleType;
  imageMediaIds?: string[];
  needOpenComment?: number;
  onlyFansCanComment?: number;
  sourceUrl?: string;
}

const TOKEN_URL = "https://api.weixin.qq.com/cgi-bin/token";
const UPLOAD_BODY_IMG_URL = "https://api.weixin.qq.com/cgi-bin/media/uploadimg";
const UPLOAD_MATERIAL_URL = "https://api.weixin.qq.com/cgi-bin/material/add_material";
const DRAFT_URL = "https://api.weixin.qq.com/cgi-bin/draft/add";

export async function fetchAccessToken(appId: string, appSecret: string, client: WechatApiClient = defaultWechatClient): Promise<string> {
  const url = `${TOKEN_URL}?grant_type=client_credential&appid=${encodeURIComponent(appId)}&secret=${encodeURIComponent(appSecret)}`;
  const data = await client.json<AccessTokenResponse>("token", url);
  if (typeof data.access_token !== "string" || !data.access_token.trim()) throw new Error("WeChat token: missing access_token");
  return data.access_token;
}

function toHttpsUrl(url: string | undefined): string {
  if (!url) return "";
  return url.startsWith("http://") ? url.replace(/^http:\/\//i, "https://") : url;
}

async function loadUploadAsset(
  imagePath: string,
  baseDir?: string,
): Promise<WechatUploadAsset> {
  let fileBuffer: Buffer;
  let filename: string;
  let contentType: string;
  let fileSize = 0;
  let fileExt = "";

  if (/^https?:\/\//i.test(imagePath)) {
    const response = await fetch(imagePath);
    if (!response.ok) {
      throw new Error(`Failed to download image: ${imagePath}`);
    }
    const buffer = await response.arrayBuffer();
    if (buffer.byteLength === 0) {
      throw new Error(`Remote image is empty: ${imagePath}`);
    }
    fileBuffer = Buffer.from(buffer);
    fileSize = buffer.byteLength;
    const urlPath = imagePath.split("?")[0];
    filename = path.basename(urlPath) || "image.jpg";
    fileExt = path.extname(filename).toLowerCase();
    contentType = response.headers.get("content-type") || "image/jpeg";
  } else {
    const resolvedPath = path.isAbsolute(imagePath)
      ? imagePath
      : path.resolve(baseDir || process.cwd(), imagePath);

    if (!fs.existsSync(resolvedPath)) {
      throw new Error(`Image not found: ${resolvedPath}`);
    }
    const stats = fs.statSync(resolvedPath);
    if (stats.size === 0) {
      throw new Error(`Local image is empty: ${resolvedPath}`);
    }
    fileSize = stats.size;
    fileBuffer = fs.readFileSync(resolvedPath);
    filename = path.basename(resolvedPath);
    fileExt = path.extname(filename).toLowerCase();
    const mimeTypes: Record<string, string> = {
      ".jpg": "image/jpeg",
      ".jpeg": "image/jpeg",
      ".png": "image/png",
      ".gif": "image/gif",
      ".webp": "image/webp",
      ".bmp": "image/bmp",
      ".tiff": "image/tiff",
      ".tif": "image/tiff",
      ".svg": "image/svg+xml",
      ".ico": "image/x-icon",
    };
    contentType = mimeTypes[fileExt] || "image/jpeg";
  }

  // Detect actual format from magic bytes to fix extension/content-type mismatches
  // (e.g. CDNs serving WebP for URLs with .png extension)
  const detected = detectImageFormatFromBuffer(fileBuffer);
  if (detected && (detected.contentType !== contentType || ![detected.fileExt, detected.fileExt === ".jpg" ? ".jpeg" : detected.fileExt].includes(fileExt))) {
    console.error(`[wechat-api] Format mismatch: ${filename} declared as ${contentType}, actual ${detected.contentType}`);
    contentType = detected.contentType;
    fileExt = detected.fileExt;
    filename = `${path.basename(filename, path.extname(filename))}${detected.fileExt}`;
  }

  return {
    buffer: fileBuffer,
    filename,
    contentType,
    fileExt,
    fileSize,
  };
}

export async function uploadImage(
  imagePath: string,
  accessToken: string,
  baseDir?: string,
  uploadType: "body" | "material" = "body",
  client: WechatApiClient = defaultWechatClient,
  session?: DraftSession,
): Promise<UploadResponse> {
  const asset = await loadUploadAsset(imagePath, baseDir);
  const cacheKey = createHash("sha256").update(uploadType + ":image-v1:").update(asset.buffer).digest("hex");
  const cached = session?.cachedUpload(cacheKey);
  if (cached) return cached;
  let uploadAsset = asset;

  // Both body (media/uploadimg) and material (material/add_material) endpoints reject
  // WeChat-unsupported formats (WebP/GIF/BMP/SVG/...) and oversize images. Run the same
  // prep step for both. See spec §7.3.
  if (
    (uploadType === "body" || uploadType === "material") &&
    needsWechatBodyImageProcessing(asset)
  ) {
    const prepared = await prepareWechatBodyImageUpload(asset);
    uploadAsset = {
      ...asset,
      buffer: prepared.buffer,
      filename: prepared.filename,
      contentType: prepared.contentType,
      fileExt: path.extname(prepared.filename).toLowerCase(),
      fileSize: prepared.buffer.length,
    };
    const note = prepared.processingNotes.join(", ");
    console.error(`[wechat-api] Processed ${asset.filename} for ${uploadType} upload: ${note}`);
  }

  const result = await uploadToWechat(
    uploadAsset.buffer,
    uploadAsset.filename,
    uploadAsset.contentType,
    accessToken,
    uploadType,
    client,
  );

  if (uploadType === "body" ? !result.url : !result.media_id) throw new Error("Image upload response is incomplete");
  result.url = toHttpsUrl(result.url);
  session?.recordUpload(cacheKey, { url: result.url || "", media_id: result.media_id || "" });
  // media/uploadimg 接口只返回 URL，material/add_material 返回 media_id
  if (uploadType === "body") {
    return {
      url: toHttpsUrl(result.url),
      media_id: "",
    } as UploadResponse;
  } else {
    result.url = toHttpsUrl(result.url);
    return result;
  }
}

// 实际的微信上传函数
async function uploadToWechat(
  fileBuffer: Buffer,
  filename: string,
  contentType: string,
  accessToken: string,
  uploadType: "body" | "material",
  client: WechatApiClient,
): Promise<UploadResponse> {
  const boundary = `----WebKitFormBoundary${Date.now().toString(16)}`;
  const header = [
    `--${boundary}`,
    `Content-Disposition: form-data; name="media"; filename="${filename}"`,
    `Content-Type: ${contentType}`,
    "",
    "",
  ].join("\r\n");
  const footer = `\r\n--${boundary}--\r\n`;

  const headerBuffer = Buffer.from(header, "utf-8");
  const footerBuffer = Buffer.from(footer, "utf-8");
  const body = Buffer.concat([headerBuffer, fileBuffer, footerBuffer]);

  const uploadUrl = uploadType === "body" ? UPLOAD_BODY_IMG_URL : UPLOAD_MATERIAL_URL;
  const url = `${uploadUrl}?type=image&access_token=${accessToken}`;
  const data = await client.json<UploadResponse>(uploadType === "body" ? "uploadimg" : "material", url, {
    method: "POST",
    headers: {
      "Content-Type": `multipart/form-data; boundary=${boundary}`,
    },
    body,
  });

  return data;
}

async function uploadImagesInHtml(
  html: string,
  accessToken: string,
  baseDir: string,
  contentImages: ImageInfo[] = [],
  articleType: ArticleType = "news",
  collectNewsCoverFallback: boolean = false,
  client: WechatApiClient = defaultWechatClient,
  session?: DraftSession,
): Promise<{ html: string; firstCoverMediaId: string; imageMediaIds: string[] }> {
  const imgRegex = /<img[^>]*\ssrc=["']([^"']+)["'][^>]*>/gi;
  const matches = [...html.matchAll(imgRegex)];

  if (matches.length === 0 && contentImages.length === 0) {
    return { html, firstCoverMediaId: "", imageMediaIds: [] };
  }

  let firstCoverMediaId = "";
  let updatedHtml = html;
  const imageMediaIds: string[] = [];
  const uploadedBySource = new Map<string, UploadResponse>();

  for (const match of matches) {
    const [fullTag, src] = match;
    if (!src) continue;

    if (src.startsWith("https://mmbiz.qpic.cn")) {
      if (collectNewsCoverFallback && !firstCoverMediaId) {
        try {
          const coverResp = await uploadImage(src, accessToken, baseDir, "material", client, session);
          firstCoverMediaId = coverResp.media_id;
        } catch (err) {
          console.error(`[wechat-api] Failed to reuse existing WeChat image as cover: ${src}`, err);
        }
      }
      continue;
    }

    const localPathMatch = fullTag.match(/data-local-path=["']([^"']+)["']/);
    const imagePath = localPathMatch ? localPathMatch[1]! : src;

    console.error(`[wechat-api] Uploading body image: ${imagePath}`);
    try {
      let resp = uploadedBySource.get(imagePath);
      if (!resp) {
        // 正文图片使用 media/uploadimg 接口获取 URL
        resp = await uploadImage(imagePath, accessToken, baseDir, "body", client, session);
        uploadedBySource.set(imagePath, resp);
      }
      const newTag = fullTag
        .replace(/\ssrc=["'][^"']+["']/, ` src="${resp.url}"`)
        .replace(/\sdata-local-path=["'][^"']+["']/, "");
      updatedHtml = updatedHtml.replace(fullTag, newTag);
      const shouldUploadMaterial = articleType === "newspic" || (collectNewsCoverFallback && !firstCoverMediaId);
      if (shouldUploadMaterial) {
        let materialResp = uploadedBySource.get(`${imagePath}:material`);
        if (!materialResp) {
          materialResp = await uploadImage(imagePath, accessToken, baseDir, "material", client, session);
          uploadedBySource.set(`${imagePath}:material`, materialResp);
        }
        if (articleType === "newspic" && materialResp.media_id) {
          imageMediaIds.push(materialResp.media_id);
        }
        if (collectNewsCoverFallback && !firstCoverMediaId && materialResp.media_id) {
          firstCoverMediaId = materialResp.media_id;
        }
      }
    } catch (err) {
      // 正文图片上传失败必须中止：否则草稿正文会残留 data-local-path 或旧 src，造成 silent data corruption
      throw new Error(`Failed to upload body image ${imagePath}: ${err instanceof Error ? err.message : String(err)}`);
    }
  }

  for (const image of contentImages) {
    if (!updatedHtml.includes(image.placeholder)) continue;

    const imagePath = image.localPath || image.originalPath;
    console.error(`[wechat-api] Uploading body image: ${imagePath}`);

    try {
      let resp = uploadedBySource.get(imagePath);
      if (!resp) {
        // 正文图片使用 media/uploadimg 接口获取 URL
        resp = await uploadImage(imagePath, accessToken, baseDir, "body", client, session);
        uploadedBySource.set(imagePath, resp);
      }

      const replacementTag = `<img src="${resp.url}" style="display: block; width: 100%; margin: 1.5em auto;">`;
      updatedHtml = replaceAllPlaceholders(updatedHtml, image.placeholder, replacementTag);
      const shouldUploadMaterial = articleType === "newspic" || (collectNewsCoverFallback && !firstCoverMediaId);
      if (shouldUploadMaterial) {
        let materialResp = uploadedBySource.get(`${imagePath}:material`);
        if (!materialResp) {
          materialResp = await uploadImage(imagePath, accessToken, baseDir, "material", client, session);
          uploadedBySource.set(`${imagePath}:material`, materialResp);
        }
        if (articleType === "newspic" && materialResp.media_id) {
          imageMediaIds.push(materialResp.media_id);
        }
        if (collectNewsCoverFallback && !firstCoverMediaId && materialResp.media_id) {
          firstCoverMediaId = materialResp.media_id;
        }
      }
    } catch (err) {
      // 占位符未替换会让 WECHATIMGPH_X 字符串残留进微信草稿，必须中止
      throw new Error(`Failed to upload body image ${imagePath} (placeholder ${image.placeholder}): ${err instanceof Error ? err.message : String(err)}`);
    }
  }

  return { html: updatedHtml, firstCoverMediaId, imageMediaIds };
}

export async function publishToDraft(
  options: ArticleOptions,
  accessToken: string,
  client: WechatApiClient = defaultWechatClient,
): Promise<PublishResponse> {
  assertSupportedMedia(options.content);
  if (options.sourceUrl !== undefined) validateSourceUrl(options.sourceUrl);
  const url = `${DRAFT_URL}?access_token=${accessToken}`;

  let article: Record<string, unknown>;

  const noc = options.needOpenComment ?? 1;
  const ofcc = options.onlyFansCanComment ?? 0;

  if (options.articleType === "newspic") {
    if (!options.imageMediaIds || options.imageMediaIds.length === 0) {
      throw new Error("newspic requires at least one image");
    }
    article = {
      article_type: "newspic",
      title: options.title,
      content: options.content,
      need_open_comment: noc,
      only_fans_can_comment: ofcc,
      image_info: {
        image_list: options.imageMediaIds.map(id => ({ image_media_id: id })),
      },
    };
    if (options.author) article.author = options.author;
  } else {
    article = {
      article_type: "news",
      title: options.title,
      content: options.content,
      thumb_media_id: options.thumbMediaId,
      need_open_comment: noc,
      only_fans_can_comment: ofcc,
    };
    if (options.author) article.author = options.author;
    if (options.digest) article.digest = options.digest;
  }

  if (options.sourceUrl !== undefined) article.content_source_url = options.sourceUrl;
  const data = await client.json<PublishResponse>("draft", url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ articles: [article] }),
  });

  if (typeof data.media_id !== "string" || !data.media_id.trim()) {
    throw new Error("WeChat draft: missing media_id; draft creation not confirmed");
  }

  return data;
}

function parseFrontmatter(content: string): { frontmatter: Record<string, string>; body: string } {
  const match = content.match(/^\s*---\r?\n([\s\S]*?)\r?\n---\r?\n?([\s\S]*)$/);
  if (!match) return { frontmatter: {}, body: content };

  const frontmatter: Record<string, string> = {};
  const lines = match[1]!.split("\n");
  for (const line of lines) {
    const colonIdx = line.indexOf(":");
    if (colonIdx > 0) {
      const key = line.slice(0, colonIdx).trim();
      let value = line.slice(colonIdx + 1).trim();
      if ((value.startsWith('"') && value.endsWith('"')) ||
          (value.startsWith("'") && value.endsWith("'"))) {
        value = value.slice(1, -1);
      }
      frontmatter[key] = value;
    }
  }

  return { frontmatter, body: match[2]! };
}

function renderMarkdownWithPlaceholders(
  markdownPath: string,
  theme: string = "default",
  color?: string,
  citeStatus: boolean = true,
  title?: string,
): MarkdownRenderResult {
  const __filename = fileURLToPath(import.meta.url);
  const __dirname = path.dirname(__filename);
  const mdToWechatScript = path.join(__dirname, "md-to-wechat.ts");
  const baseDir = path.dirname(markdownPath);

  const args = [mdToWechatScript, markdownPath];
  if (title) args.push("--title", title);
  if (theme) args.push("--theme", theme);
  if (color) args.push("--color", color);
  if (!citeStatus) args.push("--no-cite");

  console.error(`[wechat-api] Rendering markdown with placeholders via md-to-wechat: ${theme}${color ? `, color: ${color}` : ""}, citeStatus: ${citeStatus}`);
  // 用当前 runtime（bun）直接 re-spawn，避免 npx -y 联网拉 npm 包
  const result = spawnSync(process.execPath, args, {
    stdio: ["inherit", "pipe", "pipe"],
    cwd: baseDir,
  });

  if (result.status !== 0) {
    const stderr = result.stderr?.toString() || "";
    throw new Error(`Markdown placeholder render failed: ${stderr}`);
  }

  const stdout = result.stdout?.toString() || "";
  return JSON.parse(stdout) as MarkdownRenderResult;
}

function replaceAllPlaceholders(html: string, placeholder: string, replacement: string): string {
  const escapedPlaceholder = placeholder.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  return html.replace(new RegExp(escapedPlaceholder + "(?!\\d)", "g"), replacement);
}

function extractHtmlContent(htmlPath: string): string {
  const html = fs.readFileSync(htmlPath, "utf-8");
  const match = html.match(/<div id="output">([\s\S]*?)<\/div>\s*<\/body>/);
  if (match) {
    return match[1]!.trim();
  }
  const bodyMatch = html.match(/<body[^>]*>([\s\S]*?)<\/body>/i);
  return bodyMatch ? bodyMatch[1]!.trim() : html;
}

function printUsage(): never {
  console.log(`Publish article to WeChat Official Account draft using API

Usage:
  bun wechat-api.ts <file> [options]

Arguments:
  file                Markdown (.md) or HTML (.html) file

Options:
  --type <type>       Article type: news (文章, default) or newspic (图文)
  --title <title>     Override title
  --author <name>     Author name (max 16 chars)
  --summary <text>    Article summary/digest (max 128 chars)
  --theme <name>      Theme name for markdown (default, grace, simple, modern). Default: default
  --color <name|hex>  Primary color (blue, green, vermilion, etc. or hex)
  --cover <path>      Cover image path (local or URL)
  --account <alias>   Select account by alias (for multi-account setups)
  --no-cite           Disable bottom citations for ordinary external links in markdown mode
  --source-url <url>  Read-original URL (or <!-- 公众号阅读原文: URL --> in source)
  --clear-source-url  Explicitly clear the read-original URL
  --update-media-id <id>  Adopt/update an existing single-article draft
  --accept-remote     After reconciling local text, adopt current remote metadata
  --state-file <path> Stable private receipt; repeat runs update the same draft
  --cover-media-id <id> Verified original permanent cover ID (preserves crop)
  --verify-only       Read existing draft and verify receipt; no rendering/uploads/remote writes
  --inspect-only      Read draft differences and save a private inspection; receipt unchanged
  --reconcile-receipt Accept an explicitly reviewed readback snapshot, no remote writes
  --readback-sha256 <hash> Exact snapshot from --inspect-only
  --review-note <text> Review explanation required for --reconcile-receipt
  --record-published  Record the user's publication confirmation locally; no credentials/network
  --expected-media-id <id> Exact receipt ID required for --record-published
  --expected-title <title> Exact receipt title required for --record-published
  --confirmation-note <text> User's confirmation, required for --record-published
  --publication-url <url> Optional official published article URL
  --dry-run           Parse and render only, don't publish
  --help              Show this help

Frontmatter Fields (markdown):
  title               Article title
  author              Author name
  digest/summary      Article summary
  coverImage/featureImage/cover/image   Cover image path

Comments:
  Comments are enabled by default, open to all users.

Environment Variables:
  WECHAT_APP_ID       WeChat App ID
  WECHAT_APP_SECRET   WeChat App Secret

Config File Locations (in priority order):
  1. Environment variables
  2. <cwd>/.jdy_writer/.env
  3. ~/.jdy_writer/.env

Example:
  bun wechat-api.ts article.md
  bun wechat-api.ts article.md --theme grace --cover cover.png
  bun wechat-api.ts article.md --author "Author Name" --summary "Brief intro"
  bun wechat-api.ts article.html --title "My Article"
  bun wechat-api.ts images/ --type newspic --title "Photo Album"
  bun wechat-api.ts article.md --dry-run
  bun wechat-api.ts article.md --no-cite
`);
  process.exit(0);
}

interface CliArgs {
  filePath: string;
  isHtml: boolean;
  articleType: ArticleType;
  title?: string;
  author?: string;
  summary?: string;
  theme: string;
  color?: string;
  cover?: string;
  account?: string;
  citeStatus: boolean;
  dryRun: boolean;
  verifyOnly?: boolean;
  inspectOnly?: boolean;
  reconcileReceipt?: boolean;
  recordPublished?: boolean;
  readbackSha256?: string;
  reviewNote?: string;
  expectedMediaId?: string;
  expectedTitle?: string;
  confirmationNote?: string;
  publicationUrl?: string;
  sourceUrl?: string;
  updateMediaId?: string;
  stateFile?: string;
  coverMediaId?: string;
  acceptRemote?: boolean;
}

function parseArgs(argv: string[]): CliArgs {
  if (argv.length === 0 || argv.includes("--help") || argv.includes("-h")) {
    printUsage();
  }

  const args: CliArgs = {
    filePath: "",
    isHtml: false,
    articleType: "news",
    theme: "default",
    citeStatus: true,
    dryRun: false,
  };

  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i]!;
    const valueKeys = {
      "--title": "title", "--author": "author", "--summary": "summary", "--theme": "theme", "--color": "color",
      "--cover": "cover", "--account": "account", "--source-url": "sourceUrl", "--update-media-id": "updateMediaId",
      "--state-file": "stateFile", "--cover-media-id": "coverMediaId", "--readback-sha256": "readbackSha256",
      "--review-note": "reviewNote", "--expected-media-id": "expectedMediaId", "--expected-title": "expectedTitle",
      "--confirmation-note": "confirmationNote", "--publication-url": "publicationUrl",
    } as const;
    if (arg === "--type" || Object.hasOwn(valueKeys, arg)) {
      const value = argv[++i];
      if (!value || value.startsWith("--")) throw new Error(`Missing value for ${arg}`);
      if (arg === "--type") {
        const type = value.toLowerCase();
        if (type !== "news" && type !== "newspic") throw new Error("Article type must be news or newspic");
        args.articleType = type;
      } else args[valueKeys[arg as keyof typeof valueKeys]] = value;
    } else if (arg === "--cite") {
      args.citeStatus = true;
    } else if (arg === "--no-cite") {
      args.citeStatus = false;
    } else if (arg === "--accept-remote") {
      args.acceptRemote = true;
    } else if (arg === "--clear-source-url") {
      args.sourceUrl = "";
    } else if (arg === "--verify-only") {
      args.verifyOnly = true;
    } else if (arg === "--inspect-only") {
      args.inspectOnly = true;
    } else if (arg === "--reconcile-receipt") {
      args.reconcileReceipt = true;
    } else if (arg === "--record-published") {
      args.recordPublished = true;
    } else if (arg === "--dry-run") {
      args.dryRun = true;
    } else if (arg.startsWith("-")) {
      throw new Error("Unknown option; use --help to check supported arguments");
    } else {
      if (args.filePath) throw new Error("Only one source file may be specified");
      args.filePath = arg;
    }
  }

  if (!args.filePath) {
    console.error("Error: File path required");
    process.exit(1);
  }

  args.isHtml = args.filePath.toLowerCase().endsWith(".html");

  return args;
}

function extractHtmlTitle(html: string): string {
  const titleMatch = html.match(/<title>([^<]+)<\/title>/i);
  if (titleMatch) return titleMatch[1]!;
  const h1Match = html.match(/<h1[^>]*>([^<]+)<\/h1>/i);
  if (h1Match) return h1Match[1]!.replace(/<[^>]+>/g, "").trim();
  return "";
}

async function main(): Promise<void> {
  const args = parseArgs(process.argv.slice(2));

  const filePath = path.resolve(args.filePath);
  const recoveryModes = [args.verifyOnly, args.inspectOnly, args.reconcileReceipt, args.recordPublished].filter(Boolean).length;
  if (recoveryModes > 1) throw new Error("Choose only one receipt recovery mode");
  if (recoveryModes) {
    const allowed = new Set(["--state-file", ...(args.recordPublished ? ["--record-published", "--expected-media-id", "--expected-title", "--confirmation-note", "--publication-url"] : ["--account", "--update-media-id", "--verify-only", "--inspect-only", ...(args.reconcileReceipt ? ["--reconcile-receipt", "--readback-sha256", "--review-note"] : [])])]);
    for (const flag of process.argv.slice(2).filter(v => v.startsWith("--"))) if (!allowed.has(flag)) throw new Error("Receipt recovery cannot be combined with draft edits or unrelated options");
    if (args.reconcileReceipt && (!/^[a-f0-9]{64}$/.test(args.readbackSha256 || "") || !args.reviewNote?.trim())) throw new Error("Reconciliation requires --readback-sha256 and --review-note");
  } else if ([args.readbackSha256, args.reviewNote, args.expectedMediaId, args.expectedTitle, args.confirmationNote, args.publicationUrl].some(v => v !== undefined)) throw new Error("Receipt recovery options require a recovery mode");
  if (args.recordPublished) {
    if (!args.stateFile || !args.expectedMediaId || !args.expectedTitle || !args.confirmationNote) throw new Error("--record-published requires --state-file, --expected-media-id, --expected-title and --confirmation-note");
    const result = DraftSession.recordPublished(path.resolve(args.stateFile), filePath, args.expectedMediaId, args.expectedTitle, args.confirmationNote, args.publicationUrl);
    console.log(JSON.stringify({ success: true, ...result }, null, 2));
    return;
  }
  if (!recoveryModes && !fs.existsSync(filePath)) {
    console.error(`Error: File not found: ${filePath}`);
    process.exit(1);
  }

  if (recoveryModes) {
    const resolved = resolveAccount(loadWechatExtendConfig(), args.account);
    const network = loadWechatNetworkConfig();
    if (network) await verifyWechatEgress(network);
    const client = createWechatApiClient(network);
    const creds = loadCredentials(resolved);
    const key = createHash("sha256").update(creds.appId).digest("hex");
    const stateFile = args.stateFile ? path.resolve(args.stateFile) : defaultReceiptPath(filePath, key);
    if (!fs.existsSync(stateFile)) throw new Error("Receipt recovery requires an existing receipt");
    const session = DraftSession.open(stateFile, filePath, key);
    try {
      const token = await fetchAccessToken(creds.appId, creds.appSecret, client);
      const result = args.inspectOnly ? await session.inspectOnly(token, client, args.updateMediaId) : args.reconcileReceipt ? await session.reconcileOnly(token, client, args.readbackSha256!, args.reviewNote!, args.updateMediaId) : await session.verifyOnly(token, client, args.updateMediaId);
      console.log(JSON.stringify({ success: true, ...result, stateFile }, null, 2));
    } finally { session.close(); }
    return;
  }
  const baseDir = path.dirname(filePath);
  let sourceText = fs.readFileSync(filePath, "utf8");
  let title = args.title || "";
  let author = args.author || "";
  let digest = args.summary || "";
  let htmlPath: string;
  let htmlContent: string;
  let frontmatter: Record<string, string> = {};
  let contentImages: ImageInfo[] = [];

  if (args.isHtml) {
    htmlPath = filePath;
    htmlContent = extractHtmlContent(htmlPath);
    const mdPath = filePath.replace(/\.html$/i, ".md");
    if (fs.existsSync(mdPath)) {
      const mdContent = fs.readFileSync(mdPath, "utf-8");
      sourceText = mdContent;
      const parsed = parseFrontmatter(mdContent);
      frontmatter = parsed.frontmatter;
      if (!title && frontmatter.title) title = frontmatter.title;
      if (!author) author = frontmatter.author || "";
      if (!digest) digest = frontmatter.digest || frontmatter.summary || frontmatter.description || "";
    }
    if (!title) {
      title = extractHtmlTitle(fs.readFileSync(htmlPath, "utf-8"));
    }
    console.error(`[wechat-api] Using HTML file: ${htmlPath}`);
  } else {
    const content = fs.readFileSync(filePath, "utf-8");
    const parsed = parseFrontmatter(content);
    frontmatter = parsed.frontmatter;
    const body = parsed.body;

    title = title || frontmatter.title || "";
    if (!title) {
      const h1Match = body.match(/^#\s+(.+)$/m);
      if (h1Match) title = h1Match[1]!;
    }
    if (!author) author = frontmatter.author || "";
    if (!digest) digest = frontmatter.digest || frontmatter.summary || frontmatter.description || "";

    console.error(`[wechat-api] Theme: ${args.theme}${args.color ? `, color: ${args.color}` : ""}, citeStatus: ${args.citeStatus}`);
    const rendered = renderMarkdownWithPlaceholders(filePath, args.theme, args.color, args.citeStatus, args.title);
    htmlPath = rendered.htmlPath;
    contentImages = rendered.contentImages;
    if (!title) title = rendered.title;
    if (!author) author = rendered.author;
    if (!digest) digest = rendered.summary;
    console.error(`[wechat-api] HTML generated: ${htmlPath}`);
    console.error(`[wechat-api] Placeholder images: ${contentImages.length}`);
    htmlContent = extractHtmlContent(htmlPath);
  }

  if (!title) {
    console.error("Error: No title found. Provide via --title, frontmatter, or <title> tag.");
    process.exit(1);
  }

  if (digest && digest.length > 120) {
    const truncated = digest.slice(0, 117);
    const lastPunct = Math.max(truncated.lastIndexOf("。"), truncated.lastIndexOf("，"), truncated.lastIndexOf("；"), truncated.lastIndexOf("、"));
    digest = lastPunct > 80 ? truncated.slice(0, lastPunct + 1) : truncated + "...";
    console.error(`[wechat-api] Digest truncated to ${digest.length} chars`);
  }

  console.error(`[wechat-api] Title: ${title}`);
  if (author) console.error(`[wechat-api] Author: ${author}`);
  if (digest) console.error(`[wechat-api] Digest: ${digest.slice(0, 50)}...`);
  console.error(`[wechat-api] Type: ${args.articleType}`);

  const sourceUrl = args.sourceUrl !== undefined ? validateSourceUrl(args.sourceUrl) : readOriginalMetadata(sourceText);
  htmlContent = htmlContent.replace(/<!--\s*公众号阅读原文\s*[:：][\s\S]*?-->/g, "");
  assertSupportedMedia(htmlContent);
  if (args.cover && args.coverMediaId) throw new Error("Choose --cover or --cover-media-id");
  const extConfig = loadWechatExtendConfig();
  const resolved = resolveAccount(extConfig, args.account);
  if (resolved.name) console.error(`[wechat-api] Account: ${resolved.name} (${resolved.alias})`);

  if (!author && resolved.default_author) author = resolved.default_author;

  if (args.dryRun) {
    console.log(JSON.stringify({
      articleType: args.articleType,
      sourceUrl,
      operation: args.updateMediaId ? "update" : "create-or-update-from-receipt",
      title,
      author: author || undefined,
      digest: digest || undefined,
      htmlPath,
      contentLength: htmlContent.length,
      placeholderImageCount: contentImages.length || undefined,
      account: resolved.alias || undefined,
    }, null, 2));
    return;
  }

  const network = loadWechatNetworkConfig();
  if (network) {
    const ip = await verifyWechatEgress(network);
    console.error(`[wechat-api] Fixed egress verified: ${ip}`);
  }
  const wechatClient = createWechatApiClient(network);

  const creds = loadCredentials(resolved);
  for (const skippedSource of creds.skippedSources) {
    console.error(`[wechat-api] Skipped incomplete credential source: ${skippedSource}`);
  }
  console.error(`[wechat-api] Credentials source: ${creds.source}`);
  const accountKey = createHash("sha256").update(creds.appId).digest("hex");
  const stateFile = args.stateFile ? path.resolve(args.stateFile) : defaultReceiptPath(filePath, accountKey);
  const session = DraftSession.open(stateFile, filePath, accountKey);
  try {
    console.error("[wechat-api] Fetching access token...");
    const accessToken = await fetchAccessToken(creds.appId, creds.appSecret, wechatClient);

    const current = await session.prepare(accessToken, wechatClient, args.updateMediaId, args.acceptRemote);
    const rawCoverPath = args.cover || (!current && !args.coverMediaId ?
      frontmatter.coverImage ||
      frontmatter.featureImage ||
      frontmatter.cover ||
      frontmatter.image : undefined);
    const coverPath = rawCoverPath && !/^https?:\/\//i.test(rawCoverPath) && !path.isAbsolute(rawCoverPath) && args.cover
      ? path.resolve(process.cwd(), rawCoverPath)
      : rawCoverPath;
    const needNewsCoverFallback = args.articleType === "news" && !coverPath && !current && !args.coverMediaId;

    console.error("[wechat-api] Uploading body images...");
    const { html: processedHtml, firstCoverMediaId, imageMediaIds } = await uploadImagesInHtml(
      htmlContent,
      accessToken,
      baseDir,
      contentImages,
      args.articleType,
      needNewsCoverFallback,
      wechatClient,
      session,
    );
    htmlContent = processedHtml;

    const existingCoverId = current ? session.recoverCover(current) : "";
    let thumbMediaId = args.coverMediaId || existingCoverId;

    if (coverPath) {
      console.error(`[wechat-api] Uploading cover: ${coverPath}`);
      // 封面图片使用 material/add_material 接口
      const coverResp = await uploadImage(coverPath, accessToken, baseDir, "material", wechatClient, session);
      thumbMediaId = coverResp.media_id;
      console.error(`[wechat-api] Cover uploaded successfully, media_id: ${thumbMediaId}`);
    } else if (firstCoverMediaId && args.articleType === "news") {
      // news 类型没有封面时，使用第一张正文图的 media_id 作为封面（兜底逻辑）
      thumbMediaId = firstCoverMediaId;
      console.error(`[wechat-api] Using first body image as cover (fallback), media_id: ${thumbMediaId}`);
    }

    if (args.articleType === "news" && !thumbMediaId) {
      console.error("Error: No cover image. Provide via --cover, frontmatter.coverImage, or include an image in content.");
      throw new Error("Permanent article cover missing; supply --cover-media-id or --cover");
    }

    if (args.articleType === "newspic" && imageMediaIds.length === 0) {
      throw new Error("newspic requires at least one image in content");
    }

    const article: DraftArticle = current ? { ...current, content: htmlContent } : {
      article_type: args.articleType, title, ...(author ? { author } : {}), ...(digest ? { digest } : {}), content: htmlContent,
      need_open_comment: resolved.need_open_comment ?? 1, only_fans_can_comment: resolved.only_fans_can_comment ?? 0,
    };
    if (current) {
      if (args.title !== undefined) article.title = args.title;
      if (args.author !== undefined) article.author = args.author;
      if (args.summary !== undefined) article.digest = digest;
      if (args.articleType !== (current.article_type || "news")) throw new Error("Draft article type cannot change during update");
    }
    if (sourceUrl !== undefined) article.content_source_url = sourceUrl;
    if (args.articleType === "news") article.thumb_media_id = thumbMediaId;
    if (args.articleType === "newspic") article.image_info = { image_list: imageMediaIds.map(id => ({ image_media_id: id })) };
    if (coverPath && current && existingCoverId !== thumbMediaId) delete article.cover_info; // A new image needs new cropping, not the old image's crop.
    console.error("[wechat-api] Saving draft (no public publication)...");
    const result = await session.save(article, accessToken, wechatClient);
    console.log(JSON.stringify({ success: true, ...result, title: article.title, articleType: args.articleType, stateFile }, null, 2));
    console.error(`[wechat-api] Draft verified (${result.operation}); publication not attempted`);
  } finally { session.close(); }

}

// Run main() only when this file is executed directly as a CLI, not when imported as a module
// (e.g. by tests). Bun and Node expose import.meta.main / import.meta.url for this check.
const isDirectRun =
  // @ts-expect-error — Bun exposes import.meta.main
  (typeof import.meta.main === "boolean" && import.meta.main) ||
  (typeof process !== "undefined" &&
    process.argv[1] &&
    fileURLToPath(import.meta.url) === fs.realpathSync(process.argv[1]));

if (isDirectRun) {
  await main().catch((err) => {
    console.error(`Error: ${err instanceof Error ? err.message : String(err)}`);
    if (err instanceof DraftReadbackError) console.error(JSON.stringify({ readbackDifference: err.report, next: "Use --inspect-only; no automatic retry or snapshot adoption" }, null, 2));
    process.exit(1);
  });
}
