#include "fleet_native_api.h"
extern "C" {
#include "lua.h"
#include "lauxlib.h"
#include "lualib.h"
}
#include <cassert>
#include <iostream>
void fleet_register_combat(lua_State*){} // Combat hooks require FTL runtime.
void fleet_register_video(lua_State*){} // Renderer requires FTL/OpenGL runtime; not tested here.
int main(){
 auto L=luaL_newstate();luaL_openlibs(L);int top=lua_gettop(L);fleet_register_transport(L);assert(lua_gettop(L)==top);
 const char* script="assert(FleetNativeTransport.version==1); assert(not FleetNativeTransport.connected()); assert(not FleetNativeTransport.send('before connection')); assert(type(FleetNativeTransport.poll())=='table'); FleetNativeTransport.connect(); FleetNativeTransport.poll(); FleetNativeTransport.close(); assert(not FleetNativeTransport.connected()); assert(type(FleetNativeTransport.error())=='string')";
 int result=luaL_dostring(L,script);if(result){std::cerr<<lua_tostring(L,-1)<<'\n';}assert(result==0);lua_close(L);
 std::cout<<"Native Lua5.3.5 API registration checks passed\n";
}
