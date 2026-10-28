"""First-party share-page extraction and a separately consented fixed resolver.

No browser sessions, proxy/CA changes, code evaluation or unknown fallback URLs.
"""
from __future__ import annotations
import json
from pathlib import Path
import re
import time
import urllib.error
import urllib.request
from urllib.parse import urlsplit

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
WECHAT_RESOLVER = "https://sph.litao.workers.dev/api/fetch_video_profile"
KS_HOSTS = ("kwaicdn.com", "yximgs.com", "kwimgs.com", "ksapisrv.com", "kuaishou.com", "gifshow.com")
WX_HOSTS = ("qq.com", "gtimg.com", "qpic.cn")


class NativeError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def allowed_url(url, suffixes):
    if not isinstance(url, str):
        return False
    parsed = urlsplit(url)
    return (parsed.scheme == "https" and not parsed.username and not parsed.password and not parsed.port
            and any(parsed.hostname == h or (parsed.hostname or "").endswith("." + h) for h in suffixes))


class RestrictedRedirect(urllib.request.HTTPRedirectHandler):
    def __init__(self, hosts):
        self.hosts = hosts

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not allowed_url(newurl, self.hosts):
            raise NativeError("redirect_rejected", "Redirect left the permitted HTTPS platform/CDN hosts")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch_share(url, timeout):
    if not allowed_url(url, ("kuaishou.com", "gifshow.com")):
        raise NativeError("invalid_url", "Expected a Kuaishou HTTPS share URL")
    try:
        # Optional dependency in the operator's reviewed tool environment.
        # Do not fall back after a denial; the selected client makes one request.
        from curl_cffi import requests
    except ImportError:
        requests = None
    try:
        headers = {"User-Agent": UA, "Referer": "https://www.kuaishou.com/", "Accept-Language": "zh-CN,zh;q=0.9"}
        if requests:
            response = requests.get(url, headers=headers, impersonate="chrome", timeout=min(timeout, 30), allow_redirects=False, stream=True)
            try:
                if response.status_code != 200:
                    raise NativeError("share_http_error", f"Share page returned HTTP {response.status_code}; no automatic retry")
                raw = bytearray()
                for block in response.iter_content(chunk_size=65536):
                    raw.extend(block)
                    if len(raw) > 8 * 1024 * 1024:
                        raise NativeError("response_too_large", "Share response exceeds the metadata size limit")
            finally:
                response.close()
        else:
            opener = urllib.request.build_opener(RestrictedRedirect(("kuaishou.com", "gifshow.com")))
            with opener.open(urllib.request.Request(url, headers=headers), timeout=min(timeout, 30)) as response:
                raw = response.read(8 * 1024 * 1024 + 1)
        if len(raw) > 8 * 1024 * 1024:
            raise NativeError("response_too_large", "Share response exceeds the metadata size limit")
        return raw.decode("utf-8", "replace")
    except NativeError:
        raise
    except Exception as exc:
        raise NativeError("share_fetch_failed", f"Share fetch failed ({type(exc).__name__}); no response or signed URLs logged") from None


def extract_kuaishou(page: str, source: str) -> dict:
    match_id = re.search(r"/(?:short-video|photo)/([A-Za-z0-9_-]+)", urlsplit(source).path)
    if not match_id:
        raise NativeError("canonical_link_required", "Use the full /short-video/<id> link; short-link expansion is not implemented")
    video_id = match_id.group(1)
    match = re.search(r"window\.__APOLLO_STATE__\s*=\s*", page)
    if not match:
        raise NativeError("share_context_missing", "The share page contains no video state; request a fresh share link or manual browser verification")
    try:
        state, _ = json.JSONDecoder().raw_decode(page[match.end():])
        records = state["defaultClient"]
        if not isinstance(records, dict):
            raise TypeError("invalid records")
        photo = records.get("VisionVideoDetailPhoto:" + video_id)
        if not isinstance(photo, dict):
            raise KeyError("requested photo")
    except (ValueError, TypeError, KeyError):
        raise NativeError("share_context_missing", "No structured data matching the requested video; unrelated page MP4s are never selected") from None

    def deref(value):
        for _ in range(10):
            if not isinstance(value, dict):
                break
            key = value.get("__ref") or (value.get("id") if value.get("type") == "id" else None)
            if not key or key not in records:
                break
            value = records[key]
        return value

    formats = []
    def add_manifest(manifest):
        manifest = deref(manifest)
        if isinstance(manifest, dict) and "json" in manifest:
            manifest = manifest["json"]
        if isinstance(manifest, str):
            try:
                manifest = json.loads(manifest)
            except ValueError:
                return
        if not isinstance(manifest, dict):
            return
        for aset in manifest.get("adaptationSet") or []:
            aset = deref(aset)
            if not isinstance(aset, dict):
                continue
            for representation in aset.get("representation") or []:
                rep = deref(representation)
                if not isinstance(rep, dict):
                    continue
                for key in ("url", "backupUrl"):
                    values = rep.get(key)
                    if isinstance(values, dict):
                        values = values.get("json")
                    if not isinstance(values, list):
                        values = [values]
                    for value in values:
                        if allowed_url(value, KS_HOSTS):
                            formats.append({"format_id": "native-" + str(len(formats)), "url": value, "ext": "mp4",
                                            "width": rep.get("width"), "height": rep.get("height"), "tbr": rep.get("avgBitrate"),
                                            "http_headers": {"User-Agent": UA, "Referer": "https://www.kuaishou.com/"}})
    add_manifest(photo.get("manifest"))
    add_manifest(photo.get("manifestH265"))
    for key in ("photoUrl", "photoH265Url"):
        value = photo.get(key)
        if allowed_url(value, KS_HOSTS):
            formats.append({"format_id": "native-" + str(len(formats)), "url": value, "ext": "mp4", "height": None,
                            "http_headers": {"User-Agent": UA, "Referer": "https://www.kuaishou.com/"}})
    if not formats:
        raise NativeError("no_formats", "The requested video's structured data exposes no permitted HTTPS media")
    duration = photo.get("duration")
    return {"id": video_id, "title": photo.get("caption") or video_id, "duration": duration / 1000 if isinstance(duration, (int, float)) else None,
            "extractor_key": "KuaishouNative", "formats": formats, "subtitles": {}, "automatic_captions": {}}


def probe_wechat(source, timeout):
    parsed = urlsplit(source)
    if parsed.hostname != "weixin.qq.com" or not parsed.path.startswith("/sph/"):
        raise NativeError("invalid_url", "Expected a weixin.qq.com/sph/<id> public share URL")
    request = urllib.request.Request(WECHAT_RESOLVER, data=json.dumps({"url": source}).encode(),
                                    headers={"Content-Type": "application/json", "User-Agent": "video-guide/1.0"}, method="POST")
    try:
        # No redirects: consent names this service only, not a chain of services.
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *args):
                return None
        with urllib.request.build_opener(NoRedirect()).open(request, timeout=min(timeout, 30)) as response:
            raw = response.read(2 * 1024 * 1024 + 1)
        if len(raw) > 2 * 1024 * 1024:
            raise NativeError("response_too_large", "Resolver response exceeds the size limit")
        payload = json.loads(raw)
    except urllib.error.HTTPError as exc:
        code = "resolver_auth_required" if exc.code in (401, 403) else "resolver_http_error"
        raise NativeError(code, f"The chosen resolver returned HTTP {exc.code}; this is not a request to log in to WeChat") from None
    except NativeError:
        raise
    except Exception as exc:
        raise NativeError("resolver_failed", f"Resolver failed ({type(exc).__name__}); no fallback service was contacted") from None
    data = payload.get("data") if isinstance(payload, dict) else None
    feed = data.get("feedInfo") if isinstance(data, dict) else None
    if not isinstance(feed, dict):
        raise NativeError("resolver_invalid_response", "Resolver returned no structured video profile; no raw response is logged")
    formats = []
    for key, kind in (("h264VideoInfo", "h264"), ("h265VideoInfo", "h265")):
        item = feed.get(key) or {}
        if not isinstance(item, dict):
            continue
        if allowed_url(item.get("videoUrl"), WX_HOSTS):
            formats.append({"format_id": kind, "url": item["videoUrl"], "ext": "mp4", "height": item.get("height"), "width": item.get("width")})
    if not formats and allowed_url(feed.get("videoUrl"), WX_HOSTS):
        formats.append({"format_id": "native", "url": feed["videoUrl"], "ext": "mp4", "height": None})
    if not formats:
        raise NativeError("no_formats", "Resolver returned no allowed HTTPS media; its success response alone is insufficient")
    return {"id": parsed.path.rstrip("/").split("/")[-1], "title": str(feed.get("description") or "WeChat video"),
            "duration": None, "extractor_key": "WeChatOnline", "formats": formats, "subtitles": {}, "automatic_captions": {}}


def select_format(info, quality):
    formats = info["formats"]
    if quality != "best":
        formats = [f for f in formats if isinstance(f.get("height"), (int, float)) and f["height"] <= int(quality)]
    if not formats:
        raise NativeError("format_unavailable", "No native format has a known height within the cap; inspect formats or explicitly choose best")
    return max(formats, key=lambda f: (f.get("height") or 0, f.get("tbr") or 0))


def download_format(fmt, target: Path, hosts, timeout, max_bytes):
    url = fmt["url"]
    if not allowed_url(url, hosts):
        raise NativeError("media_host_rejected", "Media URL is outside the permitted HTTPS CDN hosts")
    started = time.monotonic()
    opener = urllib.request.build_opener(RestrictedRedirect(hosts))
    try:
        with opener.open(urllib.request.Request(url, headers=fmt.get("http_headers") or {"User-Agent": UA}), timeout=min(timeout, 30)) as response, target.open("xb") as out:
            total = 0
            expected = response.headers.get("Content-Length")
            if expected and int(expected) > max_bytes:
                raise NativeError("size_limit", "Media exceeds the selected size limit")
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                if total == 0 and b"ftyp" not in chunk[:64]:
                    raise NativeError("not_direct_mp4", "Native backend requires a direct MP4; HTML, HLS manifests and other non-MP4 payloads are not passed to FFprobe")
                total += len(chunk)
                if total > max_bytes or time.monotonic() - started > timeout:
                    raise NativeError("download_limit", "Native download exceeded its size or time limit; partial file retained")
                out.write(chunk)
            if expected and total != int(expected):
                raise NativeError("truncated_media", "Native download ended before its declared size")
    except NativeError:
        raise
    except Exception as exc:
        raise NativeError("native_download_failed", f"Media download failed ({type(exc).__name__}); signed URLs withheld") from None
