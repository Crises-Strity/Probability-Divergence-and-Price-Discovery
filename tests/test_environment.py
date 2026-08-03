from __future__ import annotations

from pathlib import Path
import subprocess
import sys

import pandas as pd


def test_locked_environment_can_render_latex_tables() -> None:
    latex = pd.DataFrame({"value": [1.0]}).to_latex(index=False)

    assert "\\begin{tabular}" in latex


def test_track_a_diagnostics_uses_noninteractive_backend() -> None:
    script_path = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "P1_pipeline"
        / "build_trackA_diagnostics.py"
    )
    code = (
        "import importlib.util; "
        f"spec=importlib.util.spec_from_file_location('track_a', {str(script_path)!r}); "
        "module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module); "
        "import matplotlib; print(matplotlib.get_backend())"
    )
    completed = subprocess.run(
        [sys.executable, "-c", code],
        check=True,
        capture_output=True,
        text=True,
    )

    assert completed.stdout.strip().lower() == "agg"
