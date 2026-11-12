#include <nanobind/nanobind.h>
#include <chrono>
#include <thread>

namespace nb = nanobind;

static void work(int ms) { std::this_thread::sleep_for(std::chrono::milliseconds(ms)); }

NB_MODULE(gilmod, m)
{
    m.def("hold", &work);  // the GIL stays held while the C++ code runs
    m.def("release", &work, nb::call_guard<nb::gil_scoped_release>());
}
