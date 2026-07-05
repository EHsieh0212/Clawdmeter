#pragma once
#include "data.h"
#include "ble.h"

// Tap cycles in this order (boot lands on the first): the Spotify lyrics page,
// the usage dashboard, then the Claude pixel-art animation, and back around.
enum screen_t {
    SCREEN_LYRICS,
    SCREEN_USAGE,
    SCREEN_SPLASH,
    SCREEN_COUNT,
};

void ui_init(void);
void ui_update(const UsageData* data);
void ui_tick_anim(void);
void ui_show_screen(screen_t screen);
void ui_toggle_splash(void);
screen_t ui_get_current_screen(void);
void ui_update_ble_status(ble_state_t state, const char* name, const char* mac);
void ui_update_battery(int percent, bool charging);
