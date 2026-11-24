from PySide6.QtNetwork import QHostAddress, QTcpServer

from sigma_vial.presentation.wifi_panel import WifiPanel


def test_panel_waits_for_complete_pong(qtbot):
    server = QTcpServer()
    assert server.listen(QHostAddress.SpecialAddress.LocalHost, 5050)
    panel = WifiPanel()
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
    peer.disconnectFromHost()
    qtbot.waitUntil(lambda: panel.socket is None)
    server.close()
