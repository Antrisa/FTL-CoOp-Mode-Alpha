#include "../native/fleet_scene_codec.hpp"
#include <cassert>
#include <limits>
int main(){using namespace fleet26;Frame f;f.w=600;f.h=300;f.draws.push_back({"ship/kestral_base.png",{{0,0,0,0,1,1,1,1},{600,0,1,0,1,1,1,1},{600,300,1,1,1,1,1,1}}});Frame out;auto s=encode(f);assert(decode(s,out));assert(out.draws[0].vertices[2].y==300);assert(!decode(s.substr(0,s.size()-1),out));assert(!decode(s+"x",out));std::string raw;assert(unhex(hex(s),raw)&&raw==s);assert(!unhex("gg",raw));f.draws[0].image="../evil.png";assert(!decode(encode(f),out));f.draws[0].image="ship/test.png";f.draws[0].vertices[0].x=std::numeric_limits<float>::infinity();assert(!decode(encode(f),out));
 for(auto dimensions:std::vector<std::pair<float,float>>{{600,300},{500,500},{750,250}}){auto a=fit(-80,-40,dimensions.first,dimensions.second,145,376,665,236);for(float x:{-80.f,100.f,dimensions.first-80}){float screen=a.x+x*a.s;assert(std::abs((screen-a.x)/a.s-x)<.001);}assert(a.y-40*a.s>=376-.01);assert(a.y+(dimensions.second-40)*a.s<=612+.01);}
 for(auto dims:std::vector<std::pair<float,float>>{{600,300},{300,600},{900,100},{100,900}}){auto local=localStack(0,0,600,300,dims.first,dims.second);auto remote=fit(0,0,dims.first,dims.second,145,122,665,236);assert(remote.s*dims.first>=.5f*local.s*600-.001f);assert(remote.s*dims.second>=.5f*local.s*300-.001f);}
 Frame clean;clean.w=600;clean.h=300;
 Draw good={"ship/kestral_base.png",{{0,0,0,0,1,1,1,1},{600,0,1,0,1,1,1,1},{600,300,1,1,1,1,1,1}}};
 clean.draws={good,{"",{}},good};clean.draws[2].vertices[0].u=500;
 assert(normalize(clean)==2);assert(clean.draws.size()==1);assert(decode(encode(clean),out));
 clean.draws[0].vertices[0].r=1.5;clean.draws[0].vertices[1].a=-.5;
 assert(normalize(clean)==0);assert(decode(encode(clean),out));assert(out.draws[0].vertices[0].r==1);
 clean.draws[0].vertices[0].x=std::numeric_limits<float>::quiet_NaN();assert(normalize(clean)==1);assert(!decode(encode(clean),out));


 std::vector<Vertex> quad={{10,20,0,0,1,1,1,1},{110,20,1,0,1,1,1,1},{110,70,1,1,1,1,1,1},{10,20,0,0,1,1,1,1},{110,70,1,1,1,1,1,1},{10,70,0,1,1,1,1,1}};
 assert(imageQuad(quad,0));assert(!imageQuad(quad,1));
 quad[4].u=.5;assert(!imageQuad(quad,0));quad[4].u=1;
 quad[2].a=.5;assert(!imageQuad(quad,0));quad[2].a=1;
 quad[1].y=21;assert(!imageQuad(quad,0));
 assert(shipRegion(400,450));assert(shipRegion(400,200));
 assert(!shipRegion(50,200));assert(!shipRegion(1000,450));assert(!shipRegion(400,650));
 // Every detail view keeps both complete hulls in nonoverlapping slots,
 // preserves the partner/local size floor, and round-trips crew coordinates.
 for(int mode=0;mode<3;++mode){auto l=layout(mode);
  assert(l.partnerY+l.partnerH<=l.localY-18);assert(l.localY+l.localH<=612);
  for(auto dims:std::vector<std::pair<float,float>>{{600,300},{300,600},{900,100},{100,900}}){
   auto a=localStack(-80,-40,600,300,dims.first,dims.second,mode);
   auto b=fit(0,0,dims.first,dims.second,145,l.partnerY,665,l.partnerH);
   assert(a.y-40*a.s>=l.localY-.001);assert(a.y+260*a.s<=612.001);
   assert(b.s*dims.first>=a.s*300-.001);assert(b.s*dims.second>=a.s*150-.001);
   for(float x:{-80.f,100.f,520.f})assert(std::abs(((a.x+x*a.s)-a.x)/a.s-x)<.001);
  }
 }
 // A thin room rectangle remains a floating-point quad at replay time.
 std::vector<Vertex> thin={{0.25f,0,0,0,1,1,1,1},{1.25f,0,0,0,1,1,1,1},{1.25f,35,0,0,1,1,1,1},{0.25f,0,0,0,1,1,1,1},{1.25f,35,0,0,1,1,1,1},{0.25f,35,0,0,1,1,1,1}};
 assert(imageQuad(thin,0));
}
