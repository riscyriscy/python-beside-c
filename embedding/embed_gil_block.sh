#!/bin/sh
# Run the GIL hand-off program with and without PyEval_SaveThread(), then show stacks.
# Run: sh embed_gil_block.sh path/to/build-directory
set -u
exec 2>&1
PATH="$(cd "$1" && pwd):$PATH"
export PATH

printf '$ gil_block save\n'
gil_block save
printf 'exit status %s\n' "$?"

printf '$ timeout 3 gil_block nosave\n'
timeout 3 gil_block nosave
printf 'exit status %s\n' "$?"

# The same blocked run, looked at from outside with gdb after one second
timeout 5 gil_block nosave > /dev/null &
sleep 1
pid=$(pgrep -n -x gil_block)
keep='^Thread|take_gil|PyEval_RestoreThread|PyGILState_Ensure|worker_main'
keep="$keep|clockjoin|in main"
printf '$ gdb -batch -p PID -ex "thread apply all bt -frame-arguments none"\n'
gdb -batch -p "$pid" -ex 'set debuginfod enabled off' \
    -ex 'thread apply all bt -frame-arguments none' 2>&1 |
    grep -E "$keep" |
    sed -E 's/^Thread ([0-9]+) .*/Thread \1/; s/ 0x[0-9a-f]+ in//; s/ \(.*//'
kill "$pid" 2>/dev/null
wait
