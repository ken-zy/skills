#!/usr/bin/env python3
"""Focused tests for the schema-v3 run-state validator."""

from __future__ import annotations

import copy
import importlib.util
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location(
    "validate_run_state", SCRIPT_DIR / "validate_run_state.py"
)
assert SPEC and SPEC.loader
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)

HEAD = "a" * 40
PACKAGE_ID = "sha256:" + "b" * 64


def reviewer(
    conversation_id: str = "reviewer-1",
    *,
    backend: str = "chatgpt-web",
    visible_model: str = "GPT-5.6 Sol Pro",
    selection_label: str = "Pro",
    reasoning_setting: str | None = None,
) -> dict:
    return {
        "conversation_id": conversation_id,
        "backend": backend,
        "visible_model": visible_model,
        "selection_label": selection_label,
        "reasoning_setting": reasoning_setting,
        "selection_evidence_ref": f"browser-evidence-{conversation_id}",
        "read_only": True,
        "authored_candidate": False,
        "head_sha": HEAD,
        "package_id": PACKAGE_ID,
        "verdict": "PASS",
        "findings_reconciled": True,
        "blocking_high_remaining": False,
    }


def valid_state(*, task_class: str = "normal", complete: bool = False) -> dict:
    state = {
        "schema_version": 3,
        "status": "ACTIVE",
        "state": "IMPLEMENTING",
        "task_class": task_class,
        "task_worktree": "/tmp/task-worktree",
        "task_branch": "codex/task",
        "base_commit": "0" * 40,
        "head_sha": None,
        "verified_head_sha": None,
        "active_seconds": 10,
        "active_limit_seconds": 10_800 if task_class == "high_risk" else 3_600,
        "time_extension_authorization_ref": None,
        "review_package_id": None,
        "review_package_count": 0,
        "review_package_limit": 3,
        "implementation_rework_used": 0,
        "implementation_rework_limit": 2,
        "budget_extension_authorization_ref": None,
        "accepted_blocking_high_pending": False,
        "reviewers": [],
    }
    if complete:
        state.update(
            {
                "state": "READY_FOR_AUTHORIZED_NEXT_ACTION",
                "head_sha": HEAD,
                "verified_head_sha": HEAD,
                "review_package_id": PACKAGE_ID,
                "review_package_count": 1,
                "reviewers": [reviewer()],
            }
        )
        if task_class == "high_risk":
            state["reviewers"].append(
                reviewer(
                    "reviewer-2",
                    backend="grok-web",
                    visible_model="Grok 4.5",
                    selection_label="Expert",
                )
            )
    return state


class RunStateV3Tests(unittest.TestCase):
    def assert_invalid(self, state: dict, text: str) -> None:
        self.assertTrue(
            any(text in error for error in VALIDATOR.validate_state(state)),
            VALIDATOR.validate_state(state),
        )

    def test_valid_normal_active_state(self):
        self.assertEqual([], VALIDATOR.validate_state(valid_state()))

    def test_valid_normal_completion(self):
        self.assertEqual([], VALIDATOR.validate_state(valid_state(complete=True)))

    def test_valid_chatgpt_extra_high_completion(self):
        state = valid_state(complete=True)
        state["reviewers"] = [
            reviewer(
                visible_model="GPT-5.6 Sol",
                selection_label="Extra High",
                reasoning_setting="Extra High",
            )
        ]
        self.assertEqual([], VALIDATOR.validate_state(state))

    def test_valid_grok_expert_completion(self):
        state = valid_state(complete=True)
        state["reviewers"] = [
            reviewer(
                backend="grok-web",
                visible_model="Grok 4.5",
                selection_label="Expert",
            )
        ]
        self.assertEqual([], VALIDATOR.validate_state(state))

    def test_valid_high_risk_completion_requires_two_reviewers(self):
        state = valid_state(task_class="high_risk", complete=True)
        self.assertEqual([], VALIDATOR.validate_state(state))
        state["reviewers"].pop()
        self.assert_invalid(state, "at least 2 independent")

    def test_missing_core_field_is_rejected(self):
        state = valid_state()
        del state["task_worktree"]
        self.assert_invalid(state, "missing required field: task_worktree")

    def test_schema_state_and_status_are_checked(self):
        state = valid_state()
        state["schema_version"] = 2
        state["state"] = "UNKNOWN"
        state["status"] = "UNKNOWN"
        errors = VALIDATOR.validate_state(state)
        self.assertTrue(any("schema_version" in error for error in errors))
        self.assertTrue(any("state must be" in error for error in errors))
        self.assertTrue(any("status must be" in error for error in errors))

    def test_terminal_state_and_status_must_match(self):
        state = valid_state()
        state["state"] = "WAITING_HUMAN"
        self.assert_invalid(state, "terminal state/status")

    def test_active_time_limit_forces_pause(self):
        state = valid_state()
        state["active_seconds"] = 3_600
        self.assert_invalid(state, "active-time limit")

    def test_raised_time_limit_requires_only_authorization_reference(self):
        state = valid_state()
        state["active_limit_seconds"] = 4_000
        self.assert_invalid(state, "time_extension_authorization_ref")
        state["time_extension_authorization_ref"] = "user-message-42"
        self.assertEqual([], VALIDATOR.validate_state(state))

    def test_saved_budget_limits_allow_authorized_package_four_and_rework_three(self):
        state = valid_state()
        state.update(
            {
                "review_package_count": 4,
                "review_package_limit": 4,
                "implementation_rework_used": 3,
                "implementation_rework_limit": 3,
                "budget_extension_authorization_ref": "user-message-43",
            }
        )
        self.assertEqual([], VALIDATOR.validate_state(state))

    def test_raised_budget_limit_requires_authorization_reference(self):
        state = valid_state()
        state["review_package_limit"] = 4
        self.assert_invalid(state, "budget_extension_authorization_ref")

    def test_counts_cannot_exceed_saved_limits(self):
        state = valid_state()
        state["review_package_count"] = 4
        state["implementation_rework_used"] = 3
        errors = VALIDATOR.validate_state(state)
        self.assertTrue(any("review_package_count" in error for error in errors))
        self.assertTrue(any("implementation_rework_used" in error for error in errors))

    def test_pending_high_at_budget_limit_forces_pause(self):
        state = valid_state()
        state.update(
            {
                "accepted_blocking_high_pending": True,
                "review_package_count": 3,
            }
        )
        self.assert_invalid(state, "requires WAITING_HUMAN")

    def test_completion_requires_matching_verified_head_and_package(self):
        state = valid_state(complete=True)
        state["verified_head_sha"] = "c" * 40
        state["review_package_id"] = "bad"
        state["review_package_count"] = 0
        errors = VALIDATOR.validate_state(state)
        self.assertTrue(any("identical non-empty" in error for error in errors))
        self.assertTrue(any("sha256 review_package_id" in error for error in errors))
        self.assertTrue(any("review_package_count" in error for error in errors))

    def test_completion_cannot_retain_pending_high(self):
        state = valid_state(complete=True)
        state["accepted_blocking_high_pending"] = True
        self.assert_invalid(state, "cannot retain")

    def test_reviewer_must_be_independent(self):
        state = valid_state(complete=True)
        state["implementation_author_conversation_ids"] = ["reviewer-1"]
        self.assert_invalid(state, "authored the candidate")

    def test_reviewer_ids_must_be_distinct(self):
        state = valid_state(task_class="high_risk", complete=True)
        state["reviewers"][1]["conversation_id"] = "reviewer-1"
        self.assert_invalid(state, "must be distinct")

    def test_reviewer_backend_selection_evidence_head_and_package_are_bound(self):
        state = valid_state(complete=True)
        current = state["reviewers"][0]
        current.update(
            {
                "backend": "other-site",
                "visible_model": "",
                "selection_label": "",
                "reasoning_setting": "",
                "selection_evidence_ref": "",
                "head_sha": "d" * 40,
                "package_id": "sha256:" + "e" * 64,
            }
        )
        errors = VALIDATOR.validate_state(state)
        for text in (
            "backend",
            "visible_model",
            "selection_label",
            "reasoning_setting",
            "selection_evidence_ref",
            "current head",
            "current review package",
        ):
            self.assertTrue(any(text in error for error in errors), errors)

    def test_reasoning_setting_must_be_explicitly_present_even_when_null(self):
        state = valid_state(complete=True)
        del state["reviewers"][0]["reasoning_setting"]
        self.assert_invalid(state, "reasoning_setting must be present")

    def test_completion_requires_pass_reconciled_and_no_high(self):
        state = valid_state(complete=True)
        current = state["reviewers"][0]
        current.update(
            {
                "verdict": "CHANGES_REQUESTED",
                "findings_reconciled": False,
                "blocking_high_remaining": True,
            }
        )
        errors = VALIDATOR.validate_state(state)
        for text in ("verdict", "findings_reconciled", "blocking_high_remaining"):
            self.assertTrue(any(text in error for error in errors), errors)

    def test_future_visible_model_does_not_invalidate_approved_profile_evidence(self):
        state = valid_state(complete=True)
        state["reviewers"][0]["visible_model"] = "future-chatgpt-model"
        self.assertEqual([], VALIDATOR.validate_state(state))

    def test_validator_does_not_claim_git_or_ci_truth(self):
        state = valid_state()
        state["git_clean"] = False
        state["pr_ci"] = "unknown"
        self.assertEqual([], VALIDATOR.validate_state(state))

    def test_input_is_not_mutated(self):
        state = valid_state(complete=True)
        before = copy.deepcopy(state)
        VALIDATOR.validate_state(state)
        self.assertEqual(before, state)


if __name__ == "__main__":
    unittest.main()
