#include <Arduino.h>
#include <cstring>
#include <WiFi.h>
#include <lwip/sockets.h>

#ifdef SIGMA_DEMO_AP
#include "ap_local.h"
#endif

#if __has_include("wifi_local.h")
#include "wifi_local.h"
#else
#define SIGMA_WIFI_PASSWORD ""
#endif

constexpr char WIFI_SSID[] = "Estudiantes-CEIPA";
constexpr uint16_t TCP_PORT = 5050;
int listener = -1;

void closeListener() {
    if (listener >= 0) lwip_close(listener);
    listener = -1;
}

bool listenIPv4() {
    listener = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
    if (listener < 0) return false;
    sockaddr_in address{};
    address.sin_family = AF_INET;
    address.sin_port = htons(TCP_PORT);
    address.sin_addr.s_addr = htonl(INADDR_ANY);
    const int reuse = 1;
    setsockopt(listener, SOL_SOCKET, SO_REUSEADDR, &reuse, sizeof(reuse));
    if (bind(listener, reinterpret_cast<sockaddr*>(&address), sizeof(address)) == 0 &&
        listen(listener, 4) == 0 && fcntl(listener, F_SETFL, O_NONBLOCK) == 0) {
        return true;
    }
    Serial.printf("TCP error=%d\n", errno);
    closeListener();
    return false;
}
WiFiClient client;
IPAddress announcedIP;
constexpr size_t MAX_LINE = 64;
struct LineBuffer {
    char data[MAX_LINE + 2];
    size_t used = 0;
    bool invalid = false;
};

LineBuffer tcpLine;
void readCommand(Stream& stream, LineBuffer& line, bool serialPort);

void serviceWifi() {
#ifdef SIGMA_DEMO_AP
    const IPAddress ip = WiFi.softAPIP();
    if (ip == IPAddress()) {
#else
    const IPAddress ip = WiFi.localIP();
    if (WiFi.status() != WL_CONNECTED || ip == IPAddress()) {
#endif
        if (announcedIP != IPAddress()) {
            client.stop();
            closeListener();
            announcedIP = IPAddress();
        }
        return;
    }
    if (ip != announcedIP) {
        client.stop();
        closeListener();
        if (!listenIPv4()) {
            Serial.println("TCP 5050: fallo al abrir la escucha");
            delay(250);
            return;
        }
        announcedIP = ip;
        Serial.printf("LISTEN IP=%s TCP=%u\n", ip.toString().c_str(), TCP_PORT);
    }
    if (!client.connected()) {
        const int fd = accept(listener, nullptr, nullptr);
        if (fd < 0) return;
        client = WiFiClient(fd);
        if (client) Serial.printf("TCP cliente=%s\n", client.remoteIP().toString().c_str());
        tcpLine = {};
    }
    readCommand(client, tcpLine, false);
    char peek;
    if (client.fd() >= 0 && recv(client.fd(), &peek, 1, MSG_PEEK | MSG_DONTWAIT) == 0)
        client.stop();
}

constexpr unsigned MAX_COUNT = 9999;

void processLine(char* line, Print& output, bool serialPort) {
    if (serialPort && strcmp(line, "TEST TCP") == 0) {
        WiFiClient probe;
        if (listener < 0 || client.connected()) {
            Serial.println("TEST TCP: escucha inactiva o cliente ocupado");
            return;
        }
        if (!probe.connect(IPAddress(127, 0, 0, 1), TCP_PORT, 1000)) {
            Serial.printf("TEST TCP: fallo de loopback errno=%d\n", errno);
            return;
        }
        probe.print("PING\n");
        const unsigned long start = millis();
        while (millis() - start < 1000 && !probe.available()) {
            serviceWifi();
            delay(1);
        }
        probe.setTimeout(200);
        Serial.print("TEST TCP local: ");
        Serial.println(probe.readStringUntil('\n'));
        probe.stop();
        client.stop();
        return;
    }
    char* cursor = nullptr;
    char* command = strtok_r(line, " \t", &cursor);
    if (!command) {
        output.println("ERROR comando vacio");
        return;
    }
    char* token = strtok_r(nullptr, " \t", &cursor);
    if (strcmp(command, "PING") == 0 && !token) {
        output.println("PONG");
        return;
    }
    if (strcmp(command, "TRAFICO") != 0) {
        output.println("ERROR comando invalido");
        return;
    }
    unsigned counts[4] = {};
    for (unsigned& count : counts) {
        if (!token) {
            output.println("ERROR se requieren cuatro valores");
            return;
        }
        for (const char* digit = token; *digit; ++digit) {
            if (*digit < '0' || *digit > '9') {
                output.println("ERROR se requiere un entero decimal de 0 a 9999");
                return;
            }
            count = count * 10 + (*digit - '0');
            if (count > MAX_COUNT) {
                output.println("ERROR valor fuera de rango 0 a 9999");
                return;
            }
        }
        token = strtok_r(nullptr, " \t", &cursor);
    }
    if (token) {
        output.println("ERROR sobran valores");
        return;
    }
    const unsigned ns = counts[0] + counts[1];
    const unsigned eo = counts[2] + counts[3];
    const unsigned total = ns + eo;
    const char* mayor = "EMPATE";
    if (!total) mayor = "SIN_DEMANDA";
    else if (ns > eo) mayor = "NS";
    else if (eo > ns) mayor = "EO";
    output.printf("OK NS=%u EO=%u TOTAL=%u MAYOR=%s\n", ns, eo, total, mayor);
}

void setup() {
    Serial.begin(115200);
#ifdef SIGMA_DEMO_AP
    WiFi.persistent(false);
    WiFi.mode(WIFI_AP);
    WiFi.softAP(SIGMA_AP_SSID, SIGMA_AP_PASSWORD);
#else
    if (SIGMA_WIFI_PASSWORD[0]) {
        WiFi.persistent(false);
        WiFi.mode(WIFI_STA);
        WiFi.setAutoReconnect(true);
        WiFi.begin(WIFI_SSID, SIGMA_WIFI_PASSWORD);  // DHCP por defecto.
    } else {
        Serial.println("Wi-Fi pendiente: configure wifi_local.h");
    }
#endif
}

void readCommand(Stream& stream, LineBuffer& line, bool serialPort) {
    while (stream.available()) {
        const int ch = stream.read();
        if (ch == '\n') {
            if (line.used && line.data[line.used - 1] == '\r') --line.used;
            if (line.invalid || line.used > MAX_LINE) {
                stream.println("ERROR linea invalida o mayor de 64 bytes");
            } else {
                line.data[line.used] = '\0';
                processLine(line.data, stream, serialPort);
            }
            line = {};
            return;
        }
        if (ch <= 0 || ch > 127 || line.used == sizeof(line.data) - 1) {
            line.invalid = true;
        } else {
            line.data[line.used++] = static_cast<char>(ch);
        }
    }
}

void loop() {
    serviceWifi();
    static LineBuffer serialLine;
    readCommand(Serial, serialLine, true);
}
