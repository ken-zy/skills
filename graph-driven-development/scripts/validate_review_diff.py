#!/usr/bin/env python3
"""Validate that full.diff exactly covers a frozen Git base/head range."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any


HEAD_RE = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")
DIFF_OPTIONS = [
    "--binary",
    "--full-index",
    "--no-ext-diff",
    "--no-textconv",
    "--no-color",
    "--no-renames",
    "--no-relative",
    "--src-prefix=a/",
    "--dst-prefix=b/",
    "--line-prefix=",
    "--diff-algorithm=myers",
    "--no-indent-heuristic",
    "--unified=3",
    "--inter-hunk-context=0",
    "--submodule=short",
    "--ignore-submodules=none",
]
GIT_CONFIG = [
    "-c",
    "core.quotePath=true",
    "-c",
    "diff.mnemonicPrefix=false",
    "-c",
    "diff.noprefix=false",
    "-c",
    "diff.ignoreSubmodules=none",
    "-c",
    "diff.orderFile=/dev/null",
    "-c",
    "diff.suppressBlankEmpty=false",
]
REGULAR_MODES = {b"100644", b"100755"}


def _git(repo: Path, *args: str) -> bytes:
    command = ["git", "-C", str(repo), *GIT_CONFIG, *args]
    completed = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", "replace").strip()
        raise ValueError(f"Git command failed: {' '.join(command)}: {detail}")
    return completed.stdout


def _git_with_input(repo: Path, data: bytes, *args: str) -> bytes:
    command = ["git", "-C", str(repo), *GIT_CONFIG, *args]
    completed = subprocess.run(
        command,
        input=data,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", "replace").strip()
        raise ValueError(f"Git command failed: {' '.join(command)}: {detail}")
    return completed.stdout


def _verify_commit(repo: Path, value: str, label: str) -> None:
    if not HEAD_RE.fullmatch(value):
        raise ValueError(f"{label} must be an exact 40 or 64 character lowercase Git SHA")
    resolved = _git(repo, "rev-parse", "--verify", f"{value}^{{commit}}").decode().strip()
    if resolved != value:
        raise ValueError(f"{label} does not resolve to itself exactly")


def expected_diff(repo: Path, base: str, head: str) -> bytes:
    return _git(repo, "diff", *DIFF_OPTIONS, f"{base}..{head}")


def _raw_records(
    repo: Path, base: str, head: str
) -> list[tuple[bytes, bytes, bytes, bytes, bytes]]:
    raw = _git(
        repo,
        "diff-tree",
        "--no-commit-id",
        "--raw",
        "-r",
        "-z",
        "--no-renames",
        "--ignore-submodules=none",
        "--no-abbrev",
        base,
        head,
    )
    parts = raw.split(b"\0")
    records: list[tuple[bytes, bytes, bytes, bytes, bytes]] = []
    index = 0
    while index < len(parts) and parts[index]:
        header = parts[index]
        if index + 1 >= len(parts) or not header.startswith(b":"):
            raise ValueError("unexpected git diff --raw output")
        fields = header[1:].split()
        if len(fields) != 5:
            raise ValueError("unexpected git diff --raw header")
        path = parts[index + 1]
        records.append((fields[0], fields[1], fields[2], fields[3], path))
        index += 2
    return records


def _blob_is_binary(repo: Path, mode: bytes, object_id: bytes) -> bool:
    if mode not in REGULAR_MODES or set(object_id) == {ord("0")}:
        return False
    data = _git(repo, "cat-file", "blob", object_id.decode("ascii"))
    if b"\0" in data:
        return True
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        return True
    return False


def _binary_evidence(
    repo: Path, records: list[tuple[bytes, bytes, bytes, bytes, bytes]]
) -> list[dict[str, str]]:
    binaries: list[dict[str, str]] = []
    for old_mode, new_mode, old_object, new_object, path in records:
        if _blob_is_binary(repo, old_mode, old_object) or _blob_is_binary(
            repo, new_mode, new_object
        ):
            binaries.append(
                {
                    "path": path.decode("utf-8", "surrogateescape"),
                    "old_mode": old_mode.decode("ascii"),
                    "new_mode": new_mode.decode("ascii"),
                    "old_object": old_object.decode("ascii"),
                    "new_object": new_object.decode("ascii"),
                }
            )
    return binaries


def _patch_paths(repo: Path, patch: bytes) -> list[bytes]:
    output = _git_with_input(repo, patch, "apply", "--numstat", "-z", "--allow-empty")
    paths: list[bytes] = []
    for record in output.split(b"\0"):
        if not record:
            continue
        fields = record.split(b"\t", 2)
        if len(fields) != 3:
            raise ValueError("unexpected git apply --numstat output")
        paths.append(fields[2])
    return paths


def _display(paths: list[bytes]) -> list[str]:
    return [path.decode("utf-8", "surrogateescape") for path in paths]


def validate_diff(
    *, repo: Path, base: str, head: str, supplied_diff: bytes
) -> dict[str, Any]:
    _verify_commit(repo, base, "base")
    _verify_commit(repo, head, "head")
    records = _raw_records(repo, base, head)
    changed = [record[4] for record in records]
    symlinks = [
        record[4]
        for record in records
        if record[0] == b"120000" or record[1] == b"120000"
    ]
    binary_evidence = _binary_evidence(repo, records)

    generated = expected_diff(repo, base, head)
    if supplied_diff != generated:
        raise ValueError(
            "full.diff bytes do not equal the deterministic complete Git diff "
            f"(supplied sha256={hashlib.sha256(supplied_diff).hexdigest()}, "
            f"expected sha256={hashlib.sha256(generated).hexdigest()})"
        )

    diff_paths_raw = _patch_paths(repo, supplied_diff)
    if changed != diff_paths_raw:
        raise ValueError(
            "changed paths do not exactly equal paths independently parsed from full.diff"
        )

    paths = _display(changed)
    return {
        "base_sha": base,
        "head_sha": head,
        "diff_sha256": hashlib.sha256(supplied_diff).hexdigest(),
        "changed_paths": paths,
        "diff_paths": _display(diff_paths_raw),
        "binary_paths": [item["path"] for item in binary_evidence],
        "binary_evidence": binary_evidence,
        "symlink_paths": _display(symlinks),
        "complete": True,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", required=True)
    parser.add_argument("--diff-file", required=True, type=Path)
    args = parser.parse_args(argv)

    try:
        result = validate_diff(
            repo=args.repo,
            base=args.base,
            head=args.head,
            supplied_diff=args.diff_file.read_bytes(),
        )
    except (OSError, ValueError) as exc:
        parser.exit(1, f"review diff validation error: {exc}\n")

    print(json.dumps(result, ensure_ascii=True, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
