#!/usr/bin/env python3
"""Compute a graph-review-package-v2 ID without editing package files."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


ALGORITHM = "graph-review-package-v2"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
HEAD_RE = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _object_without_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"review-request.json contains duplicate key: {key}")
        result[key] = value
    return result


def parse_request(data: bytes) -> dict[str, Any]:
    if data.startswith(b"\xef\xbb\xbf"):
        raise ValueError("review-request.json must not contain a UTF-8 BOM")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("review-request.json must be valid UTF-8") from exc
    try:
        parsed = json.loads(text, object_pairs_hook=_object_without_duplicate_keys)
    except json.JSONDecodeError as exc:
        raise ValueError(f"review-request.json is not valid JSON: {exc.msg}") from exc
    if not isinstance(parsed, dict) or not isinstance(parsed.get("review_request"), dict):
        raise ValueError("review-request.json must contain a top-level review_request object")
    return parsed["review_request"]


def build_manifest(
    *,
    head_sha: str,
    review_request_sha256: str,
    full_diff_sha256: str,
    review_context_sha256: str,
) -> bytes:
    if not HEAD_RE.fullmatch(head_sha):
        raise ValueError("head SHA must be 40 or 64 lowercase hexadecimal characters")
    for name, value in (
        ("review_request_sha256", review_request_sha256),
        ("full_diff_sha256", full_diff_sha256),
        ("review_context_sha256", review_context_sha256),
    ):
        if not SHA256_RE.fullmatch(value):
            raise ValueError(f"{name} must be 64 lowercase hexadecimal characters")
    return (
        f"{ALGORITHM}\n"
        f"head_sha={head_sha}\n"
        f"review_request_sha256={review_request_sha256}\n"
        f"full_diff_sha256={full_diff_sha256}\n"
        f"review_context_sha256={review_context_sha256}\n"
    ).encode("utf-8")


def package_id_from_hashes(
    *,
    head_sha: str,
    review_request_sha256: str,
    full_diff_sha256: str,
    review_context_sha256: str,
) -> str:
    manifest = build_manifest(
        head_sha=head_sha,
        review_request_sha256=review_request_sha256,
        full_diff_sha256=full_diff_sha256,
        review_context_sha256=review_context_sha256,
    )
    return f"sha256:{sha256_hex(manifest)}"


def compute_package(
    *, head_sha: str, request: bytes, diff: bytes, context: bytes
) -> dict[str, Any]:
    if not HEAD_RE.fullmatch(head_sha):
        raise ValueError("head SHA must be 40 or 64 lowercase hexadecimal characters")

    request_data = parse_request(request)
    if request_data.get("package_version") != ALGORITHM:
        raise ValueError(f"review_request.package_version must be '{ALGORITHM}'")
    sequence = request_data.get("package_sequence")
    if not isinstance(sequence, int) or isinstance(sequence, bool) or sequence < 1:
        raise ValueError("review_request.package_sequence must be a positive integer")
    if not HEAD_RE.fullmatch(request_data.get("base_commit", "")):
        raise ValueError(
            "review_request.base_commit must be 40 or 64 lowercase hexadecimal characters"
        )
    if request_data.get("head_commit") != head_sha:
        raise ValueError("review_request.head_commit does not match the supplied head")

    full_diff_sha256 = sha256_hex(diff)
    review_context_sha256 = sha256_hex(context)
    if request_data.get("full_diff_sha256") != full_diff_sha256:
        raise ValueError("review_request.full_diff_sha256 does not match full.diff")
    if request_data.get("review_context_sha256") != review_context_sha256:
        raise ValueError("review_request.review_context_sha256 does not match review-context.txt")

    review_request_sha256 = sha256_hex(request)
    package_id = package_id_from_hashes(
        head_sha=head_sha,
        review_request_sha256=review_request_sha256,
        full_diff_sha256=full_diff_sha256,
        review_context_sha256=review_context_sha256,
    )
    return {
        "algorithm": ALGORITHM,
        "head_sha": head_sha,
        "review_request_sha256": review_request_sha256,
        "full_diff_sha256": full_diff_sha256,
        "review_context_sha256": review_context_sha256,
        "package_id": package_id,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--head", required=True, help="Exact reviewed Git head SHA")
    parser.add_argument("--request", required=True, type=Path)
    parser.add_argument("--diff", required=True, type=Path)
    parser.add_argument("--context", required=True, type=Path)
    args = parser.parse_args(argv)

    try:
        result = compute_package(
            head_sha=args.head,
            request=args.request.read_bytes(),
            diff=args.diff.read_bytes(),
            context=args.context.read_bytes(),
        )
    except (OSError, ValueError) as exc:
        parser.exit(2, f"review package error: {exc}\n")

    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
