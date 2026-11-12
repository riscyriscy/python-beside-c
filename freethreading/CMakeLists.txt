cmake_minimum_required(VERSION 3.21)
project(counter LANGUAGES C)

find_package(Python 3.13 REQUIRED COMPONENTS Interpreter Development.Module)

# _counter declares that it is safe without the GIL. _counter_gil does not, so a free-threaded
# interpreter turns the GIL back on when it imports it.
python_add_library(_counter MODULE WITH_SOABI counter_module.c)
target_compile_definitions(_counter PRIVATE MODULE_NAME=_counter DECLARE_NO_GIL)

python_add_library(_counter_gil MODULE WITH_SOABI counter_module.c)
target_compile_definitions(_counter_gil PRIVATE MODULE_NAME=_counter_gil)

target_compile_options(_counter PRIVATE -Wall -Wextra)
target_compile_options(_counter_gil PRIVATE -Wall -Wextra)
