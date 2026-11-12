# The Python extension. It builds the firmware's library target from ../lib and adds one binding file.
cmake_minimum_required(VERSION 3.21)
project(fwcore_python LANGUAGES C)

find_package(Python 3.12 REQUIRED COMPONENTS Interpreter Development.Module)

# A compiler newer than the firmware's must not break the Python build over a new warning
set(FW_WERROR OFF CACHE BOOL "" FORCE)

# The firmware's own target: nothing is copied and no source file is listed a second time.
# The second argument is the binary directory, which is needed because ../lib is outside this tree.
add_subdirectory(${CMAKE_CURRENT_SOURCE_DIR}/../lib fw_lib)

# Linking a static library into a shared module needs position-independent code, and the library
# must not export its symbols from the module. The firmware build is left as it is: it sets neither.
set_target_properties(fw_core PROPERTIES POSITION_INDEPENDENT_CODE ON C_VISIBILITY_PRESET hidden)

python_add_library(_fwcore MODULE WITH_SOABI src/_fwcore.c)
target_link_libraries(_fwcore PRIVATE fw_core)
set_target_properties(_fwcore PROPERTIES C_VISIBILITY_PRESET hidden)

install(TARGETS _fwcore LIBRARY DESTINATION fwcore)
