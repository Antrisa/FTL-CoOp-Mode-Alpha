// Captures only a bounded region of FTL's own current OpenGL framebuffer.
// No desktop capture, other-window capture, or gameplay mutation.
#include "Global.h"
#include "fleet_pixels.hpp"
#include "fleet_gl_view.hpp"
#include <GL/gl.h>
#include <cmath>
#include <algorithm>
extern "C" {
#include "lua.h"
#include "lauxlib.h"
}
namespace {
fleet::GLView view;
void* resolveGL(const char* name){
    auto p=wglGetProcAddress(name);
    if(!p || p==reinterpret_cast<PROC>(1) || p==reinterpret_cast<PROC>(2) || p==reinterpret_cast<PROC>(3) || p==reinterpret_cast<PROC>(-1))return nullptr;
    return reinterpret_cast<void*>(p);
}
std::vector<unsigned char> latest;
int frameW=0,frameH=0;
bool dirty=false;
int capture(lua_State* L){
    double dx=luaL_checknumber(L,1),dy=luaL_checknumber(L,2),dw=luaL_checknumber(L,3),dh=luaL_checknumber(L,4);
    if(!std::isfinite(dx)||!std::isfinite(dy)||!std::isfinite(dw)||!std::isfinite(dh)||dx<0||dy<80||dw<16||dh<16||dx+dw>1280||dy+dh>660){lua_pushnil(L);lua_pushstring(L,"Invalid capture region or unavailable OpenGL viewport; launch with --force-opengl");return 2;}
    GLint vp[4]={0,0,0,0};glGetIntegerv(GL_VIEWPORT,vp);if(vp[2]<1||vp[3]<1||vp[2]>7680||vp[3]>4320){lua_pushnil(L);lua_pushstring(L,"Invalid capture region or unavailable OpenGL viewport; launch with --force-opengl");return 2;}
    const int x=vp[0]+static_cast<int>(dx*vp[2]/1280.0),y=vp[1]+static_cast<int>((720-dy-dh)*vp[3]/720.0);
    const int w=static_cast<int>(dw*vp[2]/1280.0),h=static_cast<int>(dh*vp[3]/720.0);
    if(w<1||h<1||static_cast<std::size_t>(w)*h>16000000){lua_pushnil(L);lua_pushstring(L,"Invalid capture region or unavailable OpenGL viewport; launch with --force-opengl");return 2;}
    std::vector<unsigned char> pixels(w*h*3);
    GLint alignment;glGetIntegerv(GL_PACK_ALIGNMENT,&alignment);glPixelStorei(GL_PACK_ALIGNMENT,1);
    glReadPixels(x,y,w,h,GL_RGB,GL_UNSIGNED_BYTE,pixels.data());GLenum captureError=glGetError();glPixelStorei(GL_PACK_ALIGNMENT,alignment);
    if(captureError!=GL_NO_ERROR){lua_pushnil(L);lua_pushstring(L,"OpenGL capture failed");return 2;}
    const double scale=(std::min)(320.0/dw,180.0/dh);
    const int ow=(std::max)(1,static_cast<int>(dw*scale)),oh=(std::max)(1,static_cast<int>(dh*scale));
    std::vector<unsigned char> reduced(ow*oh*3);
    for(int j=0;j<oh;++j)for(int i=0;i<ow;++i){
        int source=((h-1-j*h/oh)*w+i*w/ow)*3;int dest=(j*ow+i)*3;
        for(int c=0;c<3;++c)reduced[dest+c]=pixels[source+c];
    }
    std::string encoded=fleet::encodePixels(reduced);
    lua_pushinteger(L,ow);lua_pushinteger(L,oh);lua_pushlstring(L,encoded.data(),encoded.size());return 3;
}
int accept(lua_State* L){
    int w=static_cast<int>(luaL_checkinteger(L,1)),h=static_cast<int>(luaL_checkinteger(L,2));size_t length=0;
    const char* hex=luaL_checklstring(L,3,&length);
    if(length>320*180*8 || !fleet::decodePixels(std::string(hex,length),w,h,latest)){lua_pushboolean(L,0);return 1;}
    frameW=w;frameH=h;dirty=true;lua_pushboolean(L,1);return 1;
}
int clear(lua_State*){latest.clear();frameW=frameH=0;dirty=false;return 0;}
int draw(lua_State* L){
    float x=luaL_checknumber(L,1),y=luaL_checknumber(L,2),w=luaL_checknumber(L,3),h=luaL_checknumber(L,4);
    if(latest.empty()||!std::isfinite(x)||!std::isfinite(y)||!std::isfinite(w)||!std::isfinite(h)||w<=0||h<=0||w>1280||h>720){lua_pushboolean(L,0);return 1;}
    const bool shown=view.draw(reinterpret_cast<void*>(wglGetCurrentContext()),resolveGL,
        latest.data(),frameW,frameH,dirty,x,y,w,h);
    if(shown)dirty=false;
    lua_pushboolean(L,shown);return 1;
}
}
void fleet_register_video(lua_State* L){
    const luaL_Reg funcs[]={{"capture",capture},{"accept",accept},{"draw",draw},{"clear",clear},{nullptr,nullptr}};
    luaL_newlib(L,funcs);lua_setglobal(L,"FleetNativeVideo");
}
