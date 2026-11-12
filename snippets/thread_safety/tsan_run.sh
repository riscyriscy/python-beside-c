#!/bin/sh
# Builds tsan_demo with ThreadSanitizer and runs each mode, printing the first report of each.
set -u
cc -g -O1 -Wall -Wextra -fsanitize=thread -o tsan_demo tsan_demo.c fw_describe.c -lpthread || exit 1
echo '$ cc -g -O1 -fsanitize=thread -o tsan_demo tsan_demo.c fw_describe.c -lpthread'
for m in static counter caller atomic mutex; do
    echo "\$ ./tsan_demo $m"
    ./tsan_demo "$m" > run.out 2>&1
    rc=$?
    sed -e 's/ (BuildId[^)]*)//' -e 's/ (pid=[0-9]*)//' -e 's/ at 0x[0-9a-f]*//' -e 's/ (libtsan[^)]*)//' \
        -e 's/ (tsan_demo+0x[0-9a-f]*)//' -e 's# [^ ]*/libsanitizer/[^ ]*##' \
        -e "s#$PWD/##g" run.out | awk '/^WARNING/{p=1} p{print} /^  Location is/{exit} !/^WARNING/ && !p && !/^=+$/{print}'
    echo "exit status $rc"
done
rm -f run.out
