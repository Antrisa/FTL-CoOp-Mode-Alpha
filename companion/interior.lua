-- Live read-only floorplan, not a second ShipManager. No remote state writes.
FleetInterior19={}
local M=FleetInterior19
local pending=nil
local remote=nil
local age=10000
local lastError=''
local lastGeometry=''
local function emit(s)log('[FleetCoop7] SHIP_DIAG|INTERIOR|'..s)end
local function hash(s)
 local h=0;for i=1,#s do h=(h*65599+s:byte(i))%4294967296 end;return h
end
local function context()
 if not Hyperspace.App.world.bStartedGame or Hyperspace.App.menu.bOpen then return nil end
 local map=Hyperspace.App.world.starMap
 if not map.currentLoc then return nil end
 return string.format('%.0f|%.0f|%.0f|%.0f',Hyperspace.Global.currentSeed,map.worldLevel,map.currentLoc.loc.x,map.currentLoc.loc.y)
end
local function byte(v)
 v=math.floor(v+0.5);assert(v>=0 and v<=255,'byte range');return string.char(v)
end
local function xy(v)return byte(v/7+64)end
function M.capture()
 local ok,result=pcall(function()
  local s=Hyperspace.ships.player
  local r=s.ship.vRoomList;local c=s.vCrewList;local systems=s.vSystemList
  assert(r:size()>=1 and r:size()<=32,'room limit')
  local rooms,crew,sys={},{},{}
  for i=0,r:size()-1 do
   local room=r[i];local a=room.rect
   rooms[#rooms+1]=byte(room.iRoomId)..xy(a.x)..xy(a.y)..byte(a.w/7)..byte(a.h/7)
  end
  for i=0,c:size()-1 do
   local a=c[i]
   if not a.bDead and a.currentShipId==s.iShipId then
    assert(#crew<16,'crew limit')
    crew[#crew+1]=xy(a.x)..xy(a.y)..byte(math.max(0,math.min(100,100*a.health.first/a.health.second)))..byte(a.intruder and 1 or 0)
   end
  end
  for i=0,systems:size()-1 do
   local a=systems[i]
   if a.roomId>=0 then
    assert(#sys<20,'system limit')
    sys[#sys+1]=byte(a.roomId)..byte(a.iSystemType)..byte(a.healthState.first)..byte(a.healthState.second)..byte(a.powerState.first)
   end
  end
  local version=1;local geometry=''
  local geometryOk,encoded=pcall(function()
   local a=s.ship.shipImage
   local box=Hyperspace.ShipGraph.GetShipInfo(s.iShipId).shipBox
   assert(a.w>0 and a.h>0,'hull dimensions')
   return xy(a.x+box.x)..xy(a.y+box.y)..byte(a.w/7)..byte(a.h/7)
  end)
  if geometryOk then version=2;geometry=encoded end
  local mode=geometryOk and 'HULL_GEOMETRY_OK' or ('HULL_GEOMETRY_UNAVAILABLE|'..tostring(encoded))
  if mode~=lastGeometry then lastGeometry=mode;emit(mode)end
  local raw=byte(version)..byte(#rooms)..byte(#crew)..byte(#sys)..geometry..table.concat(rooms)..table.concat(crew)..table.concat(sys)
  return (raw:gsub('.',function(ch)return string.format('%02x',ch:byte())end))
 end)
 if ok then return result end
 if tostring(result)~=lastError then lastError=tostring(result);emit('CAPTURE_ERROR|'..lastError)end
 return nil
end
local function decode(s)
 local version,nr,nc,ns=s:byte(1,4)
 assert((version==1 or version==2) and nr and nr>=1 and nr<=32 and nc<=16 and ns<=20,'counts')
 assert(#s==(version==2 and 8 or 4)+nr*5+nc*4+ns*5,'length')
 local out={rooms={},crew={},systems={}};local ids={};local i=5
 if version==2 then
  local x,y,w,h=s:byte(5,8);assert(w>0 and h>0,'hull dimensions')
  out.hull={x=(x-64)*7,y=(y-64)*7,w=w*7,h=h*7};i=9
 end
 for n=1,nr do
  local id,x,y,w,h=s:byte(i,i+4);i=i+5
  assert(id<=31 and not ids[id] and w>0 and h>0,'room')
  local room={id=id,x=(x-64)*7,y=(y-64)*7,w=w*7,h=h*7}
  ids[id]=room;out.rooms[n]=room
 end
 for n=1,nc do
  local x,y,hp,flags=s:byte(i,i+3);i=i+4
  assert(hp<=100 and flags<=1,'crew')
  out.crew[n]={x=(x-64)*7,y=(y-64)*7,hp=hp,enemy=flags==1}
 end
 for n=1,ns do
  local room,kind,hp,maximum,power=s:byte(i,i+4);i=i+5
  assert(ids[room] and kind<=20 and maximum>=1 and maximum<=16 and hp<=maximum and power<=16,'system')
  out.systems[n]={room=ids[room],kind=kind,hp=hp,maximum=maximum,power=power}
 end
 return out
end
function M.contextGuard()local c=context();return c and hash(c) or nil end
function M.receiveRaw(hex,guard)
 local ctx=context()
 if not ctx or hash(ctx)~=guard or #hex>1024 or #hex%2~=0 or hex:find('[^%x]') then return false end
 local data=hex:gsub('..',function(s)return string.char(tonumber(s,16))end)
 local ok,value=pcall(decode,data)
 if not ok then return false end
 value.context=ctx;remote=value;age=0
 return true
end
function M.receive(op,n,g)
 local ctx=context()
 if op==50 then
  pending=nil
  if n>0 and ctx and hash(ctx)==g then pending={seq=n,context=ctx,data='',age=0}end
 elseif op==51 then
  if not pending or pending.context~=ctx then pending=nil;return end
  if #pending.data>=518 then pending=nil;return end
  local bytes={}
  for b=2,0,-1 do bytes[#bytes+1]=string.char(math.floor(n/256^b)%256)end
  for b=3,0,-1 do bytes[#bytes+1]=string.char(math.floor(g/256^b)%256)end
  pending.data=pending.data..table.concat(bytes)
 elseif op==52 then
  local p=pending;pending=nil
  if not p or p.seq~=n or p.context~=ctx or #p.data<6 then return end
  local length=p.data:byte(1)*256+p.data:byte(2)
  if length>512 or #p.data~=math.ceil((length+2)/7)*7 then return end
  local data=p.data:sub(3,2+length)
  if hash(data)~=g then emit('REJECTED_CHECKSUM');return end
  local ok,value=pcall(decode,data)
  if not ok then emit('REJECTED_DATA');return end
  value.context=ctx;remote=value;age=0
  emit('APPLIED|'..string.format('%.0f',n)..'|rooms='..#value.rooms..'|crew='..#value.crew..'|systems='..#value.systems)
 end
end
function M.tick()
 age=age+1
 local ctx=context()
 if remote and remote.context~=ctx then remote=nil end
 if pending then
  pending.age=pending.age+1
  if pending.age>900 or pending.context~=ctx then pending=nil end
 end
end
local names={[0]='SH',[1]='EN',[2]='O2',[3]='WP',[4]='DR',[5]='MED',[6]='PIL',[7]='SNS',[8]='DOOR',[9]='TEL',[10]='CLK',[11]='ART',[12]='BAT',[13]='CLN',[14]='MC',[15]='HACK'}
function M.draw(x,y,w,h,texture)
 if not remote or remote.context~=context() then return false end
 local minx,miny,maxx,maxy=1e9,1e9,-1e9,-1e9
 for _,r in ipairs(remote.rooms)do minx=math.min(minx,r.x);miny=math.min(miny,r.y);maxx=math.max(maxx,r.x+r.w);maxy=math.max(maxy,r.y+r.h)end
 local hull=texture and remote.hull
 if hull then minx=math.min(minx,hull.x);miny=math.min(miny,hull.y);maxx=math.max(maxx,hull.x+hull.w);maxy=math.max(maxy,hull.y+hull.h)end
 local scale=math.min((w-12)/(maxx-minx),(h-16)/(maxy-miny))
 local ox=x+(w-(maxx-minx)*scale)/2-minx*scale
 local oy=y+(h-(maxy-miny)*scale)/2-miny*scale
 local function rect(a,b,c,d,r,g,bl)Graphics.CSurface.GL_DrawRect(a,b,c,d,Graphics.GL_Color(r,g,bl,1))end
 if hull then
  Graphics.CSurface.GL_BlitImagePartial(texture,ox+hull.x*scale,oy+hull.y*scale,hull.w*scale,hull.h*scale,0,1,0,1,1,Graphics.GL_Color(1,1,1,1),false)
 end
 if age>600 then Graphics.freetype.easy_print(5,x+4,y+h-12,'INTERIOR UPDATE DELAYED')end
 for _,r in ipairs(remote.rooms)do
  rect(ox+r.x*scale,oy+r.y*scale,r.w*scale,r.h*scale,.55,.65,.7)
  rect(ox+r.x*scale+1,oy+r.y*scale+1,r.w*scale-2,r.h*scale-2,.08,.13,.18)
 end
 for _,s in ipairs(remote.systems)do
  local r=s.room;local px,py=ox+r.x*scale+2,oy+r.y*scale+2
  local width=math.max(1,r.w*scale-4)
  rect(px,py,width,4,.4,.1,.1)
  rect(px,py,width*s.hp/s.maximum,4,.2,.8,.3)
  rect(px,py+5,width*math.min(s.power/s.maximum,1),2,.2,.6,1)
  local label=names[s.kind] or tostring(s.kind)
  if width>=#label*8 and r.h*scale>=27 then Graphics.freetype.easy_print(5,px,py+8,label)end
 end
 for _,c in ipairs(remote.crew)do
  rect(ox+c.x*scale-3,oy+c.y*scale-3,6,6,c.enemy and 1 or .2,c.enemy and .25 or .9,.9)
  rect(ox+c.x*scale-3,oy+c.y*scale+4,6*c.hp/100,2,.2,1,.3)
 end
 return true
end
script.on_init(function()pending=nil;remote=nil;age=10000 end)
