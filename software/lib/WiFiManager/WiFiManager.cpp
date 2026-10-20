/**
 * WiFiManager.cpp
 *
 * WiFiManager, a library for the ESP8266/Arduino platform
 * for configuration of WiFi credentials using a Captive Portal
 *
 * @author Creator tzapu
 * @author tablatronix
 * @version 0.0.0
 * @license MIT
 */

#include "WiFiManager.h"

#if defined(ESP8266) || defined(ESP32)

#ifdef ESP32
uint8_t WiFiManager::_lastconxresulttmp = WL_IDLE_STATUS;
#endif

/**
 * --------------------------------------------------------------------------------
 *  WiFiManager
 * --------------------------------------------------------------------------------
 **/

// constructors

WiFiManager::WiFiManager() { WiFiManagerInit(); }

void WiFiManager::WiFiManagerInit() { setMenu(_menuIdsDefault); }

// destructor
WiFiManager::~WiFiManager() {
    _end();

#ifdef ESP32
    WiFi.removeEvent(wm_event_id);
#endif
}

void WiFiManager::_begin() {
    if (_hasBegun) return;
    _hasBegun = true;
    // _usermode = WiFi.getMode();

#ifndef ESP32
    WiFi.persistent(false);  // disable persistent so scannetworks and mode
                             // switching do not cause overwrites
#endif
}

void WiFiManager::_end() {
    _hasBegun = false;
    if (_userpersistent)
        WiFi.persistent(true);  // reenable persistent, there is no getter we
                                // rely on _userpersistent
    // if(_usermode != WIFI_OFF) WiFi.mode(_usermode);
}

// AUTOCONNECT

boolean WiFiManager::autoConnect() {
    String ssid = getDefaultAPName();
    return autoConnect(ssid.c_str(), nullptr);
}

/**
 * [autoConnect description]
 * @access public
 * @param  {[type]} char const         *apName     [description]
 * @param  {[type]} char const         *apPassword [description]
 * @return {[type]}      [description]
 */
boolean WiFiManager::autoConnect(char const* apName, char const* apPassword) {
    // bool wifiIsSaved = getWiFiIsSaved();

    setupHostname(true);

    if (_hostname != "") {
        // disable wifi if already on
        if (WiFi.getMode() & WIFI_STA) {
            WiFi.mode(WIFI_OFF);
            int timeout = millis() + 1200;
            // async loop for mode change
            while (WiFi.getMode() != WIFI_OFF && millis() < timeout) {
                delay(0);
            }
        }
    }

    // check if wifi is saved, (has autoconnect) to speed up cp start
    // NOT wifi init safe
    _startconn = millis();
    _begin();

    // attempt to connect using saved settings, on fail fallback to AP
    // config portal
    if (!WiFi.enableSTA(true)) {
        // handle failure mode Brownout detector etc.

        return false;
    }

    WiFiSetCountry();

    if (esp32persistent)
        WiFi.persistent(false);  // disable persistent for esp32 after
                                 // esp_wifi_start or else saves wont work

    _usermode = WIFI_STA;  // When using autoconnect , assume the user wants
                           // sta mode on permanently.

    // no getter for autoreconnectpolicy before this
    // https://github.com/esp8266/Arduino/pull/4359
    // so we must force it on else, if not connectimeout then
    // waitforconnectionresult gets stuck endless loop
    WiFi_autoReconnect();

#ifdef ESP8266
    if (_hostname != "") {
        setupHostname(true);
    }
#endif

    // if already connected, or try stored connect
    // @note @todo ESP32 has no autoconnect, so connectwifi will always be
    // called unless user called begin etc before
    // @todo check if correct ssid == saved ssid when already connected
    bool connected = false;
    if (WiFi.status() == WL_CONNECTED) {
        connected = true;

        setSTAConfig();
        // @todo not sure if this is safe, causes dup setSTAConfig in
        // connectwifi, and we have no idea WHAT we are connected to
    }

    if (connected || connectWifi(_defaultssid, _defaultpass) == WL_CONNECTED) {
        _lastconxresult = WL_CONNECTED;

        if (_hostname != "") {
        }
        return true;  // connected success
    }

    // possibly skip the config portal
    if (!_enableConfigPortal) {
        return false;  // not connected and not cp
    }

    // not connected start configportal
    return startConfigPortal(apName, apPassword);
}

bool WiFiManager::setupHostname(bool restart) {
    if (_hostname == "") {
        return false;
    }
    bool res;
#ifdef ESP8266

    res = WiFi.hostname(_hostname.c_str());
// #ifdef ESP8266MDNS_H
#ifdef WM_MDNS

    if (MDNS.begin(_hostname.c_str())) {
        MDNS.addService("http", "tcp", 80);
    }
#endif
#elif defined(ESP32)
    // @note hostname must be set after STA_START
    // @note, this may have changed at some point, now it wont work, I have to
    // set it before. same for S2, must set it before mode(STA) now

    res = WiFi.setHostname(_hostname.c_str());
    // esp_err_t err;
    //   // err = set_esp_interface_hostname(ESP_IF_WIFI_STA, "TEST_HOSTNAME");
    //   err = esp_netif_set_hostname(esp_netifs[ESP_IF_WIFI_STA],
    //   "TEST_HOSTNAME");
    //     if(err){
    //         log_e("Could not set hostname! %d", err);
    //         return false;
    //     }
    // #ifdef ESP32MDNS_H
#ifdef WM_MDNS

    if (MDNS.begin(_hostname.c_str())) {
        MDNS.addService("http", "tcp", 80);
    }
#endif
#endif

    if (restart && (WiFi.status() == WL_CONNECTED)) {
        // WiFi.reconnect(); // This does not reset dhcp
        WiFi_Disconnect();
        delay(200);  // do not remove, need a delay for disconnect to change
                     // status()
    }

    return res;
}

// CONFIG PORTAL
bool WiFiManager::startAP() const {
    bool ret = true;

#ifdef ESP8266
    // @bug workaround for bug #4372
    // https://github.com/esp8266/Arduino/issues/4372
    if (!WiFi.enableAP(true)) {
        return false;
    }
    delay(500);  // workaround delay
#endif

    // setup optional soft AP static ip config
    if (_ap_static_ip) {
        if (!WiFi.softAPConfig(_ap_static_ip, _ap_static_gw, _ap_static_sn)) {
        }
    }

    //@todo add callback here if needed to modify ap but cannot use
    // setAPStaticIPConfig
    //@todo rework wifi channelsync as it will work unpredictably when not
    // connected in sta

    int32_t channel = 0;
    if (_channelSync)
        channel = WiFi.channel();
    else
        channel = _apChannel;

    if (channel > 0) {
    }

    // start soft AP with password or anonymous
    // default channel is 1 here and in esplib, @todo just change to default
    // remove conditionals
    if (_apPassword != "") {
        if (channel > 0) {
            ret = WiFi.softAP(_apName.c_str(), _apPassword.c_str(), channel,
                              _apHidden);
        } else {
            ret = WiFi.softAP(_apName.c_str(), _apPassword.c_str(), 1,
                              _apHidden);  // password option
        }
    } else {
        if (channel > 0) {
            ret = WiFi.softAP(_apName.c_str(), "", channel, _apHidden);
        } else {
            ret = WiFi.softAP(_apName.c_str(), "", 1, _apHidden);
        }
    }

    // @todo add softAP retry here to dela with unknown failures

    delay(500);  // slight delay to make sure we get an AP IP

    return ret;
}

/**
 * [startWebPortal description]
 * @access public
 * @return {[type]} [description]
 */
void WiFiManager::startWebPortal() {
    if (configPortalActive || webPortalActive) return;
    connect = abort = false;
    setupConfigPortal();
    webPortalActive = true;
}

/**
 * [stopWebPortal description]
 * @access public
 * @return {[type]} [description]
 */
void WiFiManager::stopWebPortal() {
    if (!configPortalActive && !webPortalActive) return;

    webPortalActive = false;
    shutdownConfigPortal();
}

boolean WiFiManager::configPortalHasTimeout() {
    if (!configPortalActive) return false;
    uint16_t logintvl = 30000;  // how often to emit timeing out counter logging

    // handle timeout portal client check
    if (_configPortalTimeout == 0 ||
        (_apClientCheck && (WiFi_softap_num_stations() > 0))) {
        // debug num clients every 30s
        if (millis() - timer > logintvl) {
            timer = millis();
        }
        _configPortalStart =
            millis();  // kludge, bump configportal start time to skew timeouts
        return false;
    }

    // handle timeout webclient check
    if (_webClientCheck && (_webPortalAccessed > _configPortalStart) > 0)
        _configPortalStart = _webPortalAccessed;

    // handle timed out
    if (millis() > _configPortalStart + _configPortalTimeout) {
        return true;  // timeout bail, else do debug logging
    }
    if (_debug && _debugLevel > 0) {
        // log timeout time remaining every 30s
        if ((millis() - timer) > logintvl) {
            timer = millis();
        }
    }

    return false;
}

void WiFiManager::setupHTTPServer() {
    if (_httpPort != 80) {
    }

    server.reset(new WM_WebServer(_httpPort));

    // G macro workaround for Uri() bug
    // https://github.com/esp8266/Arduino/issues/7102
    server->on(WM_G(R_root), std::bind(&WiFiManager::handleRoot, this));
    server->on(WM_G(R_wifi), std::bind(&WiFiManager::handleWifi, this, true));
    server->on(WM_G(R_wifisave), std::bind(&WiFiManager::handleWifiSave, this));
    server->onNotFound(std::bind(&WiFiManager::handleNotFound, this));

    server->begin();  // Web server start
}

void WiFiManager::setupDNSD() {
    dnsServer.reset(new DNSServer());

    /* Setup the DNS server redirecting all the domains to the apIP */
    dnsServer->setErrorReplyCode(DNSReplyCode::NoError);

    dnsServer->start(DNS_PORT, F("*"), WiFi.softAPIP());
}

void WiFiManager::setupConfigPortal() {
    setupHTTPServer();
    _lastscan = 0;  // reset network scan cache
    if (_preloadwifiscan)
        WiFi_scanNetworks(true, true);  // preload wifiscan , async
}

boolean WiFiManager::startConfigPortal() {
    String ssid = getDefaultAPName();
    return startConfigPortal(ssid.c_str(), nullptr);
}

/**
 * [startConfigPortal description]
 * @access public
 * @param  {[type]} char const         *apName     [description]
 * @param  {[type]} char const         *apPassword [description]
 * @return {[type]}      [description]
 */
boolean WiFiManager::startConfigPortal(char const* apName,
                                       char const* apPassword) {
    _begin();

    if (configPortalActive) {
        return false;
    }

    // setup AP
    _apName = apName;  // @todo check valid apname ?
    _apPassword = apPassword;

    if (_apName == "") _apName = getDefaultAPName();

    if (!validApPassword()) return false;

    // HANDLE issues with STA connections, shutdown sta if not connected, or
    // else this will hang channel scanning and softap will not respond
    if (_disableSTA || (!WiFi.isConnected() && _disableSTAConn)) {
// this fixes most ap problems, however, simply doing mode(WIFI_AP) does not
// work if sta connection is hanging, must `wifi_station_disconnect`
#ifdef WM_DISCONWORKAROUND
        WiFi.mode(WIFI_AP_STA);
#endif
        WiFi_Disconnect();
        WiFi_enableSTA(false);

    } else {
        // WiFi_enableSTA(true);
    }

    // init configportal globals to known states
    configPortalActive = true;
    bool result = connect = abort =
        false;  // loop flags, connect true success, abort true break

    _configPortalStart = millis();

    // start access point

    startAP();
    WiFiSetCountry();

    // init configportal

    setupConfigPortal();

    setupDNSD();

    return result;  // skip blocking loop
}

/**
 * [process description]
 * @access public
 * @return bool connected
 */
boolean WiFiManager::process() {
    if (webPortalActive || (configPortalActive && !_configPortalIsBlocking)) {
        // if timed out or abort, break
        if (configPortalHasTimeout() || abort) {
            webPortalActive = false;
            shutdownConfigPortal();

            return false;
        }

        uint8_t state =
            processConfigPortal();  // state is WL_IDLE or WL_CONNECTED/FAILED
        return state == WL_CONNECTED;
    }
    return false;
}

/**
 * [processConfigPortal description]
 * using esp wl_status enums as returns for now, should be fine
 * returns WL_IDLE_STATUS or WL_CONNECTED/WL_CONNECT_FAILED upon connect/save
 * flag
 *
 * @return {[type]} [description]
 */
uint8_t WiFiManager::processConfigPortal() {
    if (configPortalActive) {
        // DNS handler
        dnsServer->processNextRequest();
    }

    // HTTP handler
    server->handleClient();

    // Waiting for save...
    if (connect) {
        connect = false;

        if (_enableCaptivePortal)
            delay(_cpclosedelay);  // keeps the captiveportal from closing to
                                   // fast.

        // skip wifi if no ssid
        if (_ssid == "") {
        } else {
            // attempt sta connection to submitted _ssid, _pass
            uint8_t res =
                connectWifi(_ssid, _pass, _connectonsave) == WL_CONNECTED;
            if (res || (!_connectonsave)) {
                if (_savewificallback != nullptr) {
                    _savewificallback();  // @CALLBACK
                }
                if (!_connectonsave) return WL_IDLE_STATUS;
                if (_disableConfigPortal) shutdownConfigPortal();
                return WL_CONNECTED;  // CONNECT SUCCESS
            }
        }

        if (_shouldBreakAfterConfig) {
            // do save callback
            // @todo this is more of an exiting callback than a save, clarify
            // when this should actually occur confirm or verify data was saved
            // to make this more accurate callback
            if (_savewificallback != nullptr) {
                _savewificallback();  // @CALLBACK
            }
            if (_disableConfigPortal) shutdownConfigPortal();
            return WL_CONNECT_FAILED;  // CONNECT FAIL
        }
    }

    return WL_IDLE_STATUS;
}

/**
 * [shutdownConfigPortal description]
 * @access public
 * @return bool success (softapdisconnect)
 */
bool WiFiManager::shutdownConfigPortal() {
    if (webPortalActive) return false;

    if (configPortalActive) {
        // DNS handler
        dnsServer->processNextRequest();
    }

    // HTTP handler
    server->handleClient();

    // @todo what is the proper way to shutdown and free the server up
    // debug - many open issues aobut port not clearing for use with other
    // servers
    server->stop();
    server.reset();

    WiFi.scanDelete();  // free wifi scan results

    if (!configPortalActive) return false;

    dnsServer->stop();  //  free heap ?
    dnsServer.reset();

    // turn off AP
    // @todo bug workaround
    // https://github.com/esp8266/Arduino/issues/3793
    // [APdisconnect] set_config failed! *WM: disconnect configportal -
    // softAPdisconnect failed still no way to reproduce reliably

    bool ret = false;
    ret = WiFi.softAPdisconnect(false);

    delay(1000);
    WiFi_Mode(_usermode);  // restore users wifi mode, BUG
                           // https://github.com/esp8266/Arduino/issues/4372
    if (WiFi.status() == WL_IDLE_STATUS) {
        WiFi.reconnect();  // restart wifi since we disconnected it in
                           // startconfigportal
    }

    configPortalActive = false;
    _end();
    return ret;
}

// @todo refactor this up into seperate functions
// one for connecting to flash , one for new client
// clean up, flow is convoluted, and causes bugs
uint8_t WiFiManager::connectWifi(const String& ssid, const String& pass,
                                 bool connect) {
    uint8_t retry = 1;
    uint8_t connRes = WL_NO_SSID_AVAIL;

    setSTAConfig();
    //@todo catch failures in set_config

    // make sure sta is on before `begin` so it does not call enablesta->mode
    // while persistent is ON ( which would save WM AP state to eeprom !)
    // WiFi.setAutoReconnect(false);
    if (_cleanConnect)
        WiFi_Disconnect();  // disconnect before begin, in case anything is
                            // hung, this causes a 2 seconds delay for connect
    // @todo find out what status is when this is needed, can we detect it and
    // handle it, say in between states or idle_status to avoid these

    // if retry without delay (via begin()), the IDF is still busy even after
    // returning status E (5130) wifi:sta is connecting, return error
    // [E][WiFiSTA.cpp:221] begin(): connect failed!

    while (retry <= _connectRetries && (connRes != WL_CONNECTED)) {
        if (_connectRetries > 1) {
            if (_aggresiveReconn) delay(1000);  // add idle time before recon
        }
        // if ssid argument provided connect to that
        // NOTE: this also catches preload() _defaultssid @todo rework
        if (ssid != "") {
            wifiConnectNew(ssid, pass, connect);
            // @todo connect=false seems to disconnect sta in begin() so not
            // sure if _connectonsave is useful at all skip wait if not
            // connecting if(connect){
            if (_saveTimeout > 0) {
                connRes = waitForConnectResult(
                    _saveTimeout);  // use default save timeout for saves to
                                    // prevent bugs in esp->waitforconnectresult
                                    // loop
            } else {
                connRes = waitForConnectResult();
            }
            // }
        } else {
            // connect using saved ssid if there is one
            if (WiFi_hasAutoConnect()) {
                wifiConnectDefault();
                connRes = waitForConnectResult();
            } else {
            }
        }

        retry++;
    }

// WPS enabled? https://github.com/esp8266/Arduino/pull/4889
#ifdef NO_EXTRA_4K_HEAP
    // do WPS, if WPS options enabled and not connected and no password was
    // supplied
    // @todo this seems like wrong place for this, is it a fallback or option?
    if (_tryWPS && connRes != WL_CONNECTED && pass == "") {
        startWPS();
        // should be connected at the end of WPS
        connRes = waitForConnectResult();
    }
#endif

    if (connRes != WL_SCAN_COMPLETED) {
        updateConxResult(connRes);
    }

    return connRes;
}

/**
 * connect to a new wifi ap
 * @since $dev
 * @param  String ssid
 * @param  String pass
 * @return bool success
 * @return connect only save if false
 */
bool WiFiManager::wifiConnectNew(const String& ssid, const String& pass,
                                 bool connect) {
    bool ret = false;

    WiFi_enableSTA(
        true, storeSTAmode);  // storeSTAmode will also toggle STA on in default
                              // opmode (persistent) if true (default)
    WiFi.persistent(true);
    ret = WiFi.begin(ssid.c_str(), pass.c_str(), 0, nullptr, connect);
    WiFi.persistent(false);

    return ret;
}

/**
 * connect to stored wifi
 * @since dev
 * @return bool success
 */
bool WiFiManager::wifiConnectDefault() {
    bool ret = false;

    ret = WiFi_enableSTA(true, storeSTAmode);
    delay(500);  // THIS DELAY ?

    ret = WiFi.begin();

    return ret;
}

/**
 * set sta config if set
 * @since $dev
 * @return bool success
 */
bool WiFiManager::setSTAConfig() {
    bool ret = true;
    if (_sta_static_ip) {
        if (_sta_static_dns) {
            ret = WiFi.config(_sta_static_ip, _sta_static_gw, _sta_static_sn,
                              _sta_static_dns);
        } else {
            ret = WiFi.config(_sta_static_ip, _sta_static_gw, _sta_static_sn);
        }

    } else {
    }
    return ret;
}

// @todo change to getLastFailureReason and do not touch conxresult
void WiFiManager::updateConxResult(uint8_t status) {
    // hack in wrong password detection
    _lastconxresult = status;
    if (_lastconxresult == WL_CONNECT_FAILED ||
        _lastconxresult == WL_DISCONNECTED) {
        if (_lastconxresulttmp != WL_IDLE_STATUS) {
            _lastconxresult = _lastconxresulttmp;
        }
    }
}

uint8_t WiFiManager::waitForConnectResult() {
    return waitForConnectResult(_connectTimeout);
}

/**
 * waitForConnectResult
 * @param  uint16_t timeout  in seconds
 * @return uint8_t  WL Status
 */
uint8_t WiFiManager::waitForConnectResult(uint32_t timeout) {
    if (timeout == 0) {
        return WiFi.waitForConnectResult();
    }

    unsigned long timeoutmillis = millis() + timeout;

    uint8_t status = WiFi.status();

    while (millis() < timeoutmillis) {
        status = WiFi.status();
        // @todo detect additional states, connect happens, then dhcp then get
        // ip, there is some delay here, make sure not to timeout if waiting on
        // IP
        if (status == WL_CONNECTED || status == WL_CONNECT_FAILED) {
            return status;
        }

        delay(100);
    }
    return status;
}

// WPS enabled? https://github.com/esp8266/Arduino/pull/4889
#ifdef NO_EXTRA_4K_HEAP
void WiFiManager::startWPS() {
#ifdef ESP8266
    WiFi.beginWPSConfig();
#else
    // @todo
#endif
}
#endif

String WiFiManager::getHTTPHead(const String& title) {
    String page;
    page += FPSTR(HTTP_HEAD_START);
    page.replace(FPSTR(T_v), title);
    page += FPSTR(HTTP_SCRIPT);
    page += FPSTR(HTTP_STYLE);

    if (_bodyClass != "") {
        String p = FPSTR(HTTP_HEAD_END);
        p.replace(FPSTR(T_c), _bodyClass);  // add class str
        page += p;
    } else {
        page += FPSTR(HTTP_HEAD_END);
    }

    return page;
}

void WiFiManager::HTTPSend(const String& content) {
    server->send(200, FPSTR(HTTP_HEAD_CT), content);
}

/**
 * HTTPD handler for page requests
 */
void WiFiManager::handleRequest() { _webPortalAccessed = millis(); }

/**
 * HTTPD CALLBACK root or redirect to captive portal
 */
void WiFiManager::handleRoot() {
    if (captivePortal())
        return;  // If captive portal redirect instead of displaying the page
    handleRequest();
    String page =
        getHTTPHead(_title);  // @token options @todo replace options with title
    String str = FPSTR(HTTP_ROOT_MAIN);  // @todo custom title
    str.replace(FPSTR(T_t), _title);
    str.replace(
        FPSTR(T_v),
        configPortalActive
            ? _apName
            : (getWiFiHostname() + " - " +
               WiFi.localIP().toString()));  // use ip if ap is not active for
                                             // heading @todo use hostname?
    page += str;
    page += getMenuOut();
    reportStatus(page);
    page += FPSTR(HTTP_END);

    HTTPSend(page);
    if (_preloadwifiscan)
        WiFi_scanNetworks(_scancachetime,
                          true);  // preload wifiscan throttled, async
    // @todo buggy, captive portals make a query on every page load, causing
    // this to run every time in addition to the real page load I dont
    // understand why, when you are already in the captive portal, I guess they
    // want to know that its still up and not done or gone if we can detect
    // these and ignore them that would be great, since they come from the
    // captive portal redirect maybe there is a refferer
}

/**
 * HTTPD CALLBACK Wifi config page handler
 */
void WiFiManager::handleWifi(boolean scan) {
    handleRequest();
    String page = getHTTPHead(FPSTR(S_titlewifi));  // @token titlewifi
    if (scan) {
        WiFi_scanNetworks(server->hasArg(F("refresh")),
                          false);  // wifiscan, force if arg refresh
        page += getScanItemOut();
    }
    String pitem = "";

    pitem = FPSTR(HTTP_FORM_START);
    pitem.replace(FPSTR(T_v), F("wifisave"));  // set form action
    page += pitem;

    pitem = FPSTR(HTTP_FORM_WIFI);
    pitem.replace(FPSTR(T_v), WiFi_SSID());

    if (_showPassword) {
        pitem.replace(FPSTR(T_p), WiFi_psk());
    } else if (WiFi_psk() != "") {
        pitem.replace(FPSTR(T_p), FPSTR(S_passph));
    } else {
        pitem.replace(FPSTR(T_p), "");
    }

    page += pitem;

    page += getStaticOut();
    page += FPSTR(HTTP_FORM_WIFI_END);
    page += FPSTR(HTTP_FORM_END);
    page += FPSTR(HTTP_SCAN_LINK);
    reportStatus(page);
    page += FPSTR(HTTP_END);

    HTTPSend(page);
}

String WiFiManager::getMenuOut() {
    String page;

    for (auto menuId : _menuIds) {
        page += HTTP_PORTAL_MENU[menuId];
        delay(0);
    }

    return page;
}

// // is it possible in softap mode to detect aps without scanning
// bool WiFiManager::WiFi_scanNetworksForAP(bool force){
//   WiFi_scanNetworks(force);
// }

void WiFiManager::WiFi_scanComplete(int networksFound) {
    _lastscan = millis();
    _numNetworks = networksFound;
}

bool WiFiManager::WiFi_scanNetworks() {
    return WiFi_scanNetworks(false, false);
}

bool WiFiManager::WiFi_scanNetworks(unsigned int cachetime, bool async) {
    return WiFi_scanNetworks(millis() - _lastscan > cachetime, async);
}
bool WiFiManager::WiFi_scanNetworks(unsigned int cachetime) {
    return WiFi_scanNetworks(millis() - _lastscan > cachetime, false);
}
bool WiFiManager::WiFi_scanNetworks(bool force, bool async) {
    // if 0 networks, rescan @note this was a kludge, now disabling to test real
    // cause ( maybe wifi not init etc) enable only if preload failed?
    if (_numNetworks == 0 && _autoforcerescan) {
        force = true;
    }

    // if scan is empty or stale (last scantime > _scancachetime), this avoids
    // fast reloading wifi page and constant scan delayed page loads appearing
    // to freeze.
    if (!_lastscan ||
        (_lastscan > 0 && (millis() - _lastscan > _scancachetime))) {
        force = true;
    }

    if (force) {
        int8_t res;
        _startscan = millis();
        if (async && _asyncScan) {
#ifdef ESP8266
#ifndef WM_NOASYNC  // no async available < 2.4.0

            using namespace std::placeholders;  // for `_1`
            WiFi.scanNetworksAsync(
                std::bind(&WiFiManager::WiFi_scanComplete, this, _1));
#else
            res = WiFi.scanNetworks();
#endif
#else

            res = WiFi.scanNetworks(true);
#endif
            return false;
        }
        res = WiFi.scanNetworks();
        if (res == WIFI_SCAN_FAILED) {
        } else if (res == WIFI_SCAN_RUNNING) {
            while (WiFi.scanComplete() == WIFI_SCAN_RUNNING) {
                delay(100);
            }
            _numNetworks = WiFi.scanComplete();
        } else if (res >= 0)
            _numNetworks = res;
        _lastscan = millis();

        return true;
    }
    return false;
}

String WiFiManager::WiFiManager::getScanItemOut() {
    String page;

    if (!_numNetworks)
        WiFi_scanNetworks();  // scan in case this gets called before any scans

    int n = _numNetworks;
    if (n == 0) {
        page += FPSTR(S_nonetworks);  // @token nonetworks
        page += F("<br/><br/>");
    } else {
        // sort networks
        int indices[n];
        for (int i = 0; i < n; i++) {
            indices[i] = i;
        }

        // RSSI SORT
        for (int i = 0; i < n; i++) {
            for (int j = i + 1; j < n; j++) {
                if (WiFi.RSSI(indices[j]) > WiFi.RSSI(indices[i])) {
                    std::swap(indices[i], indices[j]);
                }
            }
        }

        /* test std:sort
          std::sort(indices, indices + n, [](const int & a, const int & b) ->
          bool
          {
          return WiFi.RSSI(a) > WiFi.RSSI(b);
          });
         */

        // remove duplicates ( must be RSSI sorted )
        if (_removeDuplicateAPs) {
            String cssid;
            for (int i = 0; i < n; i++) {
                if (indices[i] == -1) continue;
                cssid = WiFi.SSID(indices[i]);
                for (int j = i + 1; j < n; j++) {
                    if (cssid == WiFi.SSID(indices[j])) {
                        indices[j] = -1;  // set dup aps to index -1
                    }
                }
            }
        }

        // token precheck, to speed up replacements on large ap lists
        String HTTP_ITEM_STR = FPSTR(HTTP_ITEM);

        // toggle icons with percentage
        HTTP_ITEM_STR.replace("{qp}", FPSTR(HTTP_ITEM_QP));
        HTTP_ITEM_STR.replace("{h}", _scanDispOptions ? "" : "h");
        HTTP_ITEM_STR.replace("{qi}", FPSTR(HTTP_ITEM_QI));
        HTTP_ITEM_STR.replace("{h}", _scanDispOptions ? "h" : "");

        // set token precheck flags
        bool tok_r = HTTP_ITEM_STR.indexOf(FPSTR(T_r)) > 0;
        bool tok_R = HTTP_ITEM_STR.indexOf(FPSTR(T_R)) > 0;
        bool tok_e = HTTP_ITEM_STR.indexOf(FPSTR(T_e)) > 0;
        bool tok_q = HTTP_ITEM_STR.indexOf(FPSTR(T_q)) > 0;
        bool tok_i = HTTP_ITEM_STR.indexOf(FPSTR(T_i)) > 0;

        // display networks in page
        for (int i = 0; i < n; i++) {
            if (indices[i] == -1) continue;  // skip dups

            int rssiperc = getRSSIasQuality(WiFi.RSSI(indices[i]));
            uint8_t enc_type = WiFi.encryptionType(indices[i]);

            if (_minimumQuality == -1 || _minimumQuality < rssiperc) {
                String item = HTTP_ITEM_STR;
                if (WiFi.SSID(indices[i]) == "") {
                    // Serial.println(WiFi.BSSIDstr(indices[i]));
                    continue;  // No idea why I am seeing these, lets just skip
                               // them for now
                }
                item.replace(
                    FPSTR(T_V),
                    htmlEntities(WiFi.SSID(indices[i])));  // ssid no encoding
                item.replace(FPSTR(T_v),
                             htmlEntities(WiFi.SSID(indices[i]),
                                          true));  // ssid no encoding
                if (tok_e)
                    item.replace(FPSTR(T_e), encryptionTypeStr(enc_type));
                if (tok_r)
                    item.replace(FPSTR(T_r),
                                 static_cast<String>(
                                     rssiperc));  // rssi percentage 0-100
                if (tok_R)
                    item.replace(
                        FPSTR(T_R),
                        static_cast<String>(WiFi.RSSI(indices[i])));  // rssi db
                if (tok_q)
                    item.replace(
                        FPSTR(T_q),
                        static_cast<String>(int(round(map(
                            rssiperc, 0, 100, 1, 4)))));  // quality icon 1-4
                if (tok_i) {
                    if (enc_type != WM_WIFIOPEN) {
                        item.replace(FPSTR(T_i), F("l"));
                    } else {
                        item.replace(FPSTR(T_i), "");
                    }
                }

                page += item;
                delay(0);
            } else {
            }
        }
        page += FPSTR(HTTP_BR);
    }

    return page;
}

String WiFiManager::getIpForm(const String& id, const String& title,
                              const String& value) {
    String item = FPSTR(HTTP_FORM_LABEL);
    item.replace(FPSTR(T_i), id);
    item.replace(FPSTR(T_n), id);
    item.replace(FPSTR(T_p), FPSTR(T_t));
    // item.replace(FPSTR(T_p), default);
    item.replace(FPSTR(T_t), title);
    item.replace(FPSTR(T_l), F("15"));
    item.replace(FPSTR(T_v), value);
    item.replace(FPSTR(T_c), "");
    return item;
}

String WiFiManager::getStaticOut() {
    String page;
    if ((_staShowStaticFields || _sta_static_ip) && _staShowStaticFields >= 0) {
        page += FPSTR(HTTP_FORM_STATIC_HEAD);
        // @todo how can we get these accurate settings from memory ,
        // wifi_get_ip_info does not seem to reveal if struct ip_info is static
        // or not
        page += getIpForm(FPSTR(S_ip), FPSTR(S_staticip),
                          (_sta_static_ip ? _sta_static_ip.toString()
                                          : ""));  // @token staticip
        // WiFi.localIP().toString();
        page += getIpForm(FPSTR(S_gw), FPSTR(S_staticgw),
                          (_sta_static_gw ? _sta_static_gw.toString()
                                          : ""));  // @token staticgw
        // WiFi.gatewayIP().toString();
        page += getIpForm(FPSTR(S_sn), FPSTR(S_subnet),
                          (_sta_static_sn ? _sta_static_sn.toString()
                                          : ""));  // @token subnet
        // WiFi.subnetMask().toString();
    }

    if ((_staShowDns || _sta_static_dns) && _staShowDns >= 0) {
        page += getIpForm(
            FPSTR(S_dns), FPSTR(S_staticdns),
            (_sta_static_dns ? _sta_static_dns.toString() : ""));  // @token dns
    }

    if (page != "") page += FPSTR(HTTP_BR);  // @todo remove these, use css

    return page;
}

/**
 * HTTPD CALLBACK save form and redirect to WLAN config page again
 */
void WiFiManager::handleWifiSave() {
    handleRequest();

    // SAVE/connect here
    _ssid = server->arg(F("s")).c_str();
    _pass = server->arg(F("p")).c_str();

    if (_ssid == "" && _pass != "") {
        _ssid = WiFi_SSID(true);  // password change, placeholder ssid, @todo
                                  // compare pass to old?, confirm ssid is clean
    }

    // set static ips from server args
    if (server->arg(FPSTR(S_ip)) != "") {
        //_sta_static_ip.fromString(server->arg(FPSTR(S_ip));
        String ip = server->arg(FPSTR(S_ip));
        optionalIPFromString(&_sta_static_ip, ip.c_str());
    }
    if (server->arg(FPSTR(S_gw)) != "") {
        String gw = server->arg(FPSTR(S_gw));
        optionalIPFromString(&_sta_static_gw, gw.c_str());
    }
    if (server->arg(FPSTR(S_sn)) != "") {
        String sn = server->arg(FPSTR(S_sn));
        optionalIPFromString(&_sta_static_sn, sn.c_str());
    }
    if (server->arg(FPSTR(S_dns)) != "") {
        String dns = server->arg(FPSTR(S_dns));
        optionalIPFromString(&_sta_static_dns, dns.c_str());
    }

    String page;

    if (_ssid == "") {
        page =
            getHTTPHead(FPSTR(S_titlewifisettings));  // @token titleparamsaved
    } else {
        page = getHTTPHead(FPSTR(S_titlewifisaved));  // @token titlewifisaved
        page += FPSTR(HTTP_SAVED);
    }

    page += FPSTR(HTTP_END);

    server->sendHeader(FPSTR(HTTP_HEAD_CORS),
                       FPSTR(HTTP_HEAD_CORS_ALLOW_ALL));  // @HTTPHEAD send cors
    HTTPSend(page);

    connect =
        true;  // signal ready to connect/reset process in processConfigPortal
}

/**
 * HTTPD CALLBACK 404
 */
void WiFiManager::handleNotFound() {
    if (captivePortal())
        return;  // If captive portal redirect instead of displaying the page
    handleRequest();
    String message = FPSTR(S_notfound);  // @token notfound

    server->sendHeader(
        F("Cache-Control"),
        F("no-cache, no-store, must-revalidate"));  // @HTTPHEAD send cache
    server->sendHeader(F("Pragma"), F("no-cache"));
    server->sendHeader(F("Expires"), F("-1"));
    server->send(404, FPSTR(HTTP_HEAD_CT2), message);
}

/**
 * HTTPD redirector
 * Redirect to captive portal if we got a request for another domain.
 * Return true in that case so the page handler do not try to handle the request
 * again.
 */
boolean WiFiManager::captivePortal() {
    if (!_enableCaptivePortal || !configPortalActive)
        return false;  // skip redirections if cp not enabled or not in ap mode

    String serverLoc = toStringIp(server->client().localIP());

    // fallback for ipv6 bug
    if (serverLoc == "0.0.0.0") {
        if ((WiFi.status()) != WL_CONNECTED)
            serverLoc = toStringIp(WiFi.softAPIP());
        else
            serverLoc = toStringIp(WiFi.localIP());
    }

    if (_httpPort != 80)
        serverLoc +=
            ":" + static_cast<String>(_httpPort);  // add port if not default
    bool doredirect =
        serverLoc != server->hostHeader();  // redirect if hostheader not server
                                            // ip, prevent redirect loops

    if (doredirect) {
        server->sendHeader(F("Location"),
                           static_cast<String>(F("http://")) + serverLoc,
                           true);  // @HTTPHEAD send redirect
        server->send(302, FPSTR(HTTP_HEAD_CT2),
                     "");  // Empty content inhibits Content-length header so we
                           // have to close the socket ourselves.
        server->client()
            .stop();  // Stop is needed because we sent no content length
        return true;
    }
    return false;
}

void WiFiManager::stopCaptivePortal() {
    _enableCaptivePortal = false;
    // @todo maybe disable configportaltimeout(optional), or just provide
    // callback for user
}

void WiFiManager::reportStatus(String& page) {
    String str;
    if (WiFi_SSID() != "") {
        if (WiFi.status() == WL_CONNECTED) {
            str = FPSTR(HTTP_STATUS_ON);
            str.replace(FPSTR(T_i), WiFi.localIP().toString());
            str.replace(FPSTR(T_v), htmlEntities(WiFi_SSID()));
        } else {
            str = FPSTR(HTTP_STATUS_OFF);
            str.replace(FPSTR(T_v), htmlEntities(WiFi_SSID()));
            if (_lastconxresult == WL_STATION_WRONG_PASSWORD) {
                // wrong password
                str.replace(FPSTR(T_c), "D");  // class
                str.replace(FPSTR(T_r), FPSTR(HTTP_STATUS_OFFPW));
            } else if (_lastconxresult == WL_NO_SSID_AVAIL) {
                // connect failed, or ap not found
                str.replace(FPSTR(T_c), "D");
                str.replace(FPSTR(T_r), FPSTR(HTTP_STATUS_OFFNOAP));
            } else if (_lastconxresult == WL_CONNECT_FAILED) {
                // connect failed
                str.replace(FPSTR(T_c), "D");
                str.replace(FPSTR(T_r), FPSTR(HTTP_STATUS_OFFFAIL));
            } else if (_lastconxresult == WL_CONNECTION_LOST) {
                // connect failed, MOST likely 4WAY_HANDSHAKE_TIMEOUT/incorrect
                // password, state is ambiguous however
                str.replace(FPSTR(T_c), "D");
                str.replace(FPSTR(T_r), FPSTR(HTTP_STATUS_OFFFAIL));
            } else {
                str.replace(FPSTR(T_c), "");
                str.replace(FPSTR(T_r), "");
            }
        }
    } else {
        str = FPSTR(HTTP_STATUS_NONE);
    }
    page += str;
}

// PUBLIC

// METHODS

/**
 * [stopConfigPortal description]
 * @return {[type]} [description]
 */
bool WiFiManager::stopConfigPortal() { return shutdownConfigPortal(); }

/**
 * disconnect
 * @access public
 * @since $dev
 * @return bool success
 */
bool WiFiManager::disconnect() {
    if (WiFi.status() != WL_CONNECTED) {
        return false;
    }

    return WiFi_Disconnect();
}

// SETTERS

/**
 * [setTimeout description]
 * @access public
 * @param {[type]} unsigned long seconds [description]
 */
void WiFiManager::setTimeout(unsigned long seconds) {
    setConfigPortalTimeout(seconds);
}

/**
 * [setConfigPortalTimeout description]
 * @access public
 * @param {[type]} unsigned long seconds [description]
 */
void WiFiManager::setConfigPortalTimeout(unsigned long seconds) {
    _configPortalTimeout = seconds * 1000;
}

/**
 * [setConnectTimeout description]
 * @access public
 * @param {[type]} unsigned long seconds [description]
 */
void WiFiManager::setConnectTimeout(unsigned long seconds) {
    _connectTimeout = seconds * 1000;
}

/**
 * [setConnectRetries description]
 * @access public
 * @param {[type]} uint8_t numRetries [description]
 */
void WiFiManager::setConnectRetries(uint8_t numRetries) {
    _connectRetries = constrain(numRetries, 1, 10);
}

/**
 * toggle _cleanconnect, always disconnect before connecting
 * @param {[type]} bool enable [description]
 */
void WiFiManager::setCleanConnect(bool enable) { _cleanConnect = enable; }

/**
 * [setConnectTimeout description
 * @access public
 * @param {[type]} unsigned long seconds [description]
 */
void WiFiManager::setSaveConnectTimeout(unsigned long seconds) {
    _saveTimeout = seconds * 1000;
}

/**
 * Set save portal connect on save option,
 * if false, will only save credentials not connect
 * @access public
 * @param {[type]} bool connect [description]
 */
void WiFiManager::setSaveConnect(bool connect) { _connectonsave = connect; }

/**
 * [setAPStaticIPConfig description]
 * @access public
 * @param {[type]} IPAddress ip [description]
 * @param {[type]} IPAddress gw [description]
 * @param {[type]} IPAddress sn [description]
 */
void WiFiManager::setAPStaticIPConfig(const IPAddress& ip, const IPAddress& gw,
                                      const IPAddress& sn) {
    _ap_static_ip = ip;
    _ap_static_gw = gw;
    _ap_static_sn = sn;
}

/**
 * [setSTAStaticIPConfig description]
 * @access public
 * @param {[type]} IPAddress ip [description]
 * @param {[type]} IPAddress gw [description]
 * @param {[type]} IPAddress sn [description]
 */
void WiFiManager::setSTAStaticIPConfig(const IPAddress& ip, const IPAddress& gw,
                                       const IPAddress& sn) {
    _sta_static_ip = ip;
    _sta_static_gw = gw;
    _sta_static_sn = sn;
}

/**
 * [setSTAStaticIPConfig description]
 * @since $dev
 * @access public
 * @param {[type]} IPAddress ip [description]
 * @param {[type]} IPAddress gw [description]
 * @param {[type]} IPAddress sn [description]
 * @param {[type]} IPAddress dns [description]
 */
void WiFiManager::setSTAStaticIPConfig(const IPAddress& ip, const IPAddress& gw,
                                       const IPAddress& sn,
                                       const IPAddress& dns) {
    setSTAStaticIPConfig(ip, gw, sn);
    _sta_static_dns = dns;
}

/**
 * [setMinimumSignalQuality description]
 * @access public
 * @param {[type]} int quality [description]
 */
void WiFiManager::setMinimumSignalQuality(int quality) {
    _minimumQuality = quality;
}

/**
 * [setBreakAfterConfig description]
 * @access public
 * @param {[type]} boolean shouldBreak [description]
 */
void WiFiManager::setBreakAfterConfig(boolean shouldBreak) {
    _shouldBreakAfterConfig = shouldBreak;
}

/**
 * setSaveConfigCallback, set a save config callback after closing configportal
 * @note calls only if wifi is saved or changed, or setBreakAfterConfig(true)
 * @access public
 * @param {[type]} void (*func)(void)
 */
void WiFiManager::setSaveConfigCallback(const std::function<void()>& func) {
    _savewificallback = func;
}

/**
 * toggle wifiscan hiding of duplicate ssid names
 * if this is false, wifiscan will remove duplicat Access Points - defaut true
 * @access public
 * @param boolean removeDuplicates [true]
 */
void WiFiManager::setRemoveDuplicateAPs(boolean removeDuplicates) {
    _removeDuplicateAPs = removeDuplicates;
}

/**
 * toggle configportal blocking loop
 * if enabled, then the configportal will enter a blocking loop and wait for
 * configuration if disabled use with process() to manually process webserver
 * @since $dev
 * @access public
 * @param boolean shoudlBlock [false]
 */
void WiFiManager::setConfigPortalBlocking(boolean shouldBlock) {
    _configPortalIsBlocking = shouldBlock;
}

/**
 * toggle restore persistent, track internally
 * sets ESP wifi.persistent so we can remember it and restore user preference on
 * destruct there is no getter in esp8266 platform prior to
 * https://github.com/esp8266/Arduino/pull/3857
 * @since $dev
 * @access public
 * @param boolean persistent [true]
 */
void WiFiManager::setRestorePersistent(boolean persistent) {
    _userpersistent = persistent;
    if (!persistent) {
    }
}

/**
 * toggle showing static ip form fields
 * if enabled, then the static ip, gateway, subnet fields will be visible, even
 * if not set in code
 * @since $dev
 * @access public
 * @param boolean alwaysShow [false]
 */
void WiFiManager::setShowStaticFields(boolean alwaysShow) {
    if (_disableIpFields)
        _staShowStaticFields = alwaysShow ? 1 : -1;
    else
        _staShowStaticFields = alwaysShow ? 1 : 0;
}

/**
 * toggle showing dns fields
 * if enabled, then the dns1 field will be visible, even if not set in code
 * @since $dev
 * @access public
 * @param boolean alwaysShow [false]
 */
void WiFiManager::setShowDnsFields(boolean alwaysShow) {
    if (_disableIpFields) _staShowDns = alwaysShow ? 1 : -1;
    _staShowDns = alwaysShow ? 1 : 0;
}

/**
 * toggle showing password in wifi password field
 * if not enabled, placeholder will be S_passph
 * @since $dev
 * @access public
 * @param boolean alwaysShow [false]
 */
void WiFiManager::setShowPassword(boolean show) { _showPassword = show; }

/**
 * toggle captive portal
 * if enabled, then devices that use captive portal checks will be redirected to
 * root if not you will automatically have to navigate to ip [192.168.4.1]
 * @since $dev
 * @access public
 * @param boolean enabled [true]
 */
void WiFiManager::setCaptivePortalEnable(boolean enabled) {
    _enableCaptivePortal = enabled;
}

/**
 * toggle wifi autoreconnect policy
 * if enabled, then wifi will autoreconnect automatically always
 * On esp8266 we force this on when autoconnect is called, see notes
 * On esp32 this is handled on SYSTEM_EVENT_STA_DISCONNECTED since it does not
 * exist in core yet
 * @since $dev
 * @access public
 * @param boolean enabled [true]
 */
void WiFiManager::setWiFiAutoReconnect(boolean enabled) {
    _wifiAutoReconnect = enabled;
}

/**
 * toggle configportal timeout wait for station client
 * if enabled, then the configportal will start timeout when no stations are
 * connected to softAP disabled by default as rogue stations can keep it open if
 * there is no auth
 * @since $dev
 * @access public
 * @param boolean enabled [false]
 */
void WiFiManager::setAPClientCheck(boolean enabled) {
    _apClientCheck = enabled;
}

/**
 * toggle configportal timeout wait for web client
 * if enabled, then the configportal will restart timeout when client requests
 * come in
 * @since $dev
 * @access public
 * @param boolean enabled [true]
 */
void WiFiManager::setWebPortalClientCheck(boolean enabled) {
    _webClientCheck = enabled;
}

/**
 * toggle wifiscan percentages or quality icons
 * @since $dev
 * @access public
 * @param boolean enabled [false]
 */
void WiFiManager::setScanDispPerc(boolean enabled) {
    _scanDispOptions = enabled;
}

/**
 * toggle configportal if autoconnect failed
 * if enabled, then the configportal will be activated on autoconnect failure
 * @since $dev
 * @access public
 * @param boolean enabled [true]
 */
void WiFiManager::setEnableConfigPortal(boolean enable) {
    _enableConfigPortal = enable;
}

/**
 * toggle configportal if autoconnect failed
 * if enabled, then the configportal will be de-activated on wifi save
 * @since $dev
 * @access public
 * @param boolean enabled [true]
 */
void WiFiManager::setDisableConfigPortal(boolean enable) {
    _disableConfigPortal = enable;
}

/**
 * set the hostname (dhcp client id)
 * @since $dev
 * @access public
 * @param hostname
 * @param  char* hostname 32 character hostname to use for sta+ap in esp32, sta
 * in esp8266
 * @return bool false if hostname is not valid
 */
bool WiFiManager::setHostname(const char* hostname) {
    //@todo max length 32
    _hostname = String(hostname);
    return true;
}

bool WiFiManager::setHostname(const String& hostname) {
    //@todo max length 32
    _hostname = hostname;
    return true;
}

/**
 * set the soft ao channel, ignored if channelsync is true and connected
 * @param int32_t   wifi channel, 0 to disable
 */
void WiFiManager::setWiFiAPChannel(int32_t channel) { _apChannel = channel; }

/**
 * set the soft ap hidden
 * @param bool   wifi ap hidden, default is false
 */
void WiFiManager::setWiFiAPHidden(bool hidden) { _apHidden = hidden; }

/**
 * check if the config portal is running
 * @return bool true if active
 */
bool WiFiManager::getConfigPortalActive() const { return configPortalActive; }

/**
 * [getConfigPortalActive description]
 * @return bool true if active
 */
bool WiFiManager::getWebPortalActive() const { return webPortalActive; }

String WiFiManager::getWiFiHostname() {
#ifdef ESP32
    return (String)WiFi.getHostname();
#else
    return (String)WiFi.hostname();
#endif
}

/**
 * [setTitle description]
 * @param String title, set app title
 */
void WiFiManager::setTitle(String title) { _title = title; }

/**
 * set menu items and order
 * if param is present in menu , params will be removed from wifi page
 * automatically eg. const char * menu[] = {"wifi","setup","sep","info","exit"};
 *  WiFiManager.setMenu(menu);
 * @since $dev
 * @param uint8_t menu[] array of menu ids
 */
void WiFiManager::setMenu(const char* menu[], uint8_t size) {
    _menuIds.clear();
    for (size_t i = 0; i < size; i++) {
        for (size_t j = 0; j < _nummenutokens; j++) {
            if (static_cast<String>(menu[i]) ==
                (__FlashStringHelper*)(_menutokens[j])) {
                if (static_cast<String>(menu[i]) == "param")
                    _menuIds.push_back(j);
            }
            delay(0);
        }
        delay(0);
    }
}

/**
 * setMenu with vector
 * eg.
 * std::vector<const char *> menu = {"wifi","setup","sep","info","exit"};
 * WiFiManager.setMenu(menu);
 * tokens can be found in _menutokens array in strings_en.h
 * @shiftIncrement $dev
 * @param {[type]} std::vector<const char *>& menu [description]
 */
void WiFiManager::setMenu(std::vector<const char*>& menu) {
    _menuIds.clear();
    for (auto menuitem : menu) {
        for (size_t j = 0; j < _nummenutokens; j++) {
            if (static_cast<String>(menuitem) ==
                (__FlashStringHelper*)(_menutokens[j])) {
                _menuIds.push_back(j);
            }
        }
    }
}

// GETTERS

/**
 * get config portal AP SSID
 * @since 0.0.1
 * @access public
 * @return String the configportal ap name
 */
String WiFiManager::getConfigPortalSSID() { return _apName; }

/**
 * return the last known connection result
 * logged on autoconnect and wifisave, can be used to check why failed
 * get as readable string with getWLStatusString(getLastConxResult);
 * @since $dev
 * @access public
 * @return bool return wl_status codes
 */
uint8_t WiFiManager::getLastConxResult() { return _lastconxresult; }

/**
 * check if wifi has a saved ap or not
 * @since $dev
 * @access public
 * @return bool true if a saved ap config exists
 */
bool WiFiManager::getWiFiIsSaved() { return WiFi_hasAutoConnect(); }

/**
 * getDefaultAPName
 * @since $dev
 * @return string
 */
String WiFiManager::getDefaultAPName() const {
    auto hostString = String(WIFI_getChipId(), HEX);
    hostString.toUpperCase();
    return _wifissidprefix + "_" + hostString;
}

/**
 * setCountry
 * @since $dev
 * @param String cc country code, must be defined in WiFiSetCountry, US, JP, CN
 */
void WiFiManager::setCountry(String cc) { _wificountry = cc; }

/**
 * setClass
 * @param String str body class string
 */
void WiFiManager::setClass(String str) { _bodyClass = str; }

/**
 * setDarkMode
 * @param bool enable, enable dark mode via invert class
 */
void WiFiManager::setDarkMode(bool enable) {
    _bodyClass = enable ? "invert" : "";
}

/**
 * setHttpPort
 * @param port
 * @param uint16_t port webserver port number default 80
 */
void WiFiManager::setHttpPort(uint16_t port) { _httpPort = port; }

bool WiFiManager::preloadWiFi(const String& ssid, const String& pass) {
    _defaultssid = ssid;
    _defaultpass = pass;
    return true;
}

// HELPERS

/**
 * getWiFiSSID
 * @since $dev
 * @param bool persistent
 * @return String
 */
String WiFiManager::getWiFiSSID(bool persistent) {
    return WiFi_SSID(persistent);
}

/**
 * getWiFiPass
 * @since $dev
 * @param bool persistent
 * @return String
 */
String WiFiManager::getWiFiPass(bool persistent) {
    return WiFi_psk(persistent);
}

int WiFiManager::getRSSIasQuality(int RSSI) {
    int quality = 0;

    if (RSSI <= -100) {
        quality = 0;
    } else if (RSSI >= -50) {
        quality = 100;
    } else {
        quality = 2 * (RSSI + 100);
    }
    return quality;
}

/** Is this an IP? */
boolean WiFiManager::isIp(const String& str) {
    for (size_t i = 0; i < str.length(); i++) {
        int c = str.charAt(i);
        if (c != '.' && (c < '0' || c > '9')) {
            return false;
        }
    }
    return true;
}

/** IP to String? */
String WiFiManager::toStringIp(IPAddress ip) {
    String res = "";
    for (int i = 0; i < 3; i++) {
        res += String((ip >> (8 * i)) & 0xFF) + ".";
    }
    res += String(((ip >> 8 * 3)) & 0xFF);
    return res;
}

boolean WiFiManager::validApPassword() {
    // check that ap password is valid, return false
    if (_apPassword == nullptr) _apPassword = "";
    if (_apPassword != "") {
        if (_apPassword.length() < 8 || _apPassword.length() > 63) {
            _apPassword = "";
            return false;  // @todo FATAL or fallback to empty , currently
                           // fatal, fail secure.
        }
    }
    return true;
}

/**
 * encode htmlentities
 * @since $dev
 * @param  string str  string to replace entities
 * @return string      encoded string
 */
String WiFiManager::htmlEntities(String str, bool whitespace) {
    str.replace("&", "&amp;");
    str.replace("<", "&lt;");
    str.replace(">", "&gt;");
    str.replace("'", "&#39;");
    if (whitespace) str.replace(" ", "&#160;");
    // str.replace("-","&ndash;");
    // str.replace("\"","&quot;");
    // str.replace("/": "&#x2F;");
    // str.replace("`": "&#x60;");
    // str.replace("=": "&#x3D;");
    return str;
}

/**
 * [getWLStatusString description]
 * @access public
 * @param  {[type]} uint8_t status        [description]
 * @return {[type]}         [description]
 */
String WiFiManager::getWLStatusString(uint8_t status) {
    if (status <= 7) return WIFI_STA_STATUS[status];
    return FPSTR(S_NA);
}

String WiFiManager::getWLStatusString() {
    uint8_t status = WiFi.status();
    if (status <= 7) return WIFI_STA_STATUS[status];
    return FPSTR(S_NA);
}

String WiFiManager::encryptionTypeStr(uint8_t authmode) {
    return AUTH_MODE_NAMES[authmode];
}

String WiFiManager::getModeString(uint8_t mode) {
    if (mode <= 3) return WIFI_MODES[mode];
    return FPSTR(S_NA);
}

bool WiFiManager::WiFiSetCountry() {
    if (_wificountry == "") return false;  // skip not set

    bool ret = true;
#ifdef ESP32
    esp_err_t err = ESP_OK;
    // @todo check if wifi is init, no idea how, doesnt seem to be exposed atm (
    // check again it might be now! )
    if (WiFi.getMode() == WIFI_MODE_NULL) {
    }  // exception if wifi not init!
    // Assumes that _wificountry is set to one of the supported country codes :
    // "01"(world safe mode) "AT","AU","BE","BG","BR",
    //               "CA","CH","CN","CY","CZ","DE","DK","EE","ES","FI","FR","GB","GR","HK","HR","HU",
    //               "IE","IN","IS","IT","JP","KR","LI","LT","LU","LV","MT","MX","NL","NO","NZ","PL","PT",
    //               "RO","SE","SI","SK","TW","US"
    // If an invalid country code is passed, ESP_ERR_WIFI_ARG will be returned
    // This also uses 802.11d mode, which matches the STA to the country code of
    // the AP it connects to (meaning that the country code will be overridden
    // if connecting to a "foreign" AP)
    else {
#ifndef WM_NOCOUNTRY
        err = esp_wifi_set_country_code(_wificountry.c_str(), true);
#else
        err = true;
#endif
    }

    ret = err == ESP_OK;

#elif defined(ESP8266) && !defined(WM_NOCOUNTRY)
#endif

    return ret;
}

// set mode ignores WiFi.persistent
bool WiFiManager::WiFi_Mode(WiFiMode_t m, bool persistent) {
    bool ret;
#ifdef ESP8266
    if ((wifi_get_opmode() == (uint8)m) && !persistent) {
        return true;
    }
    ETS_UART_INTR_DISABLE();
    if (persistent)
        ret = wifi_set_opmode(m);
    else
        ret = wifi_set_opmode_current(m);
    ETS_UART_INTR_ENABLE();
    return ret;
#elif defined(ESP32)
    if (persistent && esp32persistent) WiFi.persistent(true);
    ret = WiFi.mode(
        m);  // @todo persistent check persistant mode, was eventually added to
             // esp lib, but have to add version checking probably
    if (persistent && esp32persistent) WiFi.persistent(false);
    return ret;
#endif
}
bool WiFiManager::WiFi_Mode(WiFiMode_t m) { return WiFi_Mode(m, false); }

// sta disconnect without persistent
bool WiFiManager::WiFi_Disconnect() {
#ifdef ESP8266
    if ((WiFi.getMode() & WIFI_STA) != 0) {
        bool ret;

        ETS_UART_INTR_DISABLE();  // @todo possibly not needed
        ret = wifi_station_disconnect();
        ETS_UART_INTR_ENABLE();
        return ret;
    }
#elif defined(ESP32)

    return WiFi.disconnect();  // not persistent atm
#endif
    return false;
}

// toggle STA without persistent
bool WiFiManager::WiFi_enableSTA(bool enable, bool persistent) {
    bool ret;
    if (persistent && esp32persistent) WiFi.persistent(true);
    ret = WiFi.enableSTA(
        enable);  // @todo handle persistent when it is implemented in platform
    if (persistent && esp32persistent) WiFi.persistent(false);
    return ret;
}

bool WiFiManager::WiFi_enableSTA(bool enable) {
    return WiFi_enableSTA(enable, false);
}

uint8_t WiFiManager::WiFi_softap_num_stations() {
    return WiFi.softAPgetStationNum();
}

bool WiFiManager::WiFi_hasAutoConnect() { return WiFi_SSID(true) != ""; }

String WiFiManager::WiFi_SSID(bool persistent) const {
    if (persistent) {
        wifi_config_t conf;
        esp_wifi_get_config(WIFI_IF_STA, &conf);
        return String(reinterpret_cast<const char*>(conf.sta.ssid));
    }
    if (WiFiGenericClass::getMode() == WIFI_MODE_NULL) {
        return String();
    }
    wifi_ap_record_t info;
    if (!esp_wifi_sta_get_ap_info(&info)) {
        return String(reinterpret_cast<char*>(info.ssid));
    }
    return String();
}

String WiFiManager::WiFi_psk(bool persistent) const {
    // only if wifi is init
    if (WiFiGenericClass::getMode() == WIFI_MODE_NULL) {
        return String();
    }
    wifi_config_t conf;
    esp_wifi_get_config(WIFI_IF_STA, &conf);
    return String(reinterpret_cast<char*>(conf.sta.password));
}

#ifdef ESP32
#ifdef WM_ARDUINOEVENTS
void WiFiManager::WiFiEvent(WiFiEvent_t event, arduino_event_info_t info) {
#else
void WiFiManager::WiFiEvent(WiFiEvent_t event, system_event_info_t info) {
#define wifi_sta_disconnected disconnected
#define ARDUINO_EVENT_WIFI_STA_DISCONNECTED SYSTEM_EVENT_STA_DISCONNECTED
#define ARDUINO_EVENT_WIFI_SCAN_DONE SYSTEM_EVENT_SCAN_DONE
#endif
    if (!_hasBegun) {
        return;
    }

    if (event == ARDUINO_EVENT_WIFI_STA_DISCONNECTED) {
        if (info.wifi_sta_disconnected.reason == WIFI_REASON_AUTH_EXPIRE ||
            info.wifi_sta_disconnected.reason == WIFI_REASON_AUTH_FAIL) {
            _lastconxresulttmp =
                7;  // hack in wrong password internally, sdk emit
                    // WIFI_REASON_AUTH_EXPIRE on some routers on auth_fail
        } else
            _lastconxresulttmp = WiFi.status();
    } else if (event == ARDUINO_EVENT_WIFI_SCAN_DONE && _asyncScan) {
        uint16_t scans = WiFi.scanComplete();
        WiFi_scanComplete(scans);
    }
}
#endif

void WiFiManager::WiFi_autoReconnect() {
    using namespace std::placeholders;
    if (wm_event_id == 0)
        wm_event_id =
            WiFi.onEvent(std::bind(&WiFiManager::WiFiEvent, this, _1, _2));
}

#endif
