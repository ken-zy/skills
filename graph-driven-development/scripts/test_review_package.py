#!/usr/bin/env python3

import importlib.util
import hashlib
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
    def request(
        self,
        digest: str = "0" * 64,
        *,
        head: str = "a" * 40,
        diff: bytes = b"diff\n",
        context: bytes = b"context\n",
        algorithm: str = "graph-review-package-v1",
        sequence: int = 1,
    ) -> bytes:
        return (
            "review_request:\n"
            f"  package_sequence: {sequence}\n"
            f'  package_digest_algorithm: "{algorithm}"\n'
            f'  package_digest: "sha256:{digest}"\n'
            f'  full_diff_sha256: "{hashlib.sha256(diff).hexdigest()}"\n'
            f'  review_context_sha256: "{hashlib.sha256(context).hexdigest()}"\n'
            f'  head_commit: "{head}"\n'
            '  objective: "demo"\n'
        ).encode()

    def test_reference_vector(self):
        diff = b"diff --git a/a b/a\n"
        context = b"context\n"
        result = DIGEST.compute_package(
            head_sha="a" * 40,
            request=self.request(diff=diff, context=context),
            diff=diff,
            context=context,
        )
        self.assertEqual(
            "sha256:7e143cf45f3d8c6ed1e555fe9dcc9f2a5b1b75788e34c41e1bd5b6cf46d19c50",
            result["package_digest"],
        )

    def test_embedded_digest_does_not_change_canonical_package_digest(self):
        diff = b"diff\n"
        context = b"context\n"
        draft = DIGEST.compute_package(
            head_sha="a" * 40,
            request=self.request(diff=diff, context=context),
            diff=diff,
            context=context,
        )
        final = DIGEST.compute_package(
            head_sha="a" * 40,
            request=self.request(
                draft["package_digest"].removeprefix("sha256:"),
                diff=diff,
                context=context,
            ),
            diff=diff,
            context=context,
        )
        self.assertEqual(draft["package_digest"], final["package_digest"])
        self.assertNotEqual(draft["review_request_sha256"], final["review_request_sha256"])

    def test_one_byte_change_changes_package_digest(self):
        original_diff = b"diff\n"
        changed_diff = b"diff!\n"
        context = b"context\n"
        original = DIGEST.compute_package(
            head_sha="a" * 40,
            request=self.request(diff=original_diff, context=context),
            diff=original_diff,
            context=context,
        )
        changed = DIGEST.compute_package(
            head_sha="a" * 40,
            request=self.request(diff=changed_diff, context=context),
            diff=changed_diff,
            context=context,
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

    def test_rejects_top_level_request_self_hash(self):
        request = self.request() + (
            b'review_request_sha256: "' + b"f" * 64 + b'"\n'
        )
        with self.assertRaisesRegex(ValueError, "must not embed"):
            DIGEST.compute_package(
                head_sha="a" * 40,
                request=request,
                diff=b"diff\n",
                context=b"context\n",
            )

    def test_rejects_quoted_request_self_hash(self):
        request = self.request() + (
            b'"review_request_sha256": "' + b"f" * 64 + b'"\n'
        )
        with self.assertRaisesRegex(ValueError, "must not embed"):
            DIGEST.compute_package(
                head_sha="a" * 40,
                request=request,
                diff=b"diff\n",
                context=b"context\n",
            )

    def test_rejects_quoted_duplicate_review_request_root(self):
        request = self.request() + b'"review_request": {"objective": "shadow"}\n'
        with self.assertRaisesRegex(ValueError, "exactly one top-level review_request"):
            DIGEST.compute_package(
                head_sha="a" * 40,
                request=request,
                diff=b"diff\n",
                context=b"context\n",
            )

    def test_rejects_nested_package_digest(self):
        request = self.request().replace(
            b"  package_digest:",
            b"  metadata:\n    package_digest:",
        )
        with self.assertRaisesRegex(ValueError, "direct review_request.package_digest"):
            DIGEST.compute_package(
                head_sha="a" * 40,
                request=request,
                diff=b"diff\n",
                context=b"context\n",
            )

    def test_rejects_package_digest_inside_block_scalar(self):
        request = self.request().replace(
            b"  package_digest:",
            b"  notes: |\n    package_digest:",
        )
        with self.assertRaisesRegex(ValueError, "direct review_request.package_digest"):
            DIGEST.compute_package(
                head_sha="a" * 40,
                request=request,
                diff=b"diff\n",
                context=b"context\n",
            )

    def test_rejects_duplicate_package_digest_in_flow_mapping(self):
        request = self.request() + (
            b'metadata: {"package_digest": "sha256:' + b"f" * 64 + b'"}\n'
        )
        with self.assertRaisesRegex(ValueError, "direct review_request.package_digest"):
            DIGEST.compute_package(
                head_sha="a" * 40,
                request=request,
                diff=b"diff\n",
                context=b"context\n",
            )

    def test_rejects_stale_declared_head(self):
        with self.assertRaisesRegex(ValueError, "head_commit does not match"):
            DIGEST.compute_package(
                head_sha="a" * 40,
                request=self.request(head="b" * 40),
                diff=b"diff\n",
                context=b"context\n",
            )

    def test_rejects_stale_declared_diff_hash(self):
        with self.assertRaisesRegex(ValueError, "full_diff_sha256 does not match"):
            DIGEST.compute_package(
                head_sha="a" * 40,
                request=self.request(diff=b"old diff\n"),
                diff=b"diff\n",
                context=b"context\n",
            )

    def test_rejects_stale_declared_context_hash(self):
        with self.assertRaisesRegex(ValueError, "review_context_sha256 does not match"):
            DIGEST.compute_package(
                head_sha="a" * 40,
                request=self.request(context=b"old context\n"),
                diff=b"diff\n",
                context=b"context\n",
            )

    def test_rejects_wrong_algorithm(self):
        with self.assertRaisesRegex(ValueError, "package_digest_algorithm"):
            DIGEST.compute_package(
                head_sha="a" * 40,
                request=self.request(algorithm="graph-review-package-v0"),
                diff=b"diff\n",
                context=b"context\n",
            )

    def test_rejects_package_sequence_outside_budget(self):
        with self.assertRaisesRegex(ValueError, "package_sequence"):
            DIGEST.compute_package(
                head_sha="a" * 40,
                request=self.request(sequence=4),
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

    def commit_index(self, message: str) -> str:
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

    def test_forced_text_attribute_cannot_hide_binary_blob(self):
        (self.repo / ".gitattributes").write_text("*.bin diff\n", encoding="utf-8")
        (self.repo / "asset.bin").write_bytes(b"\x00one")
        base = self.commit_all("base")
        (self.repo / "asset.bin").write_bytes(b"\x00two")
        head = self.commit_all("head")
        full_diff = DIFF.expected_diff(self.repo, base, head)
        self.assertIn(b"\x00", full_diff)
        with self.assertRaisesRegex(ValueError, "binary changed paths block"):
            DIFF.validate_diff(
                repo=self.repo,
                base=base,
                head=head,
                supplied_diff=full_diff,
            )

    def test_ignore_submodules_config_cannot_hide_gitlink_change(self):
        (self.repo / "seed.txt").write_text("seed\n", encoding="utf-8")
        seed = self.commit_all("seed")
        self.git("update-index", "--add", "--cacheinfo", f"160000,{seed},vendor/sub")
        base = self.commit_index("base gitlink")
        self.git("update-index", "--cacheinfo", f"160000,{base},vendor/sub")
        head = self.commit_index("head gitlink")
        self.git("config", "diff.ignoreSubmodules", "all")
        full_diff = DIFF.expected_diff(self.repo, base, head)
        result = DIFF.validate_diff(
            repo=self.repo,
            base=base,
            head=head,
            supplied_diff=full_diff,
        )
        self.assertEqual(["vendor/sub"], result["changed_paths"])
        self.assertEqual(result["changed_paths"], result["diff_paths"])

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
