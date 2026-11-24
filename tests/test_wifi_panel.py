from PySide6.QtNetwork import QHostAddress, QTcpServer

from sigma_vial.presentation.wifi_panel import WifiPanel


def test_panel_waits_for_complete_pong(qtbot):
    server = QTcpServer()
    assert server.listen(QHostAddress.SpecialAddress.LocalHost, 5050)
    panel = WifiPanel(lambda: (1, 2, 7, 3))
    qtbot.addWidget(panel)
    panel.address.setText("127.0.0.1")
    panel.button.click()
    qtbot.waitUntil(server.hasPendingConnections)
    peer = server.nextPendingConnection()
    qtbot.waitUntil(peer.canReadLine)
    assert bytes(peer.readLine()) == b"PING\n"
    peer.write(b"PO")
    qtbot.waitUntil(lambda: panel.socket.bytesAvailable() == 2)
    assert panel.status.text() == "Esperando PONG…"
    peer.write(b"NG\r\n")
    qtbot.waitUntil(lambda: panel.status.text() == "Esperando primera muestra · PONG recibido")
    panel.sample_button.click()
    assert not panel.sample_button.isEnabled()
    qtbot.waitUntil(peer.canReadLine)
    assert bytes(peer.readLine()) == b"TRAFICO 1 2 7 3\n"
    peer.write(b"OK NS=3 EO=10 TOTAL=13 MAYOR=EO\n")
    qtbot.waitUntil(panel.sample_button.isEnabled)
    assert panel.reply.text() == "ESP32 responde: OK NS=3 EO=10 TOTAL=13 MAYOR=EO"
    peer.disconnectFromHost()
    qtbot.waitUntil(lambda: panel.socket is None)
    server.close()


def test_auto_sample_keeps_request_until_reply_and_discards_it_on_reset(qtbot):
    server = QTcpServer()
    assert server.listen(QHostAddress.SpecialAddress.LocalHost, 5050)
    counts = [1, 2, 7, 3]
    panel = WifiPanel(lambda: counts)
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
