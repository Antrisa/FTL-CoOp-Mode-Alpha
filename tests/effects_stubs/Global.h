#pragma once
#include <vector>
#include <string>
#include <utility>
#include <algorithm>
#include <cassert>
struct Pointf{float x,y;Pointf(float X=0,float Y=0):x(X),y(Y){}};
struct Anim{Pointf lastPosition;};
struct CrewMember{int iShipId=1,currentShipId=1;bool bOutOfGame=false,bMindControlled=false;int emptyCalls=0;bool IsDrone(){return false;}void EmptySlot(){++emptyCalls;}void ClearTask(){}void ClearPath(){}std::string species="human";float x=0,y=0;std::pair<float,float>health={100,100};int iRoomId=0;bool bDead=false;Anim*crewAnim=nullptr;};
using Crew=CrewMember;
struct CrewFactory{std::vector<CrewMember*>crewMembers;};
struct Fire{float fDamage=0,fMaxDamage=100;int roomId=0;bool bWasOnFire=false;int fireAnimation=1;};
struct Wall{float fDamage=0,fMaxDamage=100;};
struct Room{int iFireCount=0;std::vector<int>fires;};
struct Sys{int iSystemType=3;float fRepairOverTime=0,fDamageOverTime=0;bool bOnFire=false,bBreached=false;};
struct Oxygen{std::vector<float>oxygenLevels={100,100};float fTotalOxygen=100;};
struct ShipManager{std::vector<Crew*>vCrewList;struct{std::vector<Wall*>vOuterWalls;std::vector<Room*>vRoomList;}ship;struct{std::vector<std::vector<Fire>>grid;int count=0;std::vector<int>roomCount={0,0};}fireSpreader;Oxygen*oxygenSystem=nullptr;std::vector<Sys*>vSystemList;Sys*GetSystem(int n){for(auto*s:vSystemList)if(s->iSystemType==n)return s;return nullptr;}};
struct Global{CrewFactory factory;CrewFactory*GetCrewFactory(){return &factory;}ShipManager*e=nullptr;ShipManager*GetShipManager(int n){assert(n==1);return e;}};
extern Global*G_;
