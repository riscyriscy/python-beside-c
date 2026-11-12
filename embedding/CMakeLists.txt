cmake_minimum_required(VERSION 3.21)
project(sequencer LANGUAGES C)

# Development.Embed = headers plus libpython to link against
# (Development.Module has no library)
find_package(Python 3.12 REQUIRED COMPONENTS Interpreter Development.Embed)
find_package(Threads REQUIRED)

# The firmware's own crc16.c, compiled into the host program as well
add_executable(sequencer
  sequencer.c
  ../frametool-py/native/crc16.c)
target_include_directories(sequencer PRIVATE ../frametool-py/native)
target_compile_options(sequencer PRIVATE -Wall -Wextra)
target_link_libraries(sequencer PRIVATE Python::Python Threads::Threads)

# Two small programs that show the start-up rules; neither needs the firmware code
add_executable(init_probe init_probe.c)
target_compile_options(init_probe PRIVATE -Wall -Wextra)
target_link_libraries(init_probe PRIVATE Python::Python)
add_executable(gil_block gil_block.c)
target_compile_options(gil_block PRIVATE -Wall -Wextra)
target_link_libraries(gil_block PRIVATE Python::Python Threads::Threads)

enable_testing()
# The sequencer returns non-zero when a check does not pass, and this demo has
# 3 that do not (a limit, a KeyError and a corrupt frame on purpose), so the
# test matches the summary line
add_test(NAME limits COMMAND sequencer ${CMAKE_CURRENT_SOURCE_DIR})
set_tests_properties(limits PROPERTIES
  PASS_REGULAR_EXPRESSION "not passed: 3, finalize: 0")
# "gil_block save" finishes. "gil_block nosave" waits forever, so it is no test.
add_test(NAME gil_save COMMAND gil_block save)
set_tests_properties(gil_save PROPERTIES TIMEOUT 10)
