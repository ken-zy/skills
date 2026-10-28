"""Platform routing for the explicit media CLI (separate from article extraction)."""
from dataclasses import dataclass
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit


@dataclass(frozen=True)
class PlatformAdapter:
    name: str
    hosts: tuple[str, ...]
    backend: str = "yt-dlp"
    note: str = "Availability, formats and captions must be probed per URL."

    def matches(self, host: str) -> bool:
        return any(host == suffix or host.endswith("." + suffix) for suffix in self.hosts)

    def prepare(self, url: str) -> str:
        parsed = urlsplit(url)
        if self.name == "bilibili" and parsed.hostname != "b23.tv":
            query = parse_qs(parsed.query)
            if parsed.path.startswith("/video/"):
                # Select one part; a share URL is not authorization for the series.
                part = query.get("p", ["1"])[0]
                if not part.isdigit() or int(part) < 1:
                    raise ValueError("Bilibili p must be a positive part number")
                return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode({"p": part}), ""))
        return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, parsed.query, ""))


ADAPTERS = (
    PlatformAdapter("bilibili", ("bilibili.com", "b23.tv"), note="One selected part; available quality and captions can depend on login."),
    PlatformAdapter("youtube", ("youtube.com", "youtu.be", "youtube-nocookie.com"), note="May require a JS runtime or authorized login; never install or read cookies implicitly."),
    PlatformAdapter("x-twitter", ("x.com", "twitter.com")),
    PlatformAdapter("douyin", ("douyin.com", "iesdouyin.com"), note="Upstream extractor may require fresh cookies or fail as the platform changes."),
    PlatformAdapter("tiktok", ("tiktok.com",)),
    PlatformAdapter("xiaohongshu", ("xiaohongshu.com", "xhslink.com"), note="Preserve the complete share URL, including xsec_token, for extraction only."),
    PlatformAdapter("instagram", ("instagram.com",)),
    PlatformAdapter("facebook", ("facebook.com", "fb.watch")),
    PlatformAdapter("vimeo", ("vimeo.com",)),
    PlatformAdapter("twitch", ("twitch.tv",)),
    PlatformAdapter("reddit", ("reddit.com", "redd.it")),
    PlatformAdapter("weibo", ("weibo.com", "weibo.cn")),
    PlatformAdapter("acfun", ("acfun.cn",)),
    PlatformAdapter("wechat-channels", ("weixin.qq.com", "channels.weixin.qq.com"), "unavailable",
                    "WeChat Channels needs a separately reviewed backend; this CLI does not install a CA, change proxies or send URLs to a resolver."),
    PlatformAdapter("kuaishou", ("kuaishou.com", "gifshow.com"), "unavailable",
                    "No bundled Kuaishou share-page backend; provide an authorized local media file or add a reviewed backend."),
)


def resolve_platform(raw: str) -> tuple[PlatformAdapter, str]:
    parsed = urlsplit(raw.strip())
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.port:
        raise ValueError("Provide an HTTPS platform URL without credentials or a custom port")
    host = parsed.hostname.lower().rstrip(".")
    for adapter in ADAPTERS:
        if adapter.matches(host):
            return adapter, adapter.prepare(raw.strip())
    raise ValueError("No media adapter for this host; article extraction is available through main.ts")


def public_source(url: str) -> str:
    """Keep navigation keys, excluding signed share tokens and tracking parameters."""
    parsed = urlsplit(url)
    query = parse_qs(parsed.query)
    keep = {key: query[key][0] for key in ("v", "p") if key in query}
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(keep), ""))
