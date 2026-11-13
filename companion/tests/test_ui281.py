import unittest
from pathlib import Path
from lupa.lua53 import LuaRuntime
class ThemeTests(unittest.TestCase):
    def test_unicode_bounds_and_color_restored_on_draw_error(self):
        l=LuaRuntime(unpack_returned_tuples=True)
        l.execute("""
        color='original'
        Graphics={GL_Color=function(...)return 'theme'end,
        CSurface={GL_GetColor=function()return color end,GL_SetColor=function(c)color=c end},
        freetype={easy_measureWidth=function(f,s)return utf8.len(s)*8 end,
        easy_print=function()error('draw failed')end}}
        """)
        l.execute(Path('ui_theme.lua').read_text())
        self.assertEqual(l.eval("FleetUI281.fit('ééééé',32)"),'é...')
        self.assertEqual(l.eval("FleetUI281.fit('abcd',8)"),'')
        l.execute("pcall(function()FleetUI281.text(0,0,'test',80)end)")
        self.assertEqual(l.globals().color,'original')
