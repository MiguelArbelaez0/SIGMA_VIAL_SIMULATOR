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
    qtbot.waitUntil(lambda: panel.status.text() == "Conectado · PONG recibido")
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
