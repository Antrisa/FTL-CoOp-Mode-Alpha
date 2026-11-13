#define FLEET_BOARDING_TEST
#include "../native/fleet_boarding.cpp"
#include "../native/fleet_effects.cpp"
Global global;Global*G_=&global;bool replicaMode=true;
bool fleet_enemy_replica(){return replicaMode;}
bool fleet_local_connected(){return false;}
int main(){Crew crew;Anim anim;crew.crewAnim=&anim;Wall wall;Room a,b;Sys sys;Oxygen o;ShipManager e;global.e=&e;e.vCrewList={&crew};e.ship.vOuterWalls={&wall};e.ship.vRoomList={&a,&b};e.vSystemList={&sys};e.oxygenSystem=&o;e.fireSpreader.grid.resize(1);e.fireSpreader.grid[0].resize(2);e.fireSpreader.grid[0][1].roomId=1;
 std::string s="E26 1 1 2 C 0 human 35 70 60 100 1 0 F 0 1 50 B 0 20 O 0 80 O 1 50 R 3 20 0 1 1 END";
 assert(apply(s));assert(crew.health.first==60&&crew.x==35&&anim.lastPosition.y==70);assert(wall.fDamage==20&&e.fireSpreader.count==1&&b.iFireCount==1);assert(o.fTotalOxygen==65&&sys.bOnFire);
 // Malformed trailing data is rejected without any partial mutation.
 assert(!apply(s+" C 0"));assert(crew.health.first==60&&wall.fDamage==20);
 auto bad=s;bad.replace(bad.find("human"),5,"mantis");assert(!apply(bad));assert(e.fireSpreader.count==1);
 replicaMode=false;assert(!apply(s));replicaMode=true;
 std::string repaired="E26 1 1 2 C 0 human 35 70 90 100 1 0 B 0 0 O 0 100 O 1 100 R 3 0 0 0 0 END";
 assert(apply(repaired));assert(crew.health.first==90&&wall.fDamage==0&&e.fireSpreader.count==0&&b.iFireCount==0&&!sys.bOnFire);
 assert(!apply("E26 0 1 2 B 0 0 END"));assert(crew.health.first==90);
}
