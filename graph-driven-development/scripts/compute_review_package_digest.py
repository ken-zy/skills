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
FORBIDDEN_SELF_HASH_RE = re.compile(
    rb"(?<![A-Za-z0-9_])[\"']?review_request_(?:canonical_)?sha256[\"']?[ \t]*:"
)
REQUEST_ROOT_RE = re.compile(rb"(?m)^review_request:[ ]*$")
REQUEST_KEY_TOKEN_RE = re.compile(
    rb"(?<![A-Za-z0-9_])(?P<quote>[\"']?)review_request(?P=quote)[ \t]*:"
)
SECURITY_FIELD_NAMES = (
    b"package_sequence",
    b"package_digest_algorithm",
    b"package_digest",
    b"full_diff_sha256",
    b"review_context_sha256",
    b"head_commit",
)
SECURITY_KEY_TOKEN_RE = re.compile(
    rb"(?<![A-Za-z0-9_])(?P<quote>[\"']?)(?P<name>"
    + rb"|".join(SECURITY_FIELD_NAMES)
    + rb")(?P=quote)[ \t]*:"
)
DIRECT_SECURITY_FIELD_RE = re.compile(
    rb"(?m)^  (?P<name>"
    + rb"|".join(SECURITY_FIELD_NAMES)
    + rb"):(?P<value>[^\r\n]*)$"
)


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _quoted_value(raw: bytes, name: str, inner: bytes) -> tuple[str, re.Match[bytes]]:
    match = re.fullmatch(rb'[ ]*"(?P<value>' + inner + rb')"[ ]*', raw)
    if match is None:
        raise ValueError(f"review_request.{name} must use the required quoted scalar form")
    return match.group("value").decode("ascii"), match


def _request_block_bounds(data: bytes) -> tuple[int, int]:
    roots = list(REQUEST_ROOT_RE.finditer(data))
    request_key_count = len(list(REQUEST_KEY_TOKEN_RE.finditer(data)))
    if len(roots) != 1 or request_key_count != 1:
        raise ValueError("review-request.yaml must contain exactly one top-level review_request mapping")
    root = roots[0]
    block_end = len(data)
    for line in re.finditer(rb"(?m)^(?P<content>[^\r\n]*)$", data[root.end() :]):
        content = line.group("content")
        if not content or content.lstrip().startswith(b"#"):
            continue
        if content[:1] not in (b" ", b"\t"):
            block_end = root.end() + line.start()
            break
    return root.end(), block_end


def _canonicalize_request(
    data: bytes,
    *,
    expected_head_sha: str | None = None,
    expected_full_diff_sha256: str | None = None,
    expected_review_context_sha256: str | None = None,
) -> tuple[bytes, str]:
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
    if FORBIDDEN_SELF_HASH_RE.search(data):
        raise ValueError("review-request.yaml must not embed its actual or canonical self hash")

    block_start, block_end = _request_block_bounds(data)
    occurrence_counts = {name.decode("ascii"): 0 for name in SECURITY_FIELD_NAMES}
    for match in SECURITY_KEY_TOKEN_RE.finditer(data):
        occurrence_counts[match.group("name").decode("ascii")] += 1

    fields: dict[str, re.Match[bytes]] = {}
    for match in DIRECT_SECURITY_FIELD_RE.finditer(data):
        name = match.group("name").decode("ascii")
        if name in fields:
            raise ValueError(f"review_request.{name} must appear exactly once")
        if match.start() <= block_start or match.start() >= block_end:
            raise ValueError(
                f"review-request.yaml requires one direct review_request.{name} field"
            )
        fields[name] = match

    for raw_name in SECURITY_FIELD_NAMES:
        name = raw_name.decode("ascii")
        if occurrence_counts[name] != 1 or name not in fields:
            raise ValueError(
                f"review-request.yaml requires one direct review_request.{name} field"
            )

    sequence_raw = fields["package_sequence"].group("value")
    sequence_match = re.fullmatch(rb"[ ]*(?P<value>[0-9]+)[ ]*", sequence_raw)
    if sequence_match is None or int(sequence_match.group("value")) not in (1, 2, 3):
        raise ValueError("review_request.package_sequence must be an integer from 1 through 3")

    algorithm, _ = _quoted_value(
        fields["package_digest_algorithm"].group("value"),
        "package_digest_algorithm",
        rb"[A-Za-z0-9-]+",
    )
    if algorithm != ALGORITHM:
        raise ValueError(f"review_request.package_digest_algorithm must be '{ALGORITHM}'")

    embedded, digest_value_match = _quoted_value(
        fields["package_digest"].group("value"),
        "package_digest",
        rb"sha256:(?P<digest>[0-9a-f]{64})",
    )
    embedded = embedded.removeprefix("sha256:")

    declared_head, _ = _quoted_value(
        fields["head_commit"].group("value"),
        "head_commit",
        rb"(?:[0-9a-f]{40}|[0-9a-f]{64})",
    )
    declared_diff, _ = _quoted_value(
        fields["full_diff_sha256"].group("value"),
        "full_diff_sha256",
        rb"[0-9a-f]{64}",
    )
    declared_context, _ = _quoted_value(
        fields["review_context_sha256"].group("value"),
        "review_context_sha256",
        rb"[0-9a-f]{64}",
    )

    for name, declared, expected in (
        ("head_commit", declared_head, expected_head_sha),
        ("full_diff_sha256", declared_diff, expected_full_diff_sha256),
        ("review_context_sha256", declared_context, expected_review_context_sha256),
    ):
        if expected is not None and declared != expected:
            raise ValueError(f"review_request.{name} does not match the supplied package input")

    value_start = fields["package_digest"].start("value")
    digest_start = value_start + digest_value_match.start("digest")
    digest_end = value_start + digest_value_match.end("digest")
    canonical = data[:digest_start] + ZERO_DIGEST.encode() + data[digest_end:]
    return canonical, embedded


def canonicalize_request(data: bytes) -> tuple[bytes, str]:
    return _canonicalize_request(data)


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
    if not HEAD_RE.fullmatch(head_sha):
        raise ValueError("head SHA must be 40 or 64 lowercase hexadecimal characters")
    full_diff_sha256 = sha256_hex(diff)
    review_context_sha256 = sha256_hex(context)
    canonical_request, embedded_digest = _canonicalize_request(
        request,
        expected_head_sha=head_sha,
        expected_full_diff_sha256=full_diff_sha256,
        expected_review_context_sha256=review_context_sha256,
    )
    request_canonical_sha256 = sha256_hex(canonical_request)
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
