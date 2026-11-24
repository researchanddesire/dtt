#pragma once

// Stable serial evidence shared by release firmware and the hardware runner,
// printed in every build as DTT_HEALTH lines (hardwareHealthFormat.h).
// These hooks observe normal application work. They never advance the state
// machine, start a task or open a network connection, and allocate nothing
// after the boot record registers its Wi-Fi event handler.
void hardwareHealthBoot();
// The result of the application's own dashboard /health-check.
void hardwareHealthCloudResult(bool succeeded);
// Called by the UI loop on every pass.
void hardwareHealthMenuProgress();
// Called from a task that already runs; prints at most every 5 seconds.
void hardwareHealthHeartbeat(bool atMainMenu);
