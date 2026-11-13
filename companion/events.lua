-- Event snapshot and per-screen token. UTF-8 bytes are hex encoded in logs.
FleetCoop10={}
local M=FleetCoop10
local serial=math.random(1,16777215)
local previous=''
local epoch=0
local frame=0
local function hex(s)
    return (s:gsub('.',function(c) return string.format('%02x',string.byte(c)) end))
end
local function integer(n) return string.format('%.0f',n) end
function M.capture()
    local app=Hyperspace.App
    if not app.world.bStartedGame or app.menu.bOpen or not app.gui.choiceBoxOpen then
        if previous~='' then serial=serial+1;previous='' end
        return nil
    end
    local box=app.gui.choiceBox
    if not box.bOpen then return nil end
    local choices=box:GetChoices()
    if choices:size()<1 or choices:size()>9 then return nil end
    local main=tostring(box.mainText)
    if #main>8000 then return nil end
    local list={}
    for i=0,choices:size()-1 do
        local text=tostring(choices[i].text)
        if #text>2000 then return nil end
        list[#list+1]=integer(choices[i].type)..','..hex(text)
    end
    local map=app.world.starMap
    if not map.currentLoc then return nil end
    local context=integer(Hyperspace.Global.currentSeed)..'|'..integer(map.worldLevel)..'|'..integer(map.currentLoc.loc.x)..','..integer(map.currentLoc.loc.y)
    local content=context..'|'..hex(main)..'|'..table.concat(list,';')
    local signature=tostring(epoch)..'|'..content
    if previous~=signature then serial=serial+1;previous=signature end
    return {token=serial,content=content,count=choices:size(),box=box}
end
function M.safeCapture()
    local ok,result=pcall(M.capture)
    if ok then
        if result==nil and previous~='' then serial=serial+1;previous='' end
        return result
    end
    log('[FleetCoop7] ERROR|Event capture: '..tostring(result):gsub('[\r\n|]',' '))
    return nil
end
local ev=Defines.InternalEvents
if ev.POST_CREATE_CHOICEBOX then
    script.on_internal_event(ev.POST_CREATE_CHOICEBOX,function() epoch=epoch+1 end)
end
script.on_init(function()epoch=epoch+1;previous='' end)
script.on_internal_event(ev.ON_TICK,function()
    frame=frame+1
    if frame%60~=0 then return end
    local state=M.safeCapture()
    if state then log('[FleetCoop7] EVENT|'..integer(state.token)..'|'..state.content)
    else log('[FleetCoop7] EVENT_NONE') end
end)
