import type { VideoReference } from "../types";

const SELECTOR = 'video, mpvideo, mp-video, [data-mpvid], iframe.video_iframe, iframe[src*="video"], iframe[data-src*="video"], iframe[src*="v.qq.com"]';

// Replace the outermost player before Readability/Turndown strips its iframe or
// duplicates its nested <video>. Sources remain in memory, never in diagnostics.
export function preserveVideoNodes(document: any, root: any, sourceUrl: string): VideoReference[] {
  const refs: VideoReference[] = [];
  const nodes = [...root.querySelectorAll(SELECTOR)] as Element[];
  const selected = new Set(nodes);
  for (const node of nodes) {
    let parent = node.parentElement;
    let nested = false;
    while (parent && parent !== root) {
      if (selected.has(parent)) { nested = true; break; }
      parent = parent.parentElement;
    }
    if (nested) continue;
    const video = node.tagName.toLowerCase() === "video" ? node : node.querySelector("video");
    const candidates = [
      video?.getAttribute("src"), video?.getAttribute("data-src"),
      ...[...(video?.querySelectorAll("source") ?? [])].map(e => e.getAttribute("src")),
      node.getAttribute("src"), node.getAttribute("data-src"),
    ];
    let url: string | undefined;
    for (const candidate of candidates) {
      if (!candidate) continue;
      try {
        const parsed = new URL(candidate, sourceUrl);
        if (["http:", "https:"].includes(parsed.protocol) && /\.mp4$/i.test(parsed.pathname)) {
          url = parsed.href;
          break;
        }
      } catch {}
    }
    const marker = `JDYVIDEO${String(refs.length + 1).padStart(6, "0")}END`;
    const placeholder = document.createElement("p");
    placeholder.setAttribute("data-jdy-video", marker);
    placeholder.textContent = marker;
    node.replaceWith(placeholder);
    refs.push({ marker, url });
  }
  return refs;
}
