#ifndef LOCKBOX_VERSION_STRUCT_H
#define LOCKBOX_VERSION_STRUCT_H

#include "Arduino.h"
#include "constants/Version.h"
struct Version {
    int major = 0;
    int minor = 1;
    int patch = 1;
};

static Version currentVersion = {
    .major = MAJOR_VERSION,
    .minor = MINOR_VERSION,
    .patch = PATCH_VERSION,
};

#endif  // LOCKBOX_VERSION_STRUCT_H
