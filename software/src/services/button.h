#ifndef BUTTON_SERVICE_H
#define BUTTON_SERVICE_H

#include <OneButton.h>

// Global instance declaration (do not initialize here)
extern OneButton btn;

// FreeRTOS task prototype
void vButtonTask(void *pvParameters);

// Service initialization function prototype
void initButtonService();

#endif  // BUTTON_SERVICE_H
