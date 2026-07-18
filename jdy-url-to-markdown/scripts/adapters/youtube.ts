import type { ParseResult } from "../types";

interface AdapterContext {
  timeout: number;
  ensureDaemon: () => Promise<import("net").Socket>;
  sendDaemonRequest: (sock: import("net").Socket, method: string, params?: any) => Promise<any>;
}

function extractVideoId(url: string): string | null {
  const parsed = new URL(url);
  if (parsed.searchParams.has("v")) return parsed.searchParams.get("v");
  if (parsed.hostname === "youtu.be") return parsed.pathname.slice(1);
  const match = parsed.pathname.match(/\/(embed|shorts|v)\/([^/?]+)/);
  return match ? match[2] : null;
}

function parseTimestamp(ts: string): number {
  const parts = ts.split(":").map(Number);
  if (parts.length === 3) return parts[0] * 3600 + parts[1] * 60 + parts[2];
  if (parts.length === 2) return parts[0] * 60 + parts[1];
  return parts[0];
}

function formatTimestamp(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  if (h > 0) return `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  return `${m}:${String(s).padStart(2, "0")}`;
}

function extractChapters(description: string): { time: number; title: string }[] {
  const chapters: { time: number; title: string }[] = [];
  const regex = /(\d{1,2}:\d{2}(?::\d{2})?)\s+(.+)/g;
  let match;
  while ((match = regex.exec(description)) !== null) {
    chapters.push({ time: parseTimestamp(match[1]), title: match[2].trim() });
  }
  return chapters;
}

function parseTranscriptXml(xml: string): { start: number; text: string }[] {
  const entries: { start: number; text: string }[] = [];
  const textRegex = /<text\s+start="([\d.]+)"[^>]*>([\s\S]*?)<\/text>/g;
  let match;
  while ((match = textRegex.exec(xml)) !== null) {
    entries.push({
      start: parseFloat(match[1]),
      text: match[2].replace(/<[^>]+>/g, "").replace(/&amp;/g, "&").replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&#39;/g, "'").replace(/&quot;/g, '"').trim(),
    });
  }
  if (entries.length > 0) return entries;
  const pRegex = /<p\s+t="(\d+)"[^>]*>([\s\S]*?)<\/p>/g;
  while ((match = pRegex.exec(xml)) !== null) {
    entries.push({ start: parseInt(match[1]) / 1000, text: match[2].replace(/<[^>]+>/g, "").trim() });
  }
  return entries;
}

export async function extract(url: string, ctx: AdapterContext): Promise<ParseResult> {
  const videoId = extractVideoId(url);
  if (!videoId) throw new Error(`Cannot extract video ID from URL: ${url}`);

  const sock = await ctx.ensureDaemon();
  try {
    await ctx.sendDaemonRequest(sock, "navigate", { url: `https://www.youtube.com/watch?v=${videoId}`, timeout: ctx.timeout });

    const pageData = await ctx.sendDaemonRequest(sock, "evaluate", {
      expression: `JSON.stringify({
        title: document.querySelector('meta[property="og:title"]')?.content || document.title,
        channel: document.querySelector('link[itemprop="name"]')?.content || document.querySelector('#channel-name a')?.textContent?.trim() || '',
        published: document.querySelector('meta[itemprop="datePublished"]')?.content || '',
        description: document.querySelector('meta[property="og:description"]')?.content || '',
        apiKey: window.ytcfg?.data_?.INNERTUBE_API_KEY || '',
      })`,
    });
    const meta = JSON.parse(pageData);

    let transcript: { start: number; text: string }[] = [];
    if (meta.apiKey) {
      try {
        const playerResp = await fetch(`https://www.youtube.com/youtubei/v1/player?key=${meta.apiKey}`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ videoId, context: { client: { clientName: "ANDROID", clientVersion: "17.31.35", hl: "en" } } }),
        });
        const playerData = await playerResp.json();
        const captionTracks = playerData?.captions?.playerCaptionsTracklistRenderer?.captionTracks;
        if (captionTracks?.length > 0) {
          const transcriptResp = await fetch(captionTracks[0].baseUrl);
          transcript = parseTranscriptXml(await transcriptResp.text());
        }
      } catch (e) { console.error(`[youtube] InnerTube API failed: ${(e as Error).message}`); }
    }

    if (transcript.length === 0) {
      try {
        const iprData = await ctx.sendDaemonRequest(sock, "evaluate", {
          expression: `(() => { const scripts = document.querySelectorAll('script'); for (const s of scripts) { const m = s.textContent?.match(/ytInitialPlayerResponse\\s*=\\s*({.+?});/); if (m) return m[1]; } return null; })()`,
        });
        if (iprData) {
          const ipr = JSON.parse(iprData);
          const tracks = ipr?.captions?.playerCaptionsTracklistRenderer?.captionTracks;
          if (tracks?.length > 0) {
            const resp = await fetch(tracks[0].baseUrl);
            transcript = parseTranscriptXml(await resp.text());
          }
        }
      } catch { console.error("[youtube] ytInitialPlayerResponse fallback also failed"); }
    }

    const fullDescription = await ctx.sendDaemonRequest(sock, "evaluate", {
      expression: `document.querySelector('#description-inner, ytd-text-inline-expander .content')?.textContent || ''`,
    });
    const chapters = extractChapters(fullDescription || "");

    const lines: string[] = [];
    lines.push(`# ${meta.title}`, "", `**Channel:** ${meta.channel}`);
    if (meta.published) lines.push(`**Published:** ${meta.published}`);
    lines.push(`**URL:** https://www.youtube.com/watch?v=${videoId}`, "");

    if (chapters.length > 0) {
      lines.push("## Chapters", "");
      for (const ch of chapters) lines.push(`- [${formatTimestamp(ch.time)}] ${ch.title}`);
      lines.push("");
    }

    if (transcript.length > 0) {
      lines.push("## Transcript", "");
      let currentChapter = 0;
      for (const entry of transcript) {
        if (chapters.length > 0 && currentChapter < chapters.length - 1 && entry.start >= chapters[currentChapter + 1].time) {
          currentChapter++;
          lines.push("", `### ${chapters[currentChapter].title}`, "");
        }
        lines.push(`[${formatTimestamp(entry.start)}] ${entry.text}`);
      }
    } else {
      lines.push("_No transcript available for this video._");
    }

    return {
      markdown: lines.join("\n"),
      metadata: {
        url: `https://www.youtube.com/watch?v=${videoId}`,
        title: meta.title,
        author: meta.channel,
        published: meta.published || undefined,
        site_name: "YouTube",
        description: meta.description || undefined,
      },
    };
  } finally {
    sock.destroy();
  }
}
