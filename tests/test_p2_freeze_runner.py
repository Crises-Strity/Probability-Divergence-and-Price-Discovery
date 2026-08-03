from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def load_module():
    path = PROJECT_ROOT / "scripts" / "P2_diagnostics" / "run_p1_freeze.py"
    spec = importlib.util.spec_from_file_location("run_p1_freeze", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class FreezeRunnerTests(unittest.TestCase):
    def test_default_command_plan_runs_track_a_audit_and_provenance(self):
        module = load_module()

        commands = module.command_plan(include_track_b=False)
        scripts = [cmd.script for cmd in commands]

        self.assertEqual(
            scripts,
            [
                "scripts/P1_pipeline/build_trackA_diagnostics.py",
                "scripts/P1_pipeline/build_trackA_regression_diagnostics.py",
                "scripts/P2_diagnostics/build_reference_basis_audit.py",
                "scripts/P2_diagnostics/build_p1_table_provenance.py",
            ],
        )

    def test_track_b_option_inserts_track_b_before_provenance(self):
        module = load_module()

        commands = module.command_plan(include_track_b=True)
        self.assertEqual(
            commands,
            [
                module.Command("scripts/P1_pipeline/build_trackA_diagnostics.py"),
                module.Command("scripts/P1_pipeline/build_trackA_regression_diagnostics.py"),
                module.Command("scripts/P2_diagnostics/build_reference_basis_audit.py"),
                module.Command("scripts/P1_pipeline/build_trackB_kstar_panel.py"),
                module.Command("scripts/P1_pipeline/build_trackB_pm_survival_panel.py"),
                module.Command("scripts/P1_pipeline/build_trackB_deribit_survival_panel.py"),
                module.Command("scripts/P1_pipeline/build_trackB_lead_lag_panel.py"),
                module.Command(
                    "scripts/P1_pipeline/build_trackB_deribit_survival_panel.py",
                    ("--bar-hours", "6"),
                ),
                module.Command(
                    "scripts/P1_pipeline/build_trackB_lead_lag_panel.py",
                    ("--bar-hours", "6"),
                ),
                module.Command("scripts/P1_pipeline/build_trackB_lead_lag_diagnostics.py"),
                module.Command("scripts/P2_diagnostics/build_p1_table_provenance.py"),
            ],
        )

    def test_runner_uses_active_environment_interpreter(self):
        module = load_module()

        self.assertEqual(module.python_executable(), sys.executable)

    def test_input_validation_reports_every_missing_file(self):
        module = load_module()

        with patch.object(module, "PROJECT_ROOT", Path("/missing-project")):
            with self.assertRaises(FileNotFoundError) as context:
                module.validate_required_inputs(include_track_b=True)

        message = str(context.exception)
        self.assertIn("trackA_event_day_quality.parquet", message)
        self.assertIn("polymarket_distribution_hourly.parquet", message)


if __name__ == "__main__":
    unittest.main()
