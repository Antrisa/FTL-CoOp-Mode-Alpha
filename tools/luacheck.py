"""Syntax-check Lua files with a system Lua shared library via ctypes (no execution)."""
import ctypes,sys
def load(path):
    L=ctypes.CDLL(path)
    L.luaL_newstate.restype=ctypes.c_void_p
    L.luaL_loadbufferx.argtypes=[ctypes.c_void_p,ctypes.c_char_p,ctypes.c_size_t,ctypes.c_char_p,ctypes.c_char_p]
    L.lua_tolstring.argtypes=[ctypes.c_void_p,ctypes.c_int,ctypes.c_void_p];L.lua_tolstring.restype=ctypes.c_char_p
    L.lua_settop.argtypes=[ctypes.c_void_p,ctypes.c_int]
    return L
def check(lib,files):
    L=load(lib);st=L.luaL_newstate();bad=0
    for f in files:
        src=open(f,'rb').read()
        r=L.luaL_loadbufferx(st,src,len(src),('@'+f).encode(),b't')
        if r!=0:
            bad+=1;print('SYNTAX ERROR',L.lua_tolstring(st,-1,None).decode())
        else:print('ok',f)
        L.lua_settop(st,0)
    return bad
if __name__=='__main__':sys.exit(1 if check(sys.argv[1],sys.argv[2:]) else 0)
