#ifndef DTT_STRINGS_H
#define DTT_STRINGS_H

#include "Arduino.h"
#define DOCS_URL "https://docs.researchanddesire.com"

constexpr char REPETITION_STRING PROGMEM[] = "repetition";
constexpr char ENDURANCE_STRING PROGMEM[] = "endurance";
constexpr char FREEFORM_STRING PROGMEM[] = "freeform";
constexpr char BOUNCE_STRING PROGMEM[] = "bounce";

constexpr char DEFAULT_ID PROGMEM[] = "_default";
constexpr char DEFAULT_SEGMENT_NAME PROGMEM[] = "Repetition";
constexpr char DEFAULT_SEGMENT_DIFFICULTY PROGMEM[] = "Easy";
constexpr char DEFAULT_SEGMENT_TYPE PROGMEM[] = "repetition";
constexpr char DEFAULT_SEGMENT_TARGET PROGMEM[] = "5";
constexpr char DEFAULT_SEGMENT_START_POSITION PROGMEM[] = "16";
constexpr char DEFAULT_SEGMENT_END_POSITION PROGMEM[] = "2";

constexpr char DEFAULT_TOY_NAME PROGMEM[] = "Starter Toy";
constexpr char DEFAULT_TOY_DESCRIPTION PROGMEM[] = "6 inch, pink";

constexpr char DEFAULT_SESSION_NAME PROGMEM[] = "Default Session";
constexpr char DEFAULT_SESSION_DESCRIPTION PROGMEM[] = "1 segment, 5 minutes";
constexpr char DEFAULT_SESSION_FINAL_TEXT PROGMEM[] = "Default Final Text";

constexpr char SESSION_HEADER PROGMEM[] = "SESSION";
constexpr char TOY_HEADER PROGMEM[] = "TOY";
constexpr char SEGMENT_HEADER PROGMEM[] = "SEGMENT";

constexpr char EMPTY_STRING PROGMEM[] = "";

// PAGES

constexpr char PAGE_WIFI_URL PROGMEM[] = "WIFI:T:WPA;S:Trainer Setup;P:;;";
constexpr char PAGE_WIFI_CONTENT PROGMEM[] = "Connect to\n'Trainer Setup'";
constexpr char PAGE_WIFI_RIGHT_FOOTER PROGMEM[] = "Restart";

constexpr char PAGE_UPDATING_HEADER PROGMEM[] = "Updating";
constexpr char PAGE_UPDATING_CONTENT PROGMEM[] =
    "Thanks for waiting! You're almost ready to play.";

constexpr char PAGE_PAIRING_URL PROGMEM[] = RAD_SERVER "/app/settings";
constexpr char PAGE_PAIRING_CONTENT PROGMEM[] =
    "Pair me for more settings and fun!";
constexpr char PAGE_PAIRING_RIGHT_FOOTER PROGMEM[] = "Skip";

constexpr char PAGE_PREFLIGHT_CONTENT PROGMEM[] = "Getting ready...";

constexpr char PAGE_FETCHING_CONTENT PROGMEM[] =
    "I'm getting your settings from the dashboard.";

constexpr char PAGE_OFFLINE_CONTENT PROGMEM[] =
    "You're offline. Using your last session - grades won't save until you "
    "reconnect.";

constexpr char PAGE_SETTINGS_STALE_CONTENT PROGMEM[] =
    "Couldn't refresh settings. Using your last session.";

constexpr char PAGE_BAD_HEALTH_CHECK_URL PROGMEM[] = DOCS_URL "/e-dtt-1";

constexpr char PAGE_BAD_HEALTH_CHECK_TITLE PROGMEM[] = "E-DTT-1";

constexpr char PAGE_BAD_HEALTH_CHECK_CONTENT PROGMEM[] =
    "No internet. Check firewall and router.";

constexpr char PAGE_FINAL_CONTENT PROGMEM[] =
    "Well done! You finished the session.";
constexpr char PAGE_FINAL_RIGHT_FOOTER PROGMEM[] = "Play Again";

constexpr char NEXT PROGMEM[] = "Next";
constexpr char SKIP PROGMEM[] = "Skip";
constexpr char HOLD PROGMEM[] = "Hold";
constexpr char WIFI PROGMEM[] = "Wi-Fi";
constexpr char SLASH PROGMEM[] = " / ";
constexpr char CONTROLLER_CONNECTED PROGMEM[] = "Connected";
constexpr char SPACE PROGMEM[] = " ";
constexpr char PLAY PROGMEM[] = "PLAY!";

constexpr char OK_BUTTON PROGMEM[] = "OK";
constexpr char NEXT_HOLD_PLAY PROGMEM[] = "NEXT / HOLD PLAY";

constexpr char ERROR_MESSAGE PROGMEM[] = "Segment is nullptr";
constexpr char ERROR_HEADER PROGMEM[] = "ERROR";
constexpr char ERROR_RIGHT_FOOTER PROGMEM[] = "RESET";

constexpr char TRAINER_ID_LABEL PROGMEM[] = "Trainer ID";

constexpr char ERROR_SPEED_TOO_HIGH PROGMEM[] = "Speed too high.";
constexpr char ERROR_SPEED_TOO_LOW PROGMEM[] = "Speed too low.";
constexpr char ERROR_INVALID_RANGE PROGMEM[] = "Invalid Range";
constexpr char ERROR_WINDOW_TOO_SMALL PROGMEM[] = "Small window.";

constexpr char GRADE_100 PROGMEM[] = "PERFECT!";
constexpr char GRADE_90 PROGMEM[] = "Great job! Gold star!";
constexpr char GRADE_80 PROGMEM[] = "Ribbit! Froggy proud!";
constexpr char GRADE_70 PROGMEM[] = "So cool, well done!";
constexpr char GRADE_69 PROGMEM[] = "Nice.";
constexpr char GRADE_60 PROGMEM[] = "You're doing great";
constexpr char GRADE_50 PROGMEM[] = "Keep hopping!";
constexpr char GRADE_40 PROGMEM[] = "Arrgh! Try again!";
constexpr char GRADE_30 PROGMEM[] = "Boo! Ghostly effort!";
constexpr char GRADE_20 PROGMEM[] = "Bombing out is not fun";
constexpr char GRADE_0 PROGMEM[] = "Oh poop! Next time";

constexpr char STARTING_IN_3 PROGMEM[] = "Starting in 3...";
constexpr char STARTING_IN_2 PROGMEM[] = "Starting in 2...";
constexpr char STARTING_IN_1 PROGMEM[] = "Starting in 1...";
constexpr char STARTING_IN_0 PROGMEM[] = "Good Luck!";

constexpr char REPETITIONS_SHORT PROGMEM[] = "reps";
constexpr char SECONDS_SHORT PROGMEM[] = "s";
constexpr char RPM_SHORT PROGMEM[] = "RPM";

// Pass/Fail strings
constexpr char FAILED_HEADER PROGMEM[] = "Failed";
constexpr char FAILED_DEFAULT_TEXT PROGMEM[] = "Try again!";
constexpr char FAILED_ATTEMPT_PREFIX PROGMEM[] = "Attempt ";
constexpr char FAILED_ATTEMPT_SUFFIX PROGMEM[] = "/3";
constexpr char FAILED_PRESS_TO_RETRY PROGMEM[] = "Press to retry";
constexpr char THREE_STRIKES_HEADER PROGMEM[] = "YOU FAIL";
constexpr char THREE_STRIKES_CONTENT PROGMEM[] = "3 failed attempts";
constexpr char THREE_STRIKES_FOOTER PROGMEM[] = "Restarting...";

#endif