"""Pure UTC comparisons. Collection frequency never establishes flow intervals."""

from __future__ import annotations

import math
from datetime import date, datetime, time, timedelta, timezone
from typing import Any

UTC = timezone.utc
DAY = 86400


def finite_number(value: Any) -> bool:
    """JSON booleans and nonfinite values are not measurements."""
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def _iso(day: date) -> str:
    return datetime.combine(day, time(), UTC).isoformat().replace("+00:00", "Z")


def _instant(stamp: int) -> str:
    return datetime.fromtimestamp(stamp, UTC).isoformat().replace("+00:00", "Z")


def _date(value: str) -> date:
    parsed = date.fromisoformat(value)
    if parsed.isoformat() != value:
        raise ValueError("Dates must use YYYY-MM-DD")
    return parsed


def _dates(first: date, last: date) -> list[date]:
    return [first + timedelta(days=i) for i in range((last - first).days + 1)]


def _normalize(series: dict, now: float) -> dict:
    kind = series.get("kind")
    verified = (
        kind == "flow"
        and series.get("time_semantics") == "utc_calendar_day"
        and series.get("timestamp_role") in {"interval_start", "interval_end"}
        and bool(series.get("semantic_evidence"))
    )
    eligible = kind in {"stock", "rate"} or verified
    warnings = list(series.get("warnings") or [])
    points: dict[date, tuple[int, Any]] = {}
    conflicts: set[date] = set()
    seen: dict[int, Any] = {}
    invalid = False
    latest_stamp = None
    raw = series.get("points") or []
    for point in raw:
        if not isinstance(point, (list, tuple)) or len(point) != 2:
            invalid = True
            warnings.append("Malformed observation rejected")
            continue
        stamp, value = point
        if not finite_number(stamp) or stamp != int(stamp) or not 0 < stamp <= now + 300:
            invalid = True
            warnings.append("Invalid/future observation timestamp rejected")
            continue
        stamp = int(stamp)
        latest_stamp = max(latest_stamp or stamp, stamp)
        if stamp in seen:
            if seen[stamp] == value and type(seen[stamp]) is type(value):
                warnings.append("Exact duplicate observation ignored")
                continue
            # Equivalent finite int/float values are also the same observation.
            if finite_number(seen[stamp]) and finite_number(value) and seen[stamp] == value:
                warnings.append("Exact duplicate observation ignored")
                continue
            invalid = True
            warnings.append("Conflicting duplicate timestamp rejected")
        seen[stamp] = value
        bucket_stamp = stamp
        if verified:
            if stamp % DAY:
                invalid = True
                warnings.append("Verified daily flow has a non-midnight boundary")
                continue
            if series["timestamp_role"] == "interval_end":
                bucket_stamp -= DAY
        day = datetime.fromtimestamp(bucket_stamp, UTC).date()
        if verified and day in points:
            conflicts.add(day)
        if day not in points or stamp >= points[day][0]:
            points[day] = (stamp, value if finite_number(value) else None)
    for day in conflicts:
        points[day] = (points[day][0], None)
    if kind not in {"flow", "stock", "rate"}:
        eligible = False
        warnings.append("Unknown measurement kind")
    if kind == "flow" and not verified:
        warnings.append("Calendar comparison unavailable: flow UTC intervals lack evidence")
    if series.get("status") == "unavailable":
        eligible = False
    return {"series": series, "points": points, "eligible": eligible,
            "invalid": invalid, "warnings": list(dict.fromkeys(warnings)),
            "returned_observations": {
                "input_count": len(raw), "valid_timestamp_count": len(seen),
                "finite_value_count": sum(finite_number(value) for value in seen.values()),
                "scope": "entire source series; unique observation timestamps, not calendar-window coverage",
            },
            "latest_stamp": latest_stamp}


def _window(normalized: dict, first: date, last: date, today: date) -> dict:
    series, points = normalized["series"], normalized["points"]
    flow = series.get("kind") == "flow"
    wanted = _dates(first, last) if flow else [last]
    observed = [d for d in wanted if normalized["eligible"] and d < today and d in points and finite_number(points[d][1])]
    missing = [d.isoformat() for d in wanted if d not in observed]
    complete = not missing and normalized["eligible"] and not normalized["invalid"]
    values = [points[d][1] for d in observed]
    partial_sum = sum(values) if flow and normalized["eligible"] and values else None
    if partial_sum is not None and not finite_number(partial_sum):
        partial_sum = None
        complete = False
    value = (partial_sum if flow else points[last][1]) if complete else None
    return {"value": value, "complete": bool(complete),
            "expected_days": len(wanted), "observed_days": len(observed),
            "coverage_basis": "eligible comparison observations; not raw returned-point count",
            "missing_dates": missing, "partial_sum": partial_sum,
            "observed_at": _instant(points[last][0]) if not flow and last in points else None}


def _pct(current: Any, previous: Any) -> tuple[Any, str | None]:
    if not finite_number(current) or not finite_number(previous):
        return None, "Current or prior comparable value unavailable"
    if previous <= 0:
        return None, "Percentage change requires a positive prior value"
    result = (current / previous - 1) * 100
    return (result, None) if finite_number(result) else (None, "Percentage calculation overflow")


def analyze_series(series_list: list[dict], days: list[int] | None = None,
                   start: str | None = None, end: str | None = None,
                   now: float | None = None, align: str = "all") -> list[dict]:
    """Return complete/partial windows, preserving every unavailable requested series.

    ``rate`` behaves as an instantaneous observation; it is never daily-averaged.
    A null latest observation participates if earlier usable completed data exists,
    so missing data cannot silently move that series back to an older favorable
    date. A wholly unusable series cannot move otherwise valid comparisons back.
    """
    now = datetime.now(UTC).timestamp() if now is None else now
    if not finite_number(now) or now <= 0:
        raise ValueError("now must be a positive finite epoch")
    if align not in {"all", "metric"}:
        raise ValueError("align must be all or metric")
    if bool(start) != bool(end):
        raise ValueError("Both start and end are required")
    explicit = bool(start)
    if explicit and days is not None:
        raise ValueError("Explicit dates and days are mutually exclusive")
    windows = days if days is not None else [7, 30, 90]
    if not windows or any(isinstance(n, bool) or not isinstance(n, int) or not 1 <= n <= 3660 for n in windows):
        raise ValueError("days must contain integers between 1 and 3660")
    today = datetime.fromtimestamp(now, UTC).date()
    if explicit:
        first, last = _date(start), _date(end)
        if first > last or (last - first).days >= 3660:
            raise ValueError("Explicit date range must span 1 to 3660 days")
        windows = [(last - first).days + 1]
    normalized = [_normalize(s, now) for s in series_list]
    groups: dict[str, list[tuple[dict, date]]] = {}
    for n in normalized:
        past = [d for d in n["points"] if d < today]
        n["has_usable_completed"] = any(finite_number(n["points"][d][1]) for d in past)
        if n["eligible"] and not n["invalid"] and n["has_usable_completed"]:
            key = n["series"].get("metric", "") if align == "metric" else "all"
            groups.setdefault(key, []).append((n, max(past)))
    result = []
    for n in normalized:
        s = n["series"]
        key = s.get("metric", "") if align == "metric" else "all"
        participants = groups.get(key, [])
        chosen = last if explicit else min((d for _, d in participants), default=today - timedelta(days=1))
        for length in dict.fromkeys(windows):
            first_day = chosen - timedelta(days=length - 1)
            prev_last = first_day - timedelta(days=1)
            prev_first = prev_last - timedelta(days=length - 1)
            current = _window(n, first_day, chosen, today)
            # Stocks compare end snapshots N days apart; flows compare N whole days.
            previous = _window(n, prev_first, prev_last, today)
            pct, pct_reason = _pct(current["value"], previous["value"])
            complete = current["complete"] and previous["complete"]
            row = {"entity": s.get("entity", {}), "metric": s.get("metric"),
                   "kind": s.get("kind"), "unit": s.get("unit"),
                   "period_start": _iso(first_day), "period_end": _iso(chosen + timedelta(days=1)),
                   "previous_period_start": _iso(prev_first), "previous_period_end": _iso(first_day),
                   "window_days": length, "observed_at": current["observed_at"],
                   "previous_observed_at": previous["observed_at"],
                   "value": current["value"], "previous_value": previous["value"],
                   "change_pct": pct, "change_reason": pct_reason,
                   "partial_sum": current["partial_sum"],
                   "source_ids": list(s.get("source_ids") or []), "scope": s.get("scope", {}),
                   "time_semantics": s.get("time_semantics", "unknown"),
                   "timestamp_role": s.get("timestamp_role", "unknown"),
                   "semantic_evidence": s.get("semantic_evidence"),
                   "status": "ok" if complete else "partial" if n["eligible"] and not n["invalid"] and n["has_usable_completed"] else "unavailable",
                   "coverage": {"current": current, "previous": previous,
                                "current_complete": current["complete"], "previous_complete": previous["complete"],
                                "upstream_health": s.get("upstream_health", {}),
                                "returned_observations": n["returned_observations"],
                                "scope": "eligible comparison coverage and source observation counts; neither proves upstream collection completeness"},
                   "alignment": {"mode": "explicit" if explicit else align, "chosen_end_date": chosen.isoformat(),
                                 "participants": [{"entity": a["series"].get("entity", {}), "metric": a["series"].get("metric"), "latest_completed_date": d.isoformat()} for a, d in participants],
                                 "latest_timestamp": n["latest_stamp"],
                                 "dropped_newer_dates": [d.isoformat() for d in sorted(n["points"]) if chosen < d < today]},
                   "warnings": list(n["warnings"])}
            if not n["eligible"] or n["invalid"]:
                row["reason"] = s.get("reason") or ("Invalid series observations" if n["invalid"] else "Verified calendar intervals unavailable")
            elif not n["has_usable_completed"]:
                row["reason"] = "No finite completed observations; excluded from common alignment"
            if s.get("kind") == "flow" and not n["eligible"]:
                # Raw values retain their upstream timestamp and semantics, never
                # acquire inferred midnight intervals or zero substitutions.
                row["source_observations"] = s.get("points", [])
            result.append(row)
    return result


def _scope_key(row: dict) -> tuple | None:
    """Require known entity identity and equal full declared coverage signatures."""
    entity, scope = row.get("entity", {}), row.get("scope", {})
    identity = scope.get("identity") or entity.get("id") or entity.get("slug")
    if not identity or not isinstance(row.get("unit"), str) or not row["unit"]:
        return None
    def freeze(value: Any) -> Any:
        if isinstance(value, dict):
            return tuple(sorted((str(k), freeze(v)) for k, v in value.items()))
        if isinstance(value, (list, tuple, set)):
            return tuple(sorted((freeze(x) for x in value), key=repr))
        return value
    return (freeze(identity), freeze(entity.get("id")), freeze(entity.get("slug")),
            freeze(entity.get("parentProtocol")), freeze(scope.get("version")),
            freeze(scope.get("children")), freeze(scope.get("chains", entity.get("chains"))),
            freeze(scope.get("category", entity.get("category"))),
            row.get("unit"), row.get("period_start"), row.get("period_end"), row.get("window_days"))


def derive_metrics(rows: list[dict]) -> list[dict]:
    """Appendable derived rows. Independent input rows are never changed/dropped.

    Incompatible scopes produce no derived values. Reconciliation is an observed
    residual, not inferred operating expenses or profit. Arithmetic decomposition
    follows volume, fee-rate, retention in that order and has no causal meaning.
    """
    groups: dict[tuple, dict[str, list[dict]]] = {}
    for row in rows:
        if row.get("kind") != "flow" or row.get("time_semantics") != "utc_calendar_day":
            continue
        key = _scope_key(row)
        if key is not None:
            groups.setdefault(key, {}).setdefault(row.get("metric"), []).append(row)
    output = []
    for group in groups.values():
        # Repeated candidate metrics are ambiguous, never silently select one.
        metrics = {k: v[0] for k, v in group.items() if len(v) == 1}
        def valid(*names: str, prior: bool = False) -> bool:
            return all(name in metrics and metrics[name].get("coverage", {}).get("current_complete")
                       and finite_number(metrics[name].get("value"))
                       and (not prior or (metrics[name].get("coverage", {}).get("previous_complete")
                                          and finite_number(metrics[name].get("previous_value")))) for name in names)
        def emit(metric: str, names: tuple[str, ...], value: float, previous: float | None,
                 unit: str, **extras: Any) -> None:
            if not finite_number(value):
                return
            prior = previous if finite_number(previous) else None
            template = metrics[names[0]]
            pct, reason = _pct(value, prior)
            output.append({"entity": template.get("entity"), "metric": metric,
                           "kind": "rate" if unit == "percent" else "flow", "unit": unit,
                           "period_start": template["period_start"], "period_end": template["period_end"],
                           "window_days": template["window_days"], "scope": template["scope"],
                           "value": value, "previous_value": prior, "change_pct": pct, "change_reason": reason,
                           "time_semantics": "utc_calendar_day", "status": "ok" if prior is not None else "partial",
                           "source_ids": sorted(set(sid for name in names for sid in metrics[name].get("source_ids", []))),
                           "derived_from": list(names), **extras})
        for numerator, denominator, label in (("fees", "volume", "fee_volume_pct"), ("revenue", "fees", "revenue_retention_pct")):
            if valid(numerator, denominator) and metrics[denominator]["value"] > 0:
                current = metrics[numerator]["value"] / metrics[denominator]["value"] * 100
                previous = None
                if valid(numerator, denominator, prior=True) and metrics[denominator]["previous_value"] > 0:
                    previous = metrics[numerator]["previous_value"] / metrics[denominator]["previous_value"] * 100
                emit(label, (numerator, denominator), current, previous, "percent")
        supply = "supply-side" if "supply-side" in metrics else "supply_side"
        names = ("fees", "revenue", supply)
        if valid(*names):
            residual = metrics["fees"]["value"] - metrics["revenue"]["value"] - metrics[supply]["value"]
            tolerance = max(metrics["fees"]["window_days"], abs(metrics["fees"]["value"]) * 1e-6)
            previous = None
            if valid(*names, prior=True):
                previous = metrics["fees"]["previous_value"] - metrics["revenue"]["previous_value"] - metrics[supply]["previous_value"]
            emit("fees_revenue_supply_residual", names, residual, previous, metrics["fees"]["unit"],
                 tolerance=tolerance, within_tolerance=abs(residual) <= tolerance,
                 interpretation="Adapter-defined reconciliation residual; not inferred costs or profit")
        names = ("volume", "fees", "revenue")
        if valid(*names, prior=True):
            v0, f0, r0 = (metrics[n]["previous_value"] for n in names)
            v1, f1, r1 = (metrics[n]["value"] for n in names)
            if min(v0, f0, v1, f1) <= 0:
                continue
            rate0, rate1 = f0 / v0, f1 / v1
            retention0, retention1 = r0 / f0, r1 / f1
            components = (("volume", (v1 - v0) * rate0 * retention0),
                          ("fee_rate", v1 * (rate1 - rate0) * retention0),
                          ("retention", v1 * rate1 * (retention1 - retention0)))
            for component, value in components:
                emit("revenue_change_" + component + "_component", names, value, None, metrics["revenue"]["unit"],
                     status="ok", interpretation="Sequential arithmetic attribution (volume, fee rate, retention); not causality")
    return output
