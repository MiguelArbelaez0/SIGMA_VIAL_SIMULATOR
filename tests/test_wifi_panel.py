import pytest
from PySide6.QtCore import QSettings
from PySide6.QtNetwork import QHostAddress, QTcpServer
from PySide6.QtWidgets import QInputDialog

from sigma_vial.presentation.wifi_panel import WifiPanel, demand_text, wlan_ssids


@pytest.fixture
def settings(tmp_path):
    return QSettings(str(tmp_path / "panel.ini"), QSettings.Format.IniFormat)


@pytest.mark.parametrize(
    ("response", "summary"),
    [
        ("OK NS=0 EO=0 TOTAL=0 MAYOR=SIN_DEMANDA", "No hay vehículos esperando en el cruce."),
        ("OK NS=1 EO=1 TOTAL=2 MAYOR=EMPATE", "Empate: 1 vehículo en cada eje (2 en total)."),
        (
            "OK NS=2 EO=1 TOTAL=3 MAYOR=NS",
            "Hay más vehículos esperando entre Norte y Sur: 2 de 3 en total.",
        ),
    ],
)
def test_summary_from_processor(response, summary):
    assert demand_text(response) == summary


def test_panel_waits_for_complete_pong(qtbot, settings):
    server = QTcpServer()
    assert server.listen(QHostAddress.SpecialAddress.LocalHost, 5050)
    panel = WifiPanel(lambda: (1, 2, 7, 3), settings)
    qtbot.addWidget(panel)
    assert panel.address.text() == "192.168.4.1"
    panel.address.setText("127.0.0.1")
    panel.button.click()
    qtbot.waitUntil(server.hasPendingConnections)
    peer = server.nextPendingConnection()
    qtbot.waitUntil(peer.canReadLine)
    assert bytes(peer.readLine()) == b"PING\n"
    peer.write(b"PO")
    qtbot.waitUntil(lambda: panel.socket.bytesAvailable() == 2)
    assert panel.status.text() == "Esperando que responda la placa…"
    assert not settings.contains("ip")
    assert panel.button.text() == "Conectando…"
    peer.write(b"NG\r\n")
    qtbot.waitUntil(lambda: panel.status.text() == "Placa conectada. Esperando el primer conteo.")
    assert panel.button.text() == "ESP32 conectado"
    assert settings.value("ip") == "127.0.0.1"
    panel.sample_button.click()
    assert not panel.sample_button.isEnabled()
    qtbot.waitUntil(peer.canReadLine)
    assert bytes(peer.readLine()) == b"TRAFICO 1 2 7 3\n"
    peer.write(b"OK NS=3 EO=10 TOTAL=13 MAYOR=EO\n")
    qtbot.waitUntil(panel.sample_button.isEnabled)
    assert panel.reply.text() == "ESP32 responde: OK NS=3 EO=10 TOTAL=13 MAYOR=EO"
    assert (
        panel.result.text()
        == "Hay más vehículos esperando entre Oriente y Occidente: 10 de 13 en total."
    )
    assert panel.sent.isHidden() and panel.reply.isHidden()
    assert panel.counts.text().endswith("Norte: 1   Sur: 2   Oriente: 7   Occidente: 3")
    panel.details.click()
    assert not panel.sent.isHidden() and not panel.reply.isHidden()
    socket = panel.socket
    panel.change_address.click()
    panel.findChild(QInputDialog).reject()
    panel.apply_address("127.0.0.1")
    assert panel.ready and panel.socket is socket
    peer.disconnectFromHost()
    qtbot.waitUntil(lambda: panel.socket is None)
    assert panel.button.text() == "Reintentar"
    assert "desactualizada" in panel.status.text()
    server.close()


def test_auto_sample_keeps_request_until_reply_and_discards_it_on_reset(qtbot, settings):
    server = QTcpServer()
    assert server.listen(QHostAddress.SpecialAddress.LocalHost, 5050)
    counts = [1, 2, 7, 3]
    panel = WifiPanel(lambda: counts, settings)
    qtbot.addWidget(panel)
    panel.address.setText("127.0.0.1")
    panel.set_running(True)
    panel.button.click()
    qtbot.waitUntil(server.hasPendingConnections)
    peer = server.nextPendingConnection()
    qtbot.waitUntil(peer.canReadLine)
    assert bytes(peer.readLine()) == b"PING\n"
    peer.write(b"PONG\n")
    qtbot.waitUntil(peer.canReadLine, timeout=3000)
    assert bytes(peer.readLine()) == b"TRAFICO 1 2 7 3\n"
    counts[0] = 8
    qtbot.wait(1100)
    assert not peer.bytesAvailable()
    panel.set_running(False)
    peer.write(b"OK NS=3 EO=10 TOTAL=13 MAYOR=EO\n")
    qtbot.waitUntil(lambda: bool(panel.reply.text()))
    assert panel.sent.text().endswith("TRAFICO 1 2 7 3")
    assert panel.status.text() == "En pausa"
    panel.sample_button.click()
    qtbot.waitUntil(peer.canReadLine)
    assert bytes(peer.readLine()) == b"TRAFICO 8 2 7 3\n"
    peer.write(b"OK NS=10 EO=10 TOTAL=20 MAYOR=EMPATE\n")
    panel.reset_samples()
    qtbot.waitUntil(server.hasPendingConnections)
    fresh = server.nextPendingConnection()
    qtbot.waitUntil(fresh.canReadLine)
    assert bytes(fresh.readLine()) == b"PING\n"
    assert panel.reply.text() == "" and not panel.ready
    panel.disconnect_device()
    server.close()


def test_first_connection_recovers_when_processor_starts_later(qtbot, settings):
    panel = WifiPanel(lambda: (0, 0, 3, 2), settings)
    qtbot.addWidget(panel)
    panel.address.setText("127.0.0.1")
    panel.set_running(True)
    panel.button.click()
    qtbot.waitUntil(panel.retry.isActive)
    server = QTcpServer()
    assert server.listen(QHostAddress.SpecialAddress.LocalHost, 5050)
    qtbot.waitUntil(server.hasPendingConnections, timeout=6500)
    peer = server.nextPendingConnection()
    qtbot.waitUntil(peer.canReadLine)
    assert bytes(peer.readLine()) == b"PING\n"
    peer.write(b"PONG\n")
    qtbot.waitUntil(peer.canReadLine, timeout=2500)
    assert bytes(peer.readLine()) == b"TRAFICO 0 0 3 2\n"
    peer.write(b"OK NS=0 EO=5 TOTAL=5 MAYOR=EO\n")
    qtbot.waitUntil(lambda: panel.status.text() == "Datos actuales")
    panel.disconnect_device()
    server.close()


def test_windows_wifi_output_distinguishes_current_and_visible_ssids():
    assert wlan_ssids(b" SSID : Estudiantes-CEIPA\r\n BSSID : aa:bb\r\n") == {b"Estudiantes-CEIPA"}
    output = b"SSID 1 : SIGMA-VIAL-Prueba-cf98\r\nSSID 2 : iPhone de Isaid\r\n"
    assert wlan_ssids(output) == {b"SIGMA-VIAL-Prueba-cf98", b"iPhone de Isaid"}


def test_camera_replaces_only_north_and_decision_requires_current_calibration(qtbot, settings):
    server = QTcpServer()
    assert server.listen(QHostAddress.SpecialAddress.LocalHost, 5050)
    token = object()
    observation = (token, 3)
    panel = WifiPanel(lambda: (99, 2, 1, 0), settings, lambda: observation)
    qtbot.addWidget(panel)
    panel.address.setText("127.0.0.1")
    panel.set_running(True)
    panel.button.click()
    qtbot.waitUntil(server.hasPendingConnections)
    peer = server.nextPendingConnection()
    qtbot.waitUntil(peer.canReadLine)
    assert bytes(peer.readLine()) == b"PING\n"
    peer.write(b"PONG\n")
    qtbot.waitUntil(peer.canReadLine, timeout=3000)
    assert bytes(peer.readLine()) == b"TRAFICO 3 2 1 0\n"
    peer.write(b"OK NS=5 EO=1 TOTAL=6 MAYOR=NS\n")
    qtbot.waitUntil(lambda: panel.processor_axis() == "ns")
    assert "Norte medido por cámara" in panel.counts.text()
    observation = (object(), 0)
    assert panel.processor_axis() is None
    qtbot.waitUntil(peer.canReadLine, timeout=3000)
    assert bytes(peer.readLine()) == b"TRAFICO 0 2 1 0\n"
    observation = None
    peer.write(b"OK NS=2 EO=1 TOTAL=3 MAYOR=NS\n")
    qtbot.waitUntil(panel.sample_button.isEnabled)
    assert panel.processor_axis() is None
    qtbot.waitUntil(peer.canReadLine, timeout=3000)
    assert bytes(peer.readLine()) == b"TRAFICO 99 2 1 0\n"
    panel.disconnect_device()
    server.close()
