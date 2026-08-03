#!/usr/bin/env python3

import hashlib
import importlib.util
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent


def load_module(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPT_DIR / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


DIGEST = load_module("compute_review_package_digest")
DIFF = load_module("validate_review_diff")


class ReviewPackageDigestTests(unittest.TestCase):
    def request(
        self,
        *,
        head: str = "a" * 40,
        diff: bytes = b"diff\n",
        context: bytes = b"context\n",
        version: str = "graph-review-package-v2",
        sequence: int = 1,
    ) -> bytes:
        request = {
            "review_request": {
                "package_version": version,
                "package_sequence": sequence,
                "base_commit": "b" * 40,
                "head_commit": head,
                "full_diff_sha256": hashlib.sha256(diff).hexdigest(),
                "review_context_sha256": hashlib.sha256(context).hexdigest(),
                "objective": "demo",
            }
        }
        return (json.dumps(request, sort_keys=True, indent=2) + "\n").encode()

    def test_reference_vector(self):
        diff = b"diff --git a/a b/a\n"
        context = b"context\n"
        result = DIGEST.compute_package(
            head_sha="a" * 40,
            request=self.request(diff=diff, context=context),
            diff=diff,
            context=context,
        )
        self.assertEqual("graph-review-package-v2", result["algorithm"])
        self.assertRegex(result["package_id"], r"^sha256:[0-9a-f]{64}$")

    def test_mutating_any_input_changes_package_id(self):
        diff = b"diff\n"
        context = b"context\n"
        request = self.request(diff=diff, context=context)
        original = DIGEST.compute_package(
            head_sha="a" * 40, request=request, diff=diff, context=context
        )
        changed_request = self.request(diff=diff, context=context).replace(b'"demo"', b'"demo2"')
        request_result = DIGEST.compute_package(
            head_sha="a" * 40,
            request=changed_request,
            diff=diff,
            context=context,
        )
        changed_diff = b"diff!\n"
        diff_result = DIGEST.compute_package(
            head_sha="a" * 40,
            request=self.request(diff=changed_diff, context=context),
            diff=changed_diff,
            context=context,
        )
        changed_context = b"context!\n"
        context_result = DIGEST.compute_package(
            head_sha="a" * 40,
            request=self.request(diff=diff, context=changed_context),
            diff=diff,
            context=changed_context,
        )
        changed_head = "c" * 40
        head_result = DIGEST.compute_package(
            head_sha=changed_head,
            request=self.request(head=changed_head, diff=diff, context=context),
            diff=diff,
            context=context,
        )
        self.assertEqual(
            5,
            len(
                {
                    original["package_id"],
                    request_result["package_id"],
                    diff_result["package_id"],
                    context_result["package_id"],
                    head_result["package_id"],
                }
            ),
        )

    def test_package_sequence_can_continue_after_default_threshold(self):
        result = DIGEST.compute_package(
            head_sha="a" * 40,
            request=self.request(sequence=4),
            diff=b"diff\n",
            context=b"context\n",
        )
        self.assertRegex(result["package_id"], r"^sha256:[0-9a-f]{64}$")

    def test_rejects_duplicate_json_keys(self):
        request = (
            '{"review_request":{"package_version":"graph-review-package-v2",'
            '"package_sequence":1,"package_sequence":2}}\n'
        ).encode()
        with self.assertRaisesRegex(ValueError, "duplicate key"):
            DIGEST.compute_package(
                head_sha="a" * 40,
                request=request,
                diff=b"diff\n",
                context=b"context\n",
            )

    def test_rejects_stale_declared_head(self):
        with self.assertRaisesRegex(ValueError, "head_commit"):
            DIGEST.compute_package(
                head_sha="a" * 40,
                request=self.request(head="b" * 40),
                diff=b"diff\n",
                context=b"context\n",
            )

    def test_rejects_stale_declared_hashes(self):
        with self.assertRaisesRegex(ValueError, "full_diff_sha256"):
            DIGEST.compute_package(
                head_sha="a" * 40,
                request=self.request(diff=b"old\n"),
                diff=b"diff\n",
                context=b"context\n",
            )
        with self.assertRaisesRegex(ValueError, "review_context_sha256"):
            DIGEST.compute_package(
                head_sha="a" * 40,
                request=self.request(context=b"old\n"),
                diff=b"diff\n",
                context=b"context\n",
            )

    def test_rejects_wrong_version_and_nonpositive_sequence(self):
        with self.assertRaisesRegex(ValueError, "package_version"):
            DIGEST.compute_package(
                head_sha="a" * 40,
                request=self.request(version="graph-review-package-v1"),
                diff=b"diff\n",
                context=b"context\n",
            )
        with self.assertRaisesRegex(ValueError, "positive integer"):
            DIGEST.compute_package(
                head_sha="a" * 40,
                request=self.request(sequence=0),
                diff=b"diff\n",
                context=b"context\n",
            )

    def test_rejects_missing_base_commit(self):
        request = json.loads(self.request())
        del request["review_request"]["base_commit"]
        with self.assertRaisesRegex(ValueError, "base_commit"):
            DIGEST.compute_package(
                head_sha="a" * 40,
                request=json.dumps(request).encode(),
                diff=b"diff\n",
                context=b"context\n",
            )


class ReviewDiffTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        subprocess.run(["git", "-C", str(self.repo), "config", "user.name", "Test"], check=True)
        subprocess.run(
            ["git", "-C", str(self.repo), "config", "user.email", "test@example.com"],
            check=True,
        )

    def tearDown(self):
        self.temp.cleanup()

    def commit(self, message: str) -> str:
        subprocess.run(["git", "-C", str(self.repo), "add", "-A"], check=True)
        subprocess.run(["git", "-C", str(self.repo), "commit", "-qm", message], check=True)
        return subprocess.check_output(
            ["git", "-C", str(self.repo), "rev-parse", "HEAD"], text=True
        ).strip()

    def test_complete_text_diff_passes(self):
        (self.repo / "a.txt").write_text("one\n")
        base = self.commit("base")
        (self.repo / "a.txt").write_text("two\n")
        head = self.commit("head")
        patch = DIFF.expected_diff(self.repo, base, head)
        result = DIFF.validate_diff(repo=self.repo, base=base, head=head, supplied_diff=patch)
        self.assertTrue(result["complete"])
        self.assertEqual(["a.txt"], result["changed_paths"])
        self.assertEqual([], result["binary_evidence"])

    def test_symlink_target_change_is_included(self):
        os.symlink("one", self.repo / "link")
        base = self.commit("base")
        (self.repo / "link").unlink()
        os.symlink("two", self.repo / "link")
        head = self.commit("head")
        patch = DIFF.expected_diff(self.repo, base, head)
        result = DIFF.validate_diff(repo=self.repo, base=base, head=head, supplied_diff=patch)
        self.assertEqual(["link"], result["symlink_paths"])

    def test_binary_change_is_reported_not_rejected(self):
        (self.repo / "asset.bin").write_bytes(b"a\x00b")
        base = self.commit("base")
        (self.repo / "asset.bin").write_bytes(b"c\x00d")
        head = self.commit("head")
        patch = DIFF.expected_diff(self.repo, base, head)
        result = DIFF.validate_diff(repo=self.repo, base=base, head=head, supplied_diff=patch)
        self.assertEqual(["asset.bin"], result["binary_paths"])
        evidence = result["binary_evidence"][0]
        self.assertEqual("asset.bin", evidence["path"])
        self.assertRegex(evidence["old_object"], r"^[0-9a-f]{40,64}$")
        self.assertRegex(evidence["new_object"], r"^[0-9a-f]{40,64}$")

    def test_forced_text_attribute_cannot_hide_binary_blob(self):
        (self.repo / ".gitattributes").write_text("*.bin diff\n")
        (self.repo / "asset.bin").write_bytes(b"a\x00b")
        base = self.commit("base")
        (self.repo / "asset.bin").write_bytes(b"c\x00d")
        head = self.commit("head")
        patch = DIFF.expected_diff(self.repo, base, head)
        result = DIFF.validate_diff(repo=self.repo, base=base, head=head, supplied_diff=patch)
        self.assertEqual(["asset.bin"], result["binary_paths"])

    def test_ignore_submodules_config_cannot_hide_gitlink_change(self):
        other = self.repo.parent / f"{self.repo.name}-sub"
        subprocess.run(["git", "init", "-q", str(other)], check=True)
        subprocess.run(["git", "-C", str(other), "config", "user.name", "Test"], check=True)
        subprocess.run(
            ["git", "-C", str(other), "config", "user.email", "test@example.com"],
            check=True,
        )
        (other / "x").write_text("one\n")
        subprocess.run(["git", "-C", str(other), "add", "x"], check=True)
        subprocess.run(["git", "-C", str(other), "commit", "-qm", "one"], check=True)
        subprocess.run(
            [
                "git",
                "-c",
                "protocol.file.allow=always",
                "-C",
                str(self.repo),
                "submodule",
                "add",
                "-q",
                str(other),
                "sub",
            ],
            check=True,
        )
        base = self.commit("base")
        (other / "x").write_text("two\n")
        subprocess.run(["git", "-C", str(other), "commit", "-qam", "two"], check=True)
        sub_branch = subprocess.run(
            ["git", "-C", str(other), "branch", "--show-current"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        subprocess.run(
            ["git", "-C", str(self.repo / "sub"), "fetch", "-q", "origin"], check=True
        )
        subprocess.run(
            [
                "git",
                "-C",
                str(self.repo / "sub"),
                "checkout",
                "-q",
                f"origin/{sub_branch}",
            ],
            check=True,
        )
        head = self.commit("head")
        subprocess.run(
            ["git", "-C", str(self.repo), "config", "diff.ignoreSubmodules", "all"],
            check=True,
        )
        patch = DIFF.expected_diff(self.repo, base, head)
        result = DIFF.validate_diff(repo=self.repo, base=base, head=head, supplied_diff=patch)
        self.assertEqual(["sub"], result["changed_paths"])

    def test_truncated_diff_is_rejected(self):
        (self.repo / "a.txt").write_text("one\n")
        base = self.commit("base")
        (self.repo / "a.txt").write_text("two\n")
        head = self.commit("head")
        patch = DIFF.expected_diff(self.repo, base, head)
        with self.assertRaisesRegex(ValueError, "do not equal"):
            DIFF.validate_diff(repo=self.repo, base=base, head=head, supplied_diff=patch[:-1])


if __name__ == "__main__":
    unittest.main()
