#!/usr/bin/env bash
# Builds the same library target twice, as firmware and as a Python module, and shows the differences.
# Run `uv sync` first. Writes build-fw/ and build-py/ here and a scratch copy under /tmp.
set -eu
cd "$(dirname "$0")"
PY=$(uv run python -c 'import sys; print(sys.executable)')

echo "== firmware build =="
cmake -S . -B build-fw > /dev/null
cmake --build build-fw > /dev/null
ctest --test-dir build-fw 2> /dev/null | grep -E "Test +#|tests passed"
./build-fw/fw_app

echo; echo "== Python build: only lib/ and python/ are read =="
cmake -S python -B build-py -DPython_EXECUTABLE="$PY" > /dev/null
cmake --build build-py > /dev/null
echo "symbols exported by the module:"
nm -D build-py/_fwcore*.so | grep ' T ' | awk '{print "  " $3}'

echo; echo "== compile flags of fw_core in each build =="
for d in build-fw/lib build-py/fw_lib; do
    echo "$d:"
    grep -E '^C_(DEFINES|FLAGS)' "$d/CMakeFiles/fw_core.dir/flags.make" | sed 's/^/  /'
done

echo; echo "== compile flags of fw_core when uv builds the wheel =="
wheels=$(mktemp -d)
uv build --wheel --out-dir "$wheels" -C build.verbose=true 2>&1 | grep -m 1 'crc16.c.o -c' \
    | tr ' ' '\n' | grep -E '^-(O|DNDEBUG|fPIC|fvis|W|ffunc|fdata)' | tr '\n' ' ' | sed 's/^/  /'
echo
rm -rf "$wheels"

echo; echo "== the same module without the set_target_properties line =="
scratch=$(mktemp -d)
cp -r lib python "$scratch"
sed -i '/set_target_properties(fw_core/d' "$scratch/python/CMakeLists.txt"
cmake -S "$scratch/python" -B "$scratch/b" -DPython_EXECUTABLE="$PY" > /dev/null
cmake --build "$scratch/b" > /dev/null
echo "symbols exported by the module:"
nm -D "$scratch"/b/_fwcore*.so | grep ' T ' | awk '{print "  " $3}'
rm -rf "$scratch"

echo; echo "== tests =="
uv run pytest -q 2>&1 | tail -1
