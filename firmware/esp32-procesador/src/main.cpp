#include <Arduino.h>
#include <cstring>
#include <WiFi.h>

#if __has_include("wifi_local.h")
#include "wifi_local.h"
#else
#define SIGMA_WIFI_PASSWORD ""
#endif

constexpr char WIFI_SSID[] = "Estudiantes-CEIPA";
constexpr uint16_t TCP_PORT = 5050;
WiFiServer server(TCP_PORT);
WiFiClient client;
IPAddress announcedIP;
char request[7];  // PING, CR opcional y terminador.
size_t received = 0;

void serviceWifi() {
    const IPAddress ip = WiFi.localIP();
    if (WiFi.status() != WL_CONNECTED || ip == IPAddress()) {
        if (announcedIP != IPAddress()) {
            client.stop();
            server.end();
            announcedIP = IPAddress();
        }
        return;
    }
    if (ip != announcedIP) {
        client.stop();
        server.end();
        server.begin();
        announcedIP = ip;
        Serial.printf("IP=%s TCP=%u\n", ip.toString().c_str(), TCP_PORT);
    }
    if (!client.connected()) {
        client = server.accept();
        received = 0;
    }
    while (client.available()) {
        const int ch = client.read();
        if (ch == '\n') {
            if (received && request[received - 1] == '\r') --received;
            if (received == 4 && memcmp(request, "PING", 4) == 0) {
                client.print("PONG\n");
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
