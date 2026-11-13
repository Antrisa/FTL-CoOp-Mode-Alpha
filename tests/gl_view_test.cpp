#include <EGL/egl.h>
#include <GL/gl.h>
#include <GL/glext.h>
#include "fleet_gl_view.hpp"
#include <cassert>
#include <cstdio>
#include <cstring>
static void* resolve(const char* name){return reinterpret_cast<void*>(eglGetProcAddress(name));}
int main(){
 EGLDisplay d=eglGetDisplay(EGL_DEFAULT_DISPLAY);EGLint ma,mi;assert(eglInitialize(d,&ma,&mi));assert(eglBindAPI(EGL_OPENGL_API));
 EGLint ca[]={EGL_SURFACE_TYPE,EGL_PBUFFER_BIT,EGL_RENDERABLE_TYPE,EGL_OPENGL_BIT,EGL_RED_SIZE,8,EGL_GREEN_SIZE,8,EGL_BLUE_SIZE,8,EGL_NONE};EGLConfig cfg;EGLint n;assert(eglChooseConfig(d,ca,&cfg,1,&n)&&n);
 EGLint pa[]={EGL_WIDTH,1280,EGL_HEIGHT,720,EGL_NONE};EGLSurface s=eglCreatePbufferSurface(d,cfg,pa);assert(s!=EGL_NO_SURFACE);
 EGLContext ctx=eglCreateContext(d,cfg,EGL_NO_CONTEXT,nullptr);assert(ctx!=EGL_NO_CONTEXT);assert(eglMakeCurrent(d,s,s,ctx));
 auto active=(PFNGLACTIVETEXTUREPROC)resolve("glActiveTexture");auto use=(PFNGLUSEPROGRAMPROC)resolve("glUseProgram");
 auto createShader=(PFNGLCREATESHADERPROC)resolve("glCreateShader");auto source=(PFNGLSHADERSOURCEPROC)resolve("glShaderSource");auto compile=(PFNGLCOMPILESHADERPROC)resolve("glCompileShader");
 auto createProgram=(PFNGLCREATEPROGRAMPROC)resolve("glCreateProgram");auto attach=(PFNGLATTACHSHADERPROC)resolve("glAttachShader");auto link=(PFNGLLINKPROGRAMPROC)resolve("glLinkProgram");
 GLuint vs=createShader(GL_VERTEX_SHADER),fs=createShader(GL_FRAGMENT_SHADER);
 const char* v="#version 110\nvoid main(){gl_Position=ftransform();}";const char* f="#version 110\nvoid main(){gl_FragColor=vec4(0.,1.,0.,1.);}";
 source(vs,1,&v,nullptr);compile(vs);source(fs,1,&f,nullptr);compile(fs);GLuint prog=createProgram();attach(prog,vs);attach(prog,fs);link(prog);use(prog);
 glViewport(0,0,1280,720);glClearColor(0,0,0,1);glClear(GL_COLOR_BUFFER_BIT);
 GLuint font;glGenTextures(1,&font);glBindTexture(GL_TEXTURE_2D,font);unsigned char white[]={255,255,255};glTexImage2D(GL_TEXTURE_2D,0,GL_RGB,1,1,0,GL_RGB,GL_UNSIGNED_BYTE,white);
 active(GL_TEXTURE1);glEnable(GL_TEXTURE_2D);glBindTexture(GL_TEXTURE_2D,font);glEnable(GL_SCISSOR_TEST);glScissor(0,0,1,1);
 glPixelStorei(GL_UNPACK_ROW_LENGTH,7);glPixelStorei(GL_UNPACK_SKIP_PIXELS,2);
 glMatrixMode(GL_PROJECTION);glLoadIdentity();glOrtho(0,10,0,10,-1,1);GLfloat oldMatrix[16];glGetFloatv(GL_PROJECTION_MATRIX,oldMatrix);
 fleet::GLView view;unsigned char red[]={255,0,0};
 assert(view.draw(ctx,resolve,red,1,1,true,100,100,200,200));glFinish();
 unsigned char pixel[4]={};glReadPixels(150,720-150,1,1,GL_RGBA,GL_UNSIGNED_BYTE,pixel);
 assert(pixel[0]==255&&pixel[1]==0&&pixel[2]==0);
 GLint value;glGetIntegerv(GL_CURRENT_PROGRAM,&value);assert(value==(GLint)prog);glGetIntegerv(GL_ACTIVE_TEXTURE,&value);assert(value==GL_TEXTURE1);
 glGetIntegerv(GL_TEXTURE_BINDING_2D,&value);assert(value==(GLint)font);assert(glIsEnabled(GL_SCISSOR_TEST));
 glGetIntegerv(GL_UNPACK_ROW_LENGTH,&value);assert(value==7);glGetIntegerv(GL_UNPACK_SKIP_PIXELS,&value);assert(value==2);
 GLfloat after[16];glGetFloatv(GL_PROJECTION_MATRIX,after);assert(memcmp(after,oldMatrix,sizeof after)==0);
 unsigned char blue[]={0,0,255};assert(view.draw(ctx,resolve,blue,1,1,false,100,100,200,200));glReadPixels(150,570,1,1,GL_RGBA,GL_UNSIGNED_BYTE,pixel);assert(pixel[0]==255);
 assert(view.draw(ctx,resolve,blue,1,1,true,100,100,200,200));glReadPixels(150,570,1,1,GL_RGBA,GL_UNSIGNED_BYTE,pixel);assert(pixel[2]==255&&pixel[0]==0);
 assert(glGetError()==GL_NO_ERROR);
 puts("Real Mesa OpenGL: owned image renders with unrelated texture/shader bound; image update and shader/unit/matrix/pixel/scissor restoration passed");
 eglMakeCurrent(d,EGL_NO_SURFACE,EGL_NO_SURFACE,EGL_NO_CONTEXT);eglDestroyContext(d,ctx);eglDestroySurface(d,s);eglTerminate(d);
}
