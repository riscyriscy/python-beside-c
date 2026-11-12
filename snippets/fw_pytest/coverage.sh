#!/bin/sh
# Line and branch coverage of cobs.c: the suite without the long-run test, then the whole suite.
# Run: sh build_host.sh && sh coverage.sh   (needs pytest and Hypothesis on the PATH's Python, and frametool)
set -eu
export FW_LIB=build/libfw_cov.so
COBS=../../firmware-tree/lib/src/cobs.c
report() {
    gcov -b -n build/libfw_cov.so-cobs.gcda | grep -A3 "File '$COBS'" | tail -3
}
rm -f build/*.gcda
echo '== without test_cobs_runs_of_254_or_more_non_zero_bytes'
${PYTEST:-pytest} -q -p no:cacheprovider -k 'not runs_of_254' | tail -1
report
gcov -b build/libfw_cov.so-cobs.gcda > /dev/null
grep '#####' cobs.c.gcov | sed 's/^ *#####: */   line /; s/:.*//'
rm -f ./*.gcov build/*.gcda
echo '== the whole suite'
${PYTEST:-pytest} -q -p no:cacheprovider | tail -1
report
