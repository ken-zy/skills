#!/usr/bin/env python3
"""Validate the small, durable graph-driven-development run-state contract."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


DEFAULT_ACTIVE_LIMITS = {"normal": 3_600, "high_risk": 10_800}
DEFAULT_REVIEW_PACKAGE_LIMIT = 3
DEFAULT_IMPLEMENTATION_REWORK_LIMIT = 2
ALLOWED_STATES = {
    "PREFLIGHT",
    "SPEC_READY",
    "PLAN_READY",
    "IMPLEMENTING",
    "VERIFYING",
    "REVIEW_CANDIDATE",
    "REVIEWING",
    "REWORKING",
    "READY_FOR_AUTHORIZED_NEXT_ACTION",
    "PR_CI",
    "WAITING_FOR_MERGE",
    "MERGED",
    "CLEANED_UP",
    "WAITING_HUMAN",
    "DELIVERED",
    "FAILED",
    "CANCELLED",
}
ALLOWED_STATUSES = {"ACTIVE", "WAITING_HUMAN", "DELIVERED", "FAILED", "CANCELLED"}
TERMINAL_STATUSES = {"WAITING_HUMAN", "DELIVERED", "FAILED", "CANCELLED"}
COMPLETION_STATES = {
    "READY_FOR_AUTHORIZED_NEXT_ACTION",
    "PR_CI",
    "WAITING_FOR_MERGE",
    "MERGED",
    "CLEANED_UP",
    "DELIVERED",
}
ALLOWED_BACKENDS = {"chatgpt-web", "grok-web"}
PACKAGE_ID_RE = re.compile(r"^sha256:[0-9a-f]{64}$")

REQUIRED_FIELDS = {
    "schema_version",
    "status",
    "state",
    "task_class",
    "task_worktree",
    "task_branch",
    "base_commit",
    "head_sha",
    "verified_head_sha",
    "active_seconds",
    "active_limit_seconds",
    "time_extension_authorization_ref",
    "review_package_id",
    "review_package_count",
    "review_package_limit",
    "implementation_rework_used",
    "implementation_rework_limit",
    "budget_extension_authorization_ref",
    "accepted_blocking_high_pending",
    "reviewers",
}


def _is_non_negative_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _is_non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _optional_reference_is_valid(value: Any) -> bool:
    return value is None or isinstance(value, str)


def _validate_reviewer(
    reviewer: Any,
    index: int,
    *,
    head_sha: Any,
    package_id: Any,
    implementation_authors: set[str],
    errors: list[str],
) -> str | None:
    prefix = f"reviewers[{index}]"
    if not isinstance(reviewer, dict):
        errors.append(f"{prefix} must be an object")
        return None

    conversation_id = reviewer.get("conversation_id")
    if not _is_non_empty_string(conversation_id):
        errors.append(f"{prefix}.conversation_id must be non-empty")
        conversation_id = None
    elif conversation_id in implementation_authors:
        errors.append(f"{prefix} conversation authored the candidate")

    if reviewer.get("backend") not in ALLOWED_BACKENDS:
        errors.append(f"{prefix}.backend must be 'chatgpt-web' or 'grok-web'")
    if not _is_non_empty_string(reviewer.get("visible_model")):
        errors.append(f"{prefix}.visible_model must be non-empty")
    if not _is_non_empty_string(reviewer.get("selection_label")):
        errors.append(f"{prefix}.selection_label must be non-empty")
    reasoning_setting = reviewer.get("reasoning_setting")
    if "reasoning_setting" not in reviewer:
        errors.append(f"{prefix}.reasoning_setting must be present")
    elif reasoning_setting is not None and not _is_non_empty_string(reasoning_setting):
        errors.append(f"{prefix}.reasoning_setting must be null or non-empty")
    if not _is_non_empty_string(reviewer.get("selection_evidence_ref")):
        errors.append(f"{prefix}.selection_evidence_ref must be non-empty")
    if reviewer.get("read_only") is not True:
        errors.append(f"{prefix}.read_only must be true")
    if reviewer.get("authored_candidate") is not False:
        errors.append(f"{prefix}.authored_candidate must be false")
    if reviewer.get("head_sha") != head_sha:
        errors.append(f"{prefix}.head_sha must match the current head")
    if reviewer.get("package_id") != package_id:
        errors.append(f"{prefix}.package_id must match the current review package")

    return conversation_id


def validate_state(state: Any) -> list[str]:
    """Return invariant violations for a decoded schema-v3 state snapshot."""
    if not isinstance(state, dict):
        return ["top-level JSON value must be an object"]

    errors: list[str] = []
    for field in sorted(REQUIRED_FIELDS - state.keys()):
        errors.append(f"missing required field: {field}")

    if state.get("schema_version") != 3:
        errors.append("schema_version must be 3")

    task_class = state.get("task_class")
    status = state.get("status")
    phase = state.get("state")
    if task_class not in DEFAULT_ACTIVE_LIMITS:
        errors.append("task_class must be 'normal' or 'high_risk'")
    if status not in ALLOWED_STATUSES:
        errors.append(f"status must be one of {sorted(ALLOWED_STATUSES)}")
    if phase not in ALLOWED_STATES:
        errors.append(f"state must be one of {sorted(ALLOWED_STATES)}")
    if phase in TERMINAL_STATUSES and status != phase:
        errors.append("terminal state/status must match exactly")
    if status in TERMINAL_STATUSES and phase != status:
        errors.append("terminal state/status must match exactly")

    for field in ("task_worktree", "task_branch", "base_commit"):
        if not _is_non_empty_string(state.get(field)):
            errors.append(f"{field} must be a non-empty string")

    head_sha = state.get("head_sha")
    verified_head_sha = state.get("verified_head_sha")
    package_id = state.get("review_package_id")
    for field, value in (
        ("head_sha", head_sha),
        ("verified_head_sha", verified_head_sha),
        ("review_package_id", package_id),
    ):
        if value is not None and not _is_non_empty_string(value):
            errors.append(f"{field} must be null or a non-empty string")

    integer_fields = (
        "active_seconds",
        "active_limit_seconds",
        "review_package_count",
        "review_package_limit",
        "implementation_rework_used",
        "implementation_rework_limit",
    )
    for field in integer_fields:
        if not _is_non_negative_int(state.get(field)):
            errors.append(f"{field} must be a non-negative integer")

    time_authorization = state.get("time_extension_authorization_ref")
    budget_authorization = state.get("budget_extension_authorization_ref")
    if not _optional_reference_is_valid(time_authorization):
        errors.append("time_extension_authorization_ref must be null or a string")
    if not _optional_reference_is_valid(budget_authorization):
        errors.append("budget_extension_authorization_ref must be null or a string")

    active_seconds = state.get("active_seconds")
    active_limit = state.get("active_limit_seconds")
    default_active_limit = DEFAULT_ACTIVE_LIMITS.get(task_class)
    if _is_non_negative_int(active_limit) and default_active_limit is not None:
        if active_limit < default_active_limit:
            errors.append("active_limit_seconds cannot be below the task-class default")
        elif active_limit > default_active_limit and not _is_non_empty_string(time_authorization):
            errors.append("a raised active limit requires time_extension_authorization_ref")
    if (
        _is_non_negative_int(active_seconds)
        and _is_non_negative_int(active_limit)
        and active_seconds >= active_limit
        and status == "ACTIVE"
    ):
        errors.append("the active-time limit requires status WAITING_HUMAN or terminal")

    package_count = state.get("review_package_count")
    package_limit = state.get("review_package_limit")
    rework_used = state.get("implementation_rework_used")
    rework_limit = state.get("implementation_rework_limit")
    if _is_non_negative_int(package_limit):
        if package_limit < DEFAULT_REVIEW_PACKAGE_LIMIT:
            errors.append("review_package_limit cannot be below 3")
        elif package_limit > DEFAULT_REVIEW_PACKAGE_LIMIT and not _is_non_empty_string(
            budget_authorization
        ):
            errors.append("a raised review package limit requires budget_extension_authorization_ref")
    if _is_non_negative_int(rework_limit):
        if rework_limit < DEFAULT_IMPLEMENTATION_REWORK_LIMIT:
            errors.append("implementation_rework_limit cannot be below 2")
        elif rework_limit > DEFAULT_IMPLEMENTATION_REWORK_LIMIT and not _is_non_empty_string(
            budget_authorization
        ):
            errors.append("a raised rework limit requires budget_extension_authorization_ref")
    if _is_non_negative_int(package_count) and _is_non_negative_int(package_limit):
        if package_count > package_limit:
            errors.append("review_package_count cannot exceed review_package_limit")
    if _is_non_negative_int(rework_used) and _is_non_negative_int(rework_limit):
        if rework_used > rework_limit:
            errors.append("implementation_rework_used cannot exceed implementation_rework_limit")

    pending_high = state.get("accepted_blocking_high_pending")
    if not isinstance(pending_high, bool):
        errors.append("accepted_blocking_high_pending must be a boolean")
    elif pending_high and status == "ACTIVE":
        package_exhausted = (
            _is_non_negative_int(package_count)
            and _is_non_negative_int(package_limit)
            and package_count >= package_limit
        )
        rework_exhausted = (
            _is_non_negative_int(rework_used)
            and _is_non_negative_int(rework_limit)
            and rework_used >= rework_limit
        )
        if package_exhausted or rework_exhausted:
            errors.append("an accepted blocking/high finding at a saved budget limit requires WAITING_HUMAN")

    implementation_authors: set[str] = set()
    raw_authors = state.get("implementation_author_conversation_ids", [])
    if not isinstance(raw_authors, list) or any(
        not _is_non_empty_string(item) for item in raw_authors
    ):
        errors.append("implementation_author_conversation_ids must be a list of non-empty strings")
    else:
        implementation_authors = set(raw_authors)
        if len(implementation_authors) != len(raw_authors):
            errors.append("implementation_author_conversation_ids must not contain duplicates")

    reviewers = state.get("reviewers")
    reviewer_ids: list[str] = []
    if not isinstance(reviewers, list):
        errors.append("reviewers must be a list")
        reviewers = []
    else:
        for index, reviewer in enumerate(reviewers):
            conversation_id = _validate_reviewer(
                reviewer,
                index,
                head_sha=head_sha,
                package_id=package_id,
                implementation_authors=implementation_authors,
                errors=errors,
            )
            if conversation_id is not None:
                reviewer_ids.append(conversation_id)
        if len(reviewer_ids) != len(set(reviewer_ids)):
            errors.append("reviewer conversation IDs must be distinct")

    review_complete = phase in COMPLETION_STATES or status == "DELIVERED"
    if review_complete:
        if not _is_non_empty_string(head_sha) or head_sha != verified_head_sha:
            errors.append("completion requires identical non-empty head_sha and verified_head_sha")
        if not isinstance(package_id, str) or PACKAGE_ID_RE.fullmatch(package_id) is None:
            errors.append("completion requires a sha256 review_package_id")
        if not _is_non_negative_int(package_count) or package_count < 1:
            errors.append("completion requires review_package_count of at least 1")
        if pending_high is not False:
            errors.append("completion cannot retain an accepted blocking/high finding")

        required_reviewers = 2 if task_class == "high_risk" else 1
        if len(reviewers) < required_reviewers:
            errors.append(
                f"{task_class} completion requires at least {required_reviewers} independent reviewer(s)"
            )
        for index, reviewer in enumerate(reviewers):
            if not isinstance(reviewer, dict):
                continue
            if reviewer.get("verdict") != "PASS":
                errors.append(f"reviewers[{index}].verdict must be PASS for completion")
            if reviewer.get("findings_reconciled") is not True:
                errors.append(f"reviewers[{index}].findings_reconciled must be true for completion")
            if reviewer.get("blocking_high_remaining") is not False:
                errors.append(f"reviewers[{index}].blocking_high_remaining must be false for completion")

    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("state_file", type=Path, help="JSON run-state snapshot")
    args = parser.parse_args(argv)

    try:
        state = json.loads(args.state_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"invalid run-state input: {exc}", file=sys.stderr)
        return 2

    errors = validate_state(state)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print("graph-driven-development run state: valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
