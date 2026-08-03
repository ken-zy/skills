#!/usr/bin/env python3
"""Validate critical graph-driven-development run-state invariants read-only."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from compute_review_package_digest import ALGORITHM, digest_from_hashes


TASK_LIMITS = {"normal": 3_600, "high_risk": 10_800}
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
REVIEW_STATES = {"REVIEW_CANDIDATE", "REVIEWING"}
REVIEW_COMPLETION_STATES = {
    "READY_FOR_AUTHORIZED_NEXT_ACTION",
    "PR_CI",
    "WAITING_FOR_MERGE",
    "MERGED",
    "CLEANED_UP",
    "DELIVERED",
}
PACKAGE_BOUND_STATES = REVIEW_STATES | REVIEW_COMPLETION_STATES
ALLOWED_STATUSES = {"ACTIVE", "WAITING_HUMAN", "DELIVERED", "FAILED", "CANCELLED"}
TERMINAL_STATE_STATUSES = {"WAITING_HUMAN", "DELIVERED", "FAILED", "CANCELLED"}
ALLOWED_BACKENDS = {"chatgpt-web", "grok-web"}
MODEL_PREFERENCE_BASELINE = ("ChatGPT Pro", "GPT-5.6 Sol", "GPT-5.5", "GPT-5.3", "o3")
MODEL_AVAILABILITIES = {"available", "quota_exhausted", "unavailable", "reasoning_unsupported"}
REVIEW_VERDICTS = {"PASS", "CHANGES_REQUESTED", "NEEDS_EVIDENCE", "BACKEND_FAILED"}
PENDING_HIGH_TERMINAL_STATUSES = {"WAITING_HUMAN", "FAILED", "CANCELLED"}
HEX_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
PACKAGE_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


def _is_non_negative_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _is_sha256(value: Any) -> bool:
    return isinstance(value, str) and HEX_SHA256_RE.fullmatch(value) is not None


def _parse_timezone_aware_iso(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed


def _is_completed_pass_reviewer(reviewer: Any) -> bool:
    return (
        isinstance(reviewer, dict)
        and reviewer.get("verdict") == "PASS"
        and _parse_timezone_aware_iso(reviewer.get("completed_at")) is not None
        and reviewer.get("findings_reconciled") is True
        and reviewer.get("blocking_high_remaining") is False
    )


def _string_list(
    state: dict[str, Any], name: str, errors: list[str], *, unique: bool = False
) -> list[str] | None:
    value = state.get(name)
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
        errors.append(f"{name} must be a list of non-empty strings")
        return None
    if unique and len(value) != len(set(value)):
        errors.append(f"{name} must not contain duplicates")
    return value


def validate_state(state: Any) -> list[str]:
    """Return invariant violations for a decoded run-state snapshot."""
    if not isinstance(state, dict):
        return ["top-level JSON value must be an object"]

    errors: list[str] = []
    if state.get("schema_version") != 2:
        errors.append("schema_version must be 2")

    task_class = state.get("task_class")
    status = state.get("status")
    phase = state.get("state")
    active_seconds = state.get("active_seconds")
    review_round = state.get("review_round")
    package_count = state.get("review_package_count")
    rework_count = state.get("implementation_rework_used")
    plan_rework_count = state.get("plan_rework_used")

    if task_class not in TASK_LIMITS:
        errors.append("task_class must be 'normal' or 'high_risk'")
    if status not in ALLOWED_STATUSES:
        errors.append(f"status must be one of {sorted(ALLOWED_STATUSES)}")
    if phase not in ALLOWED_STATES:
        errors.append(f"state must be one of {sorted(ALLOWED_STATES)}")
    if phase in TERMINAL_STATE_STATUSES and status != phase:
        errors.append("terminal state/status must match exactly")
    if status in {"DELIVERED", "FAILED", "CANCELLED"} and phase != status:
        errors.append("terminal state/status must match exactly")

    for name, value in (
        ("active_seconds", active_seconds),
        ("review_round", review_round),
        ("review_package_count", package_count),
        ("implementation_rework_used", rework_count),
        ("plan_rework_used", plan_rework_count),
    ):
        if not _is_non_negative_int(value):
            errors.append(f"{name} must be a non-negative integer")

    if _is_non_negative_int(package_count) and package_count > 3:
        errors.append("review_package_count cannot exceed 3")
    if _is_non_negative_int(rework_count) and rework_count > 2:
        errors.append("implementation_rework_used cannot exceed 2")
    if _is_non_negative_int(plan_rework_count) and plan_rework_count > 1:
        errors.append("plan_rework_used cannot exceed 1")
    if _is_non_negative_int(review_round) and review_round > 3:
        errors.append("review_round cannot exceed 3")

    if state.get("required_reasoning_level") != "Extra High":
        errors.append("required_reasoning_level must be exactly 'Extra High'")
    if state.get("selected_reasoning_level") != "Extra High":
        errors.append("selected_reasoning_level must be exactly 'Extra High'")
    if state.get("reasoning_level_selection_reason") != "fixed_skill_policy":
        errors.append("reasoning_level_selection_reason must be 'fixed_skill_policy'")
    if state.get("exact_reasoning_level_required") is not True:
        errors.append("exact_reasoning_level_required must be true")

    for name in ("exact_backend_required", "exact_model_required"):
        if not isinstance(state.get(name), bool):
            errors.append(f"{name} must be a boolean")

    effective_limit = TASK_LIMITS.get(task_class)
    extension = state.get("extension_authorization")
    if extension is not None:
        extension_valid = True
        if not isinstance(extension, dict):
            errors.append("extension_authorization must be null or an object")
            extension_valid = False
        else:
            for name in ("authorized_by", "authorization_ref"):
                if not isinstance(extension.get(name), str) or not extension.get(name):
                    errors.append(f"extension_authorization.{name} must be non-empty")
                    extension_valid = False
            authorized_at = extension.get("authorized_at_active_seconds")
            new_limit = extension.get("new_active_limit_seconds")
            authorized_at_time = _parse_timezone_aware_iso(extension.get("authorized_at"))
            deadline = _parse_timezone_aware_iso(extension.get("new_deadline"))
            pause_evidence = extension.get("pause_evidence")
            if not _is_non_negative_int(authorized_at):
                errors.append(
                    "extension_authorization.authorized_at_active_seconds must be a "
                    "non-negative integer"
                )
                extension_valid = False
            elif effective_limit is not None and authorized_at < effective_limit:
                errors.append("extension authorization must occur after the mandatory pause")
                extension_valid = False
            elif _is_non_negative_int(active_seconds) and active_seconds < authorized_at:
                errors.append("active_seconds cannot precede the persisted extension authorization ledger")
                extension_valid = False
            if not _is_non_negative_int(new_limit):
                errors.append(
                    "extension_authorization.new_active_limit_seconds must be a "
                    "non-negative integer"
                )
                extension_valid = False
            elif (
                effective_limit is not None
                and _is_non_negative_int(authorized_at)
                and (new_limit <= effective_limit or new_limit <= authorized_at)
            ):
                errors.append("extended active limit must exceed the original limit and authorization point")
                extension_valid = False
            if authorized_at_time is None:
                errors.append("extension_authorization.authorized_at must be timezone-aware ISO 8601")
                extension_valid = False
            if deadline is None:
                errors.append("extension_authorization.new_deadline must be timezone-aware ISO 8601")
                extension_valid = False
            if authorized_at_time is not None and deadline is not None and deadline <= authorized_at_time:
                errors.append("extension deadline must be later than its authorization")
                extension_valid = False
            pause_time: datetime | None = None
            pause_active: Any = None
            if not isinstance(pause_evidence, dict):
                errors.append("extension_authorization.pause_evidence must be an object")
                extension_valid = False
            else:
                if pause_evidence.get("status") != "WAITING_HUMAN":
                    errors.append("extension pause evidence must record WAITING_HUMAN")
                    extension_valid = False
                if pause_evidence.get("reason") != "mandatory_active_limit":
                    errors.append("extension pause evidence must record mandatory_active_limit")
                    extension_valid = False
                pause_active = pause_evidence.get("active_seconds")
                if effective_limit is not None and pause_active != effective_limit:
                    errors.append("extension pause evidence must use the original active-time limit")
                    extension_valid = False
                pause_time = _parse_timezone_aware_iso(pause_evidence.get("paused_at"))
                if pause_time is None:
                    errors.append("extension pause evidence paused_at must be timezone-aware ISO 8601")
                    extension_valid = False
            if (
                _is_non_negative_int(authorized_at)
                and _is_non_negative_int(pause_active)
                and authorized_at != pause_active
            ):
                errors.append("extension authorization active time must equal the paused ledger")
                extension_valid = False
            if pause_time is not None and authorized_at_time is not None and authorized_at_time <= pause_time:
                errors.append("extension authorization must occur strictly after the recorded pause")
                extension_valid = False
            if extension_valid:
                effective_limit = new_limit

    if (
        effective_limit is not None
        and _is_non_negative_int(active_seconds)
        and active_seconds >= effective_limit
        and status == "ACTIVE"
    ):
        errors.append(
            f"ACTIVE run reached mandatory pause at {effective_limit} active seconds; "
            "status must be WAITING_HUMAN or terminal"
        )

    head = state.get("head_sha")
    verified_head = state.get("verified_head_sha")
    package_head = state.get("review_package_head_sha")
    package_digest = state.get("review_package_digest")

    if phase in PACKAGE_BOUND_STATES or status == "DELIVERED":
        if not head or head != verified_head or head != package_head:
            errors.append(
                "review candidate requires identical non-empty head_sha, "
                "verified_head_sha, and review_package_head_sha"
            )
        if not isinstance(package_digest, str) or not PACKAGE_DIGEST_RE.fullmatch(package_digest):
            errors.append("review candidate requires a sha256 review_package_digest")
        if state.get("package_digest_algorithm") != ALGORITHM:
            errors.append(f"package_digest_algorithm must be '{ALGORITHM}'")
        component_names = (
            "review_request_sha256",
            "review_request_canonical_sha256",
            "full_diff_sha256",
            "review_context_sha256",
        )
        for name in component_names:
            if not _is_sha256(state.get(name)):
                errors.append(f"{name} must be 64 lowercase hexadecimal characters")
        if (
            isinstance(package_digest, str)
            and PACKAGE_DIGEST_RE.fullmatch(package_digest)
            and isinstance(package_head, str)
            and all(_is_sha256(state.get(name)) for name in component_names)
        ):
            try:
                expected_digest = digest_from_hashes(
                    head_sha=package_head,
                    request_canonical_sha256=state["review_request_canonical_sha256"],
                    full_diff_sha256=state["full_diff_sha256"],
                    review_context_sha256=state["review_context_sha256"],
                )
            except ValueError as exc:
                errors.append(f"cannot recompute review_package_digest: {exc}")
            else:
                if package_digest != expected_digest:
                    errors.append("review_package_digest does not match graph-review-package-v1 inputs")

        if state.get("review_diff_verified") is not True:
            errors.append("review candidate requires review_diff_verified true")
        changed_paths = _string_list(state, "review_package_changed_paths", errors, unique=True)
        diff_paths = _string_list(state, "review_package_diff_paths", errors, unique=True)
        binary_paths = _string_list(state, "review_package_binary_paths", errors, unique=True)
        symlink_paths = _string_list(state, "review_package_symlink_paths", errors, unique=True)
        if changed_paths is not None and diff_paths is not None and changed_paths != diff_paths:
            errors.append("review package changed paths must exactly equal diff paths")
        if binary_paths:
            errors.append("binary changed paths block a safe complete review package")
        if changed_paths is not None and symlink_paths is not None:
            missing_symlinks = sorted(set(symlink_paths) - set(changed_paths))
            if missing_symlinks:
                errors.append("review package symlink paths must be included in diff paths")
        if not _is_non_negative_int(package_count) or package_count < 1:
            errors.append("review candidate requires review_package_count >= 1")
        if review_round != package_count:
            errors.append("review_round must equal review_package_count for a review candidate")

    pending_high = state.get("accepted_blocking_high_pending")
    if not isinstance(pending_high, bool):
        errors.append("accepted_blocking_high_pending must be a boolean")
    elif pending_high:
        if status == "DELIVERED" or phase in REVIEW_COMPLETION_STATES:
            errors.append("delivery and review-complete states cannot retain blocking/high findings")
        if package_count == 3 and status not in PENDING_HIGH_TERMINAL_STATUSES:
            errors.append(
                "package 3 has an accepted blocking/high finding; status must be "
                "WAITING_HUMAN, FAILED, or CANCELLED and package 4 is forbidden"
            )

    trigger = state.get("rework_trigger")
    if trigger not in (None, "accepted_blocking_high", "required_pr_ci_failure"):
        errors.append(
            "rework_trigger must be null, 'accepted_blocking_high', or "
            "'required_pr_ci_failure'"
        )
    if _is_non_negative_int(rework_count) and rework_count > 0 and trigger is None:
        errors.append("a used implementation rework requires an allowed rework_trigger")

    implementation_authors = _string_list(
        state, "implementation_author_conversation_ids", errors, unique=True
    )
    reviewers = state.get("reviewers", [])
    valid_conversation_ids: list[str] = []
    if not isinstance(reviewers, list):
        errors.append("reviewers must be a list")
    else:
        for index, reviewer in enumerate(reviewers):
            if not isinstance(reviewer, dict):
                errors.append(f"reviewers[{index}] must be an object")
                continue
            conversation_id = reviewer.get("conversation_id")
            if not isinstance(conversation_id, str) or not conversation_id:
                errors.append(f"reviewers[{index}].conversation_id must be non-empty")
            else:
                valid_conversation_ids.append(conversation_id)
                if implementation_authors is not None and conversation_id in implementation_authors:
                    errors.append(f"reviewers[{index}] conversation authored the candidate")
            if reviewer.get("backend") not in ALLOWED_BACKENDS:
                errors.append(f"reviewers[{index}].backend must use the cognitive allowlist")
            if reviewer.get("role") != "reviewer":
                errors.append(f"reviewers[{index}].role must be 'reviewer'")
            if reviewer.get("read_only") is not True:
                errors.append(f"reviewers[{index}].read_only must be true")
            if reviewer.get("authored_candidate") is not False:
                errors.append(f"reviewers[{index}].authored_candidate must be false")
            if reviewer.get("head_sha") != package_head:
                errors.append(f"reviewers[{index}] must use the current package head")
            if reviewer.get("package_digest") != package_digest:
                errors.append(f"reviewers[{index}] must use the current package digest")
            if reviewer.get("selected_reasoning_level") != "Extra High":
                errors.append(
                    f"reviewers[{index}].selected_reasoning_level must be exactly 'Extra High'"
                )
            verdict = reviewer.get("verdict")
            if verdict is not None and verdict not in REVIEW_VERDICTS:
                errors.append(f"reviewers[{index}].verdict is not an allowed review verdict")
            completed_at = reviewer.get("completed_at")
            if completed_at is not None and _parse_timezone_aware_iso(completed_at) is None:
                errors.append(f"reviewers[{index}].completed_at must be timezone-aware ISO 8601")
        if len(valid_conversation_ids) != len(set(valid_conversation_ids)):
            errors.append("reviewer conversation IDs must be distinct")

    review_must_be_complete = phase in REVIEW_COMPLETION_STATES or status == "DELIVERED"
    if review_must_be_complete and isinstance(reviewers, list):
        required_count = 2 if task_class == "high_risk" else 1
        incomplete_indexes = [
            index
            for index, reviewer in enumerate(reviewers)
            if not _is_completed_pass_reviewer(reviewer)
        ]
        if incomplete_indexes:
            errors.append(
                "review completion requires every current reviewer to be a completed PASS "
                "reviewer with reconciled findings and no blocking/high remaining; "
                f"invalid indexes: {incomplete_indexes}"
            )
        completed_reviewers = [reviewer for reviewer in reviewers if _is_completed_pass_reviewer(reviewer)]
        if len(completed_reviewers) < required_count:
            errors.append(
                f"{task_class} review completion requires at least {required_count} "
                "completed PASS reviewer(s) with reconciled findings"
            )

    inventory = state.get("chatgpt_model_inventory", [])
    inventory_by_name: dict[str, dict[str, Any]] = {}
    inventory_index_by_name: dict[str, int] = {}
    inventory_names: list[str] = []
    unknown_models: list[str] = []
    if not isinstance(inventory, list):
        errors.append("chatgpt_model_inventory must be a list")
    else:
        for index, item in enumerate(inventory):
            if not isinstance(item, dict):
                errors.append(f"chatgpt_model_inventory[{index}] must be an object")
                continue
            model = item.get("model")
            reasoning_levels = item.get("reasoning_levels")
            availability = item.get("availability")
            if not isinstance(model, str) or not model:
                errors.append(f"chatgpt_model_inventory[{index}].model must be non-empty")
            elif model in inventory_by_name:
                errors.append("chatgpt_model_inventory model names must be unique")
            else:
                inventory_names.append(model)
                inventory_by_name[model] = item
                inventory_index_by_name[model] = index
                if model not in MODEL_PREFERENCE_BASELINE:
                    unknown_models.append(model)
            if item.get("preference_rank") != index:
                errors.append(
                    f"chatgpt_model_inventory[{index}].preference_rank must equal {index}"
                )
            if not isinstance(reasoning_levels, list) or any(
                not isinstance(level, str) for level in reasoning_levels
            ):
                errors.append(
                    f"chatgpt_model_inventory[{index}].reasoning_levels must be a list of strings"
                )
            if availability not in MODEL_AVAILABILITIES:
                errors.append(
                    f"chatgpt_model_inventory[{index}].availability must be one of "
                    f"{sorted(MODEL_AVAILABILITIES)}"
                )

    known_positions = [
        MODEL_PREFERENCE_BASELINE.index(name)
        for name in inventory_names
        if name in MODEL_PREFERENCE_BASELINE
    ]
    if known_positions != sorted(known_positions):
        errors.append("known ChatGPT models must follow the fixed policy preference order")

    inventory_ambiguity = state.get("model_inventory_ambiguity")
    if not isinstance(inventory_ambiguity, str):
        errors.append("model_inventory_ambiguity must be a string")
    elif unknown_models:
        if status != "WAITING_HUMAN" or not inventory_ambiguity:
            errors.append(
                "unknown ChatGPT models require WAITING_HUMAN with explicit inventory ambiguity"
            )
    elif inventory_ambiguity:
        errors.append("model_inventory_ambiguity must be empty when no unknown model is present")

    observed_at = state.get("model_inventory_observed_at")
    if inventory and (not isinstance(observed_at, str) or not observed_at):
        errors.append("non-empty model inventory requires model_inventory_observed_at")

    selected_backend = state.get("selected_backend")
    required_backend = state.get("required_backend")
    if selected_backend is not None and selected_backend not in ALLOWED_BACKENDS:
        errors.append("selected_backend must be 'chatgpt-web', 'grok-web', or null")
    if required_backend is not None and required_backend not in ALLOWED_BACKENDS:
        errors.append("required_backend must be 'chatgpt-web', 'grok-web', or null")

    selected_model = state.get("selected_cognitive_model")
    if selected_model is not None and (not isinstance(selected_model, str) or not selected_model):
        errors.append("selected_cognitive_model must be null or a non-empty string")
    elif selected_model is not None and selected_backend is None:
        errors.append("selected_cognitive_model requires an allowed selected_backend")
    elif selected_backend == "chatgpt-web" and selected_model is not None:
        if selected_model not in inventory_names:
            errors.append("selected ChatGPT model must appear in chatgpt_model_inventory")
        elif selected_model not in MODEL_PREFERENCE_BASELINE:
            errors.append("selected ChatGPT model must have an unambiguous policy rank")
        else:
            selected_index = inventory_index_by_name[selected_model]
            selected_item = inventory_by_name[selected_model]
            if selected_item.get("availability") != "available":
                errors.append("selected ChatGPT model must be marked available")
            if "Extra High" not in selected_item.get("reasoning_levels", []):
                errors.append("selected ChatGPT model must confirm Extra High support")
            higher_compatible = [
                item.get("model")
                for item in inventory[:selected_index]
                if isinstance(item, dict)
                and item.get("availability") == "available"
                and "Extra High" in item.get("reasoning_levels", [])
            ]
            if higher_compatible:
                errors.append(
                    "selected ChatGPT model is a premature fallback while a higher-priority "
                    "Extra High-capable model is available"
                )

    fallback_reason = state.get("model_fallback_reason")
    if not isinstance(fallback_reason, str):
        errors.append("model_fallback_reason must be a string")
    elif (
        selected_backend == "chatgpt-web"
        and selected_model in inventory_index_by_name
        and inventory_index_by_name[selected_model] > 0
        and not fallback_reason
    ):
        errors.append("a lower-priority ChatGPT model requires a non-empty fallback reason")
    elif fallback_reason and status == "ACTIVE" and selected_backend == "chatgpt-web":
        compatible = any(
            isinstance(item, dict)
            and item.get("availability") == "available"
            and "Extra High" in item.get("reasoning_levels", [])
            for item in inventory
        ) if isinstance(inventory, list) else False
        if not compatible:
            errors.append(
                "fallback has no available ChatGPT model with Extra High; "
                "status must be WAITING_HUMAN"
            )

    if state.get("exact_backend_required"):
        if required_backend is None or selected_backend != required_backend:
            errors.append("exact backend requirement is not satisfied")
    if state.get("exact_model_required"):
        required_model = state.get("required_model")
        if not required_model or selected_model != required_model:
            errors.append("exact model requirement is not satisfied")

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
