#!/usr/bin/env python3

import copy
import importlib.util
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("validate_run_state.py")
SPEC = importlib.util.spec_from_file_location("validate_run_state", MODULE_PATH)
assert SPEC and SPEC.loader
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


def valid_state():
    return {
        "schema_version": 1,
        "status": "ACTIVE",
        "state": "REVIEW_CANDIDATE",
        "task_class": "normal",
        "active_seconds": 1200,
        "mandatory_pause_at": "2026-08-03T12:00:00+08:00",
        "extension_authorization": None,
        "head_sha": "abc123",
        "verified_head_sha": "abc123",
        "review_package_head_sha": "abc123",
        "review_package_digest": "sha256:package",
        "review_round": 1,
        "review_package_count": 1,
        "implementation_rework_used": 0,
        "plan_rework_used": 0,
        "accepted_blocking_high_pending": False,
        "rework_trigger": None,
        "chatgpt_model_inventory": [
            {
                "model": "ChatGPT Pro",
                "reasoning_levels": ["Extra High"],
                "availability": "available",
            },
            {
                "model": "GPT-5.6 Sol",
                "reasoning_levels": ["Extra High", "High", "Medium"],
                "availability": "available",
            },
        ],
        "model_inventory_observed_at": "2026-08-03T10:00:00+08:00",
        "selected_backend": "chatgpt-web",
        "selected_cognitive_model": "ChatGPT Pro",
        "required_reasoning_level": "Extra High",
        "selected_reasoning_level": "Extra High",
        "model_fallback_reason": "",
        "reasoning_level_selection_reason": "fixed_skill_policy",
        "exact_backend_required": False,
        "exact_model_required": False,
        "exact_reasoning_level_required": True,
        "reviewers": [
            {
                "backend": "chatgpt-web",
                "head_sha": "abc123",
                "package_digest": "sha256:package",
                "selected_reasoning_level": "Extra High",
            },
            {
                "backend": "grok-web",
                "head_sha": "abc123",
                "package_digest": "sha256:package",
                "selected_reasoning_level": "Extra High",
            },
        ],
    }


class ValidateRunStateTests(unittest.TestCase):
    def assert_invalid(self, mutate, expected):
        state = copy.deepcopy(valid_state())
        mutate(state)
        errors = VALIDATOR.validate_state(state)
        self.assertTrue(any(expected in error for error in errors), errors)

    def test_valid_review_candidate(self):
        self.assertEqual([], VALIDATOR.validate_state(valid_state()))

    def test_rejects_package_four(self):
        self.assert_invalid(
            lambda state: state.update(review_package_count=4),
            "cannot exceed 3",
        )

    def test_rejects_rework_three(self):
        self.assert_invalid(
            lambda state: state.update(
                implementation_rework_used=3,
                rework_trigger="accepted_blocking_high",
            ),
            "cannot exceed 2",
        )

    def test_rejects_head_mismatch(self):
        self.assert_invalid(
            lambda state: state.update(verified_head_sha="different"),
            "identical non-empty",
        )

    def test_rejects_reviewer_digest_mismatch(self):
        self.assert_invalid(
            lambda state: state["reviewers"][1].update(package_digest="other"),
            "different package_digest",
        )

    def test_rejects_reasoning_downgrade(self):
        self.assert_invalid(
            lambda state: state.update(selected_reasoning_level="High"),
            "exactly 'Extra High'",
        )

    def test_rejects_active_normal_run_at_one_hour(self):
        self.assert_invalid(
            lambda state: state.update(active_seconds=3600),
            "mandatory pause",
        )

    def test_rejects_active_high_risk_run_at_three_hours(self):
        def mutate(state):
            state.update(task_class="high_risk", active_seconds=10800)

        self.assert_invalid(mutate, "mandatory pause")

    def test_waiting_human_is_valid_at_time_limit(self):
        state = valid_state()
        state.update(status="WAITING_HUMAN", active_seconds=3600)
        self.assertEqual([], VALIDATOR.validate_state(state))

    def test_selected_model_must_be_in_inventory(self):
        self.assert_invalid(
            lambda state: state.update(selected_cognitive_model="Unknown"),
            "must appear",
        )

    def test_rejects_fourth_round_after_high_finding(self):
        def mutate(state):
            state.update(
                review_round=3,
                review_package_count=3,
                accepted_blocking_high_pending=True,
            )

        self.assert_invalid(mutate, "package 4 is forbidden")

    def test_accepts_quota_fallback_with_extra_high(self):
        state = valid_state()
        state["chatgpt_model_inventory"][0]["availability"] = "quota_exhausted"
        state.update(
            selected_cognitive_model="GPT-5.6 Sol",
            model_fallback_reason="ChatGPT Pro and Grok quota exhausted",
        )
        self.assertEqual([], VALIDATOR.validate_state(state))

    def test_rejects_missing_exact_reasoning_policy(self):
        self.assert_invalid(
            lambda state: state.update(exact_reasoning_level_required=False),
            "must be true",
        )

    def test_rejects_fallback_without_extra_high_model(self):
        def mutate(state):
            for item in state["chatgpt_model_inventory"]:
                item["availability"] = "quota_exhausted"
            state.update(
                selected_cognitive_model=None,
                model_fallback_reason="preferred backends exhausted",
            )

        self.assert_invalid(mutate, "status must be WAITING_HUMAN")

    def test_rejects_unavailable_exact_backend(self):
        self.assert_invalid(
            lambda state: state.update(
                exact_backend_required=True,
                required_backend="grok-web",
                selected_backend="chatgpt-web",
            ),
            "exact backend requirement",
        )


if __name__ == "__main__":
    unittest.main()
