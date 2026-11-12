# Portable firmware code: no registers, no RTOS, no operating-system calls.
# Anything that touches hardware belongs in another directory with its own target.
option(FW_WERROR "Treat warnings as errors in the firmware library" ON)

add_library(fw_core STATIC src/crc16.c src/cobs.c)
add_library(fw::core ALIAS fw_core)

target_include_directories(fw_core PUBLIC include)
target_compile_features(fw_core PUBLIC c_std_11)
target_compile_definitions(fw_core PUBLIC FW_MAX_FRAME=256)   # a setting every user of the library sees

# The library's own policy: PRIVATE, so it is not passed on to the code that links it
target_compile_options(fw_core PRIVATE -Wall -Wextra -Wconversion -ffunction-sections -fdata-sections)
if(FW_WERROR)
  target_compile_options(fw_core PRIVATE -Werror)
endif()
