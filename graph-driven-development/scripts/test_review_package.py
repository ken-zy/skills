#!/usr/bin/env python3

import importlib.util
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


SCRIPTS_DIR = Path(__file__).parent


def load_module(name: str):
    path = SCRIPTS_DIR / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


DIGEST = load_module("compute_review_package_digest")
DIFF = load_module("validate_review_diff")


class ReviewPackageDigestTests(unittest.TestCase):
    def request(self, digest: str = "0" * 64) -> bytes:
        return (
            "review_request:\n"
            f'  package_digest: "sha256:{digest}"\n'
            '  objective: "demo"\n'
        ).encode()

    def test_reference_vector(self):
        result = DIGEST.compute_package(
            head_sha="a" * 40,
            request=self.request(),
            diff=b"diff --git a/a b/a\n",
            context=b"context\n",
        )
        self.assertEqual(
            "sha256:9347105c5cfa21d55154d6dbc67c15202b4d21a43b543cf58611583c121f3251",
            result["package_digest"],
        )

    def test_embedded_digest_does_not_change_canonical_package_digest(self):
        draft = DIGEST.compute_package(
            head_sha="a" * 40,
            request=self.request(),
            diff=b"diff\n",
            context=b"context\n",
        )
        final = DIGEST.compute_package(
            head_sha="a" * 40,
            request=self.request(draft["package_digest"].removeprefix("sha256:")),
            diff=b"diff\n",
            context=b"context\n",
        )
        self.assertEqual(draft["package_digest"], final["package_digest"])
        self.assertNotEqual(draft["review_request_sha256"], final["review_request_sha256"])

    def test_one_byte_change_changes_package_digest(self):
        original = DIGEST.compute_package(
            head_sha="a" * 40,
            request=self.request(),
            diff=b"diff\n",
            context=b"context\n",
        )
        changed = DIGEST.compute_package(
            head_sha="a" * 40,
            request=self.request(),
            diff=b"diff!\n",
            context=b"context\n",
        )
        self.assertNotEqual(original["package_digest"], changed["package_digest"])

    def test_rejects_crlf_request(self):
        with self.assertRaisesRegex(ValueError, "LF line endings"):
            DIGEST.compute_package(
                head_sha="a" * 40,
                request=self.request().replace(b"\n", b"\r\n"),
                diff=b"diff\n",
                context=b"context\n",
            )

    def test_rejects_embedded_request_self_hash(self):
        request = self.request() + (
            b'  review_request_canonical_sha256: "' + b"f" * 64 + b'"\n'
        )
        with self.assertRaisesRegex(ValueError, "must not embed"):
            DIGEST.compute_package(
                head_sha="a" * 40,
                request=request,
                diff=b"diff\n",
                context=b"context\n",
            )


class ReviewDiffTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        self.git("init", "-q")
        self.git("config", "user.email", "review-package@example.invalid")
        self.git("config", "user.name", "Review Package Test")

    def tearDown(self):
        self.temp.cleanup()

    def git(self, *args: str) -> bytes:
        return subprocess.check_output(["git", "-C", str(self.repo), *args])

    def commit_all(self, message: str) -> str:
        self.git("add", "-A")
        self.git("commit", "-q", "-m", message)
        return self.git("rev-parse", "HEAD").decode().strip()

    def test_complete_text_diff_passes(self):
        (self.repo / "a.txt").write_text("one\n", encoding="utf-8")
        base = self.commit_all("base")
        (self.repo / "a.txt").write_text("two\n", encoding="utf-8")
        head = self.commit_all("head")
        full_diff = DIFF.expected_diff(self.repo, base, head)
        result = DIFF.validate_diff(
            repo=self.repo,
            base=base,
            head=head,
            supplied_diff=full_diff,
        )
        self.assertTrue(result["complete"])
        self.assertEqual(["a.txt"], result["changed_paths"])
        self.assertEqual(result["changed_paths"], result["diff_paths"])

    @unittest.skipUnless(hasattr(os, "symlink"), "symlinks unsupported")
    def test_symlink_target_change_is_included(self):
        os.symlink("one", self.repo / "link")
        base = self.commit_all("base")
        (self.repo / "link").unlink()
        os.symlink("two", self.repo / "link")
        head = self.commit_all("head")
        full_diff = DIFF.expected_diff(self.repo, base, head)
        result = DIFF.validate_diff(
            repo=self.repo,
            base=base,
            head=head,
            supplied_diff=full_diff,
        )
        self.assertEqual(["link"], result["symlink_paths"])
        self.assertIn(b"-one", full_diff)
        self.assertIn(b"+two", full_diff)

    def test_binary_change_fails_closed(self):
        (self.repo / "asset.bin").write_bytes(b"\x00one")
        base = self.commit_all("base")
        (self.repo / "asset.bin").write_bytes(b"\x00two")
        head = self.commit_all("head")
        full_diff = DIFF.expected_diff(self.repo, base, head)
        with self.assertRaisesRegex(ValueError, "binary changed paths block"):
            DIFF.validate_diff(
                repo=self.repo,
                base=base,
                head=head,
                supplied_diff=full_diff,
            )

    def test_truncated_diff_is_rejected(self):
        (self.repo / "a.txt").write_text("one\n", encoding="utf-8")
        base = self.commit_all("base")
        (self.repo / "a.txt").write_text("two\n", encoding="utf-8")
        head = self.commit_all("head")
        with self.assertRaisesRegex(ValueError, "do not equal"):
            DIFF.validate_diff(
                repo=self.repo,
                base=base,
                head=head,
                supplied_diff=b"",
            )


if __name__ == "__main__":
    unittest.main()
