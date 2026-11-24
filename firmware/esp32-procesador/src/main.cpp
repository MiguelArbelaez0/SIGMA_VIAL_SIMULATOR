#include <Arduino.h>
#include <cstring>
#include <WiFi.h>
#include <lwip/sockets.h>

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
char request[7];  // PING, CR opcional y terminador.
size_t received = 0;

void serviceWifi() {
    const IPAddress ip = WiFi.localIP();
    if (WiFi.status() != WL_CONNECTED || ip == IPAddress()) {
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
        received = 0;
    }
    while (client.available()) {
        const int ch = client.read();
        if (ch == '\n') {
            if (received && request[received - 1] == '\r') --received;
            if (received == 4 && memcmp(request, "PING", 4) == 0) {
                if (client.print("PONG\n") == 5) Serial.println("TCP PING recibido, PONG enviado");
            } else {
                client.stop();
            }
            received = 0;
            break;
        }
        if (received >= sizeof(request) - 1) {
            client.stop();
            break;
        }
        request[received++] = static_cast<char>(ch);
    }
}

constexpr size_t MAX_LINE = 64;
constexpr unsigned MAX_COUNT = 9999;

void processLine(char* line) {
    if (strcmp(line, "TEST TCP") == 0) {
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
        Serial.println("ERROR comando vacio");
        return;
    }
    char* token = strtok_r(nullptr, " \t", &cursor);
    if (strcmp(command, "PING") == 0 && !token) {
        Serial.println("PONG");
        return;
    }
    if (strcmp(command, "TRAFICO") != 0) {
        Serial.println("ERROR comando invalido");
        return;
    }
    unsigned counts[4] = {};
    for (unsigned& count : counts) {
        if (!token) {
            Serial.println("ERROR se requieren cuatro valores");
            return;
        }
        for (const char* digit = token; *digit; ++digit) {
            if (*digit < '0' || *digit > '9') {
                Serial.println("ERROR se requiere un entero decimal de 0 a 9999");
                return;
            }
            count = count * 10 + (*digit - '0');
            if (count > MAX_COUNT) {
                Serial.println("ERROR valor fuera de rango 0 a 9999");
                return;
            }
        }
        token = strtok_r(nullptr, " \t", &cursor);
    }
    if (token) {
        Serial.println("ERROR sobran valores");
        return;
    }
    const unsigned ns = counts[0] + counts[1];
    const unsigned eo = counts[2] + counts[3];
    const unsigned total = ns + eo;
    const char* mayor = "EMPATE";
    if (!total) mayor = "SIN_DEMANDA";
    else if (ns > eo) mayor = "NS";
    else if (eo > ns) mayor = "EO";
    Serial.printf("OK NS=%u EO=%u TOTAL=%u MAYOR=%s\n", ns, eo, total, mayor);
}

void setup() {
    Serial.begin(115200);
    if (SIGMA_WIFI_PASSWORD[0]) {
        WiFi.persistent(false);
        WiFi.mode(WIFI_STA);
        WiFi.setAutoReconnect(true);
        WiFi.begin(WIFI_SSID, SIGMA_WIFI_PASSWORD);  // DHCP por defecto.
    } else {
        Serial.println("Wi-Fi pendiente: configure wifi_local.h");
    }
}

void loop() {
    if (SIGMA_WIFI_PASSWORD[0]) serviceWifi();
    static char line[MAX_LINE + 2];  // Espacio para CR opcional y terminador.
    static size_t used = 0;
    static bool invalid = false;
    while (Serial.available()) {
        const int ch = Serial.read();
        if (ch == '\n') {
            if (used && line[used - 1] == '\r') --used;
            if (invalid || used > MAX_LINE) {
                Serial.println("ERROR linea invalida o mayor de 64 bytes");
            } else {
                line[used] = '\0';
                processLine(line);
            }
            used = 0;
            invalid = false;
        } else if (ch <= 0 || ch > 127 || used == sizeof(line) - 1) {
            invalid = true;
        } else {
            line[used++] = static_cast<char>(ch);
        }
    }
}
