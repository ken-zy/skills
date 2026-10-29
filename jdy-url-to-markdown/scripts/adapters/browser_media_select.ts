export function selectBrowserStream(items: Array<Record<string, any>>) {
  const streams: Array<Record<string, any> & { masterUrl: string }> = items.flatMap((s) => {
    if (typeof s.masterUrl !== "string") return [];
    let u: URL;
    try { u = new URL(s.masterUrl); } catch { return []; }
    if (u.protocol === "http:" && u.hostname.endsWith(".xhscdn.com")) u.protocol = "https:";
    if (u.protocol !== "https:" || !u.hostname.endsWith(".xhscdn.com") || u.username || u.password || u.port) return [];
    return [{ ...s, masterUrl: u.href }];
  });
  const hasAudio = (s: Record<string, any>) => Number(s.audioChannels > 0 || s.audioBitrate > 0);
  const expectsAudio = streams.some((s) => hasAudio(s));
  streams.sort((a, b) => hasAudio(b) - hasAudio(a)
    || (Number(a.width || 0) * Number(a.height || 0) - Number(b.width || 0) * Number(b.height || 0))
    || Number(a.size || 0) - Number(b.size || 0));
  return { stream: streams[0], expectsAudio };
}

// Rows come only from Vimeo's own Download video dialog, never player DRM data.
export function selectVimeoDownload(rows: Array<{ url: string; text: string }>, videoId: string, quality: string) {
  const cap = quality === "best" ? Infinity : Number(quality);
  const candidates = rows.flatMap((row) => {
    let url: URL;
    try { url = new URL(row.url); } catch { return []; }
    if (url.protocol !== "https:" || url.hostname !== "player.vimeo.com" || url.port || url.username || url.password
      || !url.pathname.startsWith(`/progressive_redirect/download/${videoId}/`)) return [];
    const dimensions = row.text.match(/(\d+)\s*[x×]\s*(\d+)\s*$/);
    if (!dimensions) return [];
    const width = Number(dimensions[1]), height = Number(dimensions[2]);
    if (!width || !height || height > cap) return [];
    return [{ media_url: url.href, width, height, original: /^Original\b/i.test(row.text) }];
  });
  candidates.sort((a, b) => b.height - a.height || Number(a.original) - Number(b.original));
  return candidates[0];
}
