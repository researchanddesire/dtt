#ifndef EEPROM_SERVICE_H
#define EEPROM_SERVICE_H

#include <Arduino.h>

#define EEPROM_SIZE 200

extern String trainerId;
extern String trainerIdShort;
extern int serialNumber;
extern bool isAlphaVersion;

void initEEPROM();
void toggleIsAlpha();

// Returns false when the identity could not be written and read back.
bool saveToEEPROM(const String &trainerId, const int serialNumber);

#endif  // EEPROM_SERVICE_H