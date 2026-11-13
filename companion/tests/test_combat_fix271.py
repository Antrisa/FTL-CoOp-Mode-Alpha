import unittest,socket
from pathlib import Path
import test_combat
from test_scene26 import sample
from fast_local import LocalCompanion
import scene

class CombatFixTests(unittest.TestCase):
    def test_arrival_dialog_and_neutral_ship_never_arm(self):
        for field in ('Hyperspace.App.gui.choiceBox={bOpen=true}',
                      'Hyperspace.App.gui.event_pause=true',
                      'Hyperspace.ships.enemy._targetable.hostile=false',
                      'Hyperspace.ships.player.bJumping=true'):
            l=test_combat.LuaCombatTests().lua();l.execute(field+';for i=1,500 do FleetCombat22.tick()end;callbacks.key(6)')
            self.assertFalse(any('|ARM|' in x for x in l.globals().sent.values()))
            self.assertFalse(l.globals().replica)
    def test_closed_dialog_stable_hostile_encounter_auto_arms(self):
        l=test_combat.LuaCombatTests().lua()
        l.execute('Hyperspace.App.gui.choiceBox={bOpen=true};for i=1,40 do FleetCombat22.tick()end;Hyperspace.App.gui.choiceBox.bOpen=false;for i=1,16 do FleetCombat22.tick()end')
        self.assertTrue(any('|ARM|' in x for x in l.globals().sent.values()))
        self.assertTrue(l.globals().Hyperspace.App.gui.bPaused)
    def fast(self,l):
        l.execute("incoming={};FleetNativeTransport={version=1,connected=function()return true end,close=function()end,connect=function()end,send=function(s)return true end,poll=function()local a=incoming;incoming={};return a end}")
        l.execute(Path('fast_link.lua').read_text())
        l.execute("incoming={'HELLO|1'};FleetFastLink.tick()")
    def test_heartbeat_at_deadline_is_processed_before_timeout(self):
        h=test_combat.LuaCombatTests();l=h.lua();h.start(l,'H');self.fast(l)
        l.execute('for i=1,179 do FleetCombat22.tick()end')
        l.execute("incoming={'COMBAT|START|testepoch|42|H'};FleetFastLink.tick()")
        self.assertNotIn('STOPPED',l.globals().FleetCombat22.status())
    def test_paused_event_keeps_combat_heartbeat_alive(self):
        h=test_combat.LuaCombatTests();l=h.lua();h.start(l,'H');self.fast(l)
        l.execute("Hyperspace.App.gui.event_pause=true;for i=1,1200 do if i%30==0 then incoming={'COMBAT|START|testepoch|42|H'}end;FleetFastLink.tick()end")
        self.assertNotIn('STOPPED',l.globals().FleetCombat22.status())
        # Genuine loss still stops combat; an event does not disable its watchdog.
        l.execute('for i=1,181 do FleetFastLink.tick()end')
        self.assertIn('STOPPED',l.globals().FleetCombat22.status())
    def test_lua_scene_waits_for_ack_and_keeps_latest(self):
        from test_interior import InteriorTests
        l=InteriorTests().lua()
        l.execute("Defines.InternalEvents.ON_KEY_DOWN=10;Defines.SDL.KEY_F9=290;sent={};data='aa';FleetNativeScene={version=6,setCrisp=function()end,setView=function()end,enable=function()end,poll=function()return data end};FleetFastLink={ready=function()return true end,send=function(s)table.insert(sent,s);return true end}")
        l.execute(Path('scene.lua').read_text())
        l.execute("FleetScene26.tick();data='bb';for i=1,100 do FleetScene26.tick()end")
        self.assertEqual(len(l.globals().sent),1)
        l.execute('FleetScene26.ack();FleetScene26.tick()')
        self.assertTrue(l.globals().sent[2].endswith('|bb'))
    def test_backlogged_scene_receiver_does_not_block_combat(self):
        c=LocalCompanion(lambda x:None,port=0);c.start()
        try:
            with socket.create_connection(('127.0.0.1',c.port)) as s:
                s.settimeout(2);f=s.makefile('rb');s.sendall(b'HELLO|1\n');self.assertEqual(f.readline(),b'HELLO|1\n')
                c.set_scene(sample());self.assertTrue(f.readline().startswith(b'SCENE|'))
                # The peer has consumed but not acknowledged the first scene.
                for i in range(100):c.set_scene(sample(i))
                c.send_combat('COMBAT|START|epoch|42|H')
                self.assertEqual(f.readline(),b'COMBAT|START|epoch|42|H\n')
                s.sendall(b'SCENE_ACK\n');self.assertEqual(scene.parse(f.readline().decode().strip()),sample(99))
        finally:c.stop()
    def test_hidden_scene_is_acknowledged(self):
        l=test_combat.LuaCombatTests().lua();self.fast(l)
        l.execute("sent={};FleetNativeTransport.send=function(s)table.insert(sent,s);return true end;FleetScene26={tick=function()end,receive=function()end};incoming={'SCENE|42|aa'};FleetFastLink.tick()")
        self.assertIn('SCENE_ACK',list(l.globals().sent.values()))
