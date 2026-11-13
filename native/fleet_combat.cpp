// Host enemy state remains authoritative; guest native weapons target its own ship.
#include "Global.h"
#include <algorithm>
#include <chrono>
extern "C" {
#include "lua.h"
#include "lauxlib.h"
}
namespace {
bool replica=false;
bool jumpGate=false, jumpRelease=false;
Location* voteOrigin=nullptr;
Location* voteTarget=nullptr;
unsigned voteSerial=0;
unsigned deliveredSerial=0;
using Clock=std::chrono::steady_clock;
auto lastJumpTick=Clock::now();
bool neighbor(StarMap* m,Location* loc){
 return m && m->currentLoc && loc && loc!=m->currentLoc &&
 std::find(m->currentLoc->connectedLocations.begin(),m->currentLoc->connectedLocations.end(),loc)!=m->currentLoc->connectedLocations.end();
}
void capture(StarMap* m){
 if(!jumpGate || jumpRelease || m->bChoosingNewSector || !m->readyToTravel)return;
 auto target=m->potentialLoc;
 // Sector transitions use a synthetic location; this gate covers neighbors only.
 if(!neighbor(m,target))return;
 m->readyToTravel=false;m->bOpen=true;
 if(neighbor(m,target) && !m->outOfFuel){voteOrigin=m->currentLoc;voteTarget=target;++voteSerial;}
}
}
// Do not call WeaponSystem::OnLoop outside ShipManager's normal update lifecycle.
// Guest enemy weapons/AI run locally; host snapshots reconcile enemy state.
HOOK_METHOD_PRIORITY(StarMap, MouseClick, 99999, (int x,int y) -> void)
{
 super(x,y);capture(this);
}
HOOK_METHOD_PRIORITY(StarMap, GetNewLocation, 99999, () -> Location*)
{
 // Also intercept keyboard paths before the world consumes a destination.
 capture(this);
 return super();
}
bool fleet_enemy_replica(){return replica;}
static int setReplica(lua_State* L){replica=lua_toboolean(L,1);return 0;}
static int jumpEnable(lua_State* L){
 jumpGate=lua_toboolean(L,1);lastJumpTick=Clock::now();
 if(!jumpGate){voteOrigin=nullptr;voteTarget=nullptr;deliveredSerial=voteSerial;}
 return 0;
}
static bool validVote(StarMap* m,unsigned serial){
 return jumpGate && serial==voteSerial && voteTarget && voteOrigin==m->currentLoc &&
 m->bOpen && !m->bChoosingNewSector && !m->outOfFuel && m->shipManager &&
 m->shipManager->fuel_count>0 && neighbor(m,voteTarget) &&
 std::chrono::duration<double>(Clock::now()-lastJumpTick).count()<2;
}
static int jumpPoll(lua_State* L){
 lastJumpTick=Clock::now();
 if(voteTarget && voteSerial!=deliveredSerial){
  deliveredSerial=voteSerial;lua_pushinteger(L,voteSerial);
  lua_pushinteger(L,(int)voteTarget->loc.x);lua_pushinteger(L,(int)voteTarget->loc.y);return 3;
 }
 return 0;
}
static int jumpCheck(lua_State* L){
 auto m=&G_->GetWorld()->starMap;unsigned serial=luaL_checkinteger(L,1);
 lua_pushboolean(L,validVote(m,serial));return 1;
}
static int jumpCommit(lua_State* L){
 auto m=&G_->GetWorld()->starMap;unsigned serial=luaL_checkinteger(L,1);
 if(!validVote(m,serial)){lua_pushboolean(L,false);return 1;}
 // Use FTL's normal world-consumed travel request, never teleport the ship.
 m->potentialLoc=voteTarget;m->readyToTravel=true;m->bOpen=false;
 jumpRelease=true;voteTarget=nullptr;lua_pushboolean(L,true);return 1;
}
static int jumpArrived(lua_State* L){jumpRelease=false;voteOrigin=nullptr;voteTarget=nullptr;return 0;}
void fleet_register_combat(lua_State* L){
 const luaL_Reg funcs[]={{"setReplica",setReplica},{"jumpEnable",jumpEnable},{"jumpPoll",jumpPoll},{"jumpCheck",jumpCheck},{"jumpCommit",jumpCommit},{"jumpArrived",jumpArrived},{nullptr,nullptr}};
 luaL_newlib(L,funcs);lua_pushinteger(L,4);lua_setfield(L,-2,"version");lua_setglobal(L,"FleetNativeCombat");
}
