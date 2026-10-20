#ifndef WM_CONSTS_H
#define WM_CONSTS_H

#include "Arduino.h"
#include "WiFi.h"

// -----------------------------------------------------------------------------------------------
// TOKENS

const char WM_VERSION_STR[] PROGMEM = "v2.0.17";

static const char _wifi_token[] PROGMEM = "wifi";
static PGM_P _menutokens[] PROGMEM = {_wifi_token};
const uint8_t _nummenutokens = (sizeof(_menutokens) / sizeof(PGM_P));

// Routes
const char R_root[] PROGMEM = "/";
const char R_wifi[] PROGMEM = "/wifi";
const char R_wifisave[] PROGMEM = "/wifisave";

// Classes
const char C_root[] PROGMEM = "home";
const char C_wifi[] PROGMEM = "wifi";

// Strings
const char S_ip[] PROGMEM = "ip";
const char S_gw[] PROGMEM = "gw";
const char S_sn[] PROGMEM = "sn";
const char S_dns[] PROGMEM = "dns";

// Tokens
//@todo consolidate and reduce
const char T_ss[] PROGMEM = "{";   // token start sentinel
const char T_es[] PROGMEM = "}";   // token end sentinel
const char T_1[] PROGMEM = "{1}";  // @token 1
const char T_2[] PROGMEM = "{2}";  // @token 2
const char T_3[] PROGMEM = "{3}";  // @token 2
const char T_v[] PROGMEM = "{v}";  // @token v
const char T_V[] PROGMEM = "{V}";  // @token v
const char T_I[] PROGMEM = "{I}";  // @token I
const char T_i[] PROGMEM = "{i}";  // @token i
const char T_n[] PROGMEM = "{n}";  // @token n
const char T_p[] PROGMEM = "{p}";  // @token p
const char T_t[] PROGMEM = "{t}";  // @token t
const char T_l[] PROGMEM = "{l}";  // @token l
const char T_c[] PROGMEM = "{c}";  // @token c
const char T_e[] PROGMEM = "{e}";  // @token e
const char T_q[] PROGMEM = "{q}";  // @token q
const char T_r[] PROGMEM = "{r}";  // @token r
const char T_R[] PROGMEM = "{R}";  // @token R
const char T_h[] PROGMEM = "{h}";  // @token h

// http
const char HTTP_HEAD_CT[] PROGMEM = "text/html";
const char HTTP_HEAD_CT2[] PROGMEM = "text/plain";
const char HTTP_HEAD_CORS[] PROGMEM = "Access-Control-Allow-Origin";
const char HTTP_HEAD_CORS_ALLOW_ALL[] PROGMEM = "*";

const char* const WIFI_STA_STATUS[] PROGMEM{
    "WL_IDLE_STATUS",      // 0 STATION_IDLE
    "WL_NO_SSID_AVAIL",    // 1 STATION_NO_AP_FOUND
    "WL_SCAN_COMPLETED",   // 2
    "WL_CONNECTED",        // 3 STATION_GOT_IP
    "WL_CONNECT_FAILED",   // 4 STATION_CONNECT_FAIL, STATION_WRONG_PASSWORD(NI)
    "WL_CONNECTION_LOST",  // 5
    "WL_DISCONNECTED",     // 6
    "WL_STATION_WRONG_PASSWORD"  // 7 KLUDGE
};

const char* const AUTH_MODE_NAMES[] PROGMEM{
    "OPEN", "WEP", "WPA_PSK", "WPA2_PSK", "WPA_WPA2_PSK", "WPA2_ENTERPRISE",
    "MAX"};

const char* const WIFI_MODES[] PROGMEM = {"NULL", "STA", "AP", "STA+AP"};

#endif