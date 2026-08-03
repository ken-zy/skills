#!/usr/bin/env python3
"""Validate critical graph-driven-development run-state invariants.

This command is deliberately read-only. It validates one JSON snapshot and
never performs transitions, repository operations, or browser operations.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


TASK_LIMITS = {"normal": 3_600, "high_risk": 10_800}
REVIEW_STATES = {"REVIEW_CANDIDATE", "REVIEWING"}
ALLOWED_STATUSES = {"ACTIVE", "WAITING_HUMAN", "DELIVERED", "FAILED", "CANCELLED"}


def _is_non_negative_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def validate_state(state: Any) -> list[str]:
    """Return invariant violations for a decoded run-state snapshot."""
    if not isinstance(state, dict):
        return ["top-level JSON value must be an object"]

    errors: list[str] = []
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
    if not isinstance(phase, str) or not phase:
        errors.append("state must be a non-empty string")

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

    if task_class in TASK_LIMITS and _is_non_negative_int(active_seconds):
        limit = TASK_LIMITS[task_class]
        if active_seconds >= limit and status == "ACTIVE":
            errors.append(
                f"ACTIVE run reached mandatory pause at {limit} active seconds; "
                "status must be WAITING_HUMAN or terminal"
            )

    head = state.get("head_sha")
    verified_head = state.get("verified_head_sha")
    package_head = state.get("review_package_head_sha")
    package_digest = state.get("review_package_digest")

    if phase in REVIEW_STATES:
        if not head or head != verified_head or head != package_head:
            errors.append(
                "review candidate requires identical non-empty head_sha, "
                "verified_head_sha, and review_package_head_sha"
            )
        if not isinstance(package_digest, str) or not package_digest:
            errors.append("review candidate requires review_package_digest")
        if not _is_non_negative_int(package_count) or package_count < 1:
            errors.append("review candidate requires review_package_count >= 1")
        if review_round != package_count:
            errors.append("review_round must equal review_package_count for a review candidate")

    pending_high = state.get("accepted_blocking_high_pending")
    if not isinstance(pending_high, bool):
        errors.append("accepted_blocking_high_pending must be a boolean")
    elif pending_high and package_count == 3 and status == "ACTIVE":
        errors.append(
            "package 3 has an accepted blocking/high finding; status must be "
            "WAITING_HUMAN or FAILED and package 4 is forbidden"
        )

    trigger = state.get("rework_trigger")
    if trigger not in (None, "accepted_blocking_high", "required_pr_ci_failure"):
        errors.append(
            "rework_trigger must be null, 'accepted_blocking_high', or "
            "'required_pr_ci_failure'"
        )
    if _is_non_negative_int(rework_count) and rework_count > 0 and trigger is None:
        errors.append("a used implementation rework requires an allowed rework_trigger")

    reviewers = state.get("reviewers", [])
    if not isinstance(reviewers, list):
        errors.append("reviewers must be a list")
    else:
        for index, reviewer in enumerate(reviewers):
            if not isinstance(reviewer, dict):
                errors.append(f"reviewers[{index}] must be an object")
                continue
            reviewer_head = reviewer.get("head_sha")
            reviewer_digest = reviewer.get("package_digest")
            if reviewer_head == package_head and reviewer_digest != package_digest:
                errors.append(
                    f"reviewers[{index}] uses a different package_digest for the package head"
                )
            if reviewer.get("selected_reasoning_level") != "Extra High":
                errors.append(
                    f"reviewers[{index}].selected_reasoning_level must be exactly 'Extra High'"
                )

    inventory = state.get("chatgpt_model_inventory", [])
    inventory_by_name: dict[str, dict[str, Any]] = {}
    if not isinstance(inventory, list):
        errors.append("chatgpt_model_inventory must be a list")
        inventory_names: list[str] = []
    else:
        inventory_names = []
        for index, item in enumerate(inventory):
            if not isinstance(item, dict):
                errors.append(f"chatgpt_model_inventory[{index}] must be an object")
                continue
            model = item.get("model")
            reasoning_levels = item.get("reasoning_levels")
            availability = item.get("availability")
            if not isinstance(model, str) or not model:
                errors.append(f"chatgpt_model_inventory[{index}].model must be non-empty")
            else:
                inventory_names.append(model)
                inventory_by_name[model] = item
            if not isinstance(reasoning_levels, list) or any(
                not isinstance(level, str) for level in reasoning_levels
            ):
                errors.append(
                    f"chatgpt_model_inventory[{index}].reasoning_levels must be a list of strings"
                )
            if not isinstance(availability, str) or not availability:
                errors.append(
                    f"chatgpt_model_inventory[{index}].availability must be non-empty"
                )

    selected_model = state.get("selected_cognitive_model")
    if selected_model is not None:
        if not isinstance(selected_model, str) or not selected_model:
            errors.append("selected_cognitive_model must be null or a non-empty string")
        elif state.get("selected_backend") == "chatgpt-web":
            if selected_model not in inventory_names:
                errors.append("selected ChatGPT model must appear in chatgpt_model_inventory")
            else:
                selected_item = inventory_by_name[selected_model]
                if selected_item.get("availability") != "available":
                    errors.append("selected ChatGPT model must be marked available")
                if "Extra High" not in selected_item.get("reasoning_levels", []):
                    errors.append("selected ChatGPT model must confirm Extra High support")

    observed_at = state.get("model_inventory_observed_at")
    if inventory and (not isinstance(observed_at, str) or not observed_at):
        errors.append("non-empty model inventory requires model_inventory_observed_at")

    fallback_reason = state.get("model_fallback_reason")
    if not isinstance(fallback_reason, str):
        errors.append("model_fallback_reason must be a string")
    elif fallback_reason and status == "ACTIVE" and isinstance(inventory, list):
        compatible = any(
            isinstance(item, dict)
            and item.get("availability") == "available"
            and "Extra High" in item.get("reasoning_levels", [])
            for item in inventory
        )
        if not compatible:
            errors.append(
                "fallback has no available ChatGPT model with Extra High; "
                "status must be WAITING_HUMAN"
            )

    selected_backend = state.get("selected_backend")
    if state.get("exact_backend_required"):
        required_backend = state.get("required_backend")
        if not required_backend or selected_backend != required_backend:
            errors.append("exact backend requirement is not satisfied")
    if state.get("exact_model_required"):
        required_model = state.get("required_model")
        if not required_model or selected_model != required_model:
            errors.append("exact model requirement is not satisfied")

    extension = state.get("extension_authorization")
    if extension is not None:
        if not isinstance(extension, dict):
            errors.append("extension_authorization must be null or an object")
        else:
            if not extension.get("authorized_by") or not extension.get("new_deadline"):
                errors.append(
                    "extension_authorization requires authorized_by and new_deadline"
                )

    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("state_file", type=Path, help="JSON run-state snapshot")
    args = parser.parse_args(argv)

    try:
        state = json.loads(args.state_file.read_text(encoding="utf-8"))
    except OSError as exc:
        print(f"ERROR: cannot read {args.state_file}: {exc}", file=sys.stderr)
        return 2
    except json.JSONDecodeError as exc:
        print(f"ERROR: invalid JSON in {args.state_file}: {exc}", file=sys.stderr)
        return 2

    errors = validate_state(state)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print(f"OK: {args.state_file} satisfies critical run-state invariants")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
