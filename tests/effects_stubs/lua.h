#pragma once
#include <stddef.h>
struct lua_State{std::string text;bool boolean=false;int integer=0;};
inline void lua_pushlstring(lua_State*L,const char*s,size_t n){if(L)L->text.assign(s,n);}
inline void lua_pushboolean(lua_State*L,bool b){if(L)L->boolean=b;}
inline void lua_pushinteger(lua_State*L,int n){if(L)L->integer=n;}
inline void lua_setfield(lua_State*,int,const char*){}
inline void lua_setglobal(lua_State*,const char*){}
