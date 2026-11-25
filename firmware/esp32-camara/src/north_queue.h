#pragma once

#include <stdint.h>
#include <stdlib.h>
#include <string.h>

// Two user-marked lines in the 320 x 240 image, from upstream to the stop line.
class NorthQueue {
public:
    static constexpr uint8_t unknown = 255;

    bool setGuides(const uint8_t* coordinates) {
        ready = false;
        for (int i = 0; i < 8; ++i) {
            unsigned value = coordinates[2*i] | (coordinates[2*i+1] << 8);
            if (value >= (i % 2 ? 240 : 320)) return false;
            guides[i] = value;
        }
        for (int lane = 0; lane < 2; ++lane) {
            const int* p = guides + 4 * lane;
            if (abs(p[2]-p[0]) + abs(p[3]-p[1]) < 20) return false;
        }
        return true;
    }

    uint8_t observe(const uint8_t* rgb, bool calibrate, uint32_t now, int w = 320, int h = 240) {
        if (!rgb || !((w == 320 && h == 240) || (w == 640 && h == 480))) {
            clearTracks();
            if (calibrate) ready = false;
            return unknown;
        }
        if (calibrate) {
            width = w;
            height = h;
            for (int lane = 0; lane < 2; ++lane) {
                const int* p = guides + 4 * lane;
                const int dx = abs(p[2] - p[0]) * width / 320;
                const int dy = abs(p[3] - p[1]) * height / 240;
                lengths[lane] = 1 + (dx > dy ? dx : dy);
                for (int row = 0; row < lengths[lane]; ++row)
                    sample(rgb, lane, row, background[lane][row]);
            }
            sceneMatches(rgb, true);
            ready = true;
            clearTracks();
            return unknown;
        }
        if (!ready || w != width || h != height) return unknown;
        if (!sceneMatches(rgb, false)) {
            clearTracks();
            return unknown;
        }
        if (now - lastFrame > 1800) clearTracks();
        lastFrame = now;
        int count = 0;
        for (int lane = 0; lane < 2; ++lane) {
            const int rows = lengths[lane];
            Track next[capacity];
            bool used[capacity]{};
            int found = 0, start = -1, last = -1;
            for (int row = 0; row <= rows; ++row) {
                uint8_t pixel[3];
                if (row < rows) sample(rgb, lane, row, pixel);
                if (row < rows && difference(pixel, background[lane][row]) > 66) {
                    if (start < 0) start = row;
                    last = row;
                } else if (start >= 0 && (row == rows || row - last >= 2)) {
                    if (last - start >= 3) {
                        // A continuous patch covering most of the guide is unusable.
                        if (last - start > rows * 3 / 4) {
                            clearTracks();
                            return unknown;
                        }
                        Track track{start, last, now};
                        for (int i = 0; i < sizes[lane]; ++i) {
                            const Track& old = tracks[lane][i];
                            if (!used[i] && abs(old.start - start) <= 1 && abs(old.end - last) <= 1) {
                                used[i] = true;
                                track = old;
                                break;
                            }
                        }
                        next[found++] = track;
                        if (now - track.since >= 700) ++count;
                    }
                    start = -1;
                }
            }
            memcpy(tracks[lane], next, found * sizeof(Track));
            sizes[lane] = found;
        }
        return count;
    }

private:
    // Each segment needs four samples; two clear samples separate adjacent cars.
    // Even both longest VGA guides together fit the count byte (255 = unknown).
    static constexpr int maxPixels = 640, capacity = (maxPixels + 2) / 6;
    struct Track { int start, end; uint32_t since; };
    uint8_t background[2][maxPixels][3]{};
    int16_t edges[30][40]{};
    uint32_t lastFrame = 0;
    Track tracks[2][capacity]{};
    int width = 320, height = 240, lengths[2]{};
    int sizes[2]{};
    int guides[8] = {112,32,112,206,208,32,208,206};
    bool ready = false;
    void clearTracks() { sizes[0] = sizes[1] = 0; }
    static int luminance(const uint8_t* pixel) {
        return (pixel[0] + 2 * pixel[1] + pixel[2]) / 4;
    }
    bool sceneMatches(const uint8_t* rgb, bool save) {
        // Fixed high-contrast edges survive small changes in monitor brightness.
        // If many edges move together the reference no longer describes this view.
        int anchors = 0, lost = 0;
        for (int y = 4; y < 240; y += 8) {
            for (int x = 4; x < 320; x += 8) {
                const uint8_t* p = rgb + 3 * (y * height / 240 * width + x * width / 320);
                const int offset = 3 * (width + 2) * (width / 320);
                const int contrast = luminance(p + offset) - luminance(p - offset);
                int16_t& reference = edges[y / 8][x / 8];
                if (save) reference = contrast;
                if (abs(reference) < 30) continue;
                ++anchors;
                if (contrast * reference <= 0 || abs(contrast) < abs(reference) / 3) ++lost;
            }
        }
        return anchors >= 6 && lost * 4 <= anchors;
    }
    static int difference(const uint8_t* a, const uint8_t* b) {
        return abs(a[0]-b[0]) + abs(a[1]-b[1]) + abs(a[2]-b[2]);
    }
    void sample(const uint8_t* rgb, int lane, int row, uint8_t out[3]) const {
        const int* p = guides + 4 * lane;
        const int intervals = lengths[lane] - 1;
        const int scale = width / 320;
        int x = p[0] * scale + (p[2] - p[0]) * scale * row / intervals;
        const int y = p[1] * scale + (p[3] - p[1]) * scale * row / intervals;
        x = x < 1 ? 1 : (x > width - 2 ? width - 2 : x);
        const uint8_t* mid = rgb + 3 * (y * width + x);
        for (int c = 0; c < 3; ++c)
            out[c] = (mid[c-3] + mid[c] + mid[c+3]) / 3;
    }
};
