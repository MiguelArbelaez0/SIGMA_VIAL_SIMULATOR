#include <Arduino.h>
#include <cstring>

void setup() {
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
                Serial.println("OK NORTE ROJO");
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
