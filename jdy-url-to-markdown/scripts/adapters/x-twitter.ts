import { existsSync, readFileSync, writeFileSync, unlinkSync, chmodSync } from "fs";
import { resolve } from "path";
import { homedir } from "os";
import type { ParseResult } from "../types";

const CACHE_DIR = resolve(homedir(), ".cache", "jdy-url-to-markdown");
const COOKIE_FILE = resolve(CACHE_DIR, "x-session-cookies.json");

interface AdapterContext {
  timeout: number;
  ensureDaemon: () => Promise<import("net").Socket>;
  sendDaemonRequest: (sock: import("net").Socket, method: string, params?: any) => Promise<any>;
}

function extractTweetId(url: string): string | null {
  const match = url.match(/(?:twitter\.com|x\.com)\/\w+\/status\/(\d+)/);
  return match ? match[1] : null;
}

function loadCookies(): any[] | null {
  if (!existsSync(COOKIE_FILE)) return null;
  try { return JSON.parse(readFileSync(COOKIE_FILE, "utf-8")).cookies || null; } catch { return null; }
}

function saveCookies(cookies: any[]): void {
  console.error(`[x-twitter] Saving X session cookies to ${COOKIE_FILE}`);
  writeFileSync(COOKIE_FILE, JSON.stringify({ cookies, savedAt: new Date().toISOString() }), { mode: 0o600 });
  try { chmodSync(COOKIE_FILE, 0o600); } catch {}
}

function deleteCookies(): void {
  try { unlinkSync(COOKIE_FILE); } catch {}
}

function extractTweetData(graphqlPayload: any): { tweets: any[]; author: any } {
  const tweets: any[] = [];
  const seenIds = new Set<string>();
  let author: any = null;

  function walk(obj: any, isQuoted = false): void {
    if (!obj || typeof obj !== "object") return;
    if (obj.__typename === "Tweet" || obj.legacy?.full_text) {
      const legacy = obj.legacy || obj;
      const tweetId = legacy.id_str || obj.rest_id || "";

      // Skip quoted tweets from the main list — they're rendered inline as blockquotes
      if (isQuoted || (tweetId && seenIds.has(tweetId))) return;
      if (tweetId) seenIds.add(tweetId);

      const user = obj.core?.user_results?.result?.legacy || {};
      if (!author) author = user;
      tweets.push({
        id: tweetId,
        author: user,
        text: legacy.full_text || "",
        created_at: legacy.created_at || "",
        favorite_count: legacy.favorite_count || 0,
        retweet_count: legacy.retweet_count || 0,
        media: (legacy.entities?.media || []).map((m: any) => m.media_url_https || m.url),
        quoted: obj.quoted_status_result?.result,
      });

      // Walk children but skip quoted_status_result (handled via quoted property)
      for (const [key, val] of Object.entries(obj)) {
        if (key === "quoted_status_result") continue;
        if (typeof val === "object") walk(val, false);
      }
      return;
    }
    for (const [key, val] of Object.entries(obj)) {
      if (typeof val === "object") {
        walk(val, key === "quoted_status_result");
      }
    }
  }

  walk(graphqlPayload);
  return { tweets, author };
}

export async function extract(url: string, ctx: AdapterContext): Promise<ParseResult> {
  const tweetId = extractTweetId(url);
  if (!tweetId) throw new Error(`Cannot extract tweet ID from URL: ${url}`);

  const sock = await ctx.ensureDaemon();
  try {
    const savedCookies = loadCookies();
    if (savedCookies) {
      await ctx.sendDaemonRequest(sock, "navigate", { url: "about:blank", timeout: ctx.timeout });
      await ctx.sendDaemonRequest(sock, "setCookies", { cookies: savedCookies });
    }

    // enableNetwork before navigate: daemon persists the flag and re-enables on new sessions
    await ctx.sendDaemonRequest(sock, "enableNetwork");
    await ctx.sendDaemonRequest(sock, "navigate", { url, timeout: ctx.timeout });

    const loginCheck = await ctx.sendDaemonRequest(sock, "evaluate", {
      expression: `!!document.querySelector('[data-testid="loginButton"], [href="/login"]')`,
    });

    if (loginCheck && !savedCookies) {
      if (!process.stdin.isTTY) {
        throw new Error("X login required but running in non-interactive mode. Run manually with a TTY to authenticate.");
      }
      console.error("[x-twitter] Login required. Please log in to X in the Chrome window, then press Enter.");
      await new Promise<void>((resolve) => { process.stdin.once("data", () => resolve()); });
      await ctx.sendDaemonRequest(sock, "navigate", { url, timeout: ctx.timeout });
      const { cookies } = await ctx.sendDaemonRequest(sock, "getCookies", { domain: "x.com" });
      const authCookies = cookies.filter((c: any) => ["auth_token", "ct0"].includes(c.name));
      if (authCookies.length >= 2) saveCookies(cookies);
    } else if (loginCheck && savedCookies) {
      console.error("[x-twitter] Saved cookies expired, clearing...");
      deleteCookies();
      throw new Error("X session cookies expired. Please re-run to log in again.");
    }

    await new Promise(r => setTimeout(r, 3000));

    const { responses } = await ctx.sendDaemonRequest(sock, "getNetworkResponses", {
      urlPattern: "graphql.*/TweetDetail|TweetResultByRestId",
    });

    if (responses.length === 0) {
      throw new Error("No GraphQL responses captured. The tweet may require authentication.");
    }

    const { body: bodyStr } = await ctx.sendDaemonRequest(sock, "getResponseBody", {
      requestId: responses[responses.length - 1].requestId,
    });
    const payload = JSON.parse(bodyStr);
    const { tweets, author } = extractTweetData(payload);

    if (tweets.length === 0) {
      throw new Error("No tweet data found in GraphQL response.");
    }

    // Anchor: move the target tweet (matching URL's tweetId) to position 0
    const targetIdx = tweets.findIndex((t: any) => t.id === tweetId);
    if (targetIdx === -1) {
      console.error(`[x-twitter] Warning: target tweet ${tweetId} not found in payload, using first available`);
    } else if (targetIdx > 0) {
      const [target] = tweets.splice(targetIdx, 1);
      tweets.unshift(target);
    }

    // Prefer target tweet's author over first-found author
    const resolvedAuthor = tweets[0].author || author;
    const authorName = resolvedAuthor?.name || "Unknown";
    const authorHandle = resolvedAuthor?.screen_name || "unknown";
    const lines: string[] = [];
    lines.push(`# @${authorHandle} (${authorName})`, "");

    for (let i = 0; i < tweets.length; i++) {
      const tweet = tweets[i];
      if (tweets.length > 1) { lines.push(`**[${i + 1}/${tweets.length}]**`, ""); }
      lines.push(tweet.text, "");
      if (tweet.media.length > 0) {
        for (const mediaUrl of tweet.media) lines.push(`![](${mediaUrl})`);
        lines.push("");
      }
      if (tweet.quoted) {
        const qLegacy = tweet.quoted.legacy || tweet.quoted;
        const qUser = tweet.quoted.core?.user_results?.result?.legacy || {};
        lines.push(`> **@${qUser.screen_name || "unknown"}:** ${qLegacy.full_text || ""}`, "");
      }
    }

    const mainTweet = tweets[0];
    lines.push("---");
    lines.push(`Likes: ${mainTweet.favorite_count} | Retweets: ${mainTweet.retweet_count}`);
    lines.push(`Date: ${mainTweet.created_at}`);

    return {
      markdown: lines.join("\n"),
      metadata: {
        url,
        title: `@${authorHandle}: ${tweets[0].text.slice(0, 80)}${tweets[0].text.length > 80 ? "..." : ""}`,
        author: `${authorName} (@${authorHandle})`,
        site_name: "X (Twitter)",
      },
    };
  } finally {
    sock.destroy();
  }
}
