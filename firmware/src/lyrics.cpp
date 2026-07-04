#include "lyrics.h"
#include <Arduino.h>

// ---------------------------------------------------------------------------
// Phase 1: hard-coded sample track + fake playback clock.
//
// Real synced lyrics for Maroon 5 — "This Love" (from LRCLIB), so the layout is
// exercised against genuine line lengths and timing. Phase 2 replaces the block
// below with lyrics reassembled from BLE chunks; nothing else in this file's
// public surface changes.
// ---------------------------------------------------------------------------

static const char* SAMPLE_TRACK  = "This Love";
static const char* SAMPLE_ARTIST = "Maroon 5";

static const LyricLine SAMPLE_LINES[] = {
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
    {  62360, "Whoa" },
    {  64660, "Whoa" },
    {  67210, "Whoa" },
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
    { 142100, "This love has taken its toll on me" },
    { 146340, "She said goodbye too many times before" },
    { 152100, "Her heart is breakin' in front of me" },
    { 156570, "And I have no choice" },
    { 158660, "'Cause I won't say goodbye anymore" },
    { 182630, "This love has taken its toll on me" },
    { 186900, "She said goodbye too many times before" },
    { 192320, "And her heart is breakin' in front of me" },
    { 196930, "And I have no choice" },
    { 198940, "'Cause I won't say goodbye anymore" },
};
#define SAMPLE_COUNT ((int)(sizeof(SAMPLE_LINES) / sizeof(SAMPLE_LINES[0])))
#define SAMPLE_DURATION_MS 206000u

// Playback position, interpolated locally. In Phase 1 `base_ms`/`base_millis`
// are seeded once and advanced purely from millis(); in Phase 2 they are
// refreshed by every `lp` position message from the host.
static uint32_t base_ms     = 0;
static uint32_t base_millis = 0;
static bool     playing     = true;

// Where the fake clock starts, so the very first screenshot lands mid-verse on
// a long line (good for checking wrap) rather than on the pre-intro silence.
#define FAKE_START_MS 30000u

void lyrics_init(void) {
    base_ms     = FAKE_START_MS;
    base_millis = millis();
    playing     = true;
}

void lyrics_tick(void) {
    // Phase 1: nothing to do — position is derived on read from millis().
    // Phase 2 will consume queued `lp` messages here to refresh base_ms.
}

static uint32_t playback_pos_ms(void) {
    uint32_t pos = base_ms;
    if (playing) pos += (millis() - base_millis);
    // Loop the sample so the demo keeps scrolling.
    if (SAMPLE_DURATION_MS) pos %= SAMPLE_DURATION_MS;
    return pos;
}

bool lyrics_available(void) {
    return SAMPLE_COUNT > 0;
}

bool lyrics_is_playing(void) {
    return playing;
}

const char* lyrics_track(void)  { return SAMPLE_TRACK; }
const char* lyrics_artist(void) { return SAMPLE_ARTIST; }
int         lyrics_count(void)   { return SAMPLE_COUNT; }

const char* lyrics_line(int i) {
    if (i < 0 || i >= SAMPLE_COUNT) return nullptr;
    return SAMPLE_LINES[i].text;
}

int lyrics_current_index(void) {
    uint32_t pos = playback_pos_ms();
    int idx = -1;
    for (int i = 0; i < SAMPLE_COUNT; i++) {
        if (SAMPLE_LINES[i].ms <= pos) idx = i;
        else break;
    }
    return idx;
}
