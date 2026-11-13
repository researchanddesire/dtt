#!/bin/sh
set -eu
test_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
project_dir=$(CDPATH= cd -- "$test_dir/../.." && pwd)
test_build_dir=$(mktemp -d "${TMPDIR:-/tmp}/dtt-session-security.XXXXXX")
trap 'rm -rf "$test_build_dir"' EXIT HUP INT TERM
dependency_dir="$project_dir/.pio/libdeps/test_native"
common_flags="-fsanitize=address,undefined -fno-omit-frame-pointer"
cc $common_flags -I"$dependency_dir/Unity/src" \
    -c "$dependency_dir/Unity/src/unity.c" -o "$test_build_dir/unity.o"
c++ -std=c++17 $common_flags -I"$dependency_dir/Unity/src" \
    -I"$dependency_dir/ArduinoJson/src" \
    -I"$project_dir/lib/TrainingTypes/src" \
    "$test_dir/test_main.cpp" "$test_build_dir/unity.o" \
    -o "$test_build_dir/test_session"
"$test_build_dir/test_session"
