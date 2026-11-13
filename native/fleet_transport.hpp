#pragma once
#include <string>
#include <cstdint>
#include <vector>
#include <deque>
#include <cstddef>
namespace fleet {
// Local companion connection only. No LAN address, code loading, or game memory access.
class Transport {
public:
    static const std::size_t maxLine=524288, maxQueued=1048576;
    Transport(); ~Transport();
    Transport(const Transport&)=delete; Transport& operator=(const Transport&)=delete;
    bool start();
    bool send(const std::string& message);
    std::vector<std::string> poll();
    void close();
    bool connected() const { return connected_; }
    const std::string& error() const { return error_; }
private:
    std::intptr_t socket_;
    bool connecting_=false, connected_=false, startup_=false;
    std::string input_, error_;
    std::deque<std::string> output_;
    std::size_t offset_=0, queued_=0;
    void fail(const char* reason);
};
}
