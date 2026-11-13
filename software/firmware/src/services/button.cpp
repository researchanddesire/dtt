#include "button.h"
#include "TaskStackSizes.h"

#include "services/board.hpp"
#include "state/state.h"

#define BUTTON_TAG "BUTTON"

// Initialize the global OneButton instance
OneButton btn;  // false = active high

// FreeRTOS task to poll the button
[[noreturn]] void vButtonTask(void *pvParameters) {
    while (true) {
        btn.tick();
        vTaskDelay(50 / portTICK_PERIOD_MS);  // Poll every 50ms
    }
}

void onButtonClick() {
    ESP_LOGI(BUTTON_TAG, "Button clicked");
    stateMachine->process_event(button_pressed{});
}
void onButtonDoubleClick() {
    ESP_LOGI(BUTTON_TAG, "Button double clicked");
    stateMachine->process_event(button_double_pressed{});
}
void onButtonLongPressStart() {
    ESP_LOGI(BUTTON_TAG, "Button long press started");
    stateMachine->process_event(button_long_pressed{});
}
void onButtonMultiplePress() {
    const int clicks = btn.getNumberClicks();

    if (clicks < 7) {
        return;
    }

    ESP_LOGI(BUTTON_TAG, "Button multiple pressed %d", clicks);
    stateMachine->process_event(
        button_multiple_pressed{.count = static_cast<uint8_t>(clicks)});
}

// Service initialization function
void initButtonService() {
    btn.setup(BUTTON_IN, INPUT_PULLUP, false);  // false = active high
    btn.attachClick(onButtonClick);
    btn.attachDoubleClick(onButtonDoubleClick);
    btn.attachLongPressStart(onButtonLongPressStart);
    btn.attachMultiClick(onButtonMultiplePress);

    // Start the FreeRTOS task for button polling, pinned to core 0
    xTaskCreatePinnedToCore(vButtonTask,                    // Task function
                            drawButtonTaskName,             // Name
                            taskStacks::button,            // Stack size
                            nullptr,                        // Parameters
                            1,                              // Priority
                            &drawButtonTaskHandle,          // Task handle
                            0                               // Core 0
    );
}
