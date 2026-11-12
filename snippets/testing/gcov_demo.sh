#!/usr/bin/env bash
# Line and branch coverage of the firmware's crc16.c, measured with gcov under pytest.
# Run: bash gcov_demo.sh ../../frametool-py   (needs uv, cmake, gcc, access to PyPI)
set -eu
src=$(realpath "${1:?path of frametool-py}")
demo=${DEMO_DIR:-/tmp/gcov_demo}
rm -rf "$demo" && mkdir -p "$demo/frametool-py" && cd "$demo/frametool-py"
export UV_CACHE_DIR="$demo/cache"
tar -C "$src" --exclude=.venv --exclude=.hypothesis --exclude=.pytest_cache \
    --exclude=__pycache__ -cf - . | tar -xf -

echo "== 1. build the extension with --coverage"
uv sync --quiet --no-install-project
cmake -S . -B build -DCMAKE_C_FLAGS=--coverage \
    -DPython_EXECUTABLE="$PWD/.venv/bin/python" > cmake.log
cmake --build build | grep -E 'native/crc16.c.o|Built target'

echo "== 2. run the pytest suite; the .gcda counters are written when Python exits"
PYTHONPATH=src .venv/bin/python -m pytest -q -p no:cacheprovider | tail -1

echo "== 3. gcov on crc16.c"
gcov -n -b build/CMakeFiles/_crc16.dir/native/crc16.c.gcda | head -4
