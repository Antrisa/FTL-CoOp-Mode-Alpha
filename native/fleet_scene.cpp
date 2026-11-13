// Render command replication: actual FTL assets/vertices, never framebuffer pixels.
// No additional ShipManager or ShipGraph is created; the partner is read-only.
#include "Global.h"
#include "fleet_scene_codec.hpp"
#include <GL/gl.h>
#include <unordered_map>
#include <chrono>
#include <algorithm>
extern "C" {
#include "lua.h"
#include "lauxlib.h"
}
namespace {
using namespace fleet26;
struct Shape {GL_Texture*tex;std::vector<GL_TexVertex> v;GL_Color c;Shape(GL_Texture*t=nullptr,std::vector<GL_TexVertex>a={},GL_Color z=GL_Color(1,1,1,1)):tex(t),v(std::move(a)),c(z){}};
struct Mat {float a,b,c,d,x,y;Mat(float A=1,float B=0,float C=0,float D=1,float X=0,float Y=0):a(A),b(B),c(C),d(D),x(X),y(Y){}};
Mat mat;std::vector<Mat> stack;
std::unordered_map<GL_Primitive*,Shape> shapes;
std::unordered_map<GL_Texture*,std::string> paths;
std::unordered_map<GL_Texture*,std::string> logicalPaths;
Frame captured,partner,previousPartner;float blendSeconds=.033f;bool recording=false,enabled=false;int nested=0;unsigned frames=0;
std::string pending;using Clock=std::chrono::steady_clock;auto seen=Clock::now();auto heartbeat=Clock::now();
Fit localFit={1,0,0};bool transformed=false;int viewMode=0;bool crisp=true;bool friendlyPass=false;float localInputTop=365;
// Change texture sampling only during friendly-ship drawing, restoring every
// touched texture and the prior binding before returning to FTL's other UI.
struct Filter {GLint min,mag;};
std::unordered_map<GLuint,Filter> filters;
void sampleTexture(GL_Texture* t){
 if(!friendlyPass||!t||t->id_<=0)return;
 GLuint id=GLuint(t->id_);if(filters.count(id))return;
 GLint bound=0;glGetIntegerv(GL_TEXTURE_BINDING_2D,&bound);glBindTexture(GL_TEXTURE_2D,id);
 Filter f;glGetTexParameteriv(GL_TEXTURE_2D,GL_TEXTURE_MIN_FILTER,&f.min);glGetTexParameteriv(GL_TEXTURE_2D,GL_TEXTURE_MAG_FILTER,&f.mag);filters[id]=f;
 glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_MIN_FILTER,crisp?GL_NEAREST:GL_LINEAR);
 glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_MAG_FILTER,crisp?GL_NEAREST:GL_LINEAR);
 glBindTexture(GL_TEXTURE_2D,bound);
}
struct FriendlyPass {
 bool old;
 FriendlyPass():old(friendlyPass){friendlyPass=true;}
 ~FriendlyPass(){if(!old){GLint bound=0;glGetIntegerv(GL_TEXTURE_BINDING_2D,&bound);
  for(auto&p:filters){glBindTexture(GL_TEXTURE_2D,p.first);glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_MIN_FILTER,p.second.min);glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_MAG_FILTER,p.second.mag);}
  glBindTexture(GL_TEXTURE_2D,bound);filters.clear();}friendlyPass=old;}
};
void mult(Mat m){Mat o=mat;mat={o.a*m.a+o.c*m.b,o.b*m.a+o.d*m.b,o.a*m.c+o.c*m.d,o.b*m.c+o.d*m.d,o.a*m.x+o.c*m.y+o.x,o.b*m.x+o.d*m.y+o.y};}
std::vector<GL_TexVertex> quad(float x,float y,float w,float h,float u=0,float U=1,float v=0,float V=1){return {{x,y,u,v},{x+w,y,U,v},{x+w,y+h,U,V},{x,y,u,v},{x+w,y+h,U,V},{x,y+h,u,V}};}
Shape image(GL_Texture*t,float x,float y,float w,float h,float u,float U,float v,float V,GL_Color c,bool mirror){return {t,quad(x,y,w,h,mirror?U:u,mirror?u:U,v,V),c};}
void rotate(Shape&s,float deg,float x,float y){float c=cos(deg*3.14159265f/180),n=sin(deg*3.14159265f/180);for(auto&v:s.v){float a=v.x-x,b=v.y-y;v.x=x+c*a-n*b;v.y=y+n*a+c*b;}}
void record(const Shape&s,GL_Color color){
 sampleTexture(s.tex);
 if(!recording||nested||captured.draws.size()>=1024)return;
 Draw d;if(s.tex){auto it=paths.find(s.tex);if(it==paths.end())return;d.image=it->second;}
 auto tint=CSurface::GetColorTint();
 for(auto&v:s.v)d.vertices.push_back({mat.a*v.x+mat.c*v.y+mat.x,mat.b*v.x+mat.d*v.y+mat.y,v.u,v.v,std::max(0.f,std::min(1.f,color.r*tint.r)),std::max(0.f,std::min(1.f,color.g*tint.g)),std::max(0.f,std::min(1.f,color.b*tint.b)),std::max(0.f,std::min(1.f,color.a*tint.a))});
 if(!d.vertices.empty())captured.draws.push_back(std::move(d));
}
void prim(GL_Primitive*p,int mode,GL_Color color){auto it=shapes.find(p);if(it==shapes.end())return;sampleTexture(it->second.tex);auto c=it->second.c;if(mode==1)c.a*=color.a;else if(mode==2)c=color;record(it->second,c);}
bool live(){return enabled&&!partner.draws.empty()&&std::chrono::duration<double>(Clock::now()-heartbeat).count()<1;}
}
HOOK_METHOD(ResourceControl, GetImageId, (std::string& name)->GL_Texture*){
 auto t=super(name);if(t&&path(name)&&!name.empty())logicalPaths[t]=name;return t;
}
HOOK_STATIC(CSurface, GL_CreateImagePartialPrimitive,(GL_Texture*t,float x,float y,float w,float h,float u,float U,float v,float V,float alpha,GL_Color c,bool mirror)->GL_Primitive*){auto p=super(t,x,y,w,h,u,U,v,V,alpha,c,mirror);c.a*=alpha;shapes[p]=image(t,x,y,w,h,u,U,v,V,c,mirror);return p;}
HOOK_STATIC(CSurface, GL_CreateImagePrimitive,(GL_Texture*t,float x,float y,float w,float h,float rot,GL_Color c)->GL_Primitive*){auto p=super(t,x,y,w,h,rot,c);auto s=image(t,x,y,w,h,0,1,0,1,c,false);rotate(s,rot,x+w/2,y+h/2);shapes[p]=s;return p;}
HOOK_STATIC(CSurface, GL_CreatePixelImagePrimitive,(GL_Texture*t,float x,float y,float w,float h,float rot,GL_Color c,bool unk)->GL_Primitive*){auto p=super(t,x,y,w,h,rot,c,unk);auto s=image(t,x,y,w,h,0,1,0,1,c,false);rotate(s,rot,x+w/2,y+h/2);shapes[p]=s;return p;}
HOOK_STATIC(CSurface, GL_CreateMultiImagePrimitive,(GL_Texture*t,std::vector<GL_TexVertex>*v,GL_Color c)->GL_Primitive*){auto p=super(t,v,c);if(v)shapes[p]={t,*v,c};return p;}
HOOK_STATIC(CSurface, GL_CreateRectPrimitive,(float x,float y,float w,float h,GL_Color c)->GL_Primitive*){auto p=super(x,y,w,h,c);shapes[p]={nullptr,quad(x,y,w,h),c};return p;}
HOOK_STATIC(CSurface, GL_CreateMultiRectPrimitive,(std::vector<Globals::Rect>&rs,GL_Color c)->GL_Primitive*){auto p=super(rs,c);Shape s;s.c=c;for(auto&r:rs){auto q=quad(r.x,r.y,r.w,r.h);s.v.insert(s.v.end(),q.begin(),q.end());}shapes[p]=s;return p;}
static Shape lineShape(float x,float y,float X,float Y,float width,GL_Color c){float dx=X-x,dy=Y-y,len=std::sqrt(dx*dx+dy*dy);if(len<.001f)return {nullptr,quad(x,y,width,width),c};float a=-dy*width/(2*len),b=dx*width/(2*len);return {nullptr,{{x+a,y+b,0,0},{X+a,Y+b,0,0},{X-a,Y-b,0,0},{x+a,y+b,0,0},{X-a,Y-b,0,0},{x-a,y-b,0,0}},c};}
HOOK_STATIC(CSurface, GL_CreateMultiLinePrimitive,(std::vector<GL_Line>&lines,GL_Color c,float width)->GL_Primitive*){auto p=super(lines,c,width);Shape s;s.c=c;for(auto&l:lines){auto q=lineShape(l.start.x,l.start.y,l.end.x,l.end.y,width,c);s.v.insert(s.v.end(),q.v.begin(),q.v.end());}shapes[p]=s;return p;}
HOOK_STATIC(CSurface, GL_CreateRectOutlinePrimitive,(int x,int y,int w,int h,GL_Color c,float width)->GL_Primitive*){auto p=super(x,y,w,h,c,width);Shape s;s.c=c;for(auto q:{quad(x,y,w,width),quad(x,y+h-width,w,width),quad(x,y,width,h),quad(x+w-width,y,width,h)})s.v.insert(s.v.end(),q.begin(),q.end());shapes[p]=s;return p;}
HOOK_STATIC(CSurface, GL_DrawLine,(float x,float y,float X,float Y,float width,GL_Color c)->bool){record(lineShape(x,y,X,Y,width,c),c);++nested;auto ret=super(x,y,X,Y,width,c);--nested;return ret;}
HOOK_STATIC(CSurface, GL_BlitMultiColorImage,(GL_Texture*t,const std::vector<GL_ColorTexVertex>&v,bool aa)->void){
 sampleTexture(t);
 if(recording&&!nested){Draw d;bool ok=true;if(t){auto it=paths.find(t);if(it==paths.end())ok=false;else d.image=it->second;}if(ok){for(auto&a:v)d.vertices.push_back({mat.a*a.x+mat.c*a.y+mat.x,mat.b*a.x+mat.d*a.y+mat.y,a.u,a.v,a.r,a.g,a.b,a.a});if(!d.vertices.empty())captured.draws.push_back(std::move(d));}}
 ++nested;super(t,v,aa);--nested;
}

HOOK_STATIC(CSurface, GL_DestroyPrimitive,(GL_Primitive*p)->void){shapes.erase(p);super(p);}
HOOK_STATIC(CSurface, GL_RenderPrimitive,(GL_Primitive*p)->void){prim(p,0,GL_Color(1,1,1,1));++nested;super(p);--nested;}
HOOK_STATIC(CSurface, GL_RenderPrimitiveWithAlpha,(GL_Primitive*p,float a)->void){prim(p,1,GL_Color(1,1,1,a));++nested;super(p,a);--nested;}
HOOK_STATIC(CSurface, GL_RenderPrimitiveWithColor,(GL_Primitive*p,GL_Color c)->void){prim(p,2,c);++nested;super(p,c);--nested;}
HOOK_STATIC(CSurface, GL_BlitMultiImage,(GL_Texture*t,const std::vector<GL_TexVertex>&v,bool aa)->void){record({t,v,CSurface::GL_GetColor()},CSurface::GL_GetColor());++nested;super(t,v,aa);--nested;}
HOOK_STATIC(CSurface, GL_BlitImagePartial,(GL_Texture*t,float x,float y,float w,float h,float u,float U,float v,float V,float a,GL_Color c,bool mirror)->bool){auto z=c;z.a*=a;record(image(t,x,y,w,h,u,U,v,V,z,mirror),z);++nested;auto ret=super(t,x,y,w,h,u,U,v,V,a,c,mirror);--nested;return ret;}
HOOK_STATIC(CSurface, GL_BlitImage,(GL_Texture*t,float x,float y,float w,float h,float rot,GL_Color c,bool mirror)->bool){auto s=image(t,x,y,w,h,0,1,0,1,c,mirror);rotate(s,rot,x+w/2,y+h/2);record(s,c);++nested;auto ret=super(t,x,y,w,h,rot,c,mirror);--nested;return ret;}
HOOK_STATIC(CSurface, GL_BlitPixelImage,(GL_Texture*t,float x,float y,float w,float h,float rot,GL_Color c,bool mirror)->bool){auto s=image(t,x,y,w,h,0,1,0,1,c,mirror);rotate(s,rot,x+w/2,y+h/2);record(s,c);++nested;auto ret=super(t,x,y,w,h,rot,c,mirror);--nested;return ret;}
HOOK_STATIC(CSurface, GL_DrawRect,(float x,float y,float w,float h,GL_Color c)->bool){record({nullptr,quad(x,y,w,h),c},c);++nested;auto ret=super(x,y,w,h,c);--nested;return ret;}
HOOK_STATIC(CSurface, GL_PushMatrix,()->int){if(recording)stack.push_back(mat);return super();}
HOOK_STATIC(CSurface, GL_PopMatrix,()->int){if(recording&&!stack.empty()){mat=stack.back();stack.pop_back();}return super();}
HOOK_STATIC(CSurface, GL_Translate,(float x,float y,float z)->bool){if(recording)mult({1,0,0,1,x,y});return super(x,y,z);}
HOOK_STATIC(CSurface, GL_Scale,(float x,float y,float z)->void){if(recording)mult({x,0,0,y,0,0});super(x,y,z);}
HOOK_STATIC(CSurface, GL_Rotate,(float angle,float x,float y,float z)->void){if(recording&&z!=0){float r=angle*(z<0?-1:1)*3.14159265f/180;mult({cosf(r),sinf(r),-sinf(r),cosf(r),0,0});}super(angle,x,y,z);}
HOOK_METHOD_PRIORITY(CommandGui, RenderPlayerShip, 100000, (Point&center,float jumpScale)->void){
 transformed=false;
 auto sm=shipComplete?shipComplete->shipManager:nullptr;
 if(!enabled||!sm||jumpScale!=1.f){super(center,jumpScale);return;}
 auto&im=sm->ship.shipImage;auto box=ShipGraph::GetShipInfo(0)->shipBox;
 float bx=box.x+im.x,by=box.y+im.y,bw=im.w,bh=im.h;
 if(bw<16||bh<16){super(center,jumpScale);return;}
 // Equal-size slots. Use a common visual bounding box to avoid a tiny partner.
 
 localFit=live()?localStack(bx,by,bw,bh,partner.w,partner.h,viewMode):fit(bx,by,bw,bh,145,376,665,236);
 if(live()){
  localInputTop=layout(viewMode).localY-10;
  // Each hull fits the same slot independently: comparable displayed sizes.

  CSurface::GL_PushMatrix();CSurface::GL_Translate(localFit.x,localFit.y);CSurface::GL_Scale(localFit.s,localFit.s,1);CSurface::GL_Translate(-shipPosition.x,-shipPosition.y);transformed=true;
 }
 FriendlyPass sampling;
 bool capture=(++frames%2)==0;
 if(capture){paths.clear();for(auto&p:G_->GetResources()->images)if(path(p.first)&&!p.first.empty())paths[p.second]=p.first;for(auto&p:logicalPaths)paths[p.first]=p.second;captured=Frame();captured.x=bx;captured.y=by;captured.w=bw;captured.h=bh;mat={1,0,0,1,-float(shipPosition.x),-float(shipPosition.y)};stack.clear();recording=true;}
 super(center,jumpScale);
 recording=false;
 if(capture){
  unsigned dropped=normalize(captured);auto raw=encode(captured);Frame checked;
  if(decode(raw,checked)){pending=hex(raw);if(frames%300==0)hs_log_file("[FleetCoop275] SCENE_CAPTURED draws=%u skipped=%u bytes=%u\n",unsigned(captured.draws.size()),dropped,unsigned(raw.size()));}
  else if(frames%300==0)hs_log_file("[FleetCoop275] SCENE_REJECTED draws=%u skipped=%u bytes=%u box=%f,%f,%f,%f\n",unsigned(captured.draws.size()),dropped,unsigned(raw.size()),bx,by,bw,bh);
 }
 if(transformed)CSurface::GL_PopMatrix();
}
// CrewControl receives its own world coordinates, bypassing GetWorldCoordinates.
// Keep screen coordinates intact for portraits and HUD; replace only ship-world input.
static bool shipInput(int x,int y){return transformed&&live()&&shipRegion(x,y);}
static Point localWorld(int x,int y){
 if(y<localInputTop)return Point(-10000,-10000); // partner is read-only
 return Point(std::lround((x-localFit.x)/localFit.s),std::lround((y-localFit.y)/localFit.s));
}
HOOK_METHOD_PRIORITY(CommandGui, GetWorldCoordinates,100000,(Point p,bool target)->Point){
 if(!target&&shipInput(p.x,p.y))return localWorld(p.x,p.y);
 return super(p,target);
}
HOOK_METHOD_PRIORITY(CrewControl, MouseMove,100000,(int x,int y,int wx,int wy)->void){
 if(shipInput(x,y)){auto p=localWorld(x,y);wx=p.x;wy=p.y;}
 super(x,y,wx,wy);
}
HOOK_METHOD_PRIORITY(CrewControl, LButton,100000,(int x,int y,int wx,int wy,bool shift)->void){
 if(shipInput(x,y)){auto p=localWorld(x,y);static unsigned clicks=0;if(clicks++<20)hs_log_file("[FleetCoop275] CREW_CLICK screen=%d,%d old=%d,%d mapped=%d,%d\n",x,y,wx,wy,p.x,p.y);wx=p.x;wy=p.y;}
 super(x,y,wx,wy,shift);
}
static int sceneEnable(lua_State*L){enabled=lua_toboolean(L,1);heartbeat=Clock::now();if(!enabled){partner=Frame();previousPartner=Frame();pending.clear();transformed=false;}return 0;}
static int scenePoll(lua_State*L){if(pending.empty())return 0;lua_pushlstring(L,pending.data(),pending.size());pending.clear();return 1;}
static int sceneAccept(lua_State*L){size_t n;auto p=luaL_checklstring(L,1,&n);std::string raw;Frame f;bool ok=unhex(std::string(p,n),raw)&&decode(raw,f);if(ok){auto now=Clock::now();float dt=std::chrono::duration<float>(now-seen).count();previousPartner=dt<.25f?partner:Frame();blendSeconds=blendDuration(dt);partner=std::move(f);seen=now;}lua_pushboolean(L,ok);return 1;}
static int sceneCrisp(lua_State*L){crisp=lua_toboolean(L,1);return 0;}
static int sceneView(lua_State*L){
 int mode=luaL_checkinteger(L,1);if(mode<0||mode>2)return luaL_error(L,"view must be 0, 1 or 2");
 viewMode=mode;return 0;
}
static int sceneDraw(lua_State*L){if(!live()){lua_pushboolean(L,false);return 1;}auto l=layout(viewMode);auto f=fit(partner.x,partner.y,partner.w,partner.h,145,l.partnerY,665,l.partnerH);bool old=recording;recording=false;
 // Partner replay must not inherit the local ship's clipping/stencil mask.
 glPushAttrib(GL_ENABLE_BIT|GL_STENCIL_BUFFER_BIT|GL_SCISSOR_BIT|GL_POLYGON_BIT);
 glDisable(GL_STENCIL_TEST);glDisable(GL_SCISSOR_TEST);glDisable(GL_CULL_FACE);
 // Apply the scale once to original geometry. Rounding after scaling used to
 // collapse subpixel room walls and shift their edges relative to textures.
 CSurface::GL_PushMatrix();CSurface::GL_Translate(f.x,f.y);CSurface::GL_Scale(f.s,f.s,1);
 FriendlyPass sampling;
 auto display=smoothCrew(previousPartner,partner,std::chrono::duration<float>(Clock::now()-seen).count()/blendSeconds);
 unsigned textured=0,rectangles=0;for(auto&d:display.draws){GL_Texture*t=nullptr;if(!d.image.empty()){auto resources=G_->GetResources();auto cached=resources->images.find(d.image);
 if(cached!=resources->images.end())t=cached->second;
 else {std::string name=d.image;if(name.compare(0,4,"img/")==0)name.erase(0,4);t=resources->GetImageId(name);}
 if(!t){static unsigned missing=0;if(missing++<20)hs_log_file("[FleetCoop275] SCENE_TEXTURE_MISSING %s\n",d.image.c_str());continue;}}std::vector<GL_ColorTexVertex>v;for(auto&a:d.vertices)v.push_back({a.x,a.y,a.u,a.v,a.r,a.g,a.b,a.a});if(t){sampleTexture(t);++textured;bool quads=d.vertices.size()%6==0;
 for(size_t i=0;quads&&i<d.vertices.size();i+=6)quads=imageQuad(d.vertices,i);
 if(quads){rectangles+=v.size()/6;for(size_t i=0;i<v.size();i+=6){auto&a=v[i];auto&b=v[i+1];auto&c=v[i+2];
 CSurface::GL_BlitImagePartial(t,a.x,a.y,b.x-a.x,c.y-a.y,a.u,b.u,a.v,c.v,1.f,GL_Color(a.r,a.g,a.b,a.a),false);}}
 else CSurface::GL_BlitMultiColorImage(t,v,false);
 }else for(size_t i=0;i+2<v.size();){
  if(imageQuad(d.vertices,i)){
   auto&a=v[i];auto&b=v[i+1];auto&c=v[i+2];
   CSurface::GL_DrawRect(a.x,a.y,b.x-a.x,c.y-a.y,GL_Color(a.r,a.g,a.b,a.a));i+=6;
  }else{
   CSurface::GL_DrawTriangle(Point(std::lround(v[i].x),std::lround(v[i].y)),Point(std::lround(v[i+1].x),std::lround(v[i+1].y)),Point(std::lround(v[i+2].x),std::lround(v[i+2].y)),GL_Color(v[i].r,v[i].g,v[i].b,v[i].a));i+=3;
  }
 }}
 static unsigned draws=0;if(++draws%300==0)hs_log_file("[FleetCoop275] SCENE_DRAW textured=%u total=%u rectangles=%u\n",textured,unsigned(partner.draws.size()),rectangles);
 CSurface::GL_PopMatrix();glPopAttrib();recording=old;lua_pushboolean(L,true);lua_pushboolean(L,std::chrono::duration<double>(Clock::now()-seen).count()>1);return 2;}
void fleet_register_scene(lua_State*L){const luaL_Reg f[]={{"enable",sceneEnable},{"poll",scenePoll},{"accept",sceneAccept},{"draw",sceneDraw},{"setView",sceneView},{"setCrisp",sceneCrisp},{nullptr,nullptr}};luaL_newlib(L,f);lua_pushinteger(L,6);lua_setfield(L,-2,"version");lua_setglobal(L,"FleetNativeScene");}
