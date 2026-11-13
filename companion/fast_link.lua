-- Optional native transport. Stock Hyperspace falls back to existing keyboard path.
FleetFastLink={}
local M=FleetFastLink
local ticks=0
local hello=false
local last=0
local native=FleetNativeTransport
local function emit(s)log('[FleetCoop7] SHIP_DIAG|FAST|'..s)end
function M.ready()return native and native.version==1 and hello and native.connected() and ticks-last<180 end
function M.send(s)return M.ready() and native.send(s)end
function M.tick()
 ticks=ticks+1
 if FleetScene26 then FleetScene26.tick()end
 if not FleetScene26 and FleetFastView then FleetFastView.tick()end
 if not native or native.version~=1 then if FleetPause27 then FleetPause27.tick()end;return end
 local ok,err=pcall(function()
  local messages=native.poll()
  if not native.connected() then
   hello=false
   if ticks%120==1 then native.connect()end
   return
  end
  if not hello and ticks%30==1 then native.send('HELLO|1')end
  for _,line in ipairs(messages)do
   if line=='HELLO|1' then hello=true;last=ticks;emit('CONNECTED');native.send('BUILD|2816')
   elseif line=='PONG' then last=ticks
   elseif hello and line=='SCENE_ACK' then last=ticks;if FleetScene26 then FleetScene26.ack()end
   elseif hello and line:sub(1,6)=='PAUSE|' then
    last=ticks;if FleetPause27 then FleetPause27.receive(line)end
   elseif hello and line:sub(1,5)=='JUMP|' then
    last=ticks;if FleetJump24 then FleetJump24.receive(line)end
   elseif hello and line:sub(1,7)=='COMBAT|' then
    last=ticks;if FleetCombat22 then FleetCombat22.receive(line)end
   elseif hello and line:sub(1,6)=='SCENE|' then
    last=ticks;if FleetScene26 then FleetScene26.receive(line)end;native.send('SCENE_ACK')
   elseif hello and line:sub(1,5)=='VIEW|' then
    if FleetFastView then FleetFastView.receive(line)end
   elseif hello then
    local id,hull,maximum,guard,data=line:match('^STATE|(%d+)|(%d+)|(%d+)|(%d+)|([%x]*)$')
    if id then
     id=tonumber(id);hull=tonumber(hull);maximum=tonumber(maximum);guard=tonumber(guard)
     if id<=30 and maximum>=1 and maximum<=255 and hull<=maximum and guard<=4294967295 and #data<=1024 then
      if FleetShips17 then FleetShips17.receive(1+id+hull*32+maximum*8192,guard)end
      if #data>0 and FleetInterior19 then FleetInterior19.receiveRaw(data,guard)end
      last=ticks
     end
    end
   end
  end
  if FleetJump24 then FleetJump24.tick()end
  if ticks%60==0 then native.send('PING');native.send('BUILD|2816')end
 end)
 if not ok then hello=false;native.close();emit('ERROR|'..tostring(err))end
 -- Consume queued heartbeats before testing deadlines.
 if FleetCombat22 then FleetCombat22.tick()end
 if FleetPause27 then FleetPause27.tick()end
end
script.on_init(function()hello=false;last=0;if native then native.close()end end)

script.on_load(function()emit(native and 'NATIVE_AVAILABLE' or 'NATIVE_MISSING|Using keyboard fallback')end)
