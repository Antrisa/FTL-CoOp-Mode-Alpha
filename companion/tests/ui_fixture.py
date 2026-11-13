from pathlib import Path
def load_ui(l):
    l.execute('''
    Graphics=Graphics or {};Graphics.CSurface=Graphics.CSurface or {};Graphics.freetype=Graphics.freetype or {}
    Graphics.CSurface.GL_GetColor=function()return {r=1,g=1,b=1,a=1}end
    Graphics.CSurface.GL_SetColor=function(c)end
    Graphics.freetype.easy_measureWidth=Graphics.freetype.easy_measureWidth or function(font,s)return #s*8 end
    ''')
    l.execute(Path('ui_theme.lua').read_text())
