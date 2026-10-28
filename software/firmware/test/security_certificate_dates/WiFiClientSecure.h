#pragma once
#include <stddef.h>
#include <stdint.h>

struct mbedtls_x509_time { int year, mon, day, hour, min, sec; };
struct mbedtls_x509_buf { unsigned char *p; size_t len; };
struct mbedtls_x509_crt {
    int version;
    mbedtls_x509_buf raw;
    mbedtls_x509_time valid_from, valid_to;
    mbedtls_x509_crt *next;
};
struct IPAddress {};
struct Client {
    virtual ~Client() = default;
    virtual int connect(const char *, uint16_t) = 0;
    virtual int connect(const char *, uint16_t, int32_t) = 0;
    virtual int connect(IPAddress, uint16_t) = 0;
    virtual int connect(IPAddress, uint16_t, int32_t) = 0;
    virtual size_t write(const uint8_t *, size_t) = 0;
};
class WiFiClientSecure : public Client {
   public:
    const mbedtls_x509_crt *peer = nullptr;
    bool baseHandshakeSucceeds = true;
    bool open = false;
    unsigned handshakes = 0, stops = 0, writes = 0, peerReads = 0;
    int connect(const char *, uint16_t) override { return handshake(); }
    int connect(IPAddress, uint16_t) override { return handshake(); }
    // Match the real SDK's virtual delegation for timeout overloads.
    int connect(const char *host, uint16_t port, int32_t) override {
        return connect(host, port);
    }
    int connect(IPAddress address, uint16_t port, int32_t) override {
        return connect(address, port);
    }
    void stop() { ++stops; open = false; }
    const mbedtls_x509_crt *getPeerCertificate() { ++peerReads; return peer; }
    size_t write(const uint8_t *, size_t length) override {
        if (!open) return 0;
        ++writes;
        return length;
    }
   private:
    int handshake() {
        ++handshakes;
        if (!baseHandshakeSucceeds) return 0;
        open = true;
        return 1;
    }
};
