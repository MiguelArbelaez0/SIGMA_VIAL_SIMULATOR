// Host regression for the same detector compiled into the USB firmware.
#include "../src/north_queue.h"
#include <assert.h>

static uint8_t image[240][320][3];

static void background(bool shifted = false) {
    for (int y = 0; y < 240; ++y)
        for (int x = 0; x < 320; ++x) {
            int gray = x < 65 ? (((x + (shifted ? 4 : 0)) / 5) % 2 ? 210 : 25) : 80;
            memset(image[y][x], gray, 3);
        }
}

static void car(int x, int y) {
    for (int row = y; row < y + 14; ++row)
        for (int col = x - 4; col <= x + 4; ++col)
            memset(image[row][col], 205, 3);
}

int main() {
    NorthQueue queue;
    // Deliberately different from the initial on-screen guides.
    uint8_t points[] = {90,0,20,0,90,0,194,0,170,0,20,0,170,0,194,0};
    assert(queue.setGuides(points));
    auto observe = [&](uint32_t now, bool calibrate = false) {
        return queue.observe(image[0][0], calibrate, now);
    };
    background();
    assert(observe(0) == NorthQueue::unknown);
    assert(observe(1, true) == NorthQueue::unknown);
    assert(observe(100) == 0);
    for (int i = 0; i < 10; ++i) {
        background();
        car(90, 30 + 5*i);
        assert(observe(200 + 100*i) == 0);
    }
    background();
    car(90, 120);
    car(170, 110);
    car(170, 150);
    assert(observe(1300) == 0);
    assert(observe(1700) == 0);
    assert(observe(2100) == 3);
    assert(observe(2300) == 3);
    background(true);
    assert(observe(2500) == NorthQueue::unknown);
    background();
    assert(observe(2700) == 0);
    // Forty separated stationary vehicles in one VGA guide, none in the other.
    static uint8_t vga[480][640][3];
    for (int y = 0; y < 480; ++y)
        for (int x = 0; x < 640; ++x)
            memcpy(vga[y][x], image[y/2][x/2], 3);
    assert(queue.observe(vga[0][0], true, 2800, 640, 480) == NorthQueue::unknown);
    for (int n = 0; n < 40; ++n)
        for (int y = 46 + n*8; y < 51 + n*8; ++y)
            for (int x = 177; x <= 183; ++x)
                memset(vga[y][x], 205, 3);
    assert(queue.observe(vga[0][0], false, 3000, 640, 480) == 0);
    assert(queue.observe(vga[0][0], false, 3800, 640, 480) == 40);
    points[1] = 2;  // Out-of-frame coordinate invalidates the calibration.
    assert(!queue.setGuides(points));
    assert(observe(2800) == NorthQueue::unknown);
}
