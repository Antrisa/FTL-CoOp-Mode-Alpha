// One real boarding party: enemy teleportation runs only on the host.
#include "Global.h"
#include "fleet_boarding.hpp"
#include <algorithm>
#include <set>
extern "C" {
#include "lua.h"
#include "lauxlib.h"
}
bool fleet_enemy_replica();
bool fleet_local_connected();
namespace {
bool active=false;
std::vector<FleetCrewRecord> roster;
std::set<CrewMember*> awayCrew;
bool tracked(CrewMember* c){for(auto &r:roster)if(r.crew==c)return true;return false;}
void clear(){
 // Restore native victory accounting after FINISH. Never turn a surviving
 // off-ship boarder into a dead enemy crew member on the guest.
 // Do not set native bOutOfGame: FTL may retire an out-of-game object.
 active=false;roster.clear();awayCrew.clear();
}
int begin(lua_State* L){
 clear();auto e=G_->GetShipManager(1);if(!e){lua_pushboolean(L,false);return 1;}
 // Capture once. Ship-local vectors change as crew teleport; identities do not.
 for(auto c:e->vCrewList)if(c->iShipId==1&&!c->IsDrone()){
  if(c->currentShipId!=1||c->bMindControlled||roster.size()>=64){clear();lua_pushboolean(L,false);return 1;}
  roster.push_back({c,c->species,c->health.second});
 }
 active=true;lua_pushboolean(L,true);return 1;
}
int end(lua_State*){clear();return 0;}
int boarders(lua_State* L){int n=0;for(auto c:G_->GetCrewFactory()->crewMembers)
 if(c->iShipId==1&&c->currentShipId==0&&!c->IsDrone()&&!c->bDead&&!c->bOutOfGame&&c->health.first>0)++n;
 lua_pushinteger(L,n);return 1;
}
int defeated(lua_State* L){bool dead=active&&!roster.empty();for(auto &r:roster)
 if(fleet_boarding_alive_pointer(r.crew)&&!r.crew->bDead&&r.crew->health.first>0)dead=false;
 lua_pushboolean(L,dead);return 1;
}
}
const std::vector<FleetCrewRecord>& fleet_boarding_roster(){return roster;}
bool fleet_boarding_active(){return active;}
bool fleet_boarding_alive_pointer(CrewMember* c){auto &v=G_->GetCrewFactory()->crewMembers;return std::find(v.begin(),v.end(),c)!=v.end();}
void fleet_boarding_mirror(CrewMember* c,bool away,bool dead){
 if(away||dead){if(!awayCrew.count(c)){c->EmptySlot();c->ClearTask();c->ClearPath();}awayCrew.insert(c);}
 else awayCrew.erase(c);
 // A remote boarder is not a second local boarding party. Keep its replica
 // out of simulation/rendering, without changing allegiance or transferring it.
 c->bDead=dead;
}
bool fleet_boarding_hidden(CrewMember* c){return active&&fleet_enemy_replica()&&awayCrew.count(c);}
bool fleet_boarding_blocks_teleport(int shipId){if(shipId!=1)return false;return active?fleet_enemy_replica():fleet_local_connected();}
#ifndef FLEET_BOARDING_TEST
HOOK_METHOD_PRIORITY(CompleteShip, InitiateTeleport, 100000, (int room,int command) -> void){
 if(fleet_boarding_blocks_teleport(iShipId))return;
 super(room,command);
}
HOOK_METHOD_PRIORITY(CrewMember, OnLoop, 100000, () -> void){
 if(active&&fleet_enemy_replica()&&tracked(this))return;
 super();
}
HOOK_METHOD_PRIORITY(CrewMember, OnRender, 100000, (bool outlineOnly) -> void){
 if(fleet_boarding_hidden(this))return;
 super(outlineOnly);
}
HOOK_METHOD_PRIORITY(CrewMember, Functional, 100000, () -> bool){
 if(fleet_boarding_hidden(this))return false;
 return super();
}
HOOK_METHOD_PRIORITY(CompleteShip, DeadCrew, 100000, () -> bool){
 // Remote-away replicas must not trigger a local crew-kill reward early.
 if(active&&fleet_enemy_replica()&&iShipId==1)return false;
 return super();
}
#endif
void fleet_register_boarding(lua_State*L){const luaL_Reg f[]={{"begin",begin},{"clear",end},{"boarders",boarders},{"defeated",defeated},{nullptr,nullptr}};luaL_newlib(L,f);lua_pushinteger(L,1);lua_setfield(L,-2,"version");lua_setglobal(L,"FleetNativeBoarding");}
