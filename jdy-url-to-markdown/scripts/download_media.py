#!/usr/bin/env python3
"""Local media acquisition; Python stdlib + existing yt-dlp/FFmpeg executables.

No ASR, cloud upload, automatic install, browser automation or implicit cookies.
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

from adapters.media_platforms import ADAPTERS, public_source, resolve_platform

SUBTITLE_SUFFIXES = {".srt", ".vtt", ".ass", ".ssa", ".ttml", ".srv1", ".srv2", ".srv3", ".json", ".json3"}


class MediaError(RuntimeError):
    def __init__(self, stage: str, message: str):
        super().__init__(message)
        self.stage = stage


def classify_error(text: str) -> str:
    low = text.lower()
    if any(word in low for word in ("cookies", "sign in", "login", "log in", "captcha", "not a bot", "verification")):
        return "Login or verification required. Stop and arrange authorized access; no automatic cookie retry."
    if "drm" in low:
        return "DRM-protected media is unavailable to this workflow."
    if "requested format" in low:
        return "Requested format unavailable; probe formats before selecting another quality."
    if "unsupported url" in low:
        return "The installed downloader cannot extract this URL; platform routing alone does not establish download support."
    if any(word in low for word in ("403", "429", "412", "too many requests")):
        return "Platform denied or rate-limited the request. Stop; do not repeatedly retry or switch accounts."
    return "Downloader failed. Raw output is withheld because it can contain signed URLs or account data."


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
        raise MediaError(stage, classify_error(stderr + "\n" + stdout))
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
            "--fragment-retries", "0", "--no-progress", "--no-colors"]
    if browser:
        args += ["--cookies-from-browser", browser]
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
        selector = "bestvideo+bestaudio/best" if quality == "best" else f"bestvideo[height<={quality}]+bestaudio/best[height<={quality}]"
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


def verified_files(directory: Path, action: str, ffprobe: str | None, timeout: int) -> list[dict]:
    files = []
    for path in sorted(directory.iterdir()):
        if not path.is_file() or path.suffix in (".part", ".ytdl", ".temp"):
            continue
        size = path.stat().st_size
        if size == 0:
            raise MediaError("verify", "An empty output file was produced")
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
            required = {"audio"} if action == "audio" else {"audio", "video"}
            if not math.isfinite(duration) or duration <= 0 or not required.issubset(kinds):
                raise MediaError("verify", "Output lacks a valid duration or required media tracks")
            record.update(kind="audio" if action == "audio" else "video", duration_seconds=duration, streams=streams)
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


def acquire(args) -> dict:
    adapter, url = resolve_platform(args.url)
    if adapter.backend == "unavailable":
        raise MediaError("adapter", adapter.note)
    ytdlp = require_tool("yt-dlp")
    ffprobe = require_tool("ffprobe") if args.action != "probe" and args.action != "subtitles" else None
    base = base_command(ytdlp, args.cookies_from_browser)
    if args.action in ("video", "bundle"):
        base += ["--ffmpeg-location", require_tool("ffmpeg")]
    info = probe(base, url, args.timeout)
    metadata = safe_metadata(info, adapter.name, url)
    result = {"ok": True, "action": args.action, "backend": adapter.backend,
              "downloader_version": run([ytdlp, "--version"], 15, "dependency").strip(),
              "cookies_used": bool(args.cookies_from_browser), "metadata": metadata, "files": []}
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
        run(download_command(base, url, directory, args.action, args.quality, args.sub_langs, args.caption_kind), args.timeout, "download")
        result["files"] = verified_files(directory, args.action, ffprobe, args.timeout)
        result["captions_status"] = "downloaded" if any(f["kind"] == "subtitle" for f in result["files"]) else "not_downloaded"
        result["directory"] = str(directory)
        result["created_at"] = datetime.now(timezone.utc).isoformat()
        manifest = directory / "manifest.json"
        manifest.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        os.chmod(manifest, 0o600)
        return result
    except MediaError as exc:
        raise MediaError(exc.stage, f"{exc}; inspect retained files in {directory}") from None


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("doctor", "probe", "subtitles", "audio", "video", "bundle"))
    parser.add_argument("url", nargs="?")
    parser.add_argument("--dir", help="Required download directory outside the Obsidian vault")
    parser.add_argument("--quality", choices=("best", "2160", "1080", "720", "480"), default="720")
    parser.add_argument("--sub-langs", default="zh.*,ai-zh.*,en.*,-live_chat")
    parser.add_argument("--caption-kind", choices=("manual", "auto", "both"), default="both")
    parser.add_argument("--cookies-from-browser", choices=("chrome", "firefox", "safari", "edge", "brave", "chromium"), help="Use only with explicit authorization for that browser")
    parser.add_argument("--timeout", type=int, default=600, help="Seconds per command; default 600")
    args = parser.parse_args(argv)
    if args.timeout < 1 or args.timeout > 7200:
        parser.error("--timeout must be between 1 and 7200 seconds")
    if args.action != "doctor" and not args.url:
        parser.error("URL is required")
    if args.action not in ("doctor", "probe") and not args.dir:
        parser.error("--dir is required for downloads")
    try:
        result = doctor() if args.action == "doctor" else acquire(args)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["ok"] else 1
    except (MediaError, ValueError, OSError) as exc:
        print(json.dumps({"ok": False, "stage": getattr(exc, "stage", "validate"), "error": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    sys.exit(main())
