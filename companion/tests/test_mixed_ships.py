import unittest
import test_combat
import test_travel
from combat import CombatRoom
from jump_vote import JumpRoom
from ship_view import guard,partner_ship

class MixedShipTests(unittest.TestCase):
    def setUp(self):
        self.r=CombatRoom();self.out=[];self.members={1:None,2:None};self.guards={1:42,2:42}
    def receive(self,cid,line):self.r.receive(cid,line,1,self.members,self.guards,lambda c,s:self.out.append((c,s)),10)
    def start(self):
        self.receive(1,'COMBAT|ARM|42|enemy|kestrel_rooms_30hp|LASER_BURST_2')
        self.receive(2,'COMBAT|ARM|42|enemy|rock_rooms_40hp|MISSILES_1')
    def test_different_hulls_health_layouts_and_loadouts_start(self):
        self.start();self.assertIsNotNone(self.r.active)
        self.assertEqual(self.r.active['player_signatures'],{1:'kestrel_rooms_30hp',2:'rock_rooms_40hp'})
        self.assertTrue(self.out[-1][1].endswith('|G'))
        self.receive(1,'COMBAT|ARM|42|enemy|kestrel_rooms_30hp|LASER_BURST_2')
        self.receive(2,'COMBAT|ARM|42|enemy|rock_rooms_40hp|MISSILES_1')
        self.assertIsNotNone(self.r.active)
    def test_different_ship_does_not_authorize_partners_weapon(self):
        self.start();e=self.r.active['epoch'];self.out=[]
        wrong=f'COMBAT|SHOT|{e}|1|LASER_BURST_2|35|35|10|10|90|0'
        self.receive(2,wrong);self.assertEqual(self.out,[])
        right=wrong.replace('LASER_BURST_2','MISSILES_1');self.receive(2,right)
        self.assertEqual(self.out,[(1,right)])
    def test_own_hull_changes_still_stop_and_different_enemy_still_waits(self):
        self.start();self.receive(2,'COMBAT|ARM|42|enemy|changed_ship|MISSILES_1')
        self.assertIsNone(self.r.active)
        self.setUp();self.receive(1,'COMBAT|ARM|42|enemy|kestrel|LASER_BURST_2')
        self.receive(2,'COMBAT|ARM|42|other_enemy|rock|MISSILES_1')
        self.assertIsNone(self.r.active);self.assertIn('enemy_layout_mismatch',self.out[-1][1])
    def test_actual_lua_geometry_hashes_differ_and_can_join(self):
        h=test_combat.LuaCombatTests();games=[h.lua(),h.lua()]
        games[1].execute("Hyperspace.ships.player.myBlueprint.blueprintName='PLAYER_SHIP_ROCK';Hyperspace.ships.player.ship.hullIntegrity.second=40;Hyperspace.ships.player.ship.vRoomList=vec({[0]={iRoomId=7,rect={x=100,y=50,w=140,h=70}}},1)")
        arms=[]
        for game in games:
            game.execute('for i=1,16 do FleetCombat22.tick()end')
            arms.append(next(x for x in game.globals().sent.values() if '|ARM|' in x))
        self.assertNotEqual(arms[0].split('|')[4],arms[1].split('|')[4])
        for cid,line in enumerate(arms,1):self.receive(cid,line)
        self.assertIsNotNone(self.r.active)
        # Enemy HP updates must never copy onto the different local ship.
        games[1].globals().FleetCombat22.receive('COMBAT|START|testepoch|42|G')
        games[1].globals().FleetCombat22.receive('COMBAT|SNAP|testepoch|1|12|30|0|0|')
        self.assertEqual(games[1].globals().Hyperspace.ships.enemy.ship.hullIntegrity.first,12)
        self.assertEqual(games[1].globals().Hyperspace.ships.player.ship.hullIntegrity.second,40)
    def test_different_ships_can_vote_same_beacon_and_display_partner_hull(self):
        p=test_travel.players();s=p[0]['snapshot'];g=guard(dict(seed=s['seed'],level=s['level'],x=s['position'][0],y=s['position'][1]))
        for i,x in enumerate(p):x['ship_view']=dict(id=1 if i==0 else 19,hull=30 if i==0 else 37,maximum=30 if i==0 else 40,seed=s['seed'],level=s['level'],x=s['position'][0],y=s['position'][1],seen=100)
        r=JumpRoom();out=[];send=lambda c,s:out.append((c,s));x,y=test_travel.TARGET
        for cid in (1,2):r.receive(cid,f'JUMP|VOTE|{g}|1|{x}|{y}',p,send,100)
        self.assertEqual(r.pending['phase'],'prepare')
        self.assertEqual(partner_ship(p,1,100)[:3],(19,37,40))
    def test_unsupported_system_message_names_player_or_enemy(self):
        for who in ('player','enemy'):
            l=test_combat.LuaCombatTests().lua()
            l.execute(f'Hyperspace.ships.{who}.HasSystem=function(self,id)return id==4 end;for i=1,16 do FleetCombat22.tick()end')
            self.assertIn(who+'_system_drone_list_unavailable',l.globals().FleetCombat22.status())

    def test_cloak_and_clone_are_local_but_enemy_variants_remain_blocked(self):
        for system in (10,13):
            for who in ('player','enemy'):
                l=test_combat.LuaCombatTests().lua()
                l.execute(f'Hyperspace.ships.{who}.HasSystem=function(self,id)return id=={system} end;for i=1,16 do FleetCombat22.tick()end')
                armed=any('|ARM|' in x for x in l.globals().sent.values())
                self.assertEqual(armed,who=='player')
