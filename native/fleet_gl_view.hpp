#pragma once
#include <GL/gl.h>
#include <GL/glext.h>
#include <algorithm>
#include <cmath>
namespace fleet {
// A raw GL texture name is NOT an FTL GL_Texture resource ID. Own the texture
// and draw it directly, restoring the game's shader, units, matrices and state.
class GLView {
    GLuint texture_=0;
    void* context_=nullptr;
public:
    bool draw(void* context, void* (*resolve)(const char*),const unsigned char* rgb,
              int width,int height,bool upload,float x,float y,float w,float h) {
        if(!context || !rgb || width<1 || height<1 || width>320 || height>180)return false;
        auto active=reinterpret_cast<PFNGLACTIVETEXTUREPROC>(resolve("glActiveTexture"));
        auto program=reinterpret_cast<PFNGLUSEPROGRAMPROC>(resolve("glUseProgram"));
        auto buffer=reinterpret_cast<PFNGLBINDBUFFERPROC>(resolve("glBindBuffer"));
        if(!active || !program || !buffer)return false;
        if(context_!=context){texture_=0;context_=context;upload=true;}
        GLint oldUnit=GL_TEXTURE0,oldProgram=0,oldMode=GL_MODELVIEW,oldUnpack=0;
        glGetIntegerv(GL_ACTIVE_TEXTURE,&oldUnit);glGetIntegerv(GL_CURRENT_PROGRAM,&oldProgram);
        glGetIntegerv(GL_MATRIX_MODE,&oldMode);glGetIntegerv(GL_PIXEL_UNPACK_BUFFER_BINDING,&oldUnpack);
        glPushAttrib(GL_ALL_ATTRIB_BITS);glPushClientAttrib(GL_CLIENT_PIXEL_STORE_BIT);
        program(0);buffer(GL_PIXEL_UNPACK_BUFFER,0);
        GLint units=1;glGetIntegerv(GL_MAX_TEXTURE_UNITS,&units);
        for(int i=0;i<units;++i){active(GL_TEXTURE0+i);glDisable(GL_TEXTURE_2D);}
        active(GL_TEXTURE0);glEnable(GL_TEXTURE_2D);
        if(!texture_){glGenTextures(1,&texture_);upload=true;}
        glBindTexture(GL_TEXTURE_2D,texture_);
        if(upload){
            glPixelStorei(GL_UNPACK_ALIGNMENT,1);glPixelStorei(GL_UNPACK_ROW_LENGTH,0);
            glPixelStorei(GL_UNPACK_SKIP_ROWS,0);glPixelStorei(GL_UNPACK_SKIP_PIXELS,0);
            glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_MIN_FILTER,GL_LINEAR);
            glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_MAG_FILTER,GL_LINEAR);
            glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_WRAP_S,GL_CLAMP_TO_EDGE);
            glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_WRAP_T,GL_CLAMP_TO_EDGE);
            glTexImage2D(GL_TEXTURE_2D,0,GL_RGB,width,height,0,GL_RGB,GL_UNSIGNED_BYTE,rgb);
        }
        glDisable(GL_DEPTH_TEST);glDisable(GL_BLEND);glDisable(GL_ALPHA_TEST);
        glDisable(GL_SCISSOR_TEST);glDisable(GL_CULL_FACE);glDisable(GL_LIGHTING);glDisable(GL_FOG);
        for(int i=0;i<6;++i)glDisable(GL_CLIP_PLANE0+i);
        glColorMask(GL_TRUE,GL_TRUE,GL_TRUE,GL_TRUE);
        glTexEnvi(GL_TEXTURE_ENV,GL_TEXTURE_ENV_MODE,GL_REPLACE);
        glMatrixMode(GL_TEXTURE);glPushMatrix();glLoadIdentity();
        glMatrixMode(GL_PROJECTION);glPushMatrix();glLoadIdentity();glOrtho(0,1280,720,0,-1,1);
        glMatrixMode(GL_MODELVIEW);glPushMatrix();glLoadIdentity();
        const float scale=(std::min)(w/width,h/height),dw=width*scale,dh=height*scale;
        x+=(w-dw)/2;y+=(h-dh)/2;
        glBegin(GL_QUADS);
        glTexCoord2f(0,0);glVertex2f(x,y);glTexCoord2f(1,0);glVertex2f(x+dw,y);
        glTexCoord2f(1,1);glVertex2f(x+dw,y+dh);glTexCoord2f(0,1);glVertex2f(x,y+dh);
        glEnd();
        glPopMatrix();glMatrixMode(GL_PROJECTION);glPopMatrix();glMatrixMode(GL_TEXTURE);glPopMatrix();
        glMatrixMode(oldMode);glPopClientAttrib();glPopAttrib();
        buffer(GL_PIXEL_UNPACK_BUFFER,oldUnpack);program(oldProgram);active(oldUnit);
        return texture_!=0;
    }
};
}
