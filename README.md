# Python Beside C: companion code

Source code for Book 2 of 2, "Python Beside C" (C. Paul Gordon, October 2026). Every listing in the
book comes from this repository, and every example was run as written. Book 1, "From Embedded C to
Python", has its own repository (`embedded-c-to-python`) with the language, data model, concurrency,
testing and host-tool code. This repository holds the code that calls C, is called from C, or ships
next to C: ctypes and cffi, embedding, C and C++ extensions, CMake, standalone builds, networking,
PDFs and PySide6 GUIs.

The `frametool` package here is the same package as in Book 1 with a C extension added: Book 1 builds
it with `uv_build` as pure Python, and this repository builds it with scikit-build-core and CMake.
Some files are reserve material, code from sections that were removed from the original single volume.
Their code still runs. The rows below that say "reserve" are that code.

## Layout

| Path | Book phase | What it is |
|---|---|---|
| `snippets/bitfield_layout.py` | 1 | One packed C struct with bit fields compiled with `cc`, then the same fields in ctypes with and without `_layout_ = "ms"`: 3 bytes under GCC and on 3.12, 4 bytes on 3.14 |
| `snippets/ctypes_demo.py` | 1 | Calling a C shared library and mirroring a packed struct with ctypes |
| `native-api/` | 1 | The same C driver API (opaque handle, callback, union, bit fields, 3 error conventions) from ctypes (`ctypes_adc.py`) and from cffi in API mode (`build_cffi.py`, `cffi_adc.py`); `adc.c` and `adc.h` are the C side |
| `snippets/zero_copy.py` | 1 | Which views of a receive buffer copy and which share (`bytearray` and `memoryview` slices, `unpack_from`, ctypes `from_buffer`, `numpy.frombuffer`, `recv_into`), the read-only and resizing rules, and what a copy costs on a 1 MiB buffer |
| `snippets/protocol_bench.py` | 1 | A timing of struct, shifts, `int.from_bytes`, a ctypes overlay, construct and NumPy on one 9-byte record and on a 252-byte frame, with the cost of the timing harness and a like-for-like `iter_unpack` maximum row |
| `snippets/numpy_vs_loop.py` | 1 | NumPy and scipy.signal against pure-Python loops on a 1,000,000-sample ADC capture: RMS, a Butterworth low-pass, an FFT peak, and a 15-sample frame where NumPy is slower |
| `snippets/ownership_demo.py` | 1 | Reference counting, cycles and `weakref`, `with` and `ExitStack` against C++ smart pointers, and bytes per record for classes, `__slots__`, dataclasses and tuples |
| `snippets/gc_pause.py` | 1 | Garbage-collector pauses with a large live data set, `gc.freeze()` and `gc.disable()` |
| `snippets/thread_safety/` | 1 | `fw_describe.c` (a function with a static buffer and one with a caller buffer) and `thread_safety.py`, which calls both from four threads: wrong results with the static buffer on every build, none with a lock or a caller buffer. Build line in the script; `tsan_demo.c` and `tsan_run.sh` run the same functions and a counter under `-fsanitize=thread` and print the first report of each case |
| `snippets/editor/vscode-config.sh` | 1 | `capture` copies the user settings, shortcuts and the list of installed extensions of VS Code into a repository, and `apply` copies them back and installs the missing extensions (same script as Book 1; `CODE=` and `USER_DIR=` override the command and the folder) |
| `frametool-py/.vscode/` | 1 | Editor files for the mixed project: settings (pytest, Ruff, clangd on `build/compile_commands.json`, C/C++ IntelliSense off), recommended extensions, tasks (configure, build, test, wait for debugger) and launch entries (debugpy launch and attach, gdb attach, a compound for both) |
| `snippets/logging_boundary/` | 1 | `fw_log.c` (a library that logs through a callback and through `printf`, and calls the callback from a thread it creates) and `logging_boundary.py`: the order of Python and C lines on a pipe under four settings, the callback into `logging`, and a callback that raises. Build line in the script |
| `snippets/crash_demo.py` | 1 | A segmentation fault through ctypes and the Python stack that `python -X faulthandler` prints |
| `embedding/` | 1 | A C test sequencer that embeds Python: `sequencer.c` starts the interpreter in isolated mode, registers the firmware's `crc16_ccitt()` as a module, calls rules in `limits.py` and calls a third check from a worker thread; `init_probe.c` and `gil_block.c` with `embed_traps.sh` and `embed_gil_block.sh` show the start-up rules (`init_probe` also has `where`, `pinned` and `sleep` modes for the `PATH` and SIGINT results; `embed_traps.sh` takes the interpreter to link with as its third argument); CMake with `Development.Embed`, two CTest entries, and `gdbcmds`, a gdb script that stops in the CRC function |
| `freethreading/` | 1 | A C extension with shared state in 3 versions (plain `++`, atomic, `PyMutex`), built as `_counter` (declares free-threaded support) and `_counter_gil` (does not), and a script that runs 4 threads on 3.14 and on 3.14t; `bump_callback` and `freethreading_callback.py` show updates lost when the C code calls back into Python while the GIL is held |
| `snippets/ctypes_checklist.py` | reserve | A small C helper compiled with gcc and called through ctypes: buffers, pointers, `restype`, `char *` ownership, `CDLL` against `PyDLL`, `errno`, 32-bit libraries |
| `frametool-py/` | 1, 2 | The `frametool` package with its C extension: COBS/CRC framing, `native/crc16.c` and `native/crc16_module.c` built with CMake via scikit-build-core, a `crc16_native` fallback import, a type stub, `bench/crc_bench.py` (pure-Python CRC against the C extension; needs the extension built), `bench/crc_c_compare.c` (table-driven against bitwise C on the same image) a pytest suite of 27 tests, and `abi3_check.sh` (builds one stable-ABI wheel with `-C wheel.py-api=cp312` and installs it on Python 3.12, 3.14 and 3.15; needs uv and those interpreters) |
| `firmware-tree/` | 2 | A firmware-style CMake tree (`lib/` holds the portable library target `fw_core`, `app/` is a stand-in firmware image) and a Python extension, `fwcore`, built from the same target with scikit-build-core (`python/`, `pyproject.toml`); `check.sh` builds both, prints what differs and prints the compile flags of `fw_core` when `uv build --wheel` builds it |
| `frametool-py/cross/` | 2 | `aarch64.cmake` (a CMake toolchain file for a 64-bit Arm Linux target) and `py-aarch64` (a wrapper that runs the target's Python under `qemu-aarch64`); the build line and the checks are in the book |
| `snippets/standalone/` | 2 | `crc_tool.py` and scripts that build it as a zipapp, a PyInstaller one-file executable, a PyInstaller one-folder build and a Nuitka executable, and check them (`check_exe.sh` prints sizes in MiB and start-up times to stdout) |
| `snippets/venv/offline_install.sh` | 2 | A hash-locked wheelhouse with one lock per kind of station for Linux and Windows, installed with the network cut, a changed wheel refused |
| `snippets/extras/tcp_nodelay.py`, `tcp_user_timeout.py` | 3 | A write, write, read exchange over loopback with and without `TCP_NODELAY` (about 44 ms against 0.05 ms), and `TCP_USER_TIMEOUT` of 3000 ms and 10000 ms after an `nft` rule drops the packets (Linux, root, run inside `unshare -n` so the rule stays in a new network namespace) |
| `snippets/extras/sockets_demo.py`, `status_server.py`, `http_client.py`, `fastapi_*.py`, `flask_*.py`, `slow_*.py`, `footprint.sh`, `count_lines.py` | 3 | UDP discovery (replies with a bad `tcp_port` are skipped and the source address cannot be spoofed in the reply), TCP commands, HTTP servers and clients, and the Flask and FastAPI comparison (validation, a blocking C call under each server, install size) |
| `snippets/security/tls_private_ca.py`, `mqtt_telemetry.py` | 3 | `tls_private_ca.py` (a private CA, a TLS server and clients), `mqtt_telemetry.py` (paho-mqtt 2.x against mosquitto; checks `is_published()` after `wait_for_publish()`), `mqtt_will_timing.py` (how long the broker takes to publish a will after a node freezes; not in the book listings), `tls_fleet_cases.py` (certificates with one fault each: IP address, dates, key usage, no SAN; mutual TLS; a stalled client in front of an HTTPS server; not in the book listings) and `mqtt_sessions.py` (clean and persistent sessions, QoS downgrade, retained messages across a broker restart; not in the book listings) |
| `snippets/extras/make_report_pdf.py`, `modify_pdf.py`, `snippets/files/data/` | 4 | Create (with `invariant=1`, so equal input gives equal bytes; limits from `limits.toml`, results from `results.csv`, both copied from Book 1), stamp, merge, encrypt and read PDFs |
| `snippets/gui/` | 5 | PySide6 GUIs: form, live telemetry viewer, background worker (the worker is deleted on the GUI thread, not with `deleteLater` from its own thread), results table, pytest-qt tests (the `device` fixture kills its server in a `finally` block; `snippets/pyproject.toml` sets `timeout = 30`) |
| `nanobind-demo/` | Appendix A | A C++ record log wrapped with nanobind, as the package `telemetry_log` (scikit-build-core, CMake, a generated type stub, 18 pytest tests, numpy in the dev group): exception translation, `unique_ptr` and `shared_ptr` ownership, a reference that keeps its owner alive, and `noconvert()` so that only a C-contiguous uint8 buffer is accepted |
| `nanobind-demo/gil_check/` | Appendix A | A 300 ms C++ call that holds the GIL and one that releases it with `nb::call_guard<nb::gil_scoped_release>()`, and a counter thread that shows the difference (build tools pinned with `==`) |
| `snippets/security/signing_demo.py` | reserve | `signing_demo.py` (Ed25519 manifest) |
| `snippets/security/sbom_list.py`, `sbom_demo/` | 2 | A CycloneDX 1.5 SBOM from `uv export --format cyclonedx1.5` for a project with three dependencies, listed by `sbom_list.py` (components, package URLs, files and SHA-256 hashes per component), and the same lock with `--exclude-newer 2026-04-01` |
| `snippets/fw_pytest/` | 2 | Firmware C under pytest: `build_host.sh` builds `cobs.c`, `crc16.c` and `sensor.c` three ways (plain, `-fsanitize=address,undefined`, `--coverage`), `fw.py` loads them with cffi ABI mode and passes a Python function as the ADC through the `sensor_hw_t` table, `test_fw.py` (6 tests, including a Hypothesis differential test of the firmware COBS against `frametool.cobs`), `asan_demo.py` (a heap overflow caught by ASan, run under `LD_PRELOAD`) and `coverage.sh` (gcov line and branch figures) |
| `snippets/flashtool/` | 2 | `flashtool.py`: a firmware download over the frametool link with 128-byte addressed blocks, ACK and NAK with sequence numbers, retries, a SHA-256 image digest and `FlashAborted`; `FakeBootloader` on a socket pair, `flash_demo.py` and `test_flashtool.py` (5 tests) |
| `snippets/testing/gcov_demo.sh` | reserve | C line coverage of the frametool extension with gcov, run on a copy of `frametool-py` |

## Requirements

- Python 3.12 or later (examples were run on 3.14 and 3.12)
- [uv](https://docs.astral.sh/uv/)
- CMake 3.21+ and a C compiler (for the frametool C extension and the embedding example)
- gdb (optional, for `embedding/gdbcmds`)
- mosquitto (optional, for `snippets/security/mqtt_telemetry.py` and `mqtt_sessions.py`)
- A C++17 compiler (for `nanobind-demo`) and the free-threaded interpreter (optional, for `freethreading`: `uv python install 3.14t`)

## Quick start

```bash
# The frametool package: builds the C extension with CMake, then tests and checks it
cd frametool-py
uv sync
uv run pytest -q                        # includes the Hypothesis property tests
uv run ruff check . && uv run mypy src tests
uv run python -m frametool              # live demo for 3 seconds

# Same package, CMake driving Python (CTest runs the pytest suite)
cmake -S . -B build -G Ninja -DPython_EXECUTABLE=$PWD/.venv/bin/python
cmake --build build && ctest --test-dir build

# The C program that embeds Python (build against the interpreter you want to embed)
cd ../embedding
cmake -S . -B build -DPython_EXECUTABLE=$(which python3.14)
cmake --build build && ./build/sequencer . ; ctest --test-dir build   # exit status 1 is expected: 3 checks do not pass on purpose
gdb -batch -x gdbcmds ./build/sequencer                               # needs a Debug build: -DCMAKE_BUILD_TYPE=Debug

# C++ wrapped with nanobind
cd ../nanobind-demo
uv sync                                  # builds the extension with scikit-build-core and CMake
uv run pytest -q && uv run python telemetry_log_demo.py
uv run ruff check . && uv run mypy --strict telemetry_log_demo.py tests
# if a C++ edit does not show up: uv sync --reinstall-package telemetry-log --no-cache
cd gil_check && uv venv && uv pip install . && .venv/bin/python run.py   # holds against releases the GIL; cd .. afterwards

# The same C API from ctypes and from cffi
cd ../native-api
cmake -S . -B build && cmake --build build
uv run python ctypes_adc.py build/libadc.so
uv run python build_cffi.py && uv run python cffi_adc.py     # compiles adc.c into _adc_cffi
uv run ruff check . && uv run mypy ctypes_adc.py cffi_adc.py build_cffi.py

# A firmware CMake tree, built as firmware and as a Python module from one library target
cd ../firmware-tree
cmake -S . -B build-fw && cmake --build build-fw && ctest --test-dir build-fw
uv sync && uv run pytest -q              # builds fwcore with scikit-build-core from ../lib
uv build --out-dir dist                  # sdist, then a wheel built from the sdist

# Shared state in a C extension, built once per interpreter
cd ../freethreading
cmake -S . -B build14t -DPython_EXECUTABLE=$(which python3.14t) && cmake --build build14t
PYTHONPATH=build14t python3.14t freethreading_demo.py _counter      # plain ++ loses updates here
PYTHONPATH=build14t python3.14t freethreading_demo.py _counter_gil  # the GIL is turned back on

# Everything else
cd ../snippets
uv sync
uv run python bitfield_layout.py
uv run python zero_copy.py
uv run python numpy_vs_loop.py && uv run python ownership_demo.py && uv run python protocol_bench.py && uv run python gc_pause.py
uv run python -X faulthandler crash_demo.py        # crashes on purpose: prints the Python stack, exit status 139
uv run python ctypes_checklist.py   # reserve
(cd thread_safety && cc -shared -fPIC -O2 -o libfw_describe.so fw_describe.c && uv run python thread_safety.py)
bash venv/offline_install.sh                        # needs network access to PyPI; writes to /tmp
(cd security && uv run python tls_private_ca.py && uv run python mqtt_telemetry.py && uv run python tls_fleet_cases.py && uv run python mqtt_sessions.py)
(cd security && uv run python signing_demo.py)   # reserve
bash testing/gcov_demo.sh ../frametool-py   # reserve; needs cmake, gcc and network access to PyPI

cd standalone                            # needs a C compiler for the Nuitka step; writes ./build
bash build_exe.sh && bash check_exe.sh
cd ..

cd extras                                # PDF scripts write ./out
uv run python sockets_demo.py
uv run python tcp_nodelay.py
unshare -n sh -c 'ip link set lo up && uv run python tcp_user_timeout.py'   # Linux, root; needs nft
uv run python http_client.py             # starts the stdlib status server on a free port
uv run python fastapi_check.py           # starts uvicorn on 127.0.0.1:8765
uv run python flask_check.py             # Flask's test client, no server
uv run python slow_compare.py            # 20 concurrent requests to four server setups, about 1 minute
sh footprint.sh                          # installs each stack into an empty environment
uv run python make_report_pdf.py && uv run python modify_pdf.py
cd ..

cd gui
uv run python device_server.py 5555 &    # simulated device for the viewer
uv run python telemetry_viewer.py
QT_QPA_PLATFORM=offscreen uv run pytest -q   # headless GUI tests
```

The firmware tests and the download tool (Phase 2). The first block needs gcc, pytest, cffi and Hypothesis; the second needs only the Python files:

```bash
cd snippets/fw_pytest
sh build_host.sh && FW_LIB=build/libfw_plain.so pytest -q   # builds build/libfw_*.so, runs 6 tests
FW_LIB=build/libfw_san.so LD_PRELOAD=$(gcc -print-file-name=libasan.so) PYTHONMALLOC=malloc python asan_demo.py
sh coverage.sh
cd ../flashtool
python flash_demo.py && pytest -q
```

The ctypes example needs the CRC as a shared library:

```bash
cc -shared -fPIC -O2 -o build/libcrc16.so frametool-py/native/crc16.c   # from the repository root
uv run --project snippets python snippets/ctypes_demo.py build/libcrc16.so
```

## Notes

- All servers bind to `127.0.0.1`. The only authentication or TLS is in `snippets/security/`: a private certificate authority created at run time for `tls_private_ca.py`, and the signing keys of `signing_demo.py` (reserve), which are generated in memory and are not meant for a product.
- `frametool-py/uv.lock` and `snippets/uv.lock` pin the exact versions the examples were run with
  (Python 3.14, PySide6 6.12, FastAPI 0.162, Flask 3.1, pypdf 6.20, ReportLab 5.0, among others).
- Code quality gates used for the book: `ruff check`, `ruff format --check` and
  `mypy --strict` (GUI tests excepted, as pytest-qt is untyped).
- Licence: MIT. See `LICENSE`.
