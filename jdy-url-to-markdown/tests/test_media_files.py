"""Opt-in real file/CLI smoke tests, using synthetic media and an offline downloader.

Run on the selected execution host:
python3 -m unittest discover -s tests -p 'test_media_files.py' -v
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import wave

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import download_media as media


@unittest.skipUnless(media.find_tool("ffmpeg") and media.find_tool("ffprobe"), "Existing FFmpeg tools required")
class RealFileTests(unittest.TestCase):
    def test_real_audio_and_video_tracks_and_invalid_media(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            audio = root / "audio"
            audio.mkdir()
            with wave.open(str(audio / "fixture.wav"), "wb") as handle:
                handle.setparams((1, 2, 16000, 16000, "NONE", "not compressed"))
                handle.writeframes(b"\0\0" * 16000)
            files = media.verified_files(audio, "audio", media.find_tool("ffprobe"), 20)
            self.assertAlmostEqual(files[0]["duration_seconds"], 1.0, places=2)
            video = root / "video"
            video.mkdir()
            media.run([media.find_tool("ffmpeg"), "-nostdin", "-v", "error", "-f", "lavfi", "-i", "color=c=black:s=64x64:r=10:d=1",
                       "-i", str(audio / "fixture.wav"), "-shortest", "-c:v", "mpeg4", "-c:a", "aac", str(video / "fixture.mp4")], 30, "fixture")
            files = media.verified_files(video, "video", media.find_tool("ffprobe"), 20)
            self.assertEqual({s["codec_type"] for s in files[0]["streams"]}, {"audio", "video"})
            (video / "fixture.mp4").write_text("<html>not a video</html>")
            with self.assertRaises(media.MediaError):
                media.verified_files(video, "video", media.find_tool("ffprobe"), 20)

    def test_full_cli_writes_manifest_from_offline_downloader(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            binary = root / "bin"
            binary.mkdir()
            fixture = root / "fixture.wav"
            with wave.open(str(fixture), "wb") as handle:
                handle.setparams((1, 2, 16000, 16000, "NONE", "not compressed"))
                handle.writeframes(b"\0\0" * 16000)
            fake = binary / "yt-dlp"
            fake.write_text(f"#!{sys.executable}\n" + '''import sys, json, os, shutil
from pathlib import Path
if '--version' in sys.argv:
    print('offline-test-fixture')
elif '--dump-single-json' in sys.argv:
    print(json.dumps({'id':'fixture','title':'Offline fixture','duration':1}))
else:
    destination = Path(sys.argv[sys.argv.index('--paths') + 1])
    shutil.copyfile(os.environ['MEDIA_TEST_FIXTURE'], destination / 'fixture.wav')
''')
            fake.chmod(0o700)
            env = dict(os.environ, PATH=str(binary) + os.pathsep + os.environ.get("PATH", ""), MEDIA_TEST_FIXTURE=str(fixture))
            proc = subprocess.run([sys.executable, str(Path(media.__file__)), "audio", "https://www.bilibili.com/video/BVfixture/",
                                   "--dir", str(root / "output")], env=env, capture_output=True, text=True, timeout=30)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            result = json.loads(proc.stdout)
            self.assertTrue(result["ok"])
            self.assertEqual(result["downloader_version"], "offline-test-fixture")
            self.assertEqual(result["files"][0]["kind"], "audio")
            self.assertTrue((Path(result["directory"]) / "manifest.json").is_file())


if __name__ == "__main__":
    unittest.main()
