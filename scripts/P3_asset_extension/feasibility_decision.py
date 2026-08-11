"""Pure P3 feasibility gate using the frozen continuation thresholds."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def _counts(metadata: Mapping[str, Any]) -> Mapping[str, Any]:
    counts = metadata.get("row_counts", {})
    return counts if isinstance(counts, Mapping) else {}


def feasibility_decision(
    pm_metadata: Mapping[str, Any],
    deribit_metadata: Mapping[str, Any],
    candidate_gates: Mapping[str, Any],
    final_gates: Mapping[str, Any],
) -> tuple[str, list[str]]:
    pm_counts = _counts(pm_metadata)
    candidate_events = int(pm_counts.get("candidate_events", 0))
    candidate_expiries = int(pm_counts.get("candidate_expiries", 0))
    if (
        candidate_events >= int(candidate_gates["pass_min_events"])
        and candidate_expiries >= int(candidate_gates["pass_min_expiries"])
    ):
        candidate_label = "PASS"
    elif (
        candidate_events >= int(candidate_gates["limited_pass_min_events"])
        and candidate_expiries >= int(candidate_gates["limited_pass_min_expiries"])
    ):
        candidate_label = "LIMITED PASS"
    else:
        candidate_label = "FAIL"

    blockers = []
    if candidate_label == "FAIL":
        blockers.append("Polymarket candidates do not meet the frozen LIMITED PASS panel threshold.")
    if pm_metadata.get("classification_status") != "manual_review_complete":
        blockers.append("Polymarket terminal partitions have not completed manual review.")
    if not pm_metadata.get("historical_yes_price_access_verified", False):
        blockers.append("Historical Polymarket YES-token price access has not been verified.")
    if not deribit_metadata.get("contract_units_verified_for_all_matches", False):
        blockers.append("SOL linear-USDC contract units are not verified for all matched contracts.")

    history = deribit_metadata.get("historical_ohlc_probe", {})
    if not isinstance(history, Mapping):
        return "FAIL", ["Historical full-grid OHLC evidence is absent.", *blockers]
    parameters = history.get("parameters", {})
    parameters = parameters if isinstance(parameters, Mapping) else {}
    counts = _counts(history)
    observed_days = int(counts.get("event_days_observed", 0))
    passing_days = int(counts.get("passing_event_days", 0))
    passing_events = int(counts.get("passing_events", 0))
    passing_expiries = int(counts.get("passing_expiries", 0))
    requested_expiries = int(counts.get("requested_expiries", 0))
    scope = str(parameters.get("scope", "unknown"))

    if scope == "smoke" and requested_expiries >= 3 and passing_days == 0:
        return "FAIL", [
            f"0 of {observed_days} observed event-days passed the frozen full-curve quality gate.",
            "The bounded smoke probe spans three mechanically selected exact expiries.",
            "This is an early-stop feasibility finding; all 44 candidates were not downloaded.",
            *blockers,
        ]

    if blockers:
        return "FAIL", blockers
    if "maximum_single_event_share" not in history:
        return "FAIL", ["Single-event concentration evidence is missing, so the concentration guard cannot pass."]
    concentration = float(history["maximum_single_event_share"])
    concentration_pass = concentration <= float(final_gates["maximum_single_event_share"])
    pass_gate = (
        passing_days >= int(final_gates["pass_min_event_days"])
        and passing_events >= int(final_gates["pass_min_events"])
        and passing_expiries >= int(final_gates["pass_min_expiries"])
        and concentration_pass
    )
    if scope == "all_candidates" and pass_gate and candidate_label == "PASS":
        return "PASS", [
            f"Full panel contains {passing_days} passing event-days from {passing_events} events and "
            f"{passing_expiries} expiries.",
            "The frozen concentration guard is satisfied.",
        ]

    limited_gate = (
        passing_days >= int(final_gates["limited_pass_min_event_days"])
        and passing_events >= int(final_gates["limited_pass_min_events"])
        and passing_expiries >= int(final_gates["limited_pass_min_expiries"])
        and concentration_pass
    )
    if scope == "all_candidates" and pass_gate and candidate_label == "LIMITED PASS":
        return "LIMITED PASS", [
            f"Final panel contains {passing_days} passing event-days from {passing_events} events and "
            f"{passing_expiries} expiries.",
            "The final label is capped at LIMITED PASS by the candidate-stage panel label.",
        ]
    if limited_gate:
        return "LIMITED PASS", [
            f"Panel contains {passing_days} passing event-days from {passing_events} events and "
            f"{passing_expiries} expiries.",
            "Evidence reaches the frozen descriptive-only threshold but not the full PASS gate.",
        ]
    return "FAIL", [
        f"Only {passing_days} passing event-days from {passing_events} events and {passing_expiries} expiries remain.",
        "The frozen LIMITED PASS threshold is not met.",
    ]
