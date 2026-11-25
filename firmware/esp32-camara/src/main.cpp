#include <Arduino.h>
#include <esp_camera.h>
#ifdef SIGMA_CAMARA_USB
#include <img_converters.h>
#include "north_queue.h"

NorthQueue northQueue;
uint8_t* rgb = nullptr;
bool fastFrame = false;
uint32_t fastSince = 0;

void endFastFrame() {
    if (fastFrame) {
        Serial.flush();
        Serial.updateBaudRate(460800);
        fastFrame = false;
    }
}
#endif
bool cameraReady = false;
#ifndef SIGMA_CAMARA_USB
#include <WiFi.h>
#include <esp_http_server.h>
#ifdef SIGMA_CAMARA_PRESENTACION
#include "ap_local.h"
constexpr char SSID[] = SIGMA_AP_SSID;
#define CAMERA_PASSWORD SIGMA_AP_PASSWORD
#else
#include "wifi_local.h"
constexpr char SSID[] = "Estudiantes-CEIPA";
#define CAMERA_PASSWORD SIGMA_WIFI_PASSWORD
#endif
httpd_handle_t server = nullptr;
IPAddress announced;

esp_err_t stream(httpd_req_t* req) {
    esp_err_t result = httpd_resp_set_type(req, "multipart/x-mixed-replace; boundary=frame");
    while (result == ESP_OK && WiFi.isConnected()) {
        camera_fb_t* frame = esp_camera_fb_get();
        if (!frame) return ESP_FAIL;
        char header[96];
        int length = snprintf(header, sizeof(header),
            "--frame\r\nContent-Type: image/jpeg\r\nContent-Length: %u\r\n\r\n",
            static_cast<unsigned>(frame->len));
        result = httpd_resp_send_chunk(req, header, length);
        if (result == ESP_OK) {
            result = httpd_resp_send_chunk(req, reinterpret_cast<const char*>(frame->buf), frame->len);
        }
        esp_camera_fb_return(frame);
        if (result == ESP_OK) result = httpd_resp_send_chunk(req, "\r\n", 2);
        delay(10);
    }
    return result;
}
#endif

void setup() {
#ifdef SIGMA_CAMARA_USB
    Serial.begin(460800);
    Serial.setTimeout(250);
#else
    Serial.begin(115200);
#endif
    camera_config_t c{};
    c.ledc_channel = LEDC_CHANNEL_0;
    c.ledc_timer = LEDC_TIMER_0;
    // Freenove ESP32-WROVER-DEV, camera header (WROVER-KIT mapping).
    c.pin_pwdn = -1;
    c.pin_reset = -1;
    c.pin_xclk = 21;
    c.pin_sccb_sda = 26;
    c.pin_sccb_scl = 27;
    c.pin_d0 = 4;
    c.pin_d1 = 5;
    c.pin_d2 = 18;
    c.pin_d3 = 19;
    c.pin_d4 = 36;
    c.pin_d5 = 39;
    c.pin_d6 = 34;
    c.pin_d7 = 35;
    c.pin_vsync = 25;
    c.pin_href = 23;
    c.pin_pclk = 22;
    c.xclk_freq_hz = 20000000;
    c.pixel_format = PIXFORMAT_JPEG;
    c.frame_size = FRAMESIZE_QVGA;
    c.jpeg_quality = 12;
#ifdef SIGMA_CAMARA_USB
    if (psramFound()) {
        c.frame_size = FRAMESIZE_VGA;
        c.jpeg_quality = 10;
    }
#endif
    c.fb_count = psramFound() ? 2 : 1;
    c.fb_location = psramFound() ? CAMERA_FB_IN_PSRAM : CAMERA_FB_IN_DRAM;
    c.grab_mode = CAMERA_GRAB_LATEST;
    esp_err_t err = esp_camera_init(&c);
    if (err != ESP_OK) {
        Serial.printf("ERROR camara: %s\n", esp_err_to_name(err));
        return;
    }
    cameraReady = true;
#ifndef SIGMA_CAMARA_USB
    WiFi.persistent(false);
    WiFi.mode(WIFI_STA);
    WiFi.setAutoReconnect(true);
    WiFi.begin(SSID, CAMERA_PASSWORD);
    Serial.printf("Camara lista. Conectando a %s...\n", SSID);
#endif
}

void loop() {
#ifdef SIGMA_CAMARA_USB
    const int command = Serial.available() ? Serial.read() : -1;
    if (command == 'F' && !fastFrame) {
        Serial.print("SVF1");
        Serial.flush();
        Serial.updateBaudRate(921600);
        fastFrame = true;
        fastSince = millis();
        return;
    }
    if (cameraReady && (command == 'J' || command == 'C' || command == 'N')) {
        bool valid = true;
        if (command == 'C') {
            uint8_t points[16];
            valid = Serial.readBytes(points, sizeof(points)) == sizeof(points) &&
                northQueue.setGuides(points);
        }
        camera_fb_t* frame = esp_camera_fb_get();
        if (frame) {
            uint32_t length = frame->len;
            const bool detect = command != 'J';
            uint8_t count = NorthQueue::unknown;
            if (detect) {
                if (!rgb) rgb = static_cast<uint8_t*>(ps_malloc(frame->width * frame->height * 3));
                const bool decoded = valid && rgb &&
                    fmt2rgb888(frame->buf, length, frame->format, rgb);
                count = northQueue.observe(decoded ? rgb : nullptr, command == 'C', millis(),
                                           frame->width, frame->height);
            }
            Serial.write(reinterpret_cast<const uint8_t*>(detect ? "SVJ2" : "SVJ1"), 4);
            Serial.write(reinterpret_cast<const uint8_t*>(&length), sizeof(length));
            if (detect) Serial.write(count);
            Serial.write(frame->buf, length);
            esp_camera_fb_return(frame);
        }
        endFastFrame();
    }
    if (fastFrame && millis() - fastSince > 900) endFastFrame();
    delay(1);
#else
    delay(500);
    if (!cameraReady) return;
    if (!WiFi.isConnected()) {
        announced = IPAddress();
        return;
    }
    if (!server) {
        httpd_config_t config = HTTPD_DEFAULT_CONFIG();
        config.send_wait_timeout = 3;
        if (httpd_start(&server, &config) != ESP_OK) return;
        httpd_uri_t route{};
        route.uri = "/stream";
        route.method = HTTP_GET;
        route.handler = stream;
        if (httpd_register_uri_handler(server, &route) != ESP_OK) {
            httpd_stop(server);
            server = nullptr;
            return;
        }
    }
    const IPAddress ip = WiFi.localIP();
    if (ip != announced) {
        announced = ip;
        Serial.printf("CAMARA IP=%s URL=http://%s/stream\n",
                      ip.toString().c_str(), ip.toString().c_str());
    }
#endif
}
