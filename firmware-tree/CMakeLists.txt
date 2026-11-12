# The firmware's own build (here a host stand-in for the firmware image).
# Project-wide policy lives in this file. The Python build never reads it: it takes lib/ only.
cmake_minimum_required(VERSION 3.21)
project(fw_demo LANGUAGES C)

add_compile_options(-Os)          # firmware-wide: applies to everything below this line

add_subdirectory(lib)

add_executable(fw_app app/main.c)
target_link_libraries(fw_app PRIVATE fw_core)

enable_testing()
add_test(NAME fw_app COMMAND fw_app)
