#ifndef WIFI_MANAGER_H
#define WIFI_MANAGER_H

#include <WiFiManager.h>

// Declare the global WiFiManager instance, but do not initialize it
extern WiFiManager wm;

// Declare health check status
extern bool healthCheckPassed;

void initWifi();

void processWifiTask(void* pvParameters);

void healthCheckWifi();

// Optional: Add service configuration or constants
#define WIFI_MANAGER_PORTAL_TIMEOUT 400

#endif  // WIFI_MANAGER_H
