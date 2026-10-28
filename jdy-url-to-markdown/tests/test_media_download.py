"""Offline behavioral tests; never contact platforms or inspect browser sessions."""
import contextlib
import io
import json
import shutil
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import download_media as media
from adapters.media_platforms import public_source, resolve_platform


def options(action="probe", **values):
    import argparse
    args = dict(action=action, url="https://www.bilibili.com/video/BVfixture/?p=2&vd_source=tracking", dir=None,
                quality="720", sub_langs="zh.*,en.*,-live_chat", caption_kind="both", timeout=20, cookies_from_browser=None)
    args.update(values)
    return argparse.Namespace(**args)


class MediaTests(unittest.TestCase):
    def test_platforms_and_share_tokens(self):
        for url, name in [
            ("https://b23.tv/example", "bilibili"), ("https://youtu.be/id", "youtube"),
            ("https://music.youtube.com/watch?v=id", "youtube"), ("https://x.com/user/status/123", "x-twitter"),
            ("https://v.douyin.com/id/", "douyin"), ("https://www.iesdouyin.com/share/video/1", "douyin"),
            ("https://vm.tiktok.com/id", "tiktok"), ("https://xhslink.com/a/id", "xiaohongshu"),
            ("https://instagram.com/reel/id", "instagram"), ("https://fb.watch/id", "facebook"),
            ("https://player.vimeo.com/video/1", "vimeo"), ("https://clips.twitch.tv/id", "twitch"),
            ("https://redd.it/id", "reddit"), ("https://video.weibo.com/show?fid=id", "weibo"),
            ("https://www.acfun.cn/v/ac1", "acfun")]:
            with self.subTest(url=url):
                self.assertEqual(resolve_platform(url)[0].name, name)
        adapter, prepared = resolve_platform("https://www.xiaohongshu.com/explore/id?xsec_token=PRIVATE&xsec_source=pc")
        self.assertIn("xsec_token=PRIVATE", prepared)
        self.assertNotIn("PRIVATE", public_source(prepared))

    def test_host_boundaries_and_selected_part(self):
        for raw in ["https://bilibili.com.evil.test/video/id", "file:///tmp/a", "https://user:password@x.com/a", "http://youtube.com/a"]:
            with self.assertRaises(ValueError):
                resolve_platform(raw)
        self.assertEqual(resolve_platform(options().url)[1], "https://www.bilibili.com/video/BVfixture/?p=2")
        self.assertTrue(resolve_platform("https://bilibili.com/video/BVfixture/")[1].endswith("p=1"))
        with self.assertRaises(ValueError):
            resolve_platform("https://bilibili.com/video/BVfixture/?p=invalid")

    def test_unavailable_backends_do_not_execute_downloader(self):
        for url in ("https://weixin.qq.com/sph/id", "https://v.kuaishou.com/id"):
            with patch.object(media, "run") as runner, self.assertRaises(media.MediaError) as error:
                media.acquire(options(url=url))
            self.assertEqual(error.exception.stage, "adapter")
            runner.assert_not_called()

    def test_probe_redacts_media_urls_and_does_not_write(self):
        raw = {"id": "fixture", "title": "Title", "duration": 10, "http_headers": {"Cookie": "SECRET"},
               "formats": [{"format_id": "1", "url": "https://cdn.test/a?token=SECRET", "height": 720}],
               "subtitles": {"zh": [{"ext": "vtt", "url": "https://cdn.test/sub?token=SECRET"}]}}
        with patch.object(media, "require_tool", return_value="yt-dlp"), patch.object(media, "run", side_effect=[json.dumps(raw), "2026.01.01"]), patch.object(media.tempfile, "mkdtemp") as mkdir:
            result = media.acquire(options())
        self.assertTrue(result["ok"])
        self.assertEqual(result["metadata"]["subtitles"], [{"language": "zh", "formats": ["vtt"]}])
        self.assertNotIn("SECRET", json.dumps(result))
        self.assertFalse(result["cookies_used"])
        mkdir.assert_not_called()

    def test_download_command_is_scoped_and_does_not_relax_quality(self):
        base = media.base_command("yt-dlp")
        self.assertIn("--ignore-config", base)
        self.assertIn("--no-cookies-from-browser", base)
        self.assertNotIn("--cookies-from-browser", base)
        cmd = media.download_command(base, "https://x.com/a/status/1", Path("/tmp/a b"), "video", "720", "zh.*", "both")
        self.assertEqual(cmd[cmd.index("--format") + 1], "bestvideo[height<=720]+bestaudio/best[height<=720]")
        self.assertEqual(cmd[-2:], ["--", "https://x.com/a/status/1"])
        self.assertIn("/tmp/a b", cmd)
        self.assertNotIn("--write-subs", cmd)
        audio = media.download_command(base, cmd[-1], Path("/tmp/a"), "audio", "best", "zh.*", "both")
        self.assertEqual(audio[audio.index("--format") + 1], "bestaudio")
        self.assertNotIn("--extract-audio", audio)
        subs = media.download_command(base, cmd[-1], Path("/tmp/a"), "subtitles", "720", "zh.*", "manual")
        self.assertIn("--skip-download", subs)
        self.assertIn("--write-subs", subs)
        self.assertNotIn("--write-auto-subs", subs)

    def test_subtitles_are_verified_and_missing_is_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(media.MediaError):
                media.verified_files(root, "subtitles", None, 10)
            path = root / "fixture.zh.vtt"
            path.write_text("WEBVTT\n\n00:00:01.000 --> 00:00:02.000\n测试字幕\n")
            files = media.verified_files(root, "subtitles", None, 10)
            self.assertEqual(files[0]["cues"], 1)
            self.assertEqual(len(files[0]["sha256"]), 64)
            path.write_text("<html>login page</html>")
            with self.assertRaises(media.MediaError):
                media.verified_files(root, "subtitles", None, 10)
            path.write_text("WEBVTT\n\n00:00:03.000 --> 00:00:02.000\nReversed timing\n")
            self.assertEqual(media.subtitle_entries(path), 0)
            path.write_text("WEBVTT\n\n00:00:01.000 --> 00:00:02.000\n\n")
            self.assertEqual(media.subtitle_entries(path), 0)
            path.unlink()
            (root / "fixture.ttml").write_text("<broken")
            self.assertEqual(media.subtitle_entries(root / "fixture.ttml"), 0)

    def test_native_json_captions_keep_valid_time_ranges(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixture.zh.json"
            path.write_text(json.dumps({"body": [{"from": 1.25, "to": 2.5, "content": "原字幕"}]}))
            self.assertEqual(media.subtitle_entries(path), 1)
            path.write_text(json.dumps({"body": [{"from": 3, "to": 2, "content": "坏时间轴"}]}))
            self.assertEqual(media.subtitle_entries(path), 0)

    def test_no_captions_does_not_start_download(self):
        with patch.object(media, "require_tool", return_value="yt-dlp"), patch.object(media, "probe", return_value={"id": "id", "title": "title"}), patch.object(media, "run", return_value="2026.01.01") as runner:
            with self.assertRaisesRegex(media.MediaError, "No subtitle tracks"):
                media.acquire(options("subtitles", dir="/tmp/unwritten"))
            self.assertEqual(runner.call_count, 1)  # version only

    def test_download_cannot_succeed_with_only_metadata_or_partial_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "fixture.mp4.part").write_bytes(b"partial")
            with self.assertRaises(media.MediaError):
                media.verified_files(root, "video", "ffprobe", 10)

    def test_download_records_verified_files(self):
        with tempfile.TemporaryDirectory() as directory:
            def fake_run(argv, timeout, stage):
                if stage == "dependency":
                    return "2026.01.01"
                if stage == "download":
                    destination = Path(argv[argv.index("--paths") + 1])
                    (destination / "fixture.m4a").write_bytes(b"audio fixture")
                    return ""
                if stage == "verify":
                    return json.dumps({"format": {"duration": "10.5"}, "streams": [{"codec_type": "audio", "codec_name": "aac"}]})
                raise AssertionError(stage)
            with patch.object(media, "require_tool", side_effect=lambda name: name), patch.object(media, "probe", return_value={"id": "fixture", "title": "title"}), patch.object(media, "run", side_effect=fake_run):
                result = media.acquire(options("audio", dir=directory))
            self.assertTrue(result["ok"])
            self.assertEqual(result["files"][0]["duration_seconds"], 10.5)
            manifest = Path(result["directory"]) / "manifest.json"
            self.assertEqual(json.loads(manifest.read_text())["files"], result["files"])

    def test_video_requires_audio_and_video_tracks(self):
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / "fixture.mp4").write_bytes(b"fake")
            with patch.object(media, "run", return_value=json.dumps({"format": {"duration": "10"}, "streams": [{"codec_type": "video"}]})):
                with self.assertRaisesRegex(media.MediaError, "required media tracks"):
                    media.verified_files(Path(directory), "video", "ffprobe", 10)

    def test_multi_video_and_live_guard(self):
        with self.assertRaises(media.MediaError):
            media.one_video({"entries": [{"id": "a", "title": "a"}, {"id": "b", "title": "b"}]})
        with self.assertRaises(media.MediaError):
            media.one_video({"id": "a", "title": "a", "is_live": True})
        self.assertEqual(media.one_video({"entries": [{"id": "a", "title": "a"}]})["id"], "a")

    def test_error_output_with_signed_url_is_not_exposed(self):
        with self.assertRaises(media.MediaError) as error:
            media.run([sys.executable, "-c", "import sys; sys.stderr.write('HTTP 403 https://cdn.test/a?token=SECRET'); sys.exit(1)"], 5, "download")
        self.assertNotIn("SECRET", str(error.exception))
        self.assertIn("denied", str(error.exception))

    def test_process_timeout_and_cli_validation(self):
        with self.assertRaisesRegex(media.MediaError, "timed out"):
            media.run([sys.executable, "-c", "import time; time.sleep(10)"], 0.05, "probe")
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = media.main(["probe", "https://unsupported.test/a"])
        self.assertEqual(code, 1)
        self.assertFalse(json.loads(output.getvalue())["ok"])

    @unittest.skipUnless(shutil.which("yt-dlp"), "yt-dlp not installed; no automatic installation")
    def test_installed_ytdlp_accepts_base_options_without_network(self):
        output = media.run(media.base_command(shutil.which("yt-dlp")) + ["--list-extractors"], 15, "dependency")
        self.assertIn("BiliBili", output)

    def test_media_output_cannot_enter_vault(self):
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / ".obsidian").mkdir()
            with patch.object(media, "require_tool", side_effect=lambda name: name), patch.object(media, "probe", return_value={"id": "id", "title": "title"}), patch.object(media, "run", return_value="2026.01.01"):
                with self.assertRaisesRegex(media.MediaError, "outside the Obsidian vault"):
                    media.acquire(options("audio", dir=str(Path(directory) / "media")))


if __name__ == "__main__":
    unittest.main()
