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

    uint8_t observe(const uint8_t* rgb, bool calibrate, uint32_t now) {
        if (!rgb) {
            clearTracks();
            if (calibrate) ready = false;
            return unknown;
        }
        if (calibrate) {
            for (int lane = 0; lane < 2; ++lane)
                for (int row = 0; row < rows; ++row)
                    sample(rgb, lane, row, background[lane][row]);
            sceneMatches(rgb, true);
            ready = true;
            clearTracks();
            return unknown;
        }
        if (!ready) return unknown;
        if (!sceneMatches(rgb, false)) {
            clearTracks();
            return unknown;
        }
        if (now - lastFrame > 600) clearTracks();
        lastFrame = now;
        int count = 0;
        for (int lane = 0; lane < 2; ++lane) {
            Track next[maxTracks]{};
            bool used[maxTracks]{};
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
                        if (last - start > rows * 3 / 4 || found == maxTracks) {
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
            memcpy(tracks[lane], next, sizeof(next));
            sizes[lane] = found;
        }
        return count;
    }

private:
    static constexpr int rows = 88, maxTracks = 16;
    struct Track { int start, end; uint32_t since; };
    uint8_t background[2][rows][3]{};
    int16_t edges[30][40]{};
    uint32_t lastFrame = 0;
    Track tracks[2][maxTracks]{};
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
                const uint8_t* p = rgb + 3 * (y * 320 + x);
                const int contrast = luminance(p + 3 * (320 + 2)) - luminance(p - 3 * (320 + 2));
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
        int x = p[0] + (p[2] - p[0]) * row / (rows - 1);
        const int y = p[1] + (p[3] - p[1]) * row / (rows - 1);
        x = x < 1 ? 1 : (x > 318 ? 318 : x);
        const uint8_t* mid = rgb + 3 * (y * 320 + x);
        for (int c = 0; c < 3; ++c)
            out[c] = (mid[c-3] + mid[c] + mid[c+3]) / 3;
    }
};
