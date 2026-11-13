#include "../native/fleet_scene_codec.hpp"
#include <cassert>
int main(){using namespace fleet26;
 Frame a;a.w=600;a.h=300;a.draws={{"people/human_base.png",{{0,0,0,0,1,1,1,1},{20,0,1,0,1,1,1,1},{20,20,1,1,1,1,1,1}}}};
 Frame b=a;for(auto&v:b.draws[0].vertices)v.x+=12;
 auto half=smoothCrew(a,b,.5f);assert(half.draws[0].vertices[0].x==6);
 assert(smoothCrew(a,b,2).draws[0].vertices[0].x==12);
 assert(smoothCrew(a,b,-1).draws[0].vertices[0].x==0);
 auto c=b;c.draws[0].image="ship/hull.png";assert(smoothCrew(a,c,.5).draws[0].vertices[0].x==12);
 c=b;c.draws[0].vertices[0].u=.5;assert(smoothCrew(a,c,.5).draws[0].vertices[0].x==12);
 c=b;c.draws[0].vertices[0].r=.5;assert(smoothCrew(a,c,.5).draws[0].vertices[0].x==12);
 c=b;c.draws[0].vertices[0].x=60;assert(smoothCrew(a,c,.5).draws[0].vertices[0].x==60);
 c=b;c.draws.push_back(c.draws[0]);assert(smoothCrew(a,c,.5).draws[0].vertices[0].x==12);
 c=b;c.w=500;assert(smoothCrew(a,c,.5).draws[0].vertices[0].x==12);
 assert(blendDuration(5)==.08f);assert(blendDuration(.001)==.016f);
}