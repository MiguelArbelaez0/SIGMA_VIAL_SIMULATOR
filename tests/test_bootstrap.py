"""Protección contra un segundo ciclo de eventos dentro de una sesión Qt existente."""

import pytest
from PySide6.QtWidgets import QApplication

from sigma_vial.bootstrap import main


def test_main_rejects_an_existing_application(qapp: QApplication) -> None:
    with pytest.raises(RuntimeError, match="ya está en ejecución"):
        main()
    assert QApplication.instance() is qapp
