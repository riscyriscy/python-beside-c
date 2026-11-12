#!/bin/sh
# Build the firmware sources for the host three ways: plain, with ASan and UBSan, and with gcov counters.
# Run: sh build_host.sh   (needs gcc). SENSOR_SRC=sensor/src/sensor_overflow.c builds sensor.c with the 32-bit overflow.
set -eu
FW=../../firmware-tree/lib
SENSOR=${SENSOR_SRC:-sensor/src/sensor.c}
SRC="$FW/src/cobs.c $FW/src/crc16.c $SENSOR"
CF="-shared -fPIC -g -O1 -Wall -Wextra -I$FW/include -Isensor/include"
mkdir -p build
rm -f build/*.gcda
gcc $CF $SRC -o build/libfw_plain.so
gcc $CF -fsanitize=address,undefined -fno-omit-frame-pointer $SRC -o build/libfw_san.so
gcc $CF --coverage $SRC -o build/libfw_cov.so
ls -1 build | grep '\.so$'
