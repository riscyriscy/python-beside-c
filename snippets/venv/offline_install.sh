#!/usr/bin/env bash
# A wheelhouse for stations with no internet: build it once online, then install with the network cut.
# Run: bash offline_install.sh      (needs uv and network access to PyPI for steps 1 and 2)
set -eu
demo=${DEMO_DIR:-/tmp/offline_demo}
rm -rf "$demo" && mkdir -p "$demo" && cd "$demo"

echo "== 1. build machine: lock with hashes for every platform"
cat > requirements.in <<'REQ'
pyserial>=3.5,<4
numpy>=2,<3
colorama>=0.4.6 ; sys_platform == 'win32'
REQ
uv pip compile --quiet --universal --python-version 3.12 --generate-hashes \
    requirements.in -o locked.txt
grep -E '^(pyserial|numpy|colorama)==' locked.txt | sed 's/ .$//'
echo "hash lines: $(grep -c -- '--hash=sha256:' locked.txt)"

echo "== 2. build machine: one lock and one wheelhouse per kind of station"
uv venv --quiet --python 3.14 .venv-tools && uv pip install --quiet --python .venv-tools pip
pip=".venv-tools/bin/python -m pip"
echo "-- pip download from the universal lock, Windows wheels on Linux"
$pip download --quiet --dest wheelhouse-naive --only-binary=:all: --platform win_amd64 \
    --python-version 3.12 -r locked.txt
ls wheelhouse-naive
echo "colorama wheels: $(ls wheelhouse-naive | grep -c colorama || true)"
echo "-- Windows 64-bit, Python 3.12: lock for that kind, then download from it"
uv pip compile --quiet --python-platform windows --python-version 3.12 --generate-hashes \
    requirements.in -o locked-win.txt
$pip download --quiet --dest wheelhouse-win --only-binary=:all: --platform win_amd64 \
    --python-version 3.12 -r locked-win.txt
ls wheelhouse-win
uv venv --quiet --python 3.14 probe
for kind in naive:locked.txt win:locked-win.txt; do
    echo "-- uv dry run for Windows from wheelhouse-${kind%%:*}"
    uv pip install --dry-run --python probe --python-platform windows --python-version 3.12 \
        --offline --no-index --find-links "wheelhouse-${kind%%:*}" --require-hashes \
        -r "${kind##*:}" 2>&1 | grep -oE -m1 'unsatisfiable|Would install [0-9]+ packages' || true
done
echo "-- Linux x86-64, glibc 2.28 or newer, Python 3.14"
uv pip compile --quiet --python-platform x86_64-manylinux_2_28 --python-version 3.14 \
    --generate-hashes requirements.in -o locked-linux.txt
$pip download --quiet --dest wheelhouse-linux --only-binary=:all: --platform manylinux_2_28_x86_64 \
    --python-version 3.14 -r locked-linux.txt
ls wheelhouse-linux

echo "== 3. the station: network cut, install from the folder only"
export HTTP_PROXY=http://127.0.0.1:9 HTTPS_PROXY=http://127.0.0.1:9   # nothing listens here
uv venv --quiet --python 3.14 station
station/bin/python -m ensurepip >/dev/null
station/bin/python -m pip install --quiet --no-index --find-links wheelhouse-linux \
    --require-hashes -r locked-linux.txt
station/bin/python -c "import serial, numpy; print('pyserial', serial.__version__, 'numpy', numpy.__version__)"
echo "-- the same with uv"
uv venv --quiet --python 3.14 station-uv
uv pip install --quiet --offline --no-index --find-links wheelhouse-linux --require-hashes \
    --python station-uv -r locked-linux.txt
station-uv/bin/python -c "import serial, numpy; print('uv install ok, pyserial', serial.__version__, 'numpy', numpy.__version__)"

echo "== 4. a damaged or swapped wheel is refused"
cp -r wheelhouse-linux damaged
w=$(ls damaged/pyserial-*.whl)   # still a valid zip, but no longer the file that was locked
python3 -c "import sys, zipfile; zipfile.ZipFile(sys.argv[1], 'a').writestr('serial/extra.py', 'print(1)')" "$w"
uv venv --quiet --python 3.14 station-bad
uv pip install --offline --no-index --find-links damaged --require-hashes \
    --python station-bad -r locked-linux.txt 2>&1 | grep -E 'Failed|Hash mismatch' || true

echo "== 5. a requirements.txt compiled on Linux can miss what a Windows station needs"
echo pytest > dev.in
echo "-- compiled for this machine only"
uv pip compile --quiet --python-version 3.12 dev.in | grep -ci colorama || true
echo "-- compiled with --universal"
uv pip compile --quiet --universal --python-version 3.12 dev.in | grep -i colorama
