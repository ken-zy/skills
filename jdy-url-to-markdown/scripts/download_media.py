#!/usr/bin/env python3
"""Local media acquisition; Python stdlib + existing yt-dlp/FFmpeg executables.

No ASR, cloud upload, automatic install or implicit credentials.
Optional browser reads require an explicitly selected loopback endpoint.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import signal
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from urllib.parse import urlsplit

from adapters.media_platforms import ADAPTERS, public_source, resolve_platform

SUBTITLE_SUFFIXES = {".srt", ".vtt", ".ass", ".ssa", ".ttml", ".srv1", ".srv2", ".srv3", ".json", ".json3"}


class MediaError(RuntimeError):
    def __init__(self, stage: str, message: str, code: str | None = None, diagnostic: str | None = None):
        super().__init__(message)
        self.stage = stage
        self.code = code or stage
        self.diagnostic = diagnostic


def classify_error(text: str) -> str:
    return error_details(text)[1]


def error_details(text: str) -> tuple[str, str]:
    # Warnings mentioning cookies must not turn a different fatal error into a login request.
    fatal = [line for line in text.splitlines() if "ERROR:" in line]
    low = (fatal[-1] if fatal else text).lower()
    if "cannot decrypt" in text.lower() or "no key found" in text.lower():
        return "session_unreadable", "Browser session cannot be decrypted by the CLI; do not ask the user to log in again."
    if "oauth" in low and "401" in low:
        return "backend_auth_failed", "The extractor's OAuth request was rejected; diagnose backend compatibility before requesting account login."
    if "fresh cookies" in low:
        return "session_required", "A fresh browser session is required; this does not necessarily require account login."
    if any(word in low for word in ("captcha", "not a bot", "verification")):
        return "verification_required", "Manual browser verification is required; stop automatic retries."
    if any(word in low for word in ("sign in", "login", "log in", "account authentication")):
        return "login_required", "Account login is required; arrange authorized access with the user."
    if "drm" in low:
        return "drm", "DRM-protected media is unavailable to this workflow."
    if "requested format" in low:
        return "format_unavailable", "Requested format unavailable; probe formats before selecting another quality."
    if "unsupported url" in low:
        return "unsupported_url", "The installed downloader cannot extract this URL."
    if "no video formats" in low:
        return "no_formats", "No downloadable video formats were exposed for this request."
    if "404" in low or "not found" in low:
        return "not_found", "The sample or extractor endpoint is no longer available; check a fresh public share link."
    if any(word in low for word in ("403", "429", "412", "too many requests")):
        return "access_denied", "Platform denied or rate-limited the request. Stop; do not repeatedly retry or switch accounts."
    return "extractor_failed", "Downloader failed; use the sanitized diagnostic to identify the failed stage."


def safe_diagnostic(text: str) -> str:
    lines = [line for line in text.splitlines() if "ERROR:" in line]
    value = lines[-1] if lines else "No structured extractor error was returned"
    # Generic extractor IDs can themselves be signed URLs without a scheme.
    value = re.sub(r"^.*?ERROR:\s*\[[^\]]+\]\s*.*?:\s+", "ERROR: ", value)
    value = re.sub(r"https?://[^\s]+", "[URL]", value)
    value = re.sub(r"\?[^\s]+", "[query redacted]", value)
    value = re.sub(r"(?i)(cookie|authorization|password|[\w-]*token|[\w-]*key)\s*[=:]\s*\S+", r"\1=[redacted]", value)
    return value[:600]


def run(argv: list[str], timeout: int, stage: str) -> str:
    proc = None
    try:
        proc = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                start_new_session=os.name == "posix")
        stdout, stderr = proc.communicate(timeout=timeout)
    except FileNotFoundError:
        raise MediaError("dependency", f"Missing executable: {Path(argv[0]).name}") from None
    except subprocess.TimeoutExpired:
        terminate(proc)
        raise MediaError(stage, "Command timed out; partial files are retained and must not be reported as complete") from None
    except KeyboardInterrupt:
        terminate(proc)
        raise
    except OSError:
        raise MediaError(stage, "Unable to start the required executable") from None
    if proc.returncode:
        text = stderr + "\n" + stdout
        code, message = error_details(text)
        raise MediaError(stage, message, code, safe_diagnostic(text))
    return stdout


def terminate(proc):
    if proc is not None:
        try:
            if os.name == "posix":
                os.killpg(proc.pid, signal.SIGKILL)
            else:
                proc.kill()
        except ProcessLookupError:
            pass
        proc.communicate()


def find_tool(name: str) -> str | None:
    executable = shutil.which(name)
    if executable:
        return executable
    # Non-interactive SSH on macOS often omits Homebrew and user-level tools.
    for directory in (Path("/opt/homebrew/bin"), Path("/usr/local/bin"), Path.home() / ".local/bin"):
        candidate = directory / name
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return None


def require_tool(name: str) -> str:
    executable = find_tool(name)
    if not executable:
        raise MediaError("dependency", f"{name} is missing; install a reviewed pinned version before retrying")
    return executable


def doctor() -> dict:
    tools = {}
    for name in ("yt-dlp", "ffmpeg", "ffprobe"):
        path = find_tool(name)
        tools[name] = {"available": bool(path)}
        if path:
            version = run([path, "--version" if name == "yt-dlp" else "-version"], 15, "dependency")
            tools[name].update(path=path, version=version.splitlines()[0])
    return {"ok": all(t["available"] for t in tools.values()), "action": "doctor", "tools": tools,
            "adapters": [{"platform": a.name, "backend": a.backend, "note": a.note} for a in ADAPTERS]}


def base_command(executable: str, browser: str | None = None) -> list[str]:
    # netrc is opt-in in yt-dlp; --ignore-config prevents a user's config enabling it.
    args = [executable, "--ignore-config", "--no-cache-dir", "--no-plugin-dirs", "--no-remote-components", "--no-cookies", "--no-cookies-from-browser",
            "--no-playlist", "--playlist-items", "1", "--socket-timeout", "20", "--retries", "0",
            "--fragment-retries", "0", "--abort-on-unavailable-fragments", "--no-progress", "--no-colors"]
    if browser:
        args += ["--cookies-from-browser", browser]
    runtime = find_tool("deno")
    if runtime:
        args += ["--js-runtimes", "deno:" + runtime]
    return args


def one_video(info: dict) -> dict:
    if not isinstance(info, dict):
        raise MediaError("probe", "Downloader returned invalid metadata")
    if info.get("_type") in ("playlist", "multi_video") or "entries" in info:
        entries = info.get("entries") or []
        if len(entries) != 1 or not isinstance(entries[0], dict):
            raise MediaError("probe", "Expected exactly one selected video; collections require a separate explicit request")
        info = one_video(entries[0])
    if not info.get("id") or not info.get("title"):
        raise MediaError("probe", "Missing video identity or title")
    if info.get("is_live") or info.get("live_status") in ("is_live", "is_upcoming", "post_live"):
        raise MediaError("probe", "Live or still-processing streams are outside this bounded video workflow")
    return info


def finite_number(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) else None


def source_audio_status(info: dict, context: dict | None = None) -> str:
    context = context or {}
    offered = any(f.get("acodec") not in (None, "none") or (f.get("vcodec") == "none" and f.get("acodec") != "none")
                  for f in info.get("formats") or [])
    if offered or context.get("expects_audio") or context.get("source_audio_status") == "present":
        return "present"
    return "absent" if context.get("source_audio_status") == "absent" else "unknown"


def caption_summary(tracks) -> list[dict]:
    if not isinstance(tracks, dict):
        return []
    return [{"language": language, "formats": sorted({str(t.get("ext", "unknown")) for t in entries if isinstance(t, dict)})}
            for language, entries in tracks.items() if isinstance(entries, list) and language != "live_chat"]


def safe_metadata(info: dict, platform: str, source: str) -> dict:
    formats = []
    for f in info.get("formats") or []:
        formats.append({key: f.get(key) for key in ("format_id", "ext", "width", "height", "fps", "vcodec", "acodec", "filesize", "filesize_approx", "abr")})
    return {"platform": platform, "source_url": public_source(source), "id": str(info["id"]),
            "title": str(info["title"]), "author": info.get("uploader") or info.get("channel"),
            "description": info.get("description"), "duration_seconds": finite_number(info.get("duration")),
            "extractor": info.get("extractor_key") or info.get("extractor"), "formats": formats,
            "subtitles": caption_summary(info.get("subtitles")),
            "automatic_captions": caption_summary(info.get("automatic_captions")),
            "chapters": [{key: c.get(key) for key in ("start_time", "end_time", "title")} for c in info.get("chapters") or []]}


def probe(base: list[str], url: str, timeout: int) -> dict:
    output = run(base + ["--skip-download", "--dump-single-json", "--", url], timeout, "probe")
    try:
        return one_video(json.loads(output))
    except (json.JSONDecodeError, TypeError):
        raise MediaError("probe", "Downloader did not return valid video JSON") from None


def download_command(base: list[str], url: str, directory: Path, action: str,
                     quality: str, sub_langs: str, caption_kind: str) -> list[str]:
    args = base + ["--no-overwrites", "--restrict-filenames", "--paths", str(directory),
                   "--output", "%(id).80B.%(ext)s"]
    if action == "subtitles":
        args += ["--skip-download"]
    elif action == "audio":
        # Preserve the original audio stream; ASR conversion is a subsequent step.
        args += ["--format", "bestaudio"]
    else:
        selector = "bestvideo+bestaudio/best/bestvideo" if quality == "best" else f"bestvideo[height<={quality}]+bestaudio/best[height<={quality}]/bestvideo[height<={quality}]"
        args += ["--format", selector, "--merge-output-format", "mkv"]
    if action in ("subtitles", "bundle"):
        args += ["--sub-langs", sub_langs]
        if caption_kind in ("manual", "both"):
            args += ["--write-subs"]
        if caption_kind in ("auto", "both"):
            args += ["--write-auto-subs"]
    return args + ["--", url]


def clock_seconds(value: str) -> float:
    if re.fullmatch(r"\d+(?:\.\d+)?s", value):
        return float(value[:-1])
    match = re.fullmatch(r"(?:(\d+):)?(\d{1,2}):(\d{2})(?:[.,](\d{1,3}))?", value.strip())
    if not match:
        raise ValueError("Invalid caption time")
    hours, minutes, seconds, fraction = match.groups()
    if int(minutes) >= 60 or int(seconds) >= 60:
        raise ValueError("Invalid caption time")
    return int(hours or 0) * 3600 + int(minutes) * 60 + int(seconds) + float("0." + (fraction or "0"))


def subtitle_entries(path: Path) -> int:
    try:
        text = path.read_text(encoding="utf-8-sig")
        if not text.strip() or "\ufffd" in text:
            return 0
        spans = []
        if path.suffix in (".json", ".json3"):
            data = json.loads(text)
            for row in data.get("body", []):
                if str(row.get("content", "")).strip():
                    spans.append((float(row["from"]), float(row["to"])))
            for row in data.get("events", []):
                if any(str(s.get("utf8", "")).strip() for s in row.get("segs", [])):
                    spans.append((float(row["tStartMs"]) / 1000, (float(row["tStartMs"]) + float(row["dDurationMs"])) / 1000))
        elif path.suffix in (".ass", ".ssa"):
            for line in text.splitlines():
                if line.startswith("Dialogue:"):
                    fields = line.split(",", 9)
                    if len(fields) != 10 or not fields[9].strip():
                        return 0
                    spans.append((clock_seconds(fields[1]), clock_seconds(fields[2])))
        elif path.suffix in (".ttml", ".srv1", ".srv2", ".srv3"):
            for node in ET.fromstring(text).iter():
                if node.tag.split("}")[-1] not in ("p", "text") or not "".join(node.itertext()).strip():
                    continue
                attrs = node.attrib
                if "begin" in attrs:
                    start = clock_seconds(attrs["begin"])
                    end = clock_seconds(attrs["end"]) if "end" in attrs else start + clock_seconds(attrs["dur"])
                else:
                    scale = 1000 if "t" in attrs else 1
                    start = float(attrs["t"] if "t" in attrs else attrs["start"]) / scale
                    end = start + float(attrs["d"] if "d" in attrs else attrs["dur"]) / scale
                spans.append((start, end))
        else:
            for block in re.split(r"\r?\n\s*\r?\n", text):
                lines = block.splitlines()
                for index, line in enumerate(lines):
                    if "-->" in line:
                        start, end = line.split("-->", 1)
                        if not "\n".join(lines[index + 1:]).strip():
                            return 0
                        spans.append((clock_seconds(start.strip()), clock_seconds(end.strip().split()[0])))
        previous = -1
        for start, end in spans:
            if not (math.isfinite(start) and math.isfinite(end) and 0 <= start < end and start >= previous):
                return 0
            previous = start
        return len(spans)
    except (ValueError, OSError, AttributeError, TypeError, KeyError, IndexError, ET.ParseError):
        return 0


def verified_files(directory: Path, action: str, ffprobe: str | None, timeout: int, *, only_file: Path | None = None, max_bytes: int | None = None) -> list[dict]:
    files = []
    for path in ([only_file] if only_file else sorted(directory.iterdir())):
        if not path.is_file() or path.suffix in (".part", ".ytdl", ".temp"):
            continue
        size = path.stat().st_size
        if size == 0:
            raise MediaError("verify", "An empty output file was produced")
        if max_bytes is not None and size > max_bytes:
            raise MediaError("verify", "Output exceeds the selected size budget; retained files must not be reported as complete", "size_limit")
        record = {"path": str(path.resolve()), "bytes": size}
        if path.suffix.lower() in SUBTITLE_SUFFIXES:
            entries = subtitle_entries(path)
            if not entries:
                raise MediaError("verify", "Subtitle file has no readable timed cues")
            record.update(kind="subtitle", cues=entries)
        else:
            if not ffprobe:
                raise MediaError("verify", "ffprobe is required to validate media output")
            output = run([ffprobe, "-v", "error", "-show_entries", "format=duration:stream=codec_type,codec_name,width,height", "-of", "json", str(path)], min(timeout, 60), "verify")
            try:
                info = json.loads(output)
                duration = float(info["format"]["duration"])
                streams = info["streams"]
                kinds = {s.get("codec_type") for s in streams}
            except (KeyError, ValueError, TypeError):
                raise MediaError("verify", "Invalid media metadata") from None
            required = {"audio"} if action == "audio" else {"video"}
            if not math.isfinite(duration) or duration <= 0 or not required.issubset(kinds):
                raise MediaError("verify", "Output lacks a valid duration or required media tracks")
            record.update(kind="audio" if action == "audio" else "video", duration_seconds=duration, streams=streams,
                          audio_present="audio" in kinds)
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
        record["sha256"] = digest.hexdigest()
        files.append(record)
    expected = "subtitle" if action == "subtitles" else "audio" if action == "audio" else "video"
    if not any(f["kind"] == expected for f in files):
        raise MediaError("verify", "No verified requested output; metadata or a zero exit code alone is not success")
    return files


def acquire_local(args, adapter, url) -> dict:
    source = Path(args.local_file).expanduser().resolve()
    audio_suffixes = {".m4a", ".mp3", ".wav", ".flac", ".opus", ".ogg", ".mka"}
    if source.suffix.lower() not in audio_suffixes | {".mp4", ".mkv", ".webm", ".mov", ".flv"} or not source.is_file():
        raise MediaError("validate", "--local-file must name an existing audio/video file")
    if args.action == "subtitles":
        raise MediaError("subtitles", "A local media file does not by itself supply original subtitles", "subtitles_unavailable")
    source_action = "audio" if source.suffix.lower() in audio_suffixes else "video"
    files = verified_files(source.parent, source_action, require_tool("ffprobe"), args.timeout, only_file=source)
    result = {"ok": True, "action": args.action, "backend": "local-file", "cookies_used": False,
              "share_url_sent_to_resolver": False, "metadata": {"platform": adapter.name, "source_url": public_source(url), "title": source.stem}, "files": files}
    result["source_audio_status"] = "present" if any(f.get("audio_present") for f in files) else "absent"
    if args.action == "probe":
        return result
    if args.action in ("video", "bundle") and source_action == "audio":
        raise MediaError("validate", "An audio-only local file cannot satisfy a video request")
    if source.stat().st_size > args.max_size_mib * 1024 * 1024:
        raise MediaError("validate", "Local source exceeds the selected size budget", "size_limit")
    root = Path(args.dir).expanduser().resolve()
    if any((ancestor / ".obsidian").is_dir() for ancestor in (root, *root.parents)):
        raise MediaError("validate", "Media output must be outside the Obsidian vault")
    root.mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix=adapter.name + "-local-", dir=root))
    output = directory / ("audio.mka" if args.action == "audio" else "source" + source.suffix.lower())
    if args.action == "audio":
        run([require_tool("ffmpeg"), "-nostdin", "-v", "error", "-n", "-i", str(source), "-vn", "-c:a", "copy", str(output)], args.timeout, "audio_extract")
    else:
        shutil.copyfile(source, output)
    result["files"] = verified_files(directory, args.action, require_tool("ffprobe"), args.timeout, max_bytes=args.max_size_mib * 1024 * 1024)
    if args.quality != "best" and args.action in ("video", "bundle"):
        if any(s.get("height", 0) > int(args.quality) for f in result["files"] for s in f.get("streams", [])):
            raise MediaError("verify", "Local video exceeds the selected height cap; original retained", "quality_limit")
    result.update(directory=str(directory), captions_status="not_supplied", created_at=datetime.now(timezone.utc).isoformat())
    manifest = directory / "manifest.json"
    manifest.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    os.chmod(manifest, 0o600)
    return result


def acquire_native(args, adapter, url) -> dict:
    from adapters import native_media as native
    if args.action == "subtitles":
        raise MediaError("subtitles", "Native share backends do not expose original subtitle tracks", "subtitles_unavailable")
    if adapter.name == "wechat-channels" and not getattr(args, "wechat_online", False):
        service = urlsplit(native.WECHAT_RESOLVERS[getattr(args, "wechat_resolver", "sph")]).hostname
        raise MediaError("consent", f"Sending this public share URL to {service} requires explicit user consent", "resolver_consent_required")
    directory = None
    try:
        info = native.probe_wechat(url, args.timeout, getattr(args, "wechat_resolver", "sph")) if adapter.name == "wechat-channels" else native.extract_kuaishou(native.fetch_share(url, args.timeout), url)
        metadata = safe_metadata(info, adapter.name, url)
        result = {"ok": True, "action": args.action, "backend": adapter.backend, "cookies_used": False,
                  "share_url_sent_to_resolver": adapter.name == "wechat-channels", "metadata": metadata, "files": []}
        result["source_audio_status"] = "unknown"
        if adapter.name == "wechat-channels":
            result["resolver_service"] = getattr(args, "wechat_resolver", "sph")
        if args.action == "probe":
            return result
        root = Path(args.dir).expanduser().resolve()
        if any((ancestor / ".obsidian").is_dir() for ancestor in (root, *root.parents)):
            raise MediaError("validate", "Media output must be outside the Obsidian vault")
        root.mkdir(parents=True, exist_ok=True)
        directory = Path(tempfile.mkdtemp(prefix=adapter.name + "-", dir=root))
        media_dir = directory / "media"
        media_dir.mkdir()
        fmt = native.select_format(info, args.quality)
        source_dir = directory / "source" if args.action == "audio" else media_dir
        source_dir.mkdir(exist_ok=True)
        source = source_dir / "source.mp4"
        native.download_format(fmt, source, native.WX_HOSTS if adapter.name == "wechat-channels" else native.KS_HOSTS,
                               args.timeout, getattr(args, "max_size_mib", 256) * 1024 * 1024)
        if args.action == "audio":
            run([require_tool("ffmpeg"), "-nostdin", "-v", "error", "-n", "-i", str(source), "-vn", "-c:a", "copy", str(media_dir / "audio.mka")], args.timeout, "audio_extract")
        result["files"] = verified_files(media_dir, args.action, require_tool("ffprobe"), args.timeout, max_bytes=getattr(args, "max_size_mib", 256) * 1024 * 1024)
        if any(f.get("audio_present") for f in result["files"]):
            result["source_audio_status"] = "present"
        if args.quality != "best" and args.action != "audio":
            if any(s.get("height", 0) > int(args.quality) for f in result["files"] for s in f.get("streams", [])):
                raise MediaError("verify", "Actual video exceeds the selected height cap", "quality_limit")
        result.update(directory=str(directory), captions_status="not_exposed", created_at=datetime.now(timezone.utc).isoformat())
        manifest = directory / "manifest.json"
        manifest.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        os.chmod(manifest, 0o600)
        return result
    except native.NativeError as exc:
        suffix = f"; retained files in {directory}" if directory else ""
        raise MediaError("native", str(exc) + suffix, exc.code) from None


def acquire(args) -> dict:
    adapter, url = resolve_platform(args.url)
    if getattr(args, "local_file", None):
        return acquire_local(args, adapter, url)
    if adapter.backend in ("native-share", "wechat-online"):
        return acquire_native(args, adapter, url)
    if adapter.backend == "unavailable":
        raise MediaError("adapter", adapter.note, "backend_unavailable")
    ytdlp = require_tool("yt-dlp")
    ffprobe = require_tool("ffprobe") if args.action != "probe" and args.action != "subtitles" else None
    browser = args.cookies_from_browser
    profile = getattr(args, "browser_profile", None)
    if profile:
        if not browser:
            raise MediaError("validate", "--browser-profile requires an explicitly selected browser")
        browser += ":" + str(Path(profile).expanduser().resolve())
    base = base_command(ytdlp, browser)
    if getattr(args, "impersonate", None):
        base += ["--impersonate", args.impersonate]
    if args.action in ("video", "bundle"):
        base += ["--ffmpeg-location", require_tool("ffmpeg")]
    download_url = adapter.extraction_url(url)
    download_quality = args.quality
    browser_session_used = False
    expects_audio = False
    context = {}
    cdp = getattr(args, "browser_cdp", None)
    if cdp:
        if adapter.name not in ("reddit", "douyin", "xiaohongshu", "vimeo") or browser:
            raise MediaError("validate", "--browser-cdp is only for explicitly authorized Reddit/Douyin/Xiaohongshu/Vimeo browser sessions; do not combine cookie extraction")
        parsed_cdp = urlsplit(cdp)
        if parsed_cdp.scheme != "http" or parsed_cdp.hostname != "127.0.0.1" or not parsed_cdp.port or parsed_cdp.path not in ("", "/") or parsed_cdp.username or parsed_cdp.password:
            raise MediaError("validate", "Browser endpoint must be an explicitly authorized loopback HTTP port")
        raw = run([require_tool("deno"), "run", "--no-config", "--no-lock", f"--allow-net=127.0.0.1:{parsed_cdp.port}",
                   str(Path(__file__).with_name("browser_media.ts")), cdp.rstrip("/") + "/", url, args.quality], min(args.timeout, 60), "browser_read")
        try:
            context = json.loads(raw)
        except ValueError:
            raise MediaError("browser_read", "Browser helper returned invalid JSON") from None
        if not context.get("ok"):
            raise MediaError("browser_read", "The selected browser could not expose the requested public post video", context.get("code", "browser_read_failed"))
        from adapters.native_media import allowed_url
        download_url = context.get("dash_url") or context.get("media_url")
        hosts = {"reddit": ("v.redd.it",), "douyin": ("douyinvod.com", "douyin.com", "douyincdn.com", "snssdk.com", "bytecdn.cn", "ibytedtos.com"),
                 "xiaohongshu": ("xhscdn.com", "xiaohongshu.com"), "vimeo": ("player.vimeo.com",)}[adapter.name]
        if not allowed_url(download_url, hosts):
            raise MediaError("browser_read", "Browser exposed an unexpected media host", "media_host_rejected")
        if context.get("media_url"):
            base += ["--referer", "https://" + urlsplit(url).hostname + "/"]
            if context.get("user_agent"):
                base += ["--user-agent", context["user_agent"]]
        info = probe(base, download_url, args.timeout)
        info.update(id=context["id"], title=context["title"], duration=context.get("duration"))
        if context.get("media_url"):
            # Generic MP4 extraction does not know dimensions. The selected browser
            # does; check its dimensions, then check the downloaded file as well.
            if args.quality != "best" and (not context.get("height") or context["height"] > int(args.quality)):
                raise MediaError("browser_read", "Displayed video exceeds the selected cap or its height is unknown", "quality_limit")
            download_quality = "best"
            for fmt in info.get("formats") or []:
                fmt.update(width=context.get("width"), height=context.get("height"))
        browser_session_used = True
        expects_audio = bool(context.get("expects_audio"))
    else:
        info = probe(base, download_url, args.timeout)
    audio_status = source_audio_status(info, context)
    expects_audio = audio_status == "present"
    metadata = safe_metadata(info, adapter.name, url)
    result = {"ok": True, "action": args.action, "backend": adapter.backend,
              "downloader_version": run([ytdlp, "--version"], 15, "dependency").strip(),
              "cookies_used": bool(args.cookies_from_browser), "metadata": metadata, "files": []}
    result["browser_session_used"] = browser_session_used
    result["source_audio_expected"] = expects_audio
    result["source_audio_status"] = audio_status
    if args.action == "probe":
        return result
    if args.action == "subtitles" and not (metadata["subtitles"] or metadata["automatic_captions"]):
        raise MediaError("subtitles", "No subtitle tracks were exposed; this does not prove the website has none without login")
    root = Path(args.dir).expanduser().resolve()
    if any((ancestor / ".obsidian").is_dir() for ancestor in (root, *root.parents)):
        raise MediaError("validate", "Media output must be outside the Obsidian vault")
    root.mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix=adapter.name + "-", dir=root))
    try:
        command = download_command(base, download_url, directory, args.action, download_quality, args.sub_langs, args.caption_kind)
        if browser_session_used:
            # Generic direct-media IDs may be signed query strings. Never use
            # them as durable filenames, even when metadata was replaced above.
            command[command.index("--output") + 1] = "media.%(ext)s"
        command = command[:-2] + ["--max-filesize", str(getattr(args, "max_size_mib", 256)) + "M"] + command[-2:]
        run(command, args.timeout, "download")
        result["files"] = verified_files(directory, args.action, ffprobe, args.timeout, max_bytes=getattr(args, "max_size_mib", 256) * 1024 * 1024)
        if any(f.get("audio_present") for f in result["files"]):
            result["source_audio_status"] = "present"
        if expects_audio and args.action in ("video", "bundle") and not any(f.get("audio_present") for f in result["files"]):
            raise MediaError("verify", "The source exposes audio but the downloaded video lacks it", "source_audio_missing")
        if browser_session_used and args.quality != "best":
            if any(s.get("height", 0) > int(args.quality) for f in result["files"] for s in f.get("streams", [])):
                raise MediaError("verify", "Actual browser video exceeds the selected height cap", "quality_limit")
        result["captions_status"] = "downloaded" if any(f["kind"] == "subtitle" for f in result["files"]) else "not_downloaded"
        result["directory"] = str(directory)
        result["created_at"] = datetime.now(timezone.utc).isoformat()
        manifest = directory / "manifest.json"
        manifest.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        os.chmod(manifest, 0o600)
        return result
    except MediaError as exc:
        raise MediaError(exc.stage, f"{exc}; inspect retained files in {directory}", exc.code, exc.diagnostic) from None


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("doctor", "probe", "subtitles", "audio", "video", "bundle"))
    parser.add_argument("url", nargs="?")
    parser.add_argument("--dir", help="Required download directory outside the Obsidian vault")
    parser.add_argument("--quality", choices=("best", "2160", "1080", "720", "480"), default="720")
    parser.add_argument("--sub-langs", default="zh.*,ai-zh.*,en.*,-live_chat")
    parser.add_argument("--caption-kind", choices=("manual", "auto", "both"), default="both")
    parser.add_argument("--cookies-from-browser", choices=("chrome", "firefox", "safari", "edge", "brave", "chromium"), help="Use only with explicit authorization for that browser")
    parser.add_argument("--browser-profile", help="Explicitly authorized isolated browser profile; no automatic profile discovery")
    parser.add_argument("--browser-cdp", help="Explicitly authorized local platform browser CDP endpoint; cookies are never exported")
    parser.add_argument("--impersonate", choices=("chrome", "safari", "edge"), help="Use a reviewed installed curl_cffi browser compatibility target")
    parser.add_argument("--wechat-online", action="store_true", help="Explicit consent to send this public share URL to the selected fixed resolver only")
    parser.add_argument("--wechat-resolver", choices=("sph", "qiaomu"), default="sph", help="One fixed resolver; requires explicit user consent naming its domain, never automatic failover")
    parser.add_argument("--max-size-mib", type=int, default=256, help="Maximum accepted output file size in MiB; default 256; unknown-size transfers may exceed it before validation")
    parser.add_argument("--local-file", help="Import a user-supplied media file without contacting any platform or resolver")
    parser.add_argument("--timeout", type=int, default=600, help="Seconds per command; default 600")
    args = parser.parse_args(argv)
    if args.timeout < 1 or args.timeout > 7200:
        parser.error("--timeout must be between 1 and 7200 seconds")
    if args.max_size_mib < 1 or args.max_size_mib > 4096:
        parser.error("--max-size-mib must be between 1 and 4096")
    if args.action != "doctor" and not args.url:
        parser.error("URL is required")
    if args.action not in ("doctor", "probe") and not args.dir:
        parser.error("--dir is required for downloads")
    try:
        result = doctor() if args.action == "doctor" else acquire(args)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["ok"] else 1
    except (MediaError, ValueError, OSError) as exc:
        print(json.dumps({"ok": False, "stage": getattr(exc, "stage", "validate"), "code": getattr(exc, "code", "validate"), "error": str(exc), "diagnostic": getattr(exc, "diagnostic", None)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    sys.exit(main())
