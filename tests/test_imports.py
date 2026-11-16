"""Las importaciones se verifican en procesos sin la QApplication de pytest-qt."""

import os
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize(
    "module",
    [
        "sigma_vial",
        "sigma_vial.__main__",
        "sigma_vial.bootstrap",
        "sigma_vial.presentation.main_window",
        "sigma_vial.domain",
        "sigma_vial.application",
        "sigma_vial.infrastructure",
    ],
)
def test_import_has_no_application_or_output(module: str, tmp_path: Path) -> None:
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            f"import importlib; importlib.import_module({module!r}); "
            "from PySide6.QtWidgets import QApplication; "
            "assert QApplication.instance() is None",
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == ""
    assert result.stderr == ""
