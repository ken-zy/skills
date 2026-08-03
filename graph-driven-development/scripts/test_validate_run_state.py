#!/usr/bin/env python3

import copy
import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPTS_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPTS_DIR))
import compute_review_package_digest as DIGEST  # noqa: E402

MODULE_PATH = SCRIPTS_DIR / "validate_run_state.py"
SPEC = importlib.util.spec_from_file_location("validate_run_state", MODULE_PATH)
assert SPEC and SPEC.loader
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


HEAD = "a" * 40
REQUEST_SHA = "1" * 64
CANONICAL_REQUEST_SHA = "2" * 64
DIFF_SHA = "3" * 64
CONTEXT_SHA = "4" * 64
PACKAGE_DIGEST = DIGEST.digest_from_hashes(
    head_sha=HEAD,
    request_canonical_sha256=CANONICAL_REQUEST_SHA,
    full_diff_sha256=DIFF_SHA,
    review_context_sha256=CONTEXT_SHA,
)


def reviewer(conversation_id: str, backend: str) -> dict:
    return {
        "conversation_id": conversation_id,
        "backend": backend,
        "role": "reviewer",
        "read_only": True,
        "authored_candidate": False,
        "head_sha": HEAD,
        "package_digest": PACKAGE_DIGEST,
        "selected_reasoning_level": "Extra High",
    }


def valid_state():
    return {
        "schema_version": 2,
        "status": "ACTIVE",
        "state": "REVIEW_CANDIDATE",
        "task_class": "normal",
        "active_seconds": 1200,
        "mandatory_pause_at": "2026-08-03T12:00:00+08:00",
        "extension_authorization": None,
        "head_sha": HEAD,
        "verified_head_sha": HEAD,
        "review_package_head_sha": HEAD,
        "review_package_digest": PACKAGE_DIGEST,
        "package_digest_algorithm": DIGEST.ALGORITHM,
        "review_request_sha256": REQUEST_SHA,
        "review_request_canonical_sha256": CANONICAL_REQUEST_SHA,
        "full_diff_sha256": DIFF_SHA,
        "review_context_sha256": CONTEXT_SHA,
        "review_diff_verified": True,
        "review_package_changed_paths": ["graph-driven-development/SKILL.md"],
        "review_package_diff_paths": ["graph-driven-development/SKILL.md"],
        "review_package_binary_paths": [],
        "review_package_symlink_paths": [],
        "review_round": 1,
        "review_package_count": 1,
        "implementation_rework_used": 0,
        "plan_rework_used": 0,
        "accepted_blocking_high_pending": False,
        "rework_trigger": None,
        "chatgpt_model_inventory": [
            {
                "model": "ChatGPT Pro",
                "preference_rank": 0,
                "reasoning_levels": ["Extra High"],
                "availability": "available",
            },
            {
                "model": "GPT-5.6 Sol",
                "preference_rank": 1,
                "reasoning_levels": ["Extra High", "High", "Medium"],
                "availability": "available",
            },
        ],
        "model_inventory_observed_at": "2026-08-03T10:00:00+08:00",
        "selected_backend": "chatgpt-web",
        "selected_cognitive_model": "ChatGPT Pro",
        "required_backend": None,
        "required_model": None,
        "required_reasoning_level": "Extra High",
        "selected_reasoning_level": "Extra High",
        "model_fallback_reason": "",
        "reasoning_level_selection_reason": "fixed_skill_policy",
        "exact_backend_required": False,
        "exact_model_required": False,
        "exact_reasoning_level_required": True,
        "implementation_author_conversation_ids": ["author-1"],
        "reviewers": [
            reviewer("reviewer-1", "chatgpt-web"),
            reviewer("reviewer-2", "grok-web"),
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

    def test_rejects_schema_v1(self):
        self.assert_invalid(lambda state: state.update(schema_version=1), "schema_version")

    def test_rejects_package_four(self):
        self.assert_invalid(lambda state: state.update(review_package_count=4), "cannot exceed 3")

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
            lambda state: state.update(verified_head_sha="b" * 40),
            "identical non-empty",
        )

    def test_rejects_package_digest_mismatch(self):
        self.assert_invalid(
            lambda state: state.update(review_package_digest="sha256:" + "f" * 64),
            "does not match",
        )

    def test_rejects_changed_path_omission(self):
        self.assert_invalid(
            lambda state: state.update(review_package_diff_paths=[]),
            "must exactly equal",
        )

    def test_rejects_binary_review_package(self):
        self.assert_invalid(
            lambda state: state.update(review_package_binary_paths=["asset.bin"]),
            "binary changed paths block",
        )

    def test_accepts_included_symlink_path(self):
        state = valid_state()
        state["review_package_symlink_paths"] = ["graph-driven-development/SKILL.md"]
        self.assertEqual([], VALIDATOR.validate_state(state))

    def test_rejects_omitted_symlink_path(self):
        self.assert_invalid(
            lambda state: state.update(review_package_symlink_paths=["link"]),
            "symlink paths must be included",
        )

    def test_rejects_reasoning_downgrade(self):
        self.assert_invalid(
            lambda state: state.update(selected_reasoning_level="High"),
            "exactly 'Extra High'",
        )

    def test_rejects_active_normal_run_at_one_hour(self):
        self.assert_invalid(lambda state: state.update(active_seconds=3600), "mandatory pause")

    def test_rejects_active_high_risk_run_at_three_hours(self):
        self.assert_invalid(
            lambda state: state.update(task_class="high_risk", active_seconds=10800),
            "mandatory pause",
        )

    def test_waiting_human_is_valid_at_time_limit(self):
        state = valid_state()
        state.update(status="WAITING_HUMAN", active_seconds=3600)
        self.assertEqual([], VALIDATOR.validate_state(state))

    def test_valid_post_pause_extension(self):
        state = valid_state()
        state.update(
            active_seconds=3600,
            extension_authorization={
                "authorized_by": "jdy",
                "authorization_ref": "message-123",
                "authorized_at_active_seconds": 3600,
                "new_active_limit_seconds": 5400,
                "new_deadline": "2026-08-03T13:30:00+08:00",
            },
        )
        self.assertEqual([], VALIDATOR.validate_state(state))

    def test_rejects_extension_before_initial_pause(self):
        self.assert_invalid(
            lambda state: state.update(
                extension_authorization={
                    "authorized_by": "jdy",
                    "authorization_ref": "message-123",
                    "authorized_at_active_seconds": 3500,
                    "new_active_limit_seconds": 5400,
                    "new_deadline": "2026-08-03T13:30:00+08:00",
                }
            ),
            "after the mandatory pause",
        )

    def test_rejects_active_run_at_extended_limit(self):
        self.assert_invalid(
            lambda state: state.update(
                active_seconds=5400,
                extension_authorization={
                    "authorized_by": "jdy",
                    "authorization_ref": "message-123",
                    "authorized_at_active_seconds": 3600,
                    "new_active_limit_seconds": 5400,
                    "new_deadline": "2026-08-03T13:30:00+08:00",
                },
            ),
            "mandatory pause at 5400",
        )

    def test_rejects_delivered_with_pending_high(self):
        self.assert_invalid(
            lambda state: state.update(
                status="DELIVERED",
                accepted_blocking_high_pending=True,
            ),
            "cannot retain blocking/high",
        )

    def test_rejects_package_three_pending_high_as_active(self):
        self.assert_invalid(
            lambda state: state.update(
                review_round=3,
                review_package_count=3,
                accepted_blocking_high_pending=True,
            ),
            "package 4 is forbidden",
        )

    def test_accepts_package_three_pending_high_while_waiting(self):
        state = valid_state()
        state.update(
            status="WAITING_HUMAN",
            review_round=3,
            review_package_count=3,
            accepted_blocking_high_pending=True,
        )
        self.assertEqual([], VALIDATOR.validate_state(state))

    def test_rejects_forbidden_selected_backend(self):
        self.assert_invalid(
            lambda state: state.update(selected_backend="claude-web"),
            "selected_backend",
        )

    def test_rejects_chatgpt_pro_backend_alias(self):
        self.assert_invalid(
            lambda state: state.update(selected_backend="chatgpt-pro-web"),
            "selected_backend",
        )

    def test_rejects_forbidden_exact_backend_even_when_equal(self):
        self.assert_invalid(
            lambda state: state.update(
                exact_backend_required=True,
                required_backend="claude-web",
                selected_backend="claude-web",
            ),
            "required_backend",
        )

    def test_rejects_premature_model_fallback(self):
        self.assert_invalid(
            lambda state: state.update(selected_cognitive_model="GPT-5.6 Sol"),
            "premature fallback",
        )

    def test_accepts_quota_fallback_with_extra_high(self):
        state = valid_state()
        state["chatgpt_model_inventory"][0]["availability"] = "quota_exhausted"
        state.update(
            selected_cognitive_model="GPT-5.6 Sol",
            model_fallback_reason="ChatGPT Pro quota exhausted",
        )
        self.assertEqual([], VALIDATOR.validate_state(state))

    def test_rejects_inventory_rank_gap(self):
        self.assert_invalid(
            lambda state: state["chatgpt_model_inventory"][1].update(preference_rank=3),
            "preference_rank",
        )

    def test_review_candidate_can_wait_without_reviewers(self):
        state = valid_state()
        state["reviewers"] = []
        self.assertEqual([], VALIDATOR.validate_state(state))

    def test_review_completion_still_requires_package_evidence(self):
        self.assert_invalid(
            lambda state: state.update(
                state="READY_FOR_AUTHORIZED_NEXT_ACTION",
                review_package_digest=None,
            ),
            "requires a sha256 review_package_digest",
        )

    def test_normal_review_completion_requires_one_reviewer(self):
        self.assert_invalid(
            lambda state: state.update(
                state="READY_FOR_AUTHORIZED_NEXT_ACTION",
                reviewers=[],
            ),
            "requires at least 1 reviewer",
        )

    def test_high_risk_review_completion_requires_two_reviewers(self):
        self.assert_invalid(
            lambda state: state.update(
                state="READY_FOR_AUTHORIZED_NEXT_ACTION",
                task_class="high_risk",
                reviewers=[state["reviewers"][0]],
            ),
            "requires at least 2 reviewer",
        )

    def test_rejects_stale_reviewer_head(self):
        self.assert_invalid(
            lambda state: state["reviewers"][0].update(head_sha="b" * 40),
            "current package head",
        )

    def test_rejects_reviewer_digest_mismatch_even_on_stale_head(self):
        def mutate(state):
            state["reviewers"][0].update(
                head_sha="b" * 40,
                package_digest="sha256:" + "f" * 64,
            )

        self.assert_invalid(mutate, "current package digest")

    def test_rejects_duplicate_reviewer_conversation(self):
        self.assert_invalid(
            lambda state: state["reviewers"][1].update(conversation_id="reviewer-1"),
            "must be distinct",
        )

    def test_rejects_implementation_author_self_review(self):
        self.assert_invalid(
            lambda state: state["reviewers"][0].update(conversation_id="author-1"),
            "authored the candidate",
        )

    def test_rejects_unavailable_exact_backend(self):
        self.assert_invalid(
            lambda state: state.update(
                exact_backend_required=True,
                required_backend="grok-web",
                selected_backend="chatgpt-web",
            ),
            "exact backend requirement",
        )

    def test_rejects_model_without_backend(self):
        self.assert_invalid(
            lambda state: state.update(selected_backend=None),
            "requires an allowed selected_backend",
        )


if __name__ == "__main__":
    unittest.main()
