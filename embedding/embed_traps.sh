#!/bin/sh
# What in the station's environment can change what an embedded interpreter imports.
# Run: sh embed_traps.sh path/to/build-directory path/to/directory-with-limits.py [path/to/python]
# The optional third argument is the interpreter that the probe is linked with. It adds the runs
# that show how PATH selects the interpreter, and that pin it with program_name.
set -eu
exec 2>&1
PATH="$(cd "$1" && pwd):$PATH"
export PATH
rules=$(cd "$2" && pwd)
work=$(mktemp -d)
cd "$work"

mkdir trap
echo 'print("TRAP: sitecustomize.py ran", flush=True)' > trap/sitecustomize.py
echo 'print("TRAP: statistics.py ran", flush=True)' > trap/statistics.py
for v in 3.12 3.13 3.14; do
    mkdir -p "user/lib/python$v/site-packages"
    echo 'print("TRAP: usercustomize.py ran", flush=True)' \
        > "user/lib/python$v/site-packages/usercustomize.py"
done

show() { printf '$ %s\n' "$*"; env "$@"; }

show PYTHONPATH=trap init_probe plain
show PYTHONPATH=trap init_probe isolated
show PYTHONUSERBASE=user init_probe plain
show PYTHONUSERBASE=user init_probe isolated
printf '$ PYTHONHOME=/nonexistent init_probe plain 2>&1 | grep -m 1 Fatal\n'
PYTHONHOME=/nonexistent init_probe plain 2>&1 | grep -m 1 Fatal || true
show PYTHONHOME=/nonexistent init_probe isolated
printf '$ init_probe badconfig\n'
init_probe badconfig || printf 'exit status %s\n' "$?"
if [ $# -ge 3 ]; then
    "$3" -m venv venv
    printf '$ init_probe where\n'
    init_probe where | sed "s|$work|WORK|"
    printf '$ PATH=venv/bin:$PATH init_probe where\n'
    PATH="$work/venv/bin:$PATH" init_probe where | sed "s|$work|WORK|"
    printf '$ PATH=venv/bin:$PATH init_probe pinned PY/bin/%s\n' "$(basename "$3")"
    PATH="$work/venv/bin:$PATH" init_probe pinned "$3" | sed "s|$work|WORK|; s|$(dirname "$(dirname "$3")")|PY|g"
fi
for mode in sleep-plain sleep-isolated; do
    printf '$ timeout -s INT 1.5 init_probe %s\n' "$mode"
    timeout --preserve-status -s INT 1.5 init_probe "$mode" 2>/dev/null || printf 'exit status %s\n' "$?"
done
printf '$ PYTHONPATH=trap sequencer . | head -n 2\n'
(cd "$rules" && PYTHONPATH="$work/trap" sequencer . | head -n 2)
cd /
rm -rf "$work"
