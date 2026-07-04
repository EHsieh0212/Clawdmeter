#pragma once
#include <stdint.h>

// Time-synced lyrics model shared by the UI. In Phase 1 the data is a
// hard-coded sample driven by a fake local clock so the SCREEN_LYRICS layout
// can be iterated on with the `screenshot` command. In Phase 2 the same query
// surface is fed by lyric chunks arriving over BLE (see docs/lyrics-design).
//
// The current-line logic is deliberately identical to the host-side probe:
// a base playback position (progress_ms) captured at a base millis(), advanced
// locally between updates. That means smooth scrolling regardless of how often
// the host reports position.

#define LYRICS_MAX_LINES 96

struct LyricLine {
    uint32_t    ms;    // start timestamp within the track, milliseconds
    const char* text;  // UTF-8 line text (Latin only for now)
};

void lyrics_init(void);
void lyrics_tick(void);   // advance the playback clock (fake in Phase 1)

bool        lyrics_available(void);      // have a track + at least one line
bool        lyrics_is_playing(void);     // playback currently active
const char* lyrics_track(void);
const char* lyrics_artist(void);
int         lyrics_count(void);
const char* lyrics_line(int i);          // NULL if i out of range
int         lyrics_current_index(void);  // -1 before the first line's timestamp
