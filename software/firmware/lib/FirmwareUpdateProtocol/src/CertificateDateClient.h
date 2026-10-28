#pragma once

#include <WiFiClientSecure.h>
#include <stddef.h>
#include <stdint.h>
#include <time.h>

namespace firmware {

// Arduino-ESP32 2.0.17 ships mbedTLS with certificate date checks disabled.
// Its x509_time_is_past/future functions are stubs, so compare parsed calendar
// fields here after the normal CA-chain and hostname verification succeeds.
// Profiles that build the SDK with MBEDTLS_HAVE_TIME_DATE (staging V2) reject
// expired and not-yet-valid chain certificates during the handshake and may
// free the peer chain afterwards; they only need a plausible device clock.
#if defined(MBEDTLS_HAVE_TIME_DATE)
constexpr bool SDK_VERIFIES_CERTIFICATE_DATES = true;
#else
constexpr bool SDK_VERIFIES_CERTIFICATE_DATES = false;
#if defined(ARDUINO_ARCH_ESP32) && !defined(MBEDTLS_SSL_KEEP_PEER_CERTIFICATE)
#error "Certificate dates need MBEDTLS_HAVE_TIME_DATE or a retained peer chain"
#endif
#endif
constexpr int64_t MINIMUM_CERTIFICATE_UTC = 1704067200LL;  // 2024-01-01
constexpr int64_t MAXIMUM_CERTIFICATE_UTC = 4102444799LL;  // 2099-12-31
constexpr size_t MAX_PRESENTED_CERTIFICATES = 16;

inline bool certificateClockPlausible(const time_t now) {
    const int64_t seconds = static_cast<int64_t>(now);
    return seconds >= MINIMUM_CERTIFICATE_UTC &&
           seconds <= MAXIMUM_CERTIFICATE_UTC;
}

inline bool certificateCalendarValid(const mbedtls_x509_time &date) {
    if (date.year < 1 || date.year > 9999 || date.mon < 1 || date.mon > 12 ||
        date.day < 1 || date.hour < 0 || date.hour > 23 || date.min < 0 ||
        date.min > 59 || date.sec < 0 || date.sec > 59) {
        return false;
    }
    static constexpr int DAYS_PER_MONTH[] =
        {31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31};
    int days = DAYS_PER_MONTH[date.mon - 1];
    if (date.mon == 2 && date.year % 4 == 0 &&
        (date.year % 100 != 0 || date.year % 400 == 0)) {
        ++days;
    }
    return date.day <= days;
}

inline int compareCertificateCalendar(const mbedtls_x509_time &left,
                                      const mbedtls_x509_time &right) {
    const int leftFields[] =
        {left.year, left.mon, left.day, left.hour, left.min, left.sec};
    const int rightFields[] =
        {right.year, right.mon, right.day, right.hour, right.min, right.sec};
    for (size_t index = 0; index < 6; ++index) {
        if (leftFields[index] < rightFields[index]) return -1;
        if (leftFields[index] > rightFields[index]) return 1;
    }
    return 0;
}

inline bool certificateChainDatesValid(const mbedtls_x509_crt *certificate,
                                      const time_t now) {
    if (certificate == nullptr || !certificateClockPlausible(now)) {
        return false;
    }
    struct tm utc = {};
    if (gmtime_r(&now, &utc) == nullptr) return false;
    const mbedtls_x509_time current = {
        utc.tm_year + 1900, utc.tm_mon + 1, utc.tm_mday,
        utc.tm_hour, utc.tm_min, utc.tm_sec};
    if (!certificateCalendarValid(current)) return false;

    size_t count = 0;
    for (; certificate != nullptr; certificate = certificate->next) {
        if (++count > MAX_PRESENTED_CERTIFICATES || certificate->version < 1 ||
            certificate->version > 3 || certificate->raw.p == nullptr ||
            certificate->raw.len == 0 ||
            !certificateCalendarValid(certificate->valid_from) ||
            !certificateCalendarValid(certificate->valid_to) ||
            compareCertificateCalendar(certificate->valid_from,
                                       certificate->valid_to) > 0 ||
            compareCertificateCalendar(current, certificate->valid_from) < 0 ||
            compareCertificateCalendar(current, certificate->valid_to) > 0) {
            return false;
        }
    }
    return true;
}

class CertificateDateClient : public WiFiClientSecure {
   public:
    using UtcClock = time_t (*)();
    explicit CertificateDateClient(UtcClock clock = systemUtc) : clock_(clock) {}
    CertificateDateClient(const CertificateDateClient &) = delete;
    CertificateDateClient &operator=(const CertificateDateClient &) = delete;

    int connect(const char *host, uint16_t port) override {
        return validateConnection(WiFiClientSecure::connect(host, port));
    }
    int connect(const char *host, uint16_t port, int32_t timeout) override {
        return validateConnection(WiFiClientSecure::connect(host, port, timeout));
    }
    int connect(IPAddress address, uint16_t port) override {
        return validateConnection(WiFiClientSecure::connect(address, port));
    }
    int connect(IPAddress address, uint16_t port, int32_t timeout) override {
        return validateConnection(
            WiFiClientSecure::connect(address, port, timeout));
    }

   private:
    static time_t systemUtc() { return time(nullptr); }
    int validateConnection(const int connected) {
        if (connected != 1) {
            WiFiClientSecure::stop();
            return 0;
        }
        // Inspect the complete presented chain before HTTPClient can send any
        // application data. The peer pointer is owned by the TLS context and
        // must not be retained across another SSL call. Trust anchors in the
        // compressed CA bundle contain keys/names only, not validity dates.
        if (clock_ == nullptr ||
            !(SDK_VERIFIES_CERTIFICATE_DATES
                  ? certificateClockPlausible(clock_())
                  : certificateChainDatesValid(getPeerCertificate(),
                                               clock_()))) {
            WiFiClientSecure::stop();
            return 0;
        }
        return 1;
    }
    const UtcClock clock_;
};

}  // namespace firmware
