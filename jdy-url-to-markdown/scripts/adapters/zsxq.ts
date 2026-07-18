import type { ParseResult } from "../types";

interface AdapterContext {
  timeout: number;
  ensureDaemon: () => Promise<import("net").Socket>;
  sendDaemonRequest: (sock: import("net").Socket, method: string, params?: any) => Promise<any>;
}

type ZsxqUrl =
  | { type: "topic"; groupId: string; topicId: string }
  | { type: "article"; slug: string }
  | { type: "shortlink"; code: string };

export function parseZsxqUrl(url: string): ZsxqUrl | null {
  const parsed = new URL(url);
  const host = parsed.hostname.replace(/^www\./, "");

  if (host === "wx.zsxq.com") {
    const match = parsed.pathname.match(/^\/group\/(\d+)\/topic\/(\d+)/);
    if (match) return { type: "topic", groupId: match[1], topicId: match[2] };
    return null;
  }

  if (host === "articles.zsxq.com") {
    const match = parsed.pathname.match(/^\/id_([^.]+)\.html/);
    if (match) return { type: "article", slug: match[1] };
    return null;
  }

  if (host === "t.zsxq.com") {
    const code = parsed.pathname.slice(1);
    if (code) return { type: "shortlink", code };
    return null;
  }

  return null;
}

export function cleanZsxqMarkup(text: string): string {
  return text
    .replace(/<e type="text_bold" title="([^"]*)"[^/]*\/>/g, (_, t) => `**${decodeURIComponent(t)}**`)
    .replace(/<e type="hashtag"[^/]*title="([^"]*)"[^/]*\/>/g, (_, t) => `#${decodeURIComponent(t)}`)
    .replace(/<e type="mention"[^/]*name="([^"]*)"[^/]*\/>/g, (_, n) => `@${decodeURIComponent(n)}`)
    .replace(/<e type="web"[^/]*href="([^"]*)"[^/]*title="([^"]*)"[^/]*\/>/g, (_, h, t) => `[${decodeURIComponent(t)}](${decodeURIComponent(h)})`)
    .replace(/<e type="web"[^/]*href="([^"]*)"[^/]*\/>/g, (_, h) => decodeURIComponent(h))
    .replace(/<e [^/]*\/>/g, "");
}

async function extractArticle(
  slug: string,
  ctx: AdapterContext,
  existingSock?: import("net").Socket,
): Promise<string> {
  const sock = existingSock || (await ctx.ensureDaemon());
  const shouldDestroy = !existingSock;
  try {
    await ctx.sendDaemonRequest(sock, "navigate", {
      url: `https://articles.zsxq.com/id_${slug}.html`,
      timeout: ctx.timeout,
    });

    const { html } = await ctx.sendDaemonRequest(sock, "getHTML", {});
    const text = html
      .replace(/<script[\s\S]*?<\/script>/gi, "")
      .replace(/<style[\s\S]*?<\/style>/gi, "")
      .replace(/<[^>]+>/g, "\n")
      .replace(/&nbsp;/g, " ")
      .replace(/&lt;/g, "<")
      .replace(/&gt;/g, ">")
      .replace(/&amp;/g, "&")
      .replace(/\n{3,}/g, "\n\n")
      .trim();

    // Strip header boilerplate (title, "来自：", date line)
    const lines = text.split("\n");
    let startIdx = 0;
    for (let i = 0; i < Math.min(lines.length, 10); i++) {
      if (lines[i].includes("来自：") || /^\d{4}年\d{2}月\d{2}日/.test(lines[i].trim())) {
        startIdx = i + 1;
      }
    }
    return lines.slice(startIdx).join("\n").trim();
  } finally {
    if (shouldDestroy) sock.destroy();
  }
}

async function extractTopic(
  groupId: string,
  topicId: string,
  ctx: AdapterContext,
): Promise<ParseResult> {
  const sock = await ctx.ensureDaemon();
  try {
    // Navigate to group page (not topic page, which may redirect if SPA routing fails)
    await ctx.sendDaemonRequest(sock, "navigate", {
      url: `https://wx.zsxq.com/group/${groupId}`,
      timeout: ctx.timeout,
    });

    // Check login status
    const { value: currentUrl } = await ctx.sendDaemonRequest(sock, "evaluate", {
      expression: "window.location.href",
    });
    if (currentUrl.includes("join_group") || currentUrl.includes("login")) {
      throw new Error("知识星球未登录，请在 Chrome 中登录 wx.zsxq.com 后重试");
    }

    // Fetch topic data via API from page context
    // Use resp.text() + manual extraction to avoid JSON.parse BigInt precision loss
    const { value: raw } = await ctx.sendDaemonRequest(sock, "evaluate", {
      expression: `(async () => {
        const resp = await fetch('https://api.zsxq.com/v2/topics/${topicId}', {
          credentials: 'include',
          headers: { 'Accept': 'application/json' }
        });
        const text = await resp.text();
        if (text.startsWith('<!')) throw new Error('API returned HTML — topic not found or auth failed');
        const data = JSON.parse(text);
        if (!data.succeeded) throw new Error('API error: ' + (data.code || 'unknown'));
        const t = data.resp_data.topic;
        return JSON.stringify({
          text: t.talk?.text || t.question?.text || '',
          author: t.talk?.owner?.name || t.question?.owner?.name || '',
          create_time: t.create_time,
          article_title: t.talk?.article?.title || null,
          article_url: t.talk?.article?.article_url || null,
          images: (t.talk?.images || []).map(i => i.large?.url || i.original?.url || '').filter(Boolean),
          likes: t.likes_count || 0,
          comments: t.comments_count || 0,
        });
      })()`,
    });

    const topic = JSON.parse(raw);
    const cleanedText = cleanZsxqMarkup(topic.text);
    const title = topic.article_title || cleanedText.replace(/\n/g, " ").slice(0, 50);
    const published = topic.create_time?.slice(0, 10) || "";

    const lines: string[] = [];
    lines.push(topic.article_title ? `# ${topic.article_title}` : "");
    lines.push(cleanedText);

    // If topic has article URL, fetch the full article content
    if (topic.article_url) {
      try {
        const articleResult = await extractArticle(topic.article_url.match(/id_([^.]+)\.html/)?.[1] || "", ctx, sock);
        lines.push("", "---", "", articleResult);
      } catch (e) {
        lines.push("", `[阅读全文](${topic.article_url})`);
      }
    }

    if (topic.images.length > 0) {
      lines.push("");
      for (const img of topic.images) lines.push(`![](${img})`);
    }

    return {
      markdown: lines.filter(Boolean).join("\n"),
      metadata: {
        url: `https://wx.zsxq.com/group/${groupId}/topic/${topicId}`,
        title,
        author: topic.author,
        published,
        site_name: "知识星球",
        description: cleanedText.slice(0, 100),
      },
    };
  } finally {
    sock.destroy();
  }
}

async function extractArticleFull(slug: string, ctx: AdapterContext): Promise<ParseResult> {
  const sock = await ctx.ensureDaemon();
  try {
    await ctx.sendDaemonRequest(sock, "navigate", {
      url: `https://articles.zsxq.com/id_${slug}.html`,
      timeout: ctx.timeout,
    });

    // Extract title and meta from page
    const { value: meta } = await ctx.sendDaemonRequest(sock, "evaluate", {
      expression: `JSON.stringify({
        title: document.querySelector('title')?.textContent || '',
        author: document.querySelector('.author, .name')?.textContent?.trim() || '',
        date: document.querySelector('.date, time')?.textContent?.trim() || '',
      })`,
    });
    const pageMeta = JSON.parse(meta);

    const content = await extractArticle(slug, ctx, sock);

    return {
      markdown: `# ${pageMeta.title}\n\n${content}`,
      metadata: {
        url: `https://articles.zsxq.com/id_${slug}.html`,
        title: pageMeta.title,
        author: pageMeta.author || undefined,
        published: pageMeta.date || undefined,
        site_name: "知识星球",
        description: content.slice(0, 100),
      },
    };
  } finally {
    sock.destroy();
  }
}

export async function extract(url: string, ctx: AdapterContext): Promise<ParseResult> {
  const parsed = parseZsxqUrl(url);
  if (!parsed) throw new Error(`Unrecognized zsxq URL: ${url}`);

  switch (parsed.type) {
    case "topic":
      return extractTopic(parsed.groupId, parsed.topicId, ctx);

    case "article":
      return extractArticleFull(parsed.slug, ctx);

    case "shortlink": {
      // Resolve short link by following redirect via CDP
      const sock = await ctx.ensureDaemon();
      try {
        await ctx.sendDaemonRequest(sock, "navigate", { url, timeout: ctx.timeout });
        const { value: resolvedUrl } = await ctx.sendDaemonRequest(sock, "evaluate", {
          expression: "window.location.href",
        });
        sock.destroy();

        const resolvedParsed = parseZsxqUrl(resolvedUrl);
        if (!resolvedParsed || resolvedParsed.type === "shortlink") {
          throw new Error(`Short link resolved to unrecognized URL: ${resolvedUrl}`);
        }
        return extract(resolvedUrl, ctx);
      } catch (e) {
        sock.destroy();
        throw e;
      }
    }
  }
}
