#define FLEET_BOARDING_TEST
#include "../native/fleet_boarding.cpp"
#include "../native/fleet_effects.cpp"
Global global;Global*G_=&global;bool replicaMode=false;
bool linked=true;bool fleet_local_connected(){return linked;}
bool fleet_enemy_replica(){return replicaMode;}
int main(){
 Crew crew;Anim anim;crew.crewAnim=&anim;Room a,b;ShipManager enemy;global.e=&enemy;
 enemy.ship.vRoomList={&a,&b};enemy.vCrewList={&crew};global.factory.crewMembers={&crew};lua_State L;
 assert(fleet_boarding_blocks_teleport(1)); // hold until the session assigns a role
 begin(&L);assert(L.boolean&&fleet_boarding_active());
 assert(!fleet_boarding_blocks_teleport(1));replicaMode=true;assert(fleet_boarding_blocks_teleport(1));assert(!fleet_boarding_blocks_teleport(0));
 // A boarder leaves the host enemy: capture the persistent roster, not the shrinking ship vector.
 replicaMode=false;crew.currentShipId=0;crew.iRoomId=8;enemy.vCrewList.clear();capture(&L);
 assert(L.text.find("E28 1 0 2 C 0 human 0.0000 0.0000 100.0000 100.0000 -1 0 0 ")==0);
 std::string boarding=L.text;boarders(&L);assert(L.integer==1);defeated(&L);assert(!L.boolean);
 // Guest suppresses the duplicate party and does not assign friendly-ship room 8 to its enemy.
 replicaMode=true;crew.currentShipId=1;crew.iRoomId=0;enemy.vCrewList={&crew};
 assert(apply(boarding));assert(fleet_boarding_hidden(&crew)&&crew.emptyCalls==1&&crew.currentShipId==1&&crew.iRoomId==0);
 assert(apply(boarding));assert(crew.emptyCalls==1); // repeated state is idempotent
 std::string recall="E28 1 0 2 C 0 human 35 70 40 100 1 0 1 END";
 assert(apply(recall));assert(!fleet_boarding_hidden(&crew)&&crew.health.first==40&&crew.iRoomId==1);
 // Validate every row before mutating any crew. Away state cannot use an enemy room.
 assert(!apply("E28 1 0 2 C 0 human 0 0 1 100 1 0 0 END"));assert(crew.health.first==40);
 assert(!apply(recall+" garbage"));assert(crew.health.first==40);
 std::string transit="E28 1 0 2 C 0 human 0 0 40 100 -1 0 -1 END";
 assert(apply(transit)&&fleet_boarding_hidden(&crew));assert(apply(recall)&&!fleet_boarding_hidden(&crew));
 // Host-side boarder death is mirrored exactly once; tombstones survive factory cleanup.
 assert(apply("E28 1 0 2 C 0 human 0 0 0 100 -1 1 0 END"));assert(crew.bDead&&crew.health.first==0);
 defeated(&L);assert(L.boolean);global.factory.crewMembers.clear();
 capture(&L);assert(L.text.find("-1 1 -1 END")!=std::string::npos);assert(apply(L.text));
 assert(!apply(recall)); // no resurrection of an absent native object
 clear();assert(!fleet_boarding_active()&&fleet_boarding_blocks_teleport(1));linked=false;assert(!fleet_boarding_blocks_teleport(1));
 // Reset restores native victory accounting for surviving away replicas.
 crew.bDead=false;crew.health.first=100;crew.currentShipId=1;global.factory.crewMembers={&crew};begin(&L);
 assert(apply(boarding)&&fleet_boarding_hidden(&crew));clear();assert(!fleet_boarding_hidden(&crew));
}
