#pragma once

#include <cstddef>
#include <cstdint>

// Compare a closed file against JSON serialization without a second payload
// buffer. Failure stays latched even if the serializer attempts more writes.
template <typename Reader>
class JsonFileVerifier {
   public:
    explicit JsonFileVerifier(Reader& reader) : reader_(reader) {}
    std::size_t write(std::uint8_t value) { return write(&value, 1); }
    std::size_t write(const std::uint8_t* bytes, std::size_t length) {
        if (failed_) return 0;
        for (std::size_t index = 0; index < length; ++index) {
            const int value = reader_.read();
            if (value < 0 || static_cast<std::uint8_t>(value) != bytes[index]) {
                failed_ = true;
                return index;
            }
            ++verified_;
        }
        return length;
    }
    bool complete(std::size_t expected) {
        return !failed_ && verified_ == expected && reader_.read() == -1;
    }
   private:
    Reader& reader_;
    std::size_t verified_ = 0;
    bool failed_ = false;
};
