#!/bin/sh
# Install each stack into an empty virtual environment and count what arrives. Run: sh footprint.sh
set -e
for stack in "Flask + waitress:flask waitress" "FastAPI + uvicorn:fastapi uvicorn"; do
    name=${stack%%:*}; pkgs=${stack#*:}
    d=$(mktemp -d)
    uv venv --python 3.14 -q "$d/v"
    uv pip install -q --python "$d/v/bin/python" $pkgs
    sp=$("$d/v/bin/python" -c "import sysconfig; print(sysconfig.get_paths()['purelib'])")
    n=$(ls -d "$sp"/*.dist-info | wc -l)
    kb=$(du -sk "$sp" | cut -f1)
    names=$(ls -d "$sp"/*.dist-info | sed 's|.*/||; s|-[0-9].*||' | tr '\n' ' ')
    printf '%-18s %2d packages  %6d KiB\n  %s\n' "$name" "$n" "$kb" "$names"
    rm -rf "$d"
done
