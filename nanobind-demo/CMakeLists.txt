cmake_minimum_required(VERSION 3.21)
project(telemetry_log LANGUAGES C CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# The firmware's crc16.c and crc16.h. In a real repository this is the firmware's own directory.
set(FIRMWARE_DIR "${CMAKE_CURRENT_SOURCE_DIR}/../frametool-py/native"
    CACHE PATH "Directory with crc16.c")

# Development.Module = headers for building an extension (no libpython to link)
find_package(Python 3.12 REQUIRED COMPONENTS Interpreter Development.Module)
execute_process(COMMAND "${Python_EXECUTABLE}" -m nanobind --cmake_dir
                OUTPUT_VARIABLE nanobind_DIR OUTPUT_STRIP_TRAILING_WHITESPACE COMMAND_ERROR_IS_FATAL ANY)
find_package(nanobind CONFIG REQUIRED)

# The compiled module is telemetry_log._core; src/telemetry_log/__init__.py re-exports it
nanobind_add_module(_core cpp/bindings.cpp "${FIRMWARE_DIR}/crc16.c")
target_include_directories(_core PRIVATE cpp "${FIRMWARE_DIR}")
target_compile_options(_core PRIVATE -Wall -Wextra)

# Type stub: nanobind imports the built module and writes _core.pyi, so that mypy and IDEs see
# the signatures. src/telemetry_log/py.typed tells type checkers that the package is typed.
nanobind_add_stub(_core_stub MODULE _core OUTPUT _core.pyi
                  PYTHON_PATH $<TARGET_FILE_DIR:_core> DEPENDS _core)

if(SKBUILD)
  # pip install, uv sync or uv build: scikit-build-core adds these to the wheel,
  # next to the Python files of src/telemetry_log
  install(TARGETS _core LIBRARY DESTINATION telemetry_log)
  install(FILES "${CMAKE_CURRENT_BINARY_DIR}/_core.pyi" DESTINATION telemetry_log)
endif()
