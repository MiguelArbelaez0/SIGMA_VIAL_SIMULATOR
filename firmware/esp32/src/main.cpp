#include <Arduino.h>
#include <cstring>

constexpr uint8_t NORTH_LED_PIN = 23;

void setup() {
    pinMode(NORTH_LED_PIN, OUTPUT);
    digitalWrite(NORTH_LED_PIN, LOW);
    Serial.begin(115200);
}

void loop() {
    static char line[64];
    static size_t length = 0;
    static bool invalid = false;
    while (Serial.available()) {
        const int ch = Serial.read();
        if (ch == '\n') {
            if (length && line[length - 1] == '\r') --length;
            line[length] = '\0';
            if (!invalid && strcmp(line, "PING") == 0) {
                Serial.println("PONG");
            } else if (!invalid && strcmp(line, "NORTE ROJO") == 0) {
                digitalWrite(NORTH_LED_PIN, HIGH);
                Serial.println("OK NORTE ROJO");
            } else if (!invalid && strcmp(line, "NORTE APAGADO") == 0) {
                digitalWrite(NORTH_LED_PIN, LOW);
                Serial.println("OK NORTE APAGADO");
            } else {
                Serial.println("ERROR orden desconocida");
            }
            length = 0;
            invalid = false;
        } else if (length < sizeof(line) - 1 && ch > 0) {
            line[length++] = static_cast<char>(ch);
        } else {
            invalid = true;
        }
    }
}
