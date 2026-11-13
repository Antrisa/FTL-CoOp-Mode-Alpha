// Host-authoritative enemy state only. Never applies to the friendly ship.
#include "Global.h"
#include "fleet_boarding.hpp"
#include <sstream>
#include <iomanip>
#include <functional>
#include <set>
#include <cmath>
extern "C" {
#include "lua.h"
#include "lauxlib.h"
}
bool fleet_enemy_replica();
namespace {
bool finite(float n,float lo,float hi){return std::isfinite(n)&&n>=lo&&n<=hi;}
ShipManager* enemy(){return G_->GetShipManager(1);}
int capture(lua_State*L){auto e=enemy();if(!e)return 0;std::ostringstream o;o<<std::fixed<<std::setprecision(4)<<(fleet_boarding_active()?"E28 ":"E26 ")<<(fleet_boarding_active()?fleet_boarding_roster().size():e->vCrewList.size())<<' '<<e->ship.vOuterWalls.size()<<' '<<e->ship.vRoomList.size()<<' ';
 if(fleet_boarding_active()){
  const auto &roster=fleet_boarding_roster();
  for(size_t i=0;i<roster.size();++i){auto &r=roster[i];auto c=r.crew;bool valid=fleet_boarding_alive_pointer(c);bool dead=!valid||c->bDead||c->health.first<=0;
   int location=valid&&c->iRoomId>=0?c->currentShipId:-1;bool aboard=valid&&location==1;
   o<<"C "<<i<<' '<<r.species<<' '<<(aboard?c->x:0)<<' '<<(aboard?c->y:0)<<' '<<(dead?0:c->health.first)<<' '<<r.maximum<<' '<<(aboard?c->iRoomId:-1)<<' '<<dead<<' '<<location<<' ';
  }
 }else{
  for(size_t i=0;i<e->vCrewList.size();++i){auto c=e->vCrewList[i];o<<"C "<<i<<' '<<c->species<<' '<<c->x<<' '<<c->y<<' '<<c->health.first<<' '<<c->health.second<<' '<<c->iRoomId<<' '<<c->bDead<<' ';}
 }
 for(size_t x=0;x<e->fireSpreader.grid.size();++x)for(size_t y=0;y<e->fireSpreader.grid[x].size();++y){auto&f=e->fireSpreader.grid[x][y];if(f.fDamage>0)o<<"F "<<x<<' '<<y<<' '<<f.fDamage<<' ';}
 for(size_t i=0;i<e->ship.vOuterWalls.size();++i)o<<"B "<<i<<' '<<e->ship.vOuterWalls[i]->fDamage<<' ';
 if(e->oxygenSystem)for(size_t i=0;i<e->oxygenSystem->oxygenLevels.size();++i)o<<"O "<<i<<' '<<e->oxygenSystem->oxygenLevels[i]<<' ';
 for(auto s:e->vSystemList)o<<"R "<<s->iSystemType<<' '<<s->fRepairOverTime<<' '<<s->fDamageOverTime<<' '<<s->bOnFire<<' '<<s->bBreached<<' ';
 o<<"END";auto s=o.str();if(s.size()>48000)return 0;lua_pushlstring(L,s.data(),s.size());return 1;
}
bool apply(const std::string&data){
 auto e=enemy();if(!e||!fleet_enemy_replica()||data.size()>48000)return false;
 std::istringstream in(data);std::string tag;size_t nc,nb,nr;
 if(!(in>>tag>>nc>>nb>>nr)||(tag!="E26"&&tag!="E28")||nc!=(tag=="E28"?fleet_boarding_roster().size():e->vCrewList.size())||nb!=e->ship.vOuterWalls.size()||nr!=e->ship.vRoomList.size()||nc>64||nb>1024||nr>64)return false;
 bool boarding=tag=="E28";if(boarding&&!fleet_boarding_active())return false;
 std::vector<std::function<void()>> changes;std::set<std::string> ids;bool ended=false;
 while(in>>tag){if(tag=="END"){ended=true;break;}if(changes.size()>4096)return false;int i;float a,b,c,d;int room,dead;
 if(tag=="C") {std::string race;int location=1;
 if(!(in>>i>>race>>a>>b>>c>>d>>room>>dead)||i<0||size_t(i)>=nc||!finite(a,-2048,4096)||!finite(b,-2048,4096)||!finite(c,0,1000)||!finite(d,1,1000)||c>d||(dead!=0&&dead!=1))return false;
 if(boarding&&(!(in>>location)||location<-1||location>1))return false;
 bool away=boarding&&location!=1;
 if(room<-1||(!away&&room>=0&&size_t(room)>=nr)||(room==-1&&!dead&&!away)||(away&&room!=-1))return false;
 auto v=boarding?fleet_boarding_roster()[i].crew:e->vCrewList[i];
 if(boarding&&!fleet_boarding_alive_pointer(v)){
  const auto &r=fleet_boarding_roster()[i];
  if(!dead||c!=0||r.species!=race||std::abs(r.maximum-d)>.1)return false;
  if(!ids.insert(tag+":"+std::to_string(i)).second)return false;
  continue;
 }
 if(v->species!=race||std::abs(v->health.second-d)>.1)return false;
 changes.push_back([v,a,b,c,room,dead,boarding,away](){
  if(boarding)fleet_boarding_mirror(v,away,dead!=0);
  if(!away){v->x=a;v->y=b;v->iRoomId=room;if(v->crewAnim)v->crewAnim->lastPosition=Pointf(a,b);}
  v->health.first=c;v->bDead=dead!=0;
 });}

 else if(tag=="F"){int y;if(!(in>>i>>y>>a)||i<0||size_t(i)>=e->fireSpreader.grid.size()||y<0||size_t(y)>=e->fireSpreader.grid[i].size()||!finite(a,0,1000))return false;auto f=&e->fireSpreader.grid[i][y];if(a>f->fMaxDamage||f->roomId<0||size_t(f->roomId)>=nr)return false;tag+="_"+std::to_string(y);changes.push_back([f,a](){f->fDamage=a;f->bWasOnFire=a>0;});}
 else if(tag=="B"){if(!(in>>i>>a)||i<0||size_t(i)>=nb||!finite(a,0,1000)||a>e->ship.vOuterWalls[i]->fMaxDamage)return false;auto v=e->ship.vOuterWalls[i];changes.push_back([v,a](){v->fDamage=a;});}
 else if(tag=="O"){if(!(in>>i>>a)||!e->oxygenSystem||i<0||size_t(i)>=e->oxygenSystem->oxygenLevels.size()||!finite(a,0,100))return false;changes.push_back([e,i,a](){e->oxygenSystem->oxygenLevels[i]=a;});}
 else if(tag=="R"){int fire,breach;if(!(in>>i>>a>>b>>fire>>breach)||i<0||i>20||!finite(a,0,10000)||!finite(b,0,10000)||(fire!=0&&fire!=1)||(breach!=0&&breach!=1))return false;auto v=e->GetSystem(i);if(!v)return false;changes.push_back([v,a,b,fire,breach](){v->fRepairOverTime=a;v->fDamageOverTime=b;v->bOnFire=fire;v->bBreached=breach;});}
 else return false;
 if(!ids.insert(tag+":"+std::to_string(i)).second)return false;
 }
 if(!ended||(in>>tag))return false;
 for(size_t i=0;i<nc;++i)if(!ids.count("C:"+std::to_string(i)))return false;
 for(size_t i=0;i<nb;++i)if(!ids.count("B:"+std::to_string(i)))return false;
 for(auto sys:e->vSystemList)if(!ids.count("R:"+std::to_string(sys->iSystemType)))return false;
 if(e->oxygenSystem)for(size_t i=0;i<e->oxygenSystem->oxygenLevels.size();++i)if(!ids.count("O:"+std::to_string(i)))return false;
 // Validation completes before any mutation. Authoritative absence clears fires.
 for(auto&column:e->fireSpreader.grid)for(auto&f:column){f.fDamage=0;f.bWasOnFire=false;}
 for(auto&change:changes)change();
 e->fireSpreader.count=0;std::fill(e->fireSpreader.roomCount.begin(),e->fireSpreader.roomCount.end(),0);
 for(auto r:e->ship.vRoomList){r->iFireCount=0;r->fires.clear();}
 for(auto&column:e->fireSpreader.grid)for(auto&f:column)if(f.fDamage>0&&f.roomId>=0&&size_t(f.roomId)<nr){++e->fireSpreader.count;if(size_t(f.roomId)<e->fireSpreader.roomCount.size())++e->fireSpreader.roomCount[f.roomId];auto r=e->ship.vRoomList[f.roomId];++r->iFireCount;r->fires.push_back(f.fireAnimation);}
 if(e->oxygenSystem){float sum=0;for(float o:e->oxygenSystem->oxygenLevels)sum+=o;e->oxygenSystem->fTotalOxygen=e->oxygenSystem->oxygenLevels.empty()?0:sum/e->oxygenSystem->oxygenLevels.size();}
 return true;
}
int accept(lua_State*L){size_t n;auto s=luaL_checklstring(L,1,&n);lua_pushboolean(L,apply(std::string(s,n)));return 1;}
}
void fleet_register_effects(lua_State*L){const luaL_Reg f[]={{"capture",capture},{"apply",accept},{nullptr,nullptr}};luaL_newlib(L,f);lua_pushinteger(L,2);lua_setfield(L,-2,"version");lua_setglobal(L,"FleetNativeEffects");}
