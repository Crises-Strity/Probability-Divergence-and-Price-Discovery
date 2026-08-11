from __future__ import annotations

from scripts.P3_asset_extension.feasibility_decision import feasibility_decision


def candidate_metadata() -> dict[str, object]:
    return {
        "row_counts": {"candidate_events": 44, "candidate_expiries": 44},
        "classification_status": "manual_review_complete",
        "historical_yes_price_access_verified": True,
    }


def deribit_metadata() -> dict[str, object]:
    return {
        "contract_units_verified_for_all_matches": True,
        "row_counts": {"matched_events": 44, "matched_expiries": 41},
        "historical_ohlc_probe": {
            "parameters": {
                "scope": "smoke",
                "selected_event_ids": ["25536", "57016", "211899"],
            },
            "row_counts": {
                "requested_expiries": 3,
                "event_days_observed": 14,
                "passing_event_days": 0,
                "passing_events": 0,
                "passing_expiries": 0,
            },
        },
    }


def final_gates() -> dict[str, object]:
    return {
        "pass_min_event_days": 30,
        "pass_min_events": 10,
        "pass_min_expiries": 3,
        "limited_pass_min_event_days": 15,
        "limited_pass_min_events": 5,
        "limited_pass_min_expiries": 2,
        "maximum_single_event_share": 0.25,
    }


def candidate_gates() -> dict[str, object]:
    return {
        "pass_min_events": 10,
        "pass_min_expiries": 3,
        "limited_pass_min_events": 5,
        "limited_pass_min_expiries": 2,
    }


def test_three_expiry_smoke_with_zero_passing_days_is_fail() -> None:
    label, reasons = feasibility_decision(
        candidate_metadata(), deribit_metadata(), candidate_gates(), final_gates()
    )

    assert label == "FAIL"
    assert "0 of 14 observed event-days" in reasons[0]
    assert any("three mechanically selected exact expiries" in reason for reason in reasons)
    assert any("all 44 candidates were not downloaded" in reason for reason in reasons)


def test_unverified_contract_units_cannot_pass() -> None:
    deribit = deribit_metadata()
    deribit["contract_units_verified_for_all_matches"] = False

    label, reasons = feasibility_decision(candidate_metadata(), deribit, candidate_gates(), final_gates())

    assert label == "FAIL"
    assert any("contract units" in reason for reason in reasons)


def test_full_panel_meeting_frozen_thresholds_is_pass() -> None:
    deribit = deribit_metadata()
    deribit["historical_ohlc_probe"] = {
        "parameters": {"scope": "all_candidates"},
        "row_counts": {
            "event_days_observed": 50,
            "passing_event_days": 32,
            "passing_events": 11,
            "passing_expiries": 10,
        },
        "maximum_single_event_share": 0.125,
    }

    label, reasons = feasibility_decision(candidate_metadata(), deribit, candidate_gates(), final_gates())

    assert label == "PASS"
    assert any("32 passing event-days" in reason for reason in reasons)


def test_final_label_cannot_exceed_limited_candidate_stage() -> None:
    pm = candidate_metadata()
    pm["row_counts"] = {"candidate_events": 5, "candidate_expiries": 2}
    deribit = deribit_metadata()
    deribit["historical_ohlc_probe"] = {
        "parameters": {"scope": "all_candidates"},
        "row_counts": {
            "event_days_observed": 50,
            "passing_event_days": 32,
            "passing_events": 11,
            "passing_expiries": 10,
        },
        "maximum_single_event_share": 0.125,
    }

    label, reasons = feasibility_decision(pm, deribit, candidate_gates(), final_gates())

    assert label == "LIMITED PASS"
    assert any("capped" in reason for reason in reasons)


def test_missing_concentration_evidence_cannot_pass() -> None:
    deribit = deribit_metadata()
    deribit["historical_ohlc_probe"] = {
        "parameters": {"scope": "all_candidates"},
        "row_counts": {
            "event_days_observed": 50,
            "passing_event_days": 32,
            "passing_events": 11,
            "passing_expiries": 10,
        },
    }

    label, reasons = feasibility_decision(
        candidate_metadata(), deribit, candidate_gates(), final_gates()
    )

    assert label == "FAIL"
    assert any("concentration" in reason for reason in reasons)


def test_incomplete_polymarket_audit_cannot_pass() -> None:
    pm = candidate_metadata()
    pm["classification_status"] = "automated_pending_manual_review"
    pm["historical_yes_price_access_verified"] = False
    deribit = deribit_metadata()
    deribit["historical_ohlc_probe"] = {
        "parameters": {"scope": "all_candidates"},
        "row_counts": {
            "event_days_observed": 50,
            "passing_event_days": 32,
            "passing_events": 11,
            "passing_expiries": 10,
        },
        "maximum_single_event_share": 0.125,
    }

    label, reasons = feasibility_decision(pm, deribit, candidate_gates(), final_gates())

    assert label == "FAIL"
    assert any("manual review" in reason for reason in reasons)
    assert any("YES-token" in reason for reason in reasons)
