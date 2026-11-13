import unittest
from pathlib import Path
import test_interior

class ClarityTests(unittest.TestCase):
    def lua(self, version=6):
        l=test_interior.InteriorTests().lua()
        l.execute('''Defines.InternalEvents.ON_KEY_DOWN=10;Defines.SDL.KEY_F9=290;Defines.SDL.KEY_F10=291
        views={};FleetNativeScene={version=6,enable=function()end,
        setCrisp=function(v)end,setView=function(v)table.insert(views,v)end,poll=function()end,
        draw=function()return true,false end};FleetFastLink={ready=function()return true end}''')
        l.globals().FleetNativeScene.version=version
        l.execute(Path('scene.lua').read_text())
        return l
    def test_detail_cycles_and_resets_without_gameplay_actions(self):
        l=self.lua()
        for expected_y,expected_name in ((286,'YOUR SHIP DETAIL'),(428,'PARTNER DETAIL'),(356,'BALANCED')):
            self.assertEqual(l.globals().callbacks[10](290),1)
            self.assertEqual(l.globals().FleetScene26.localLabelY(),expected_y)
            self.assertIn(expected_name,l.globals().FleetScene26.viewLabel())
            self.assertFalse(l.globals().Hyperspace.App.gui.bPaused)
        self.assertEqual(list(l.globals().views.values()),[1,2,0])
        l.globals().callbacks[10](290);l.globals().init()
        self.assertEqual(l.globals().FleetScene26.localLabelY(),356)
        self.assertEqual(list(l.globals().views.values())[-1],0)
    def test_map_event_menu_panel_and_old_dll_do_not_consume_f9(self):
        for state in ('Hyperspace.App.world.starMap.bOpen=true',
                      'Hyperspace.App.gui.choiceBoxOpen=true',
                      'Hyperspace.App.menu.bOpen=true',
                      'FleetPanel11={isOpen=function()return true end}'):
            l=self.lua();l.execute(state)
            self.assertEqual(l.globals().callbacks[10](290),0)
            self.assertEqual(len(l.globals().views),0)
        l=self.lua(4)
        self.assertFalse(l.globals().FleetScene26.available())
        self.assertEqual(l.globals().callbacks[10](290),0)
    def test_other_keys_pass_through(self):
        l=self.lua();self.assertEqual(l.globals().callbacks[10](32),0)
        self.assertEqual(len(l.globals().views),0)

    def test_f10_only_changes_texture_preference(self):
        l=self.lua();l.execute('filters={};FleetNativeScene.setCrisp=function(v)table.insert(filters,v)end')
        self.assertEqual(l.globals().callbacks[10](291),1)
        self.assertIn('SMOOTH',l.globals().FleetScene26.viewLabel())
        self.assertEqual(l.globals().callbacks[10](291),1)
        self.assertIn('CRISP',l.globals().FleetScene26.viewLabel())
        self.assertEqual(list(l.globals().filters.values()),[False,True])
        self.assertEqual(len(l.globals().views),0)
        self.assertFalse(l.globals().Hyperspace.App.gui.bPaused)
    def test_cadence_is_bounded_and_ack_prevents_queue_growth(self):
        l=self.lua();l.execute("sent=0;FleetNativeScene.poll=function()return 'aa'end;FleetFastLink.send=function(s)sent=sent+1;return true end")
        m=l.globals().FleetScene26
        for i in range(60):m.tick();m.ack()
        self.assertEqual(l.globals().sent,30)
        for i in range(60):m.tick()
        self.assertEqual(l.globals().sent,31)
        m.ack();m.tick();m.tick();self.assertEqual(l.globals().sent,32)
