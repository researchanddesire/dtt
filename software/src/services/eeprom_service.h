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

#ifdef PROVISION
void saveToEEPROM(const String &trainerId, const int serialNumber);
#endif

#endif  // EEPROM_SERVICE_H