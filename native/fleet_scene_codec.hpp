#pragma once
#include <vector>
#include <string>
#include <cstring>
#include <cmath>
#include <cstdint>
namespace fleet26 {
struct Vertex {float x,y,u,v,r,g,b,a;};
struct Draw {std::string image;std::vector<Vertex> vertices;};
struct Frame {float x=0,y=0,w=1,h=1;std::vector<Draw> draws;};
// Recognize exactly the two-triangle rectangle emitted by our image capture.
// Arbitrary meshes and per-vertex gradients must remain on the mesh path.
inline bool imageQuad(const std::vector<Vertex>& v,size_t i){
 if(i+6>v.size())return false;
 const auto&a=v[i];const auto&b=v[i+1];const auto&c=v[i+2];const auto&d=v[i+3];const auto&e=v[i+4];const auto&f=v[i+5];
 auto eq=[](float x,float y){return std::abs(x-y)<.001f;};
 for(size_t j=i;j<i+6;++j){auto&t=v[j];if(!eq(t.r,a.r)||!eq(t.g,a.g)||!eq(t.b,a.b)||!eq(t.a,a.a))return false;}
 return b.x>a.x&&c.y>b.y&&eq(a.y,b.y)&&eq(b.x,c.x)&&eq(c.y,f.y)&&eq(f.x,a.x)
 &&eq(a.x,d.x)&&eq(a.y,d.y)&&eq(c.x,e.x)&&eq(c.y,e.y)
 &&eq(a.u,d.u)&&eq(a.v,d.v)&&eq(c.u,e.u)&&eq(c.v,e.v)
 &&eq(a.u,f.u)&&eq(b.u,c.u)&&eq(a.v,b.v)&&eq(c.v,f.v);
}
inline bool shipRegion(int x,int y){return x>=135&&x<=825&&y>=110&&y<616;}
const size_t MAX_BYTES=196608;
inline bool path(const std::string&s){if(s.size()>180||s.find("..")!=std::string::npos)return false;for(char c:s)if(!((c>='a'&&c<='z')||(c>='A'&&c<='Z')||(c>='0'&&c<='9')||c=='_'||c=='-'||c=='/'||c=='.'))return false;return true;}
template<class T>void put(std::string&s,const T&x){s.append(reinterpret_cast<const char*>(&x),sizeof(x));}
template<class T>bool get(const std::string&s,size_t&p,T&x){if(p+sizeof(x)>s.size())return false;std::memcpy(&x,s.data()+p,sizeof(x));p+=sizeof(x);return true;}
inline std::string encode(const Frame&f){std::string s="FS26";put(s,f.x);put(s,f.y);put(s,f.w);put(s,f.h);uint32_t n=f.draws.size();put(s,n);for(auto&d:f.draws){uint32_t l=d.image.size(),v=d.vertices.size();put(s,l);s+=d.image;put(s,v);for(auto&p:d.vertices)put(s,p);}return s.size()<=MAX_BYTES?s:std::string();}
inline bool decode(const std::string&s,Frame&out){
 if(s.size()>MAX_BYTES||s.substr(0,4)!="FS26")return false;size_t p=4;Frame f;uint32_t n;
 if(!get(s,p,f.x)||!get(s,p,f.y)||!get(s,p,f.w)||!get(s,p,f.h)||!get(s,p,n)||n>1024||n==0)return false;
 if(!std::isfinite(f.x)||!std::isfinite(f.y)||!std::isfinite(f.w)||!std::isfinite(f.h)||std::abs(f.x)>4096||std::abs(f.y)>4096||f.w<16||f.h<16||f.w>2048||f.h>2048)return false;
 size_t total=0;for(uint32_t i=0;i<n;++i){Draw d;uint32_t l,v;if(!get(s,p,l)||l>180||p+l>s.size())return false;d.image=s.substr(p,l);p+=l;if(!path(d.image)||!get(s,p,v)||v==0||v%3||v>4096||(total+=v)>6000)return false;for(uint32_t j=0;j<v;++j){Vertex a;if(!get(s,p,a))return false;float z[8]={a.x,a.y,a.u,a.v,a.r,a.g,a.b,a.a};for(float x:z)if(!std::isfinite(x))return false;if(std::abs(a.x)>8192||std::abs(a.y)>8192||std::abs(a.u)>32||std::abs(a.v)>32||a.r<0||a.r>1||a.g<0||a.g>1||a.b<0||a.b>1||a.a<0||a.a>1)return false;d.vertices.push_back(a);}f.draws.push_back(d);}
 if(p!=s.size())return false;out=std::move(f);return true;
}
// Normalize locally captured optional drawing layers; network decoder stays strict.
inline unsigned normalize(Frame& f){
 unsigned skipped=0;std::vector<Draw> accepted;size_t total=0;
 for(auto d:f.draws){bool ok=path(d.image)&&!d.vertices.empty()&&d.vertices.size()%3==0&&d.vertices.size()<=4096&&total+d.vertices.size()<=6000;
  for(auto &v:d.vertices){float a[]={v.x,v.y,v.u,v.v,v.r,v.g,v.b,v.a};for(float n:a)if(!std::isfinite(n))ok=false;
   if(std::abs(v.x)>8192||std::abs(v.y)>8192||std::abs(v.u)>32||std::abs(v.v)>32)ok=false;
   v.r=std::fmax(0.f,std::fmin(1.f,v.r));v.g=std::fmax(0.f,std::fmin(1.f,v.g));v.b=std::fmax(0.f,std::fmin(1.f,v.b));v.a=std::fmax(0.f,std::fmin(1.f,v.a));
  }
  if(ok){total+=d.vertices.size();accepted.push_back(std::move(d));}else ++skipped;
 }
 f.draws=std::move(accepted);return skipped;
}
inline std::string hex(const std::string&s){static const char*d="0123456789abcdef";std::string o;o.reserve(s.size()*2);for(unsigned char c:s){o+=d[c>>4];o+=d[c&15];}return o;}
inline bool unhex(const std::string&s,std::string&o){if(s.size()%2||s.size()>MAX_BYTES*2)return false;o.clear();auto n=[](char c){return c>='0'&&c<='9'?c-'0':c>='a'&&c<='f'?c-'a'+10:-1;};for(size_t i=0;i<s.size();i+=2){int a=n(s[i]),b=n(s[i+1]);if(a<0||b<0)return false;o+=char(a*16+b);}return true;}
// Smooth only a rigid translation of the same crew sprite. Never blend texture
// UVs, topology, health colors, doors, projectiles or unrelated scene layers.
inline bool crewTranslation(const Draw& old,const Draw& now,float& dx,float& dy){
 if(now.image.find("people/")==std::string::npos || old.image!=now.image || old.vertices.empty() || old.vertices.size()!=now.vertices.size())return false;
 dx=now.vertices[0].x-old.vertices[0].x;dy=now.vertices[0].y-old.vertices[0].y;
 if(dx*dx+dy*dy>48.f*48.f)return false;
 for(size_t i=0;i<now.vertices.size();++i){auto&a=old.vertices[i];auto&b=now.vertices[i];
  if(std::abs(b.x-a.x-dx)>.001f||std::abs(b.y-a.y-dy)>.001f||a.u!=b.u||a.v!=b.v||a.r!=b.r||a.g!=b.g||a.b!=b.b||a.a!=b.a)return false;
 }
 return true;
}
inline float blendDuration(float interval){return std::fmax(.016f,std::fmin(.08f,interval));}
inline Frame smoothCrew(const Frame& old,const Frame& now,float alpha){
 Frame out=now;alpha=std::fmax(0.f,std::fmin(1.f,alpha));
 if(old.x!=now.x||old.y!=now.y||old.w!=now.w||old.h!=now.h||old.draws.size()!=now.draws.size())return out;
 for(size_t i=0;i<now.draws.size();++i){float dx,dy;if(crewTranslation(old.draws[i],now.draws[i],dx,dy))
  for(auto&v:out.draws[i].vertices){v.x-=(1-alpha)*dx;v.y-=(1-alpha)*dy;}
 }
 return out;
}
struct Fit {float s,x,y;};
inline Fit fit(float bx,float by,float bw,float bh,float x,float y,float w,float h){float s=std::fmin(w/bw,h/bh);return {s,x+(w-bw*s)/2-bx*s,y+(h-bh*s)/2-by*s};}
// The two views stay inside the ship region and clear the weapons HUD.
// View preference is local presentation only; it never changes scene packets.
struct Layout {float partnerY,partnerH,localY,localH;};
inline Layout layout(int mode){
 if(mode==1)return {122,164,306,306};
 if(mode==2)return {122,306,448,164};
 return {122,236,376,236};
}
inline Fit localStack(float bx,float by,float bw,float bh,float pw,float ph,int mode=0){
 auto l=layout(mode);
 auto local=fit(bx,by,bw,bh,145,l.localY,665,l.localH);
 auto remote=fit(0,0,pw,ph,145,l.partnerY,665,l.partnerH);
 float s=std::fmin(local.s,std::fmin(2*remote.s*pw/bw,2*remote.s*ph/bh));
 return {s,145+(665-bw*s)/2-bx*s,l.localY+(l.localH-bh*s)/2-by*s};
}

}
