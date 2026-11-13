#include "fleet_transport.hpp"
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <unistd.h>
#include <fcntl.h>
#include <thread>
#include <chrono>
#include <cassert>
#include <algorithm>
#include <iostream>
static void wait(){std::this_thread::sleep_for(std::chrono::milliseconds(1));}
int main(){
    int server=socket(AF_INET,SOCK_STREAM,0);assert(server>=0);int yes=1;
    setsockopt(server,SOL_SOCKET,SO_REUSEADDR,&yes,sizeof(yes));
    sockaddr_in addr={};addr.sin_family=AF_INET;addr.sin_addr.s_addr=htonl(INADDR_LOOPBACK);addr.sin_port=htons(38474);
    assert(bind(server,reinterpret_cast<sockaddr*>(&addr),sizeof(addr))==0);assert(listen(server,1)==0);
    fleet::Transport client;assert(!client.send("before connection"));assert(client.start());
    int peer=accept(server,nullptr,nullptr);assert(peer>=0);fcntl(peer,F_SETFL,O_NONBLOCK);
    for(int i=0;i<100 && !client.connected();++i){client.poll();wait();}assert(client.connected());
    assert(!client.send("a\nb"));assert(!client.send(std::string(fleet::Transport::maxLine+1,'x')));
    assert(client.send("HELLO|1"));std::string recvdata;char b[4096];
    for(int i=0;i<100 && recvdata.find('\n')==std::string::npos;++i){client.poll();int n=recv(peer,b,sizeof(b),0);if(n>0)recvdata.append(b,n);wait();}
    assert(recvdata=="HELLO|1\n");
    assert(send(peer,"S|split",7,0)==7);assert(client.poll().empty());
    assert(send(peer,"|frame\nS|next\n",14,0)==14);
    std::vector<std::string> received;
    for(int i=0;i<100 && received.size()<2;++i){auto v=client.poll();received.insert(received.end(),v.begin(),v.end());wait();}
    assert(received.size()==2 && received[0]=="S|split|frame" && received[1]=="S|next");
    // Exercise high-frequency messages through real loopback, not a fake socket.
    auto start=std::chrono::steady_clock::now();int count=0;
    for(int n=0;n<200;++n){std::string line="FRAME|"+std::to_string(n)+"\n";assert(send(peer,line.data(),line.size(),0)==static_cast<int>(line.size()));
        bool got=false;for(int i=0;i<100 && !got;++i){auto v=client.poll();if(!v.empty()){assert(v.size()==1 && v[0]==line.substr(0,line.size()-1));got=true;++count;}else wait();}assert(got);}
    auto elapsed=std::chrono::duration_cast<std::chrono::microseconds>(std::chrono::steady_clock::now()-start).count();
    std::cout<<"200 loopback frames received in "<<elapsed<<" us (Linux transport only)\n";
    assert(count==200);
    // Newest scene replaces older unsent scenes; gameplay control goes first.
    assert(client.send("SCENE|1|old"));assert(client.send("SCENE|1|new"));assert(client.send("COMBAT|STOP|test"));
    recvdata.clear();
    for(int i=0;i<200 && std::count(recvdata.begin(),recvdata.end(),'\n')<2;++i){client.poll();int n=recv(peer,b,sizeof(b),0);if(n>0)recvdata.append(b,n);wait();}
    assert(recvdata=="COMBAT|STOP|test\nSCENE|1|new\n");
    // Backpressure is bounded even when poll is not called.
    int queued=0;while(client.send(std::string(8000,'x')))++queued;assert(queued>0 && queued<=64);
    client.close();assert(!client.connected());close(peer);
    assert(client.start());peer=accept(server,nullptr,nullptr);assert(peer>=0);fcntl(peer,F_SETFL,O_NONBLOCK);
    for(int i=0;i<100 && !client.connected();++i){client.poll();wait();}assert(client.connected());
    std::string oversized(fleet::Transport::maxLine+1,'x');oversized+='\n';std::size_t offset=0;
    for(int i=0;i<1000 && client.connected();++i){
        if(offset<oversized.size()){int n=send(peer,oversized.data()+offset,oversized.size()-offset,MSG_NOSIGNAL);if(n>0)offset+=n;}
        client.poll();wait();
    }
    assert(!client.connected());assert(client.error()=="oversized message");
    close(peer);close(server);std::cout<<"Native transport checks passed\n";
}
