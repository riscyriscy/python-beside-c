// telemetry_log.hpp: a C++ utility as a firmware repository might already have it.
// Nothing here knows about Python.
#pragma once

#include <cstddef>
#include <cstdint>
#include <memory>
#include <stdexcept>
#include <string>
#include <vector>

extern "C" {
#include "crc16.h"  // the firmware's CRC, plain C
}

constexpr std::size_t kRecordBytes = 9;  // telemetry_t on the wire, little endian

struct Record {
    std::uint32_t timestamp_ms;
    std::int16_t temperature_cdeg;
    std::uint16_t supply_mv;
    std::uint8_t status;
};

// Thrown for bytes that are not a valid record.
class FrameError : public std::runtime_error {
public:
    using std::runtime_error::runtime_error;
};

inline Record decode_record(const std::uint8_t* d, std::size_t len)
{
    if (len != kRecordBytes) {
        throw FrameError("a record is 9 bytes, got " + std::to_string(len));
    }
    if (d[8] & 0xF0) {
        throw FrameError("reserved status bits are set");
    }
    const std::uint32_t t = d[0] | d[1] << 8 | d[2] << 16 | static_cast<std::uint32_t>(d[3]) << 24;
    return Record{
        t,
        static_cast<std::int16_t>(d[4] | d[5] << 8),
        static_cast<std::uint16_t>(d[6] | d[7] << 8),
        d[8],
    };
}

inline int live_logs = 0;  // how many RecordLog objects exist right now, so a test can see destruction

// Owns its records. at() returns a reference into the log's own storage.
class RecordLog {
public:
    explicit RecordLog(std::size_t capacity) : capacity_(capacity)
    {
        records_.reserve(capacity);
        ++live_logs;
    }
    RecordLog(const RecordLog&) = delete;
    RecordLog& operator=(const RecordLog&) = delete;
    ~RecordLog() { --live_logs; }

    void add(const Record& r)
    {
        if (records_.size() == capacity_) {
            throw std::length_error("the log is full");
        }
        records_.push_back(r);
    }
    const Record& at(std::size_t i) const { return records_.at(i); }  // std::out_of_range
    std::size_t size() const noexcept { return records_.size(); }

    // CRC-16 over all records, each in its 9-byte wire form
    std::uint16_t crc() const
    {
        std::vector<std::uint8_t> wire;
        for (const Record& r : records_) {
            const std::uint8_t b[kRecordBytes] = {
                std::uint8_t(r.timestamp_ms), std::uint8_t(r.timestamp_ms >> 8),
                std::uint8_t(r.timestamp_ms >> 16), std::uint8_t(r.timestamp_ms >> 24),
                std::uint8_t(r.temperature_cdeg), std::uint8_t(r.temperature_cdeg >> 8),
                std::uint8_t(r.supply_mv), std::uint8_t(r.supply_mv >> 8), r.status,
            };
            wire.insert(wire.end(), b, b + kRecordBytes);
        }
        return crc16_ccitt(wire.data(), wire.size());
    }

private:
    std::size_t capacity_;
    std::vector<Record> records_;
};

// A factory that hands the caller sole ownership
inline std::unique_ptr<RecordLog> make_log(std::size_t capacity)
{
    return std::make_unique<RecordLog>(capacity);
}

// Shares ownership of a log with whoever else holds it
class Recorder {
public:
    explicit Recorder(std::shared_ptr<RecordLog> log) : log_(std::move(log)) {}
    std::shared_ptr<RecordLog> log() const { return log_; }
    void record(const Record& r) { log_->add(r); }

private:
    std::shared_ptr<RecordLog> log_;
};
