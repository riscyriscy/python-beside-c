cmake_minimum_required(VERSION 3.21)
project(adc LANGUAGES C)

# libadc.so for the ctypes example. The cffi example compiles adc.c into its own module.
add_library(adc SHARED adc.c)
target_compile_options(adc PRIVATE -Wall -Wextra)
set_target_properties(adc PROPERTIES C_VISIBILITY_PRESET default)
