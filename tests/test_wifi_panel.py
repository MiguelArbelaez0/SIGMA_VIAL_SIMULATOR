import pytest
from PySide6.QtCore import QSettings
from PySide6.QtNetwork import QHostAddress, QTcpServer

from sigma_vial.presentation.wifi_panel import WifiPanel, demand_text


@pytest.fixture
def settings(tmp_path):
    return QSettings(str(tmp_path / "panel.ini"), QSettings.Format.IniFormat)


@pytest.mark.parametrize(
    ("response", "summary"),
    [
        ("OK NS=0 EO=0 TOTAL=0 MAYOR=SIN_DEMANDA", "Sin demanda · ninguna cola detectada"),
        ("OK NS=1 EO=1 TOTAL=2 MAYOR=EMPATE", "Empate · 1 vehículo en cada eje"),
        ("OK NS=2 EO=1 TOTAL=3 MAYOR=NS", "Mayor cola: Norte–Sur · 2 vehículos en ese eje"),
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
    panel.change_address.click()
    panel.address.setText("127.0.0.1")
    panel.button.click()
    qtbot.waitUntil(server.hasPendingConnections)
    peer = server.nextPendingConnection()
    qtbot.waitUntil(peer.canReadLine)
    assert bytes(peer.readLine()) == b"PING\n"
    peer.write(b"PO")
    qtbot.waitUntil(lambda: panel.socket.bytesAvailable() == 2)
    assert panel.status.text() == "Esperando PONG…"
    assert not settings.contains("ip")
    assert panel.button.text() == "Conectando…"
    peer.write(b"NG\r\n")
    qtbot.waitUntil(lambda: panel.status.text() == "Esperando primera muestra · PONG recibido")
    assert panel.button.text() == "ESP32 conectado"
    assert settings.value("ip") == "127.0.0.1"
    panel.sample_button.click()
    assert not panel.sample_button.isEnabled()
    qtbot.waitUntil(peer.canReadLine)
    assert bytes(peer.readLine()) == b"TRAFICO 1 2 7 3\n"
    peer.write(b"OK NS=3 EO=10 TOTAL=13 MAYOR=EO\n")
    qtbot.waitUntil(panel.sample_button.isEnabled)
    assert panel.reply.text() == "ESP32 responde: OK NS=3 EO=10 TOTAL=13 MAYOR=EO"
    assert panel.result.text() == "Mayor cola: Oriente–Occidente · 10 vehículos en ese eje"
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
