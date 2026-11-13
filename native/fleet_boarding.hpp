#pragma once
#include <vector>
#include <string>
struct CrewMember;
struct lua_State;
struct FleetCrewRecord { CrewMember* crew; std::string species; float maximum; };
const std::vector<FleetCrewRecord>& fleet_boarding_roster();
bool fleet_boarding_active();
bool fleet_boarding_alive_pointer(CrewMember* crew);
void fleet_boarding_mirror(CrewMember* crew, bool away, bool dead);
void fleet_register_boarding(lua_State* L);

bool fleet_boarding_blocks_teleport(int shipId);
bool fleet_boarding_hidden(CrewMember* crew);
