#pragma once
#include "lua.h"
struct luaL_Reg{const char*name;int(*fn)(lua_State*);};
inline const char*luaL_checklstring(lua_State*,int,size_t*){return "";}
inline void luaL_newlib(lua_State*,const luaL_Reg*){}
