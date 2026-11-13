#include "fleet_native_api.h"
#include "fleet_transport.hpp"
extern "C" {
#include "lua.h"
#include "lauxlib.h"
}
void fleet_register_boarding(lua_State* L);
void fleet_register_scene(lua_State* L);
void fleet_register_effects(lua_State* L);
void fleet_register_video(lua_State* L);
void fleet_register_combat(lua_State* L);
// Initialize Winsock only when Lua calls us, never from DLL loader-lock startup.
// Process-lifetime singleton; the OS releases it on game exit.
static fleet::Transport& transport(){static fleet::Transport* instance=new fleet::Transport();return *instance;}
bool fleet_local_connected(){return transport().connected();}
static int connectLocal(lua_State* L){lua_pushboolean(L,transport().start());return 1;}
static int connected(lua_State* L){lua_pushboolean(L,transport().connected());return 1;}
static int closeLocal(lua_State*){transport().close();return 0;}
static int lastError(lua_State* L){lua_pushlstring(L,transport().error().data(),transport().error().size());return 1;}
static int sendMessage(lua_State* L){
    size_t length=0;const char* text=luaL_checklstring(L,1,&length);
    if(length>fleet::Transport::maxLine){lua_pushboolean(L,0);return 1;}
    lua_pushboolean(L,transport().send(std::string(text,length)));return 1;
}
static int pollMessages(lua_State* L){
    auto messages=transport().poll();lua_createtable(L,static_cast<int>(messages.size()),0);
    int index=1;for(const auto& message:messages){lua_pushlstring(L,message.data(),message.size());lua_rawseti(L,-2,index++);}return 1;
}
void fleet_register_transport(lua_State* L){
    const luaL_Reg funcs[]={{"connect",connectLocal},{"connected",connected},{"close",closeLocal},{"error",lastError},{"send",sendMessage},{"poll",pollMessages},{nullptr,nullptr}};
    luaL_newlib(L,funcs);lua_pushinteger(L,1);lua_setfield(L,-2,"version");lua_setglobal(L,"FleetNativeTransport");
    fleet_register_video(L);
    fleet_register_combat(L);
    fleet_register_scene(L);
    fleet_register_effects(L);
    fleet_register_boarding(L);
}
