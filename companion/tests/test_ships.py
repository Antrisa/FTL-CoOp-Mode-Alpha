from ui_fixture import load_ui
import unittest
from pathlib import Path
from lupa.lua53 import LuaRuntime
from ship_view import validate_ship,parse_ship,guard,partner_ship,CATALOG
from input_bridge import ship_packet_keys
import test_event_vote

class ShipTests(unittest.TestCase):
    def data(self,i=1):return dict(id=i,hull=27,maximum=30,seed=7062026,level=0,x=43,y=168,seen=100)
    def test_parser_and_bounds(self):
        self.assertEqual(parse_ship('SHIP|1|27.0|30.0|7062026|0|43|168|END')['ship']['hull'],27)
        for s in ['SHIP|31|27|30|1|0|0|0|END','SHIP|1|31|30|1|0|0|0|END','SHIP|1|1|0|1|0|0|0|END']:
            self.assertIsNone(parse_ship(s))
        self.assertEqual(len(CATALOG),30)
    def test_peer_identity_and_fresh_context(self):
        p=[dict(id=1,ship_view=self.data(1)),dict(id=2,ship_view=self.data(5))]
        self.assertEqual(partner_ship(p,1,100),(5,27,30,guard(p[0]['ship_view'])))
        p[1]['ship_view']['x']=44;self.assertIsNone(partner_ship(p,1,100))
        p[1]['ship_view']['x']=43;self.assertIsNone(partner_ship(p,1,106))
    def test_display_packet_has_no_action_or_ack(self):
        t=test_event_vote.EventLuaTests();t.setUp();t.l.execute('FleetShips17={receive=function(n,g)received={n,g}end}')
        for k in ship_packet_keys(30,255,255,123):t.l.globals().callbacks.key(k)
        self.assertEqual(t.l.globals().received[1],1+30+(255<<5)+(255<<13))
        self.assertEqual(t.logs(),[])
    def lua(self):
        l=LuaRuntime(unpack_returned_tuples=True)
        l.execute('''callbacks={};logs={};texts={};images={}
        Defines={SDL={KEY_F7=288,KEY_ESCAPE=27},Chain={PREEMPT=1,CONTINUE=0},InternalEvents={ON_MOUSE_L_BUTTON_DOWN=1,ON_MOUSE_L_BUTTON_UP=2,ON_MOUSE_R_BUTTON_DOWN=3,ON_TICK=4},RenderEvents={MOUSE_CONTROL=1}}
        script={on_internal_event=function(k,f)callbacks[k]=f end,on_render_event=function(k,b,a)render=a end,on_init=function(f)init=f end,on_load=function(f)f()end}
        log=function(s)table.insert(logs,s)end
        player={myBlueprint={blueprintName='PLAYER_SHIP_HARD'},ship={hullIntegrity={first=27,second=30}}}
        Hyperspace={App={world={bStartedGame=true,starMap={worldLevel=0,currentLoc={loc={x=43,y=168}}}},menu={bOpen=false},gui={bPaused=false,choiceBoxOpen=false}},Global={currentSeed=7062026},ships={player=player},Blueprints={GetShipBlueprint=function(self,name,sector)return {imgFile=name}end},Resources={ImageExists=function(self,p)return true end,GetImageId=function(self,p)return {width=400,height=200,path=p}end}}
        Graphics={GL_Color=function(...)return {}end,CSurface={GL_DrawRect=function(...)end,GL_BlitImagePartial=function(tex,...)table.insert(images,tex.path)end},freetype={easy_print=function(font,x,y,s)table.insert(texts,s)end}}
        ''')
        load_ui(l);l.execute(Path('ships.lua').read_text());return l
    def test_actual_peer_asset_upper_local_lower(self):
        l=self.lua();d=self.data();g=guard(d)
        l.globals().FleetShips17.receive(1+5+(23<<5)+(30<<13),g)
        self.assertEqual(l.globals().FleetShips17.key(288),1)
        self.assertTrue(l.globals().Hyperspace.App.gui.bPaused)
        l.execute('render()')
        paths=list(l.globals().images.values())
        self.assertEqual(paths,['ship/PLAYER_SHIP_STEALTH_2_base.png','ship/PLAYER_SHIP_HARD_base.png'])
        self.assertIn('Hull 23 / 30',list(l.globals().texts.values()))
        self.assertEqual(l.globals().callbacks[1](),1)
        l.globals().FleetShips17.key(288);self.assertEqual(l.globals().callbacks[1](),0)
        self.assertTrue(l.globals().Hyperspace.App.gui.bPaused)
    def test_wrong_guard_and_expiry_hide_peer(self):
        l=self.lua();l.globals().FleetShips17.receive(1+5+(23<<5)+(30<<13),99)
        l.globals().FleetShips17.key(288);l.execute('render()')
        self.assertEqual(len(list(l.globals().images.values())),1)
        l.globals().FleetShips17.receive(1+5+(23<<5)+(30<<13),guard(self.data()))
        l.execute('for i=1,601 do callbacks[4]() end;images={};render()')
        self.assertEqual(len(list(l.globals().images.values())),1)
    def test_report_lua_matches_python_and_events_block_view(self):
        l=self.lua();l.execute('for i=1,60 do callbacks[4]() end')
        lines=[s for s in l.globals().logs.values() if '[FleetCoop7] SHIP|' in s]
        self.assertEqual(parse_ship(lines[0].split('[FleetCoop7] ')[1])['ship']['id'],1)
        l.execute('Hyperspace.App.gui.choiceBoxOpen=true')
        l.globals().FleetShips17.key(288)
        self.assertFalse(l.globals().Hyperspace.App.gui.bPaused)
    def test_live_display_needs_no_f7_and_preserves_controls(self):
        l=self.lua()
        l.globals().FleetShips17.receive(1+5+(23<<5)+(30<<13),guard(self.data()))
        l.execute('render();callbacks[4]()')
        self.assertEqual(list(l.globals().images.values()),['ship/PLAYER_SHIP_STEALTH_2_base.png'])
        self.assertFalse(l.globals().Hyperspace.App.gui.bPaused)
        self.assertEqual(l.globals().callbacks[1](),0)
        self.assertEqual(l.globals().FleetShips17.key(49),0)
        self.assertIn('PARTNER  |  HULL 23 / 30',list(l.globals().texts.values()))
    def test_live_display_hides_in_menus_events_map_and_stale_context(self):
        for change in ['Hyperspace.App.gui.choiceBoxOpen=true',
                       'Hyperspace.App.gui.menu_pause=true',
                       'Hyperspace.App.gui.event_pause=true',
                       'Hyperspace.App.gui.bHideUI=true',
                       'Hyperspace.App.world.starMap.bOpen=true',
                       'FleetPanel11={isOpen=function()return true end}',
                       'Hyperspace.App.world.starMap.currentLoc.loc.x=99',
                       'Hyperspace.App.menu.bOpen=true']:
            with self.subTest(change=change):
                l=self.lua()
                l.globals().FleetShips17.receive(1+5+(23<<5)+(30<<13),guard(self.data()))
                l.execute(change+';render()')
                self.assertEqual(list(l.globals().images.values()),[])
                self.assertFalse(l.globals().Hyperspace.App.gui.bPaused)
    def test_live_damage_update_and_reconnect(self):
        l=self.lua();g=guard(self.data())
        l.globals().FleetShips17.receive(1+5+(23<<5)+(30<<13),g)
        l.execute('for i=1,601 do callbacks[4]() end;render()')
        self.assertEqual(len(list(l.globals().images.values())),1)
        self.assertTrue(any('UPDATE DELAYED' in t for t in l.globals().texts.values()))
        l.globals().FleetShips17.receive(1+5+(19<<5)+(30<<13),g)
        l.execute('render()')
        self.assertIn('PARTNER  |  HULL 19 / 30',list(l.globals().texts.values()))
