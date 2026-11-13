"""Run a Lua 5.3 script through the Hyperspace-shipped liblua via ctypes (mock tests only)."""
import ctypes,sys
import os
lib=ctypes.CDLL(os.environ.get("LIBLUA53","liblua5.3.so.0"))
lib.luaL_newstate.restype=ctypes.c_void_p
lib.luaL_openlibs.argtypes=[ctypes.c_void_p]
lib.luaL_loadfilex.argtypes=[ctypes.c_void_p,ctypes.c_char_p,ctypes.c_char_p]
lib.lua_pcallk.argtypes=[ctypes.c_void_p,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_void_p,ctypes.c_void_p]
lib.lua_tolstring.argtypes=[ctypes.c_void_p,ctypes.c_int,ctypes.c_void_p];lib.lua_tolstring.restype=ctypes.c_char_p
L=lib.luaL_newstate();lib.luaL_openlibs(L)
r=lib.luaL_loadfilex(L,sys.argv[1].encode(),None) or lib.lua_pcallk(L,0,0,0,None,None)
if r:print('LUA ERROR:',lib.lua_tolstring(L,-1,None).decode());sys.exit(1)
