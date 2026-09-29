"""Behavioral fixtures for calendar eligibility, missingness and safe arithmetic."""
import copy
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from defillama_lib.analysis import analyze_series, derive_metrics, finite_number

UTC = timezone.utc


def epoch(day, hour=0):
    return int(datetime.fromisoformat(day).replace(tzinfo=UTC, hour=hour).timestamp())


def fixture(metric="fees", kind="flow", values=None, first="2024-02-01", **overrides):
    values = values if values is not None else [10] * 29
    stamp = epoch(first)
    entity = {"id": "711", "slug": "example", "name": "Example", "chains": ["Polygon"], "parentProtocol": "parent#x", "category": "Prediction Market"}
    result = {"entity": entity, "metric": metric, "kind": kind, "unit": "USD",
              "points": [[stamp + i * 86400, value] for i, value in enumerate(values)],
              "source_ids": [metric], "time_semantics": "utc_calendar_day" if kind == "flow" else "snapshot",
              "timestamp_role": "interval_start" if kind == "flow" else "sample_time",
              "semantic_evidence": {"revision": "test-adapter", "verified": True},
              "scope": {"identity": "711", "version": "international", "chains": ["Polygon"], "category": "Prediction Market"}, "status": "ok", "warnings": []}
    result.update(overrides)
    return result


NOW = epoch("2024-03-01", 12)


class AnalysisTests(unittest.TestCase):
    def test_leap_equal_windows_and_negative_revenue(self):
        rows = analyze_series([fixture(metric="revenue", values=[10] * 22 + [-5] * 7)], days=[7], now=NOW)
        row = rows[0]
        self.assertEqual(row["period_start"], "2024-02-23T00:00:00Z")
        self.assertEqual(row["period_end"], "2024-03-01T00:00:00Z")
        self.assertEqual(row["previous_period_start"], "2024-02-16T00:00:00Z")
        self.assertEqual(row["value"], -35)
        self.assertEqual(row["previous_value"], 70)
        self.assertEqual(row["change_pct"], -150)
        self.assertEqual(row["status"], "ok")

    def test_rolling_dates_do_not_become_calendar(self):
        for semantics, role in (("rolling_window", "sample_time"), ("unknown", "unknown")):
            source = fixture(time_semantics=semantics, timestamp_role=role)
            row = analyze_series([source], days=[7], now=NOW)[0]
            self.assertIsNone(row["value"])
            self.assertIsNone(row["change_pct"])
            self.assertEqual(row["source_observations"], source["points"])
            self.assertEqual(row["alignment"]["participants"], [])
            self.assertEqual(row["status"], "unavailable")
            returned = row["coverage"]["returned_observations"]
            self.assertEqual(returned["input_count"], 29)
            self.assertEqual(returned["valid_timestamp_count"], 29)
            self.assertEqual(returned["finite_value_count"], 29)
            self.assertEqual(row["coverage"]["current"]["observed_days"], 0)

    def test_drifting_rolling_collection_and_mixed_comparison(self):
        rolling = fixture(time_semantics="rolling_window", timestamp_role="sample_time", values=[12] * 10)
        rolling["points"] = [[stamp + (8 if i % 2 else 10) * 3600, value] for i, (stamp, value) in enumerate(rolling["points"])]
        verified = fixture()
        rows = analyze_series([rolling, verified], days=[7], now=NOW, align="metric")
        self.assertIsNone(rows[0]["value"])
        self.assertEqual(rows[1]["value"], 70)
        self.assertEqual(rows[1]["alignment"]["chosen_end_date"], "2024-02-29")
        self.assertEqual(len(rows[1]["alignment"]["participants"]), 1)

    def test_unproven_midnight_does_not_establish_semantics(self):
        for update in ({"semantic_evidence": None}, {"timestamp_role": "sample_time"}):
            row = analyze_series([fixture(**update)], days=[7], now=NOW)[0]
            self.assertIsNone(row["value"])

    def test_interval_end_and_nonmidnight_rejected(self):
        source = fixture(timestamp_role="interval_end")
        source["points"] = [[stamp + 86400, value] for stamp, value in source["points"]]
        row = analyze_series([source], days=[7], now=NOW)[0]
        self.assertEqual(row["value"], 70)
        self.assertEqual(row["period_end"], "2024-03-01T00:00:00Z")
        source["points"][-1][0] += 1
        row = analyze_series([source], days=[7], now=NOW)[0]
        self.assertIsNone(row["value"])

    def test_missing_day_partial_sum_not_comparable(self):
        source = fixture()
        source["points"].pop(-2)
        row = analyze_series([source], days=[7], now=NOW)[0]
        self.assertIsNone(row["value"])
        self.assertEqual(row["partial_sum"], 60)
        self.assertEqual(row["coverage"]["current"]["missing_dates"], ["2024-02-28"])
        self.assertEqual(row["previous_value"], 70)

    def test_missing_baseline_preserves_current(self):
        source = fixture(first="2024-02-23", values=[0] * 7)
        row = analyze_series([source], days=[7], now=NOW)[0]
        self.assertEqual(row["value"], 0)
        self.assertIsNone(row["previous_value"])
        self.assertIsNone(row["change_pct"])
        self.assertEqual(row["status"], "partial")

    def test_absent_series_is_not_an_observed_zero(self):
        row = analyze_series([fixture(values=[])], days=[7], now=NOW)[0]
        self.assertIsNone(row["value"])
        self.assertIsNone(row["partial_sum"])
        self.assertEqual(row["coverage"]["current"]["observed_days"], 0)

    def test_nonpositive_prior_disables_pct(self):
        for value in (0, -2):
            row = analyze_series([fixture(values=[value] * 22 + [4] * 7)], days=[7], now=NOW)[0]
            self.assertEqual(row["value"], 28)
            self.assertIsNone(row["change_pct"])

    def test_current_day_excluded_and_explicit_not_shifted(self):
        source = fixture(values=[10] * 30)
        default = analyze_series([source], days=[7], now=NOW)[0]
        self.assertEqual(default["period_end"], "2024-03-01T00:00:00Z")
        explicit = analyze_series([source], start="2024-02-24", end="2024-03-01", now=NOW)[0]
        self.assertEqual(explicit["period_end"], "2024-03-02T00:00:00Z")
        self.assertIsNone(explicit["value"])

    def test_stock_latest_null_no_rollback_and_no_sum(self):
        source = fixture(kind="stock", metric="tvl")
        source["points"] += [[epoch("2024-02-29", 8), 30], [epoch("2024-02-29", 10), None]]
        row = analyze_series([source], days=[7], now=NOW)[0]
        self.assertIsNone(row["value"])
        self.assertEqual(row["observed_at"], "2024-02-29T10:00:00Z")
        self.assertEqual(row["previous_value"], 10)
        self.assertEqual(row["alignment"]["chosen_end_date"], "2024-02-29")
        source["points"][-1][1] = 35
        row = analyze_series([source], days=[7], now=NOW)[0]
        self.assertEqual(row["value"], 35)
        self.assertIsNone(row["partial_sum"])

    def test_stock_baseline_not_nearest_filled(self):
        source = fixture(kind="stock", metric="tvl")
        source["points"] = [p for p in source["points"] if p[0] != epoch("2024-02-22")]
        row = analyze_series([source], days=[7], now=NOW)[0]
        self.assertEqual(row["value"], 10)
        self.assertIsNone(row["previous_value"])

    def test_alignment_all_and_by_metric_preserve_failures(self):
        a, b = fixture(), fixture(metric="volume", values=[20] * 28)
        missing = fixture(metric="revenue", status="unavailable", points=[], reason="HTTP failure")
        rows = analyze_series([a, b, missing], days=[7], now=NOW)
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]["period_end"], "2024-02-29T00:00:00Z")
        self.assertEqual(rows[0]["alignment"]["dropped_newer_dates"], ["2024-02-29"])
        self.assertEqual(rows[2]["reason"], "HTTP failure")
        rows = analyze_series([a, b], days=[7], now=NOW, align="metric")
        self.assertNotEqual(rows[0]["period_end"], rows[1]["period_end"])

    def test_wholly_null_old_series_cannot_drag_valid_alignment_backward(self):
        for kind in ("flow", "stock"):
            for align in ("all", "metric"):
                usable = fixture(kind=kind)
                unusable = fixture(kind=kind, values=[None] * 10)
                rows = analyze_series([usable, unusable], days=[7], now=NOW, align=align)
                self.assertEqual(rows[0]["alignment"]["chosen_end_date"], "2024-02-29")
                self.assertEqual(len(rows[0]["alignment"]["participants"]), 1)
                self.assertEqual(rows[0]["value"], 70 if kind == "flow" else 10)
                self.assertIsNone(rows[1]["value"])
                self.assertEqual(rows[1]["status"], "unavailable")
                self.assertIn("excluded from common alignment", rows[1]["reason"])
                self.assertEqual(rows[1]["coverage"]["returned_observations"]["finite_value_count"], 0)

    def test_earlier_valid_and_latest_null_still_align_to_latest_null(self):
        for kind in ("flow", "stock"):
            usable = fixture(kind=kind)
            with_gap = fixture(kind=kind, values=[10] * 27 + [None])
            rows = analyze_series([usable, with_gap], days=[7], now=NOW)
            self.assertEqual(rows[0]["alignment"]["chosen_end_date"], "2024-02-28")
            self.assertEqual(len(rows[0]["alignment"]["participants"]), 2)
            self.assertIsNone(rows[1]["value"])
            self.assertEqual(rows[1]["status"], "partial")

    def test_duplicates_do_not_doublecount_and_conflicts_fail(self):
        source = fixture()
        source["points"].append(source["points"][-1].copy())
        row = analyze_series([source], days=[7], now=NOW)[0]
        self.assertEqual(row["value"], 70)
        self.assertTrue(row["warnings"])
        source["points"][-1][1] = 20
        row = analyze_series([source], days=[7], now=NOW)[0]
        self.assertIsNone(row["value"])
        self.assertEqual(row["status"], "unavailable")

    def test_invalid_values_timestamps_and_overflow(self):
        for value in (True, float("inf"), float("nan"), "10"):
            source = fixture()
            source["points"][-1][1] = value
            self.assertIsNone(analyze_series([source], days=[7], now=NOW)[0]["value"])
        for stamp in (True, 1.5, -1, NOW + 301, float("nan")):
            source = fixture()
            source["points"][-1][0] = stamp
            self.assertEqual(analyze_series([source], days=[7], now=NOW)[0]["status"], "unavailable")
        self.assertFalse(finite_number(10 ** 1000))
        self.assertIsNone(analyze_series([fixture(values=[1e308] * 29)], days=[7], now=NOW)[0]["value"])

    def test_long_windows_and_exact_explicit_custom_window(self):
        source = fixture(first="2022-03-02", values=list(range(1, 731)))
        rows = analyze_series([source], days=[7, 30, 90, 365], now=NOW)
        for row in rows:
            n = row["window_days"]
            self.assertEqual(row["value"], sum(range(731 - n, 731)))
            self.assertEqual(row["previous_value"], sum(range(731 - 2*n, 731 - n)))
        custom = analyze_series([fixture()], start="2024-02-20", end="2024-02-24", now=NOW)[0]
        self.assertEqual(custom["value"], 50)
        self.assertEqual(custom["window_days"], 5)
        for kwargs in ({"days": [0]}, {"days": [True]}, {"start": "2024-02-01"}, {"start": "2024-02-01", "end": "2024-02-03", "days": [7]}):
            with self.assertRaises(ValueError):
                analyze_series([fixture()], now=NOW, **kwargs)

    def test_health_flags_preserved_without_erasing_valid_history(self):
        row = analyze_series([fixture(upstream_health={"latestFetchIsOk": False, "disabled": True})], days=[7], now=NOW)[0]
        self.assertEqual(row["value"], 70)
        self.assertFalse(row["coverage"]["upstream_health"]["latestFetchIsOk"])


class DerivationTests(unittest.TestCase):
    def rows(self):
        return analyze_series([fixture("volume", values=[100] * 22 + [200] * 7),
                               fixture("fees", values=[10] * 22 + [30] * 7),
                               fixture("revenue", values=[4] * 22 + [18] * 7),
                               fixture("supply-side", values=[6] * 22 + [12] * 7)], days=[7], now=NOW)

    def test_ratios_reconciliation_and_arithmetic_decomposition(self):
        rows = self.rows()
        before = copy.deepcopy(rows)
        derived = {r["metric"]: r for r in derive_metrics(rows)}
        self.assertEqual(derived["fee_volume_pct"]["value"], 15)
        self.assertEqual(derived["revenue_retention_pct"]["value"], 60)
        self.assertEqual(derived["fees_revenue_supply_residual"]["value"], 0)
        components = [r["value"] for k, r in derived.items() if k.startswith("revenue_change_")]
        self.assertAlmostEqual(sum(components), 126 - 28)
        self.assertEqual(rows, before)

    def test_weighted_ratio_not_average_daily_ratios(self):
        sources = [fixture("volume", values=[100] * 27 + [1, 100]), fixture("fees", values=[10] * 27 + [1, 10])]
        rows = analyze_series(sources, days=[2], now=NOW)
        value = next(r["value"] for r in derive_metrics(rows) if r["metric"] == "fee_volume_pct")
        self.assertAlmostEqual(value, 11 / 101 * 100)
        self.assertNotAlmostEqual(value, 55)

    def test_same_parent_known_scope_mismatches_block_derived(self):
        for field, value in (("children", ["other-child"]), ("version", "US"), ("chains", ["Ethereum"]), ("category", "Lending")):
            rows = self.rows()[:2]
            rows[1]["scope"][field] = value
            self.assertEqual(derive_metrics(rows), [])
        rows = self.rows()[:2]
        rows[1]["entity"]["slug"] = "parent-example"
        self.assertEqual(derive_metrics(rows), [])

    def test_missing_ratio_inputs_do_not_remove_other_independent_derivations(self):
        rows = self.rows()
        rows[0]["value"] = None
        rows[0]["coverage"]["current_complete"] = False
        metrics = {r["metric"] for r in derive_metrics(rows)}
        self.assertNotIn("fee_volume_pct", metrics)
        self.assertIn("revenue_retention_pct", metrics)
        self.assertIn("fees_revenue_supply_residual", metrics)

    def test_unit_and_time_mismatch_and_ambiguous_duplicates(self):
        for change in ({"unit": "ETH"}, {"period_end": "2024-02-29T00:00:00Z"}, {"time_semantics": "rolling_window"}):
            rows = self.rows()[:2]
            rows[1].update(change)
            self.assertEqual(derive_metrics(rows), [])
        rows = self.rows()[:2]
        self.assertEqual(derive_metrics(rows + [copy.deepcopy(rows[1])]), [])
        rows = self.rows()[:2]
        for row in rows:
            row["unit"] = None
        self.assertEqual(derive_metrics(rows), [])

    def test_nonzero_reconciliation_residual_disclosed(self):
        rows = self.rows()
        rows[-1]["value"] -= 100
        residual = next(r for r in derive_metrics(rows) if r["metric"] == "fees_revenue_supply_residual")
        self.assertEqual(residual["value"], 100)
        self.assertFalse(residual["within_tolerance"])
        self.assertEqual(residual["tolerance"], 7)


if __name__ == "__main__":
    unittest.main()
