"""Lua integration with mocked Hyperspace objects, NOT an in-game test.
Optional developer dependency: pip install lupa. Not used by the application.
"""
import unittest
from pathlib import Path
from shared_map import parse_line
try:
    from lupa.lua53 import LuaRuntime
except ImportError:
    LuaRuntime=None

@unittest.skipUnless(LuaRuntime, 'Optional Lua harness requires lupa')
class LuaTests(unittest.TestCase):
    def setUp(self):
        self.lua=LuaRuntime(unpack_returned_tuples=True)
        self.lua.execute('''
        logs = {}; callbacks = {}
        function log(s) logs[#logs+1] = s end
        script = {
          on_load = function(f) callbacks.load=f end,
          on_init = function(f) callbacks.init=f end,
          on_internal_event = function(e,f) callbacks[e]=f end
        }
        Defines = {InternalEvents={GET_RUN_SEED='seed',MAIN_MENU='menu',ON_TICK='tick',JUMP_LEAVE='leave',JUMP_ARRIVE='arrive'}}
        function vector(t,n) t.size=function() return n end; return t end
        a={loc={x=10,y=20},nebula=false}
        b={loc={x=30,y=40},nebula=true}
        a.connectedLocations=vector({[0]=b},1)
        b.connectedLocations=vector({[0]=a},1)
        map={locations=vector({[0]=a,[1]=b},2), currentLoc=a, worldLevel=0}
        Hyperspace={Global={currentSeed=7062026},App={world={bStartedGame=true,starMap=map}}}
        ''')
        self.lua.execute((Path(__file__).resolve().parents[1]/'fleet_coop_v07.lua').read_text())
    def lines(self): return list(self.lua.globals().logs.values())
    def test_seed_hook_and_snapshot(self):
        self.assertEqual(self.lua.eval('callbacks.seed(false,42)'),(True,7062026))
        self.lua.execute('callbacks.load();callbacks.init(true);callbacks.tick()')
        data=parse_line(self.lines()[-1])
        self.assertEqual(data['position'],[10,20])
        self.assertEqual(data['nodes'],[[10,20,0,[1]],[30,40,1,[0]]])
    def test_player_jump_and_menu(self):
        self.lua.execute('callbacks.init(true);callbacks.tick();map.currentLoc=b;callbacks.arrive({iShipId=0});callbacks.tick()')
        self.assertEqual(parse_line(self.lines()[-1])['position'],[30,40])
        self.lua.execute('callbacks.menu()')
        n=len(self.lines())
        self.lua.execute('for i=1,250 do callbacks.tick() end')
        self.assertEqual(len(self.lines()),n)
    def test_errors_are_caught_and_reported(self):
        self.lua.execute('map.locations=nil;callbacks.init(false);callbacks.tick()')
        self.assertIn('[FleetCoop7] ERROR|',self.lines()[-1])
