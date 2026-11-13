#include <cstdint>
#include "fleet_transport.hpp"
#include <algorithm>
#ifdef _WIN32
#include <winsock2.h>
#include <ws2tcpip.h>
using Sock=SOCKET;
static int lastError(){return WSAGetLastError();}
static bool wouldBlock(int e){return e==WSAEWOULDBLOCK || e==WSAEINPROGRESS;}
static void release(Sock s){closesocket(s);}
static const Sock invalid=INVALID_SOCKET;
#else
#include <sys/socket.h>
#include <sys/select.h>
#include <arpa/inet.h>
#include <fcntl.h>
#include <unistd.h>
#include <cerrno>
using Sock=int;
static int lastError(){return errno;}
static bool wouldBlock(int e){return e==EAGAIN || e==EWOULDBLOCK || e==EINPROGRESS;}
static void release(Sock s){::close(s);}
static const Sock invalid=-1;
#endif
namespace fleet {
Transport::Transport():socket_(static_cast<std::intptr_t>(invalid)) {
#ifdef _WIN32
    WSADATA data;startup_=WSAStartup(MAKEWORD(2,2),&data)==0;
#else
    startup_=true;
#endif
}
Transport::~Transport(){close();
#ifdef _WIN32
    if(startup_)WSACleanup();
#endif
}
void Transport::close(){
    if(static_cast<Sock>(socket_)!=invalid)release(static_cast<Sock>(socket_));
    socket_=static_cast<std::intptr_t>(invalid);connecting_=connected_=false;
    input_.clear();output_.clear();offset_=queued_=0;
}
void Transport::fail(const char* reason){error_=reason;close();}
bool Transport::start(){
    close();error_.clear();if(!startup_){fail("socket initialization failed");return false;}
    Sock s=::socket(AF_INET,SOCK_STREAM,IPPROTO_TCP);
    if(s==invalid){fail("socket creation failed");return false;}socket_=static_cast<std::intptr_t>(s);
#ifdef _WIN32
    u_long on=1;if(ioctlsocket(s,FIONBIO,&on)!=0){fail("nonblocking setup failed");return false;}
#else
    int flags=fcntl(s,F_GETFL,0);
    if(flags<0 || fcntl(s,F_SETFL,flags|O_NONBLOCK)<0){fail("nonblocking setup failed");return false;}
#endif
    sockaddr_in a={};a.sin_family=AF_INET;a.sin_port=htons(38474);a.sin_addr.s_addr=htonl(INADDR_LOOPBACK);
    int ret=::connect(s,reinterpret_cast<sockaddr*>(&a),sizeof(a));
    if(ret==0)connected_=true;
    else if(wouldBlock(lastError()))connecting_=true;
    else {fail("local companion unavailable");return false;}
    return true;
}
bool Transport::send(const std::string& message){
    if(!connected_ || message.empty() || message.size()>maxLine || message.find_first_of("\r\n")!=std::string::npos || message.find('\0')!=std::string::npos)return false;
    const bool scene=message.compare(0,6,"SCENE|")==0;
    // Only the newest unsent scene is useful. Never alter a partially sent line.
    for(auto it=output_.begin();it!=output_.end();){
        if(scene && it->compare(0,6,"SCENE|")==0 && !(it==output_.begin()&&offset_)){
            queued_-=it->size();it=output_.erase(it);
        }else ++it;
    }
    if(output_.size()>=64 || queued_+message.size()+1>(scene?maxQueued-65536:maxQueued))return false;
    auto at=output_.end();
    if(!scene){at=output_.begin();if(offset_&&at!=output_.end())++at;while(at!=output_.end()&&at->compare(0,6,"SCENE|")!=0)++at;}
    output_.insert(at,message+"\n");queued_+=message.size()+1;return true;
}
std::vector<std::string> Transport::poll(){
    std::vector<std::string> messages;Sock s=static_cast<Sock>(socket_);
    if(s==invalid)return messages;
    if(connecting_){
        fd_set w,e;FD_ZERO(&w);FD_ZERO(&e);FD_SET(s,&w);FD_SET(s,&e);timeval wait={0,0};
        int ret=select(static_cast<int>(s)+1,nullptr,&w,&e,&wait);
        if(ret<0){fail("connect polling failed");return messages;}
        if(ret==0)return messages;
        int err=0;
#ifdef _WIN32
        int len=sizeof(err);
#else
        socklen_t len=sizeof(err);
#endif
        if(getsockopt(s,SOL_SOCKET,SO_ERROR,reinterpret_cast<char*>(&err),&len)!=0 || err){fail("local companion refused connection");return messages;}
        connecting_=false;connected_=true;
    }
    // Per-frame budgets prevent an unavailable/malicious companion stalling FTL.
    std::size_t budget=65536;
    while(!output_.empty() && budget){
        const auto& front=output_.front();std::size_t amount=std::min(front.size()-offset_,budget);
#ifdef _WIN32
        int n=::send(s,front.data()+offset_,static_cast<int>(amount),0);
#else
        int n=::send(s,front.data()+offset_,amount,MSG_NOSIGNAL);
#endif
        if(n<0){if(wouldBlock(lastError()))break;fail("send failed");return messages;}
        if(n==0)break;
        offset_+=n;queued_-=n;budget-=n;
        if(offset_==front.size()){output_.pop_front();offset_=0;}
    }
    char buffer[4096];budget=65536;
    while(budget && messages.size()<32){
        auto newline=input_.find('\n');
        if(newline!=std::string::npos){
            if(newline>maxLine){fail("oversized message");messages.clear();return messages;}
            std::string line=input_.substr(0,newline);input_.erase(0,newline+1);
            if(line.empty() || line.find_first_of("\r")!=std::string::npos || line.find('\0')!=std::string::npos){fail("invalid message");messages.clear();return messages;}
            messages.push_back(line);continue;
        }
        if(input_.size()>maxLine){fail("oversized message");messages.clear();return messages;}
        int n=recv(s,buffer,static_cast<int>(std::min(budget,sizeof(buffer))),0);
        if(n<0){if(wouldBlock(lastError()))break;fail("receive failed");return messages;}
        if(n==0){fail("companion disconnected");return messages;}
        input_.append(buffer,n);budget-=n;
    }
    return messages;
}
}
