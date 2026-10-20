#!/bin/sh
set -eu
test_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
test_build_dir=$(mktemp -d "${TMPDIR:-/tmp}/dtt-session-mutex.XXXXXX")
trap 'rm -rf "$test_build_dir"' EXIT HUP INT TERM
c++ -std=c++17 -pthread -fsanitize=address,undefined -fno-omit-frame-pointer \
    -I"$test_dir/fakes" "$test_dir/main.cpp" -o "$test_build_dir/test_mutex"
"$test_build_dir/test_mutex"
