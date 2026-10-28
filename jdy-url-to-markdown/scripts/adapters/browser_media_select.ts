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
