#pragma once
#include <stdint.h>

// Time-synced lyrics model shared by the UI. Data arrives as discrete messages
// (see ble.cpp dispatch): a header naming the track + line count, then one
// message per line, then periodic playback-position updates. The current line
// is derived by interpolating the last reported position with millis(), so the
// display scrolls smoothly regardless of how often the host reports position.
//
// A built-in demo song (lyrics_load_demo) drives the same ingest path without
// BLE, for screenshot iteration and as an offline smoke test.

#define LYRICS_MAX_LINES 96
#define LYRICS_MAX_LINE  100   // bytes per line incl. NUL
#define LYRICS_MAX_NAME  64    // bytes for track / artist incl. NUL
#define LYRICS_DEMO_ID   0xDEADBEEF   // track id used by lyrics_load_demo()

void lyrics_init(void);
void lyrics_tick(void);

// --- Ingest (from BLE dispatch or the demo loader) ---
// `id` is a per-track hash so late chunks from a previous track are dropped and
// a header for a new id resets the buffer.
void lyrics_ingest_header(uint32_t id, uint16_t n_lines,
                          const char* track, const char* artist);
void lyrics_ingest_line(uint32_t id, uint16_t idx, uint32_t ms, const char* text);
void lyrics_ingest_pos(uint32_t id, uint32_t ms, bool playing);
void lyrics_ingest_none(void);    // nothing playing / stopped
void lyrics_load_demo(void);      // inject the built-in sample (no BLE)

// --- Query for rendering ---
bool        lyrics_available(void);      // a track header has been received
bool        lyrics_is_playing(void);     // playback currently active
const char* lyrics_track(void);
const char* lyrics_artist(void);
int         lyrics_count(void);          // lines received so far
const char* lyrics_line(int i);          // NULL if i out of range
int         lyrics_current_index(void);  // -1 before the first line's timestamp
