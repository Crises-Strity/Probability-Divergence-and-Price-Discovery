from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def load_module():
    path = PROJECT_ROOT / "scripts" / "P2_diagnostics" / "build_reference_basis_audit.py"
    spec = importlib.util.spec_from_file_location("build_reference_basis_audit", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class ReferenceBasisAuditTests(unittest.TestCase):
    def test_classifies_proxy_when_text_exists_and_mismatch_is_true(self):
        module = load_module()

        status = module.reference_basis_status(
            settlement_reference="binance_btcusdt_1m_close_12:00_et",
            settlement_reference_detail="source=Binance; pair=BTCUSDT",
            deribit_index_reference="btc_usd",
            reference_basis_mismatch=True,
        )

        self.assertEqual(status, "proxy_assumed")

    def test_build_summary_counts_events_and_shares(self):
        module = load_module()
        audit = pd.DataFrame(
            [
                {
                    "event_id": 1,
                    "asset": "BTC",
                    "trackA_eligible": True,
                    "trackB_eligible": True,
                    "polymarket_resolution_text_available": True,
                    "reference_basis_mismatch": True,
                    "reference_basis_status": "proxy_assumed",
                },
                {
                    "event_id": 2,
                    "asset": "BTC",
                    "trackA_eligible": False,
                    "trackB_eligible": True,
                    "polymarket_resolution_text_available": False,
                    "reference_basis_mismatch": False,
                    "reference_basis_status": "unknown",
                },
            ]
        )

        summary = module.build_summary(audit)
        proxy = summary[
            (summary["asset"] == "BTC") & (summary["reference_basis_status"] == "proxy_assumed")
        ].iloc[0]

        self.assertEqual(int(proxy["n_events"]), 1)
        self.assertEqual(int(proxy["n_trackA_eligible"]), 1)
        self.assertEqual(int(proxy["n_trackB_eligible"]), 1)
        self.assertEqual(float(proxy["resolution_text_available_share"]), 1.0)
        self.assertEqual(float(proxy["reference_basis_mismatch_share"]), 1.0)


if __name__ == "__main__":
    unittest.main()
