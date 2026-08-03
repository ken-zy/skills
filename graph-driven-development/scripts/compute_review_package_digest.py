#!/usr/bin/env python3
"""Compute or verify a graph-review-package-v1 digest without editing files."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


ALGORITHM = "graph-review-package-v1"
ZERO_DIGEST = "0" * 64
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
HEAD_RE = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")
PACKAGE_LINE_RE = re.compile(
    rb'(?m)^(?P<prefix>[ \t]+package_digest:[ \t]+"sha256:)'
    rb'(?P<digest>[0-9a-f]{64})(?P<suffix>"[ \t]*)$'
)


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonicalize_request(data: bytes) -> tuple[bytes, str]:
    if data.startswith(b"\xef\xbb\xbf"):
        raise ValueError("review-request.yaml must not contain a UTF-8 BOM")
    if b"\r" in data:
        raise ValueError("review-request.yaml must use LF line endings")
    if not data.endswith(b"\n"):
        raise ValueError("review-request.yaml must end with LF")
    try:
        data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("review-request.yaml must be valid UTF-8") from exc

    matches = list(PACKAGE_LINE_RE.finditer(data))
    if len(matches) != 1:
        raise ValueError(
            "review-request.yaml must contain exactly one quoted "
            "package_digest sha256 scalar"
        )
    match = matches[0]
    embedded = match.group("digest").decode("ascii")
    canonical = data[: match.start("digest")] + ZERO_DIGEST.encode() + data[match.end("digest") :]
    return canonical, embedded


def build_manifest(
    *,
    head_sha: str,
    request_canonical_sha256: str,
    full_diff_sha256: str,
    review_context_sha256: str,
) -> bytes:
    if not HEAD_RE.fullmatch(head_sha):
        raise ValueError("head SHA must be 40 or 64 lowercase hexadecimal characters")
    for name, value in (
        ("review_request_canonical_sha256", request_canonical_sha256),
        ("full_diff_sha256", full_diff_sha256),
        ("review_context_sha256", review_context_sha256),
    ):
        if not SHA256_RE.fullmatch(value):
            raise ValueError(f"{name} must be 64 lowercase hexadecimal characters")

    return (
        f"{ALGORITHM}\n"
        f"head_sha={head_sha}\n"
        f"review_request_canonical_sha256={request_canonical_sha256}\n"
        f"full_diff_sha256={full_diff_sha256}\n"
        f"review_context_sha256={review_context_sha256}\n"
    ).encode("utf-8")


def digest_from_hashes(
    *,
    head_sha: str,
    request_canonical_sha256: str,
    full_diff_sha256: str,
    review_context_sha256: str,
) -> str:
    manifest = build_manifest(
        head_sha=head_sha,
        request_canonical_sha256=request_canonical_sha256,
        full_diff_sha256=full_diff_sha256,
        review_context_sha256=review_context_sha256,
    )
    return f"sha256:{sha256_hex(manifest)}"


def compute_package(
    *, head_sha: str, request: bytes, diff: bytes, context: bytes
) -> dict[str, Any]:
    canonical_request, embedded_digest = canonicalize_request(request)
    request_canonical_sha256 = sha256_hex(canonical_request)
    full_diff_sha256 = sha256_hex(diff)
    review_context_sha256 = sha256_hex(context)
    package_digest = digest_from_hashes(
        head_sha=head_sha,
        request_canonical_sha256=request_canonical_sha256,
        full_diff_sha256=full_diff_sha256,
        review_context_sha256=review_context_sha256,
    )
    return {
        "algorithm": ALGORITHM,
        "head_sha": head_sha,
        "review_request_sha256": sha256_hex(request),
        "review_request_canonical_sha256": request_canonical_sha256,
        "full_diff_sha256": full_diff_sha256,
        "review_context_sha256": review_context_sha256,
        "package_digest": package_digest,
        "embedded_package_digest": f"sha256:{embedded_digest}",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--head", required=True, help="Exact reviewed Git head SHA")
    parser.add_argument("--request", required=True, type=Path)
    parser.add_argument("--diff", required=True, type=Path)
    parser.add_argument("--context", required=True, type=Path)
    parser.add_argument(
        "--verify-embedded",
        action="store_true",
        help="Fail unless review-request.yaml contains the computed package digest",
    )
    args = parser.parse_args(argv)

    try:
        result = compute_package(
            head_sha=args.head,
            request=args.request.read_bytes(),
            diff=args.diff.read_bytes(),
            context=args.context.read_bytes(),
        )
    except (OSError, ValueError) as exc:
        parser.exit(2, f"review package digest error: {exc}\n")

    if args.verify_embedded and result["embedded_package_digest"] != result["package_digest"]:
        parser.exit(
            1,
            "review package digest mismatch: embedded "
            f"{result['embedded_package_digest']} != computed {result['package_digest']}\n",
        )

    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
