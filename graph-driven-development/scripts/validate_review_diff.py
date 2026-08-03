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
]
GIT_CONFIG = [
    "-c",
    "core.quotePath=true",
    "-c",
    "diff.mnemonicPrefix=false",
    "-c",
    "diff.noprefix=false",
]


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


def _verify_commit(repo: Path, value: str, label: str) -> None:
    if not HEAD_RE.fullmatch(value):
        raise ValueError(f"{label} must be an exact 40 or 64 character lowercase Git SHA")
    resolved = _git(repo, "rev-parse", "--verify", f"{value}^{{commit}}").decode().strip()
    if resolved != value:
        raise ValueError(f"{label} does not resolve to itself exactly")


def expected_diff(repo: Path, base: str, head: str) -> bytes:
    return _git(repo, "diff", *DIFF_OPTIONS, f"{base}..{head}")


def _raw_path_evidence(repo: Path, base: str, head: str) -> tuple[list[bytes], list[bytes]]:
    raw = _git(repo, "diff", "--raw", "-z", "--no-renames", f"{base}..{head}")
    parts = raw.split(b"\0")
    changed: list[bytes] = []
    symlinks: list[bytes] = []
    index = 0
    while index < len(parts) and parts[index]:
        header = parts[index]
        if index + 1 >= len(parts) or not header.startswith(b":"):
            raise ValueError("unexpected git diff --raw output")
        fields = header[1:].split()
        if len(fields) != 5:
            raise ValueError("unexpected git diff --raw header")
        path = parts[index + 1]
        changed.append(path)
        if fields[0] == b"120000" or fields[1] == b"120000":
            symlinks.append(path)
        index += 2
    return changed, symlinks


def _binary_paths(repo: Path, base: str, head: str) -> list[bytes]:
    output = _git(repo, "diff", "--numstat", "-z", "--no-renames", f"{base}..{head}")
    binaries: list[bytes] = []
    for record in output.split(b"\0"):
        if not record:
            continue
        fields = record.split(b"\t", 2)
        if len(fields) != 3:
            raise ValueError("unexpected git diff --numstat output")
        if fields[0] == b"-" or fields[1] == b"-":
            binaries.append(fields[2])
    return binaries


def _display(paths: list[bytes]) -> list[str]:
    return [path.decode("utf-8", "surrogateescape") for path in paths]


def validate_diff(
    *, repo: Path, base: str, head: str, supplied_diff: bytes
) -> dict[str, Any]:
    _verify_commit(repo, base, "base")
    _verify_commit(repo, head, "head")
    changed, symlinks = _raw_path_evidence(repo, base, head)
    binaries = _binary_paths(repo, base, head)
    if binaries:
        raise ValueError(
            "binary changed paths block a safe complete review package: "
            + ", ".join(_display(binaries))
        )

    generated = expected_diff(repo, base, head)
    if supplied_diff != generated:
        raise ValueError(
            "full.diff bytes do not equal the deterministic complete Git diff "
            f"(supplied sha256={hashlib.sha256(supplied_diff).hexdigest()}, "
            f"expected sha256={hashlib.sha256(generated).hexdigest()})"
        )

    paths = _display(changed)
    return {
        "base_sha": base,
        "head_sha": head,
        "diff_sha256": hashlib.sha256(supplied_diff).hexdigest(),
        "changed_paths": paths,
        "diff_paths": list(paths),
        "binary_paths": [],
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
