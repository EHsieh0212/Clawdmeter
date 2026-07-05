#include "lyrics.h"
#include <Arduino.h>
#include <string.h>

// ---------------------------------------------------------------------------
// Lyrics state. Fixed-size storage (no dynamic allocation): on the S3 this sits
// in PSRAM-backed BSS comfortably; the whole buffer is ~9.6 KB. A C6 port would
// need to shrink LYRICS_MAX_LINES to fit internal SRAM.
// ---------------------------------------------------------------------------

static char     g_track[LYRICS_MAX_NAME];
static char     g_artist[LYRICS_MAX_NAME];
static uint32_t g_track_id;                 // 0 = none
static uint16_t g_n_lines;                  // total lines the header promised
static uint16_t g_n_received;               // contiguous lines stored so far
static uint32_t g_line_ms[LYRICS_MAX_LINES];
static char     g_line_text[LYRICS_MAX_LINES][LYRICS_MAX_LINE];
static bool     g_have_header;

// Playback position: last reported position captured at a base millis(),
// advanced locally between updates. `g_loop_ms` is non-zero only for the demo
// (so it repeats); real playback leaves it 0 and refreshes the base on every
// position message.
static uint32_t g_base_ms;
static uint32_t g_base_millis;
static bool     g_playing;
static uint32_t g_loop_ms;

static void reset_track(void) {
    g_track[0] = '\0';
    g_artist[0] = '\0';
    g_track_id = 0;
    g_n_lines = 0;
    g_n_received = 0;
    g_have_header = false;
    g_base_ms = 0;
    g_base_millis = millis();
    g_playing = false;
    g_loop_ms = 0;
}

void lyrics_init(void) {
    reset_track();
}

void lyrics_tick(void) {
    // Position is derived on read from millis(); nothing to advance here.
}

// --- Ingest -----------------------------------------------------------------

void lyrics_ingest_header(uint32_t id, uint16_t n_lines,
                          const char* track, const char* artist) {
    reset_track();
    g_track_id = id;
    g_n_lines = (n_lines > LYRICS_MAX_LINES) ? LYRICS_MAX_LINES : n_lines;
    if (n_lines > LYRICS_MAX_LINES)
        Serial.printf("lyrics: truncating %u lines to %u\n", n_lines, LYRICS_MAX_LINES);
    strlcpy(g_track,  track  ? track  : "", sizeof(g_track));
    strlcpy(g_artist, artist ? artist : "", sizeof(g_artist));
    g_have_header = true;
    g_playing = true;   // a fresh song implies playback; a pos msg refines this
    g_base_millis = millis();
}

void lyrics_ingest_line(uint32_t id, uint16_t idx, uint32_t ms, const char* text) {
    if (!g_have_header || id != g_track_id) return;   // stale / unknown track
    if (idx >= g_n_lines || idx >= LYRICS_MAX_LINES) return;
    g_line_ms[idx] = ms;
    strlcpy(g_line_text[idx], text ? text : "", LYRICS_MAX_LINE);
    // Lines stream in order; advance the contiguous-received count.
    if (idx == g_n_received) {
        g_n_received++;
        while (g_n_received < g_n_lines && g_line_text[g_n_received][0] != '\0'
               && g_line_ms[g_n_received] != 0)
            g_n_received++;
    } else if (idx + 1 > g_n_received) {
        g_n_received = idx + 1;   // gap (dropped write): best-effort
    }
}

void lyrics_ingest_pos(uint32_t id, uint32_t ms, bool playing) {
    if (g_have_header && id != g_track_id) return;   // position for another track
    g_base_ms = ms;
    g_base_millis = millis();
    g_playing = playing;
    g_loop_ms = 0;   // real playback: no wraparound
}

void lyrics_ingest_none(void) {
    // Host reports paused / nothing playing → show the idle logo, but KEEP the
    // buffered lyrics. Resuming the same track only sends a position update (no
    // re-push), so clearing here would leave nothing to display on resume.
    g_playing = false;
}

// --- Query ------------------------------------------------------------------

static uint32_t playback_pos_ms(void) {
    uint32_t pos = g_base_ms;
    if (g_playing) pos += (millis() - g_base_millis);
    if (g_loop_ms) pos %= g_loop_ms;
    return pos;
}

bool lyrics_available(void) {
    // True as soon as the header arrives — the lines stream in over the next
    // fraction of a second, and we must not bounce to the gif in that gap.
    // The renderer shows the track name with a placeholder line until lines land.
    return g_have_header;
}

bool lyrics_is_playing(void) {
    return g_playing;
}

const char* lyrics_track(void)  { return g_track; }
const char* lyrics_artist(void) { return g_artist; }
int         lyrics_count(void)   { return g_n_received; }

const char* lyrics_line(int i) {
    if (i < 0 || i >= (int)g_n_received) return nullptr;
    return g_line_text[i];
}

int lyrics_current_index(void) {
    uint32_t pos = playback_pos_ms();
    int idx = -1;
    for (int i = 0; i < (int)g_n_received; i++) {
        if (g_line_ms[i] <= pos) idx = i;
        else break;
    }
    return idx;
}

// --- Built-in demo (no BLE) -------------------------------------------------
// Real synced lyrics for Maroon 5 — "This Love" (from LRCLIB), fed through the
// same ingest path a BLE stream uses, then driven by a looping local clock.

void lyrics_load_demo(void) {
    struct { uint32_t ms; const char* text; } S[] = {
        {  20330, "I was so high, I did not recognize" },
        {  23980, "The fire burning in her eyes" },
        {  26560, "The chaos that controlled my mind" },
        {  30520, "Whispered goodbye as she got on a plane" },
        {  34170, "Never to return again but always in my heart, oh" },
        {  41020, "This love has taken its toll on me" },
        {  45360, "She said goodbye too many times before" },
        {  50900, "And her heart is breakin' in front of me" },
        {  55470, "And I have no choice" },
        {  57730, "'Cause I won't say goodbye anymore" },
        {  71190, "I tried my best to feed her appetite" },
        {  74530, "Keep her coming every night" },
        {  76930, "So hard to keep her satisfied, oh" },
        {  80870, "Kept playing love like it was just a game" },
        {  84320, "Pretending to feel the same" },
        {  86930, "Then turn around and leave again, but uh-oh" },
        {  91539, "This love has taken its toll on me" },
        {  95830, "She said goodbye too many times before" },
        { 101490, "And her heart is breakin' in front of me" },
        { 105990, "And I have no choice" },
        { 108289, "'Cause I won't say goodbye anymore" },
        { 121140, "I'll fix these broken things, repair your broken wings" },
        { 126440, "And make sure everything's all right" },
        { 131520, "My pressure on your hips, I'm sinking my fingertips" },
        { 136470, "Every inch of you" },
        { 138280, "Because I know that's what you want me to do" },
    };
    const int n = (int)(sizeof(S) / sizeof(S[0]));
    const uint32_t id = LYRICS_DEMO_ID;
    lyrics_ingest_header(id, n, "This Love", "Maroon 5");
    for (int i = 0; i < n; i++)
        lyrics_ingest_line(id, i, S[i].ms, S[i].text);
    // Looping local clock, starting mid-verse so the first frame lands on a
    // long line (wrap check).
    g_base_ms = 30000;
    g_base_millis = millis();
    g_playing = true;
    g_loop_ms = 206000;
    Serial.printf("lyrics: demo loaded (%d lines)\n", n);
}
