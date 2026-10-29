// Comparison only: never rewrite the uploaded body or a remote editor snapshot.
// Preserve text, whitespace, styles, link targets and all non-image attributes.
function imageTag(tag: string): string {
  const head = /^<img\b/i.exec(tag);
  if (!head) return tag;
  let at = head[0].length;
  const attrs: { name: string; start: number; end: number; value?: string; valueStart?: number; valueEnd?: number }[] = [];
  const seen = new Set<string>();
  while (at < tag.length) {
    const whitespace = /^\s*/.exec(tag.slice(at))![0]; at += whitespace.length;
    if (/^\/?\s*>$/.test(tag.slice(at))) break;
    if (!whitespace) return tag;
    const start = at, name = /^[^\s=<>/'"]+/.exec(tag.slice(at))?.[0];
    if (!name || seen.has(name.toLowerCase())) return tag;
    seen.add(name.toLowerCase()); at += name.length;
    const attr: typeof attrs[number] = { name, start, end: at };
    const assignment = /^\s*=\s*/.exec(tag.slice(at));
    if (assignment) {
      at += assignment[0].length;
      const quote = tag[at];
      if (quote !== '"' && quote !== "'") return tag; // Unobserved forms stay strict.
      attr.valueStart = ++at;
      const end = tag.indexOf(quote, at); if (end < 0) return tag;
      attr.value = tag.slice(at, end); attr.valueEnd = end; at = end + 1;
    }
    attrs.push(attr);
  }
  const sources = attrs.filter(a => a.name.toLowerCase() === 'src' || a.name.toLowerCase() === 'data-src');
  if (sources.length !== 1) return tag;
  const src = sources[0]!;
  if (!src.value || src.valueStart === undefined || src.valueEnd === undefined) return tag;
  // Only WeChat's exact public image host and known image paths, same asset/query.
  const value = src.value.replace(/^(https:\/\/mmbiz\.qpic\.cn\/(?:sz_)?mmbiz_(?:jpg|png|gif|webp)\/[A-Za-z0-9]+\/)640(?=\?|$)/, (_match, prefix) => prefix + '0');
  if (!/^https:\/\/mmbiz\.qpic\.cn\/(?:sz_)?mmbiz_(?:jpg|png|gif|webp)\/[A-Za-z0-9]+\/0(?:\?|$)/.test(value)) return tag;
  return tag.slice(0, src.start) + 'src' + tag.slice(src.end, src.valueStart) + value + tag.slice(src.valueEnd);
}
export function normalizeWechatHtml(html: string): string {
  let previousEnd = -1, previousVoid = '';
  // Quoted '>' and comments/raw-text elements must not be mistaken for tags.
  const tokens = /<!--[\s\S]*?(?:-->|$)|<(script|style|textarea|title)\b(?:"[^"]*"|'[^']*'|[^'">])*?>[\s\S]*?(?:<\/\1\s*>|$)|<\/?[A-Za-z](?:"[^"]*"|'[^']*'|[^'">])*?>/gi;
  return html.replace(tokens, (tag: string, _raw: string, offset: number) => {
    const closing = /^<\/(br|hr)>$/i.exec(tag);
    const remove = closing && offset === previousEnd && closing[1]!.toLowerCase() === previousVoid;
    previousEnd = offset + tag.length;
    previousVoid = /^<(br|hr)\b/i.exec(tag)?.[1]?.toLowerCase() || '';
    if (remove) return '';
    if (previousVoid) return tag.replace(/\s*\/>$/, '>');
    return /^<img\b/i.test(tag) ? imageTag(tag) : tag;
  });
}
export function sameWechatHtml(a: string, b: string) {
  return a === b || normalizeWechatHtml(a) === normalizeWechatHtml(b);
}
