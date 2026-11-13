-- Explicit vanilla merchant allowlist. No generic single-choice bypass.
FleetTrade2812={}
local M=FleetTrade2812
local transaction=nil
local main="There is a black market hub here. You receive a message, \"These are dangerous times. If you have extra military-grade explosives, we'll gladly pay you for them.\""
local labels={"Sell 5 missiles for 15 scrap.","Sell 10 missiles for 30 scrap.","Sell 15 missiles for 45 scrap.","Ignore the station."}
local function context(state)
 return state and state.content and state.content:match('^([^|]+|[^|]+|[^|]+)|')
end
function M.isOffer(state)
 if not state or state.count~=4 or tostring(state.box.mainText)~=main then return false end
 local c=state.box:GetChoices()
 for i=0,3 do if not c[i] or tostring(c[i].text)~=labels[i+1] or (c[i].type~=0 and c[i].type~=1)then return false end end
 return true
end
function M.localEvent(state)
 local ctx=context(state)
 if not ctx then transaction=nil;return false end
 if M.isOffer(state)then
  transaction={context=ctx,offer=state.token};return true
 end
 if transaction and ctx==transaction.context and state.token~=transaction.offer then
  local c=state.box:GetChoices()[0]
  if state.count==1 and c and c.type==0 and tostring(c.text)=='Continue...' and
     (not transaction.result or transaction.result==state.token)then
   transaction.result=state.token;return true
  end
 end
 transaction=nil;return false
end
script.on_init(function()transaction=nil end)
