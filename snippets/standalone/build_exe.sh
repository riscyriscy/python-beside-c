#!/usr/bin/env bash
# Build 4 distributable forms of crc_tool.py. Build on the operating system that the users have:
# none of these tools cross-compile. Run: bash build_exe.sh
set -euo pipefail
rm -rf build && mkdir -p build/app

# 1. zipapp (standard library): one .pyz file. Needs Python 3 on the target. Pure Python only,
#    because a zip file cannot hold compiled extension modules.
cp crc_tool.py build/app/
python3 -m zipapp build/app -o build/crc_tool.pyz -p "/usr/bin/env python3" -m "crc_tool:cli"

# 2. PyInstaller: bundles the interpreter, the libraries and your code. No Python needed.
#    --onefile unpacks to a temporary folder at each start. --onedir makes a folder instead.
uvx pyinstaller --onefile --noconfirm --name crc_tool \
    --distpath build/exe --workpath build/work --specpath build crc_tool.py
uvx pyinstaller --onedir --noconfirm --name crc_tool \
    --distpath build/exe_dir --workpath build/work_dir --specpath build crc_tool.py

# 3. Nuitka: translates the code to C and compiles it. Needs a C compiler. Slower build.
uvx --with patchelf nuitka --onefile --assume-yes-for-downloads --output-dir=build/nuitka \
    --output-filename=crc_tool_nuitka crc_tool.py
