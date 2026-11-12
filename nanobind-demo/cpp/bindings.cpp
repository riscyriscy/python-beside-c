// bindings.cpp: the nanobind layer. It is the only file that includes nanobind.
#include <nanobind/nanobind.h>
#include <nanobind/ndarray.h>
#include <nanobind/stl/shared_ptr.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/unique_ptr.h>

#include <cstdint>
#include <string>

#include "telemetry_log.hpp"

namespace nb = nanobind;
using namespace nb::literals;

NB_MODULE(_core, m)
{
    m.doc() = "The compiled part of telemetry_log.";

    // FrameError becomes telemetry_log.FrameError, a subclass of ValueError. std::length_error
    // and std::out_of_range need no line here: nanobind maps them to ValueError and IndexError.
    nb::exception<FrameError>(m, "FrameError", PyExc_ValueError);

    nb::class_<Record>(m, "Record")
        .def(nb::init<std::uint32_t, std::int16_t, std::uint16_t, std::uint8_t>(),
             "timestamp_ms"_a, "temperature_cdeg"_a, "supply_mv"_a, "status"_a)
        .def_ro("timestamp_ms", &Record::timestamp_ms)
        .def_ro("temperature_cdeg", &Record::temperature_cdeg)
        .def_ro("supply_mv", &Record::supply_mv)
        .def_ro("status", &Record::status)
        .def("__repr__", [](const Record& r) {
            return "Record(" + std::to_string(r.timestamp_ms) + " ms, " +
                   std::to_string(r.temperature_cdeg) + " cdeg, " + std::to_string(r.supply_mv) +
                   " mV, status " + std::to_string(r.status) + ")";
        });

    // Any C-contiguous uint8 buffer: bytes, bytearray, memoryview, array.array('B'), a uint8
    // NumPy array. noconvert() makes any other dtype or a strided view raise TypeError; without
    // it nanobind converts them (a copy that decodes the wrong bytes).
    m.def("decode_record",
          [](nb::ndarray<const std::uint8_t, nb::ndim<1>, nb::c_contig> data) {
              return decode_record(data.data(), data.size());
          },
          "data"_a.noconvert(),
          // The stub says Buffer, not "a NumPy array": the function takes a uint8 buffer
          nb::sig("def decode_record(data: collections.abc.Buffer, /) -> Record"));

    nb::class_<RecordLog>(m, "RecordLog")
        .def(nb::init<std::size_t>(), "capacity"_a)
        .def("add", &RecordLog::add, "record"_a)
        // A reference into the log's storage: the returned Record keeps the log alive. The
        // element address stays valid only because the vector never reallocates (reserve() in
        // the constructor, and add() throws when full)
        .def("at", &RecordLog::at, "index"_a, nb::rv_policy::reference_internal)
        .def("__len__", &RecordLog::size)
        .def_prop_ro("crc", &RecordLog::crc);

    m.def("live_logs", [] { return live_logs; });  // for tests: C++ objects that still exist

    m.def("make_log", &make_log, "capacity"_a);  // std::unique_ptr: Python becomes the sole owner

    nb::class_<Recorder>(m, "Recorder")
        .def(nb::init<std::shared_ptr<RecordLog>>(), "log"_a)  // shares ownership with Python
        .def_prop_ro("log", &Recorder::log)
        .def("record", &Recorder::record, "record"_a);
}
