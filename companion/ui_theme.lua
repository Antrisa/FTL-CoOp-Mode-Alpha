-- Presentation only: native FTL font, bounded labels, restored draw color.
FleetUI281={}
local M=FleetUI281
local font=12
function M.fit(value,width)
 local s=tostring(value):gsub('[\r\n\t]',' ')
 if Graphics.freetype.easy_measureWidth(font,s)<=width then return s end
 local chars={}
 for c in s:gmatch('[%z\1-\127\194-\244][\128-\191]*')do chars[#chars+1]=c end
 while #chars>0 and Graphics.freetype.easy_measureWidth(font,table.concat(chars)..'...')>width do chars[#chars]=nil end
 return Graphics.freetype.easy_measureWidth(font,'...')<=width and table.concat(chars)..'...' or ''
end
function M.text(x,y,s,width)
 local surface=Graphics.CSurface
 local old=surface.GL_GetColor()
 surface.GL_SetColor(Graphics.GL_Color(.93,.98,.94,1))
 local ok,err=pcall(Graphics.freetype.easy_print,font,x,y,M.fit(s,width or 640))
 surface.GL_SetColor(old)
 if not ok then error(err)end
end
function M.box(x,y,w,h)
 Graphics.CSurface.GL_DrawRect(x,y,w,h,Graphics.GL_Color(.55,.72,.70,1))
 Graphics.CSurface.GL_DrawRect(x+1,y+1,w-2,h-2,Graphics.GL_Color(.035,.065,.075,.98))
end
function M.readable(s)return tostring(s):gsub('_',' ')end
