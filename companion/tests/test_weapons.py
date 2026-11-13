"""Weapon wire round trips and authoritative/replica routing (mock FTL API)."""
import unittest
import test_combat
from combat import parse,CombatRoom

class WeaponTests(unittest.TestCase):
    def setup_lua(self,kind,role='G',fake=False):
        harness=test_combat.LuaCombatTests();l=harness.lua()
        l.globals().weapon_type=kind;l.globals().fragment_fake=fake
        l.execute('''
        bp.type=weapon_type+0.0;bp.name='TEST_WEAPON';bp.length=150.0
        bp.miniProjectiles=vec({[0]={image='flak_test',fake=fragment_fake}},1)
        calls={}
        local function record(kind,...)
          local args={...};local q={damage={}};spawned=spawned+1
          calls[#calls+1]={kind=kind,args=args,q=q};return q
        end
        local sp=Hyperspace.App.world.space
        sp.CreateLaserBlast=function(self,...)return record('laser',...)end
        sp.CreateMissile=function(self,...)return record('missile',...)end
        sp.CreateBeam=function(self,...)return record('beam',...)end
        sp.CreateBomb=function(self,...)return record('bomb',...)end
        sp.CreateBurstProjectile=function(self,...)return record('flak',...)end
        function projectile()
          return {target={x=35,y=35},target1={x=10,y=15},target2={x=140,y=90},
           position={x=10,y=20},heading=90.0,ownerId=0.0,targetId=1.0,currentSpace=0.0,
           flight_animation={animName='flak_test'},
           damage={iDamage=2.0,iShieldPiercing=1.0,fireChance=3.0,breachChance=4.0,
            stunChance=5.0,iIonDamage=6.0,iSystemDamage=7.0,iPersDamage=8.0,iStun=9.0,
            bHullBuster=true,bLockdown=true,crystalShard=false,bFriendlyFire=true,ownerId=0},
           Kill=function(self)self.killed=true end,GetType=function()return weapon_type==2 and 5 or 1 end}
        end
        ''')
        harness.start(l,role);return l
    def fire(self,l,mutate=''):
        l.execute('p=projectile();'+mutate+';callbacks.fire(p,{blueprint=bp})')
        return next(x for x in reversed(list(l.globals().sent.values())) if '|SHOT|' in x or '|SPAWN|' in x)
    def test_every_vanilla_weapon_family_round_trip(self):
        for kind,name in enumerate(('laser','missile','beam','bomb','flak')):
            with self.subTest(kind=name):
                guest=self.setup_lua(kind);line=self.fire(guest)
                self.assertEqual(len(parse(line)),20)
                self.assertTrue(guest.globals().p.killed)
                host=self.setup_lua(kind,'H')
                host.globals().FleetCombat22.receive(line)
                c=host.globals().calls[1];self.assertEqual(c.kind,name)
                self.assertEqual(c.q.damage.iIonDamage,6)
                self.assertEqual(c.q.damage.breachChance,4)
                self.assertTrue(c.q.damage.bLockdown)
                self.assertIn('COMBAT|ACK|testepoch|1',list(host.globals().sent.values()))
                if kind==2:
                    self.assertEqual(c.args[5].x,10);self.assertEqual(c.args[6].x,140)
                    self.assertEqual(c.args[8],150)
                if kind==3:self.assertEqual(c.args[3].x,35)
    def test_fake_flak_and_off_room_scatter_preserved(self):
        guest=self.setup_lua(4,fake=True)
        line=self.fire(guest,"p.target.x=-100;p.target.y=800;for k,v in pairs(p.damage)do if type(v)=='number'then p.damage[k]=0 else p.damage[k]=false end end;p.damage.ownerId=-1;p.damage.bFriendlyFire=true")
        self.assertEqual(parse(line)[17],'1')
        host=self.setup_lua(4,'H',fake=True);host.globals().FleetCombat22.receive(line)
        self.assertEqual(host.globals().calls[1].kind,'flak')
        self.assertTrue(host.globals().calls[1].args[3])
        self.assertEqual(host.globals().calls[1].q.damage.iDamage,0)
    def test_bomb_int_min_origin_is_not_transmitted(self):
        l=self.setup_lua(3);line=self.fire(l,'p.position.x=-2147483648;p.position.y=-2147483648')
        self.assertEqual(parse(line)[7:9],['0.00','0.00'])
    def test_self_bombs_stay_local_for_both_players(self):
        for role in ('H','G'):
            l=self.setup_lua(3,role);l.execute('sent={};p=projectile();p.targetId=0;callbacks.fire(p,{blueprint=bp})')
            self.assertIsNone(l.globals().p.killed);self.assertEqual(len(l.globals().sent),0)
    def test_enemy_fire_is_local_on_both_games_and_never_forwarded(self):
        for role in ('H','G'):
            for kind in range(5):
                l=self.setup_lua(kind,role);l.execute('sent={};p=projectile();p.ownerId=1;p.currentSpace=1;p.targetId=0;callbacks.fire(p,{blueprint=bp})')
                self.assertIsNone(l.globals().p.killed)
                self.assertEqual(len(l.globals().sent),0)
    def test_enemy_ion_stun_fire_does_not_request_pause(self):
        for role in ('H','G'):
            l=self.setup_lua(1,role)
            l.execute("sent={};Hyperspace.App.gui.bPaused=false;bp.name='ION_STUN';p=projectile();p.ownerId=1;p.currentSpace=1;p.targetId=0;p.damage.iIonDamage=1;p.damage.iStun=5;callbacks.fire(p,{blueprint=bp})")
            self.assertFalse(l.globals().Hyperspace.App.gui.bPaused)
            self.assertIsNone(l.globals().p.killed)
            self.assertEqual(len(l.globals().sent),0)
    def test_old_remote_enemy_beam_is_ignored(self):
        g=self.setup_lua(2)
        g.globals().FleetCombat22.receive('COMBAT|SPAWN|testepoch|1|TEST_WEAPON|10|10|0|0|90|1|0|2|50|50|45|none|0|1,0,0,0,0,0,0,0,0,0,0,0,1|1')
        self.assertEqual(g.globals().spawned,0)
    def test_guest_beam_does_not_apply_second_damage_or_die_at_shield(self):
        g=self.setup_lua(2)
        self.assertEqual(g.eval('callbacks.beam(Hyperspace.ships.enemy,nil,nil,nil,true,2)')[0],1)
        self.assertEqual(g.eval('callbacks.beam(Hyperspace.ships.player,nil,nil,nil,true,2)')[0],0)
        g.execute('p=projectile();callbacks.shield(Hyperspace.ships.enemy,p,nil,nil)')
        self.assertIsNone(g.globals().p.killed)
    def test_mismatch_blueprint_or_flak_image_never_acknowledged(self):
        for change in ('kind','image'):
            g=self.setup_lua(4);line=self.fire(g)
            h=self.setup_lua(4,'H')
            if change=='kind':h.execute('bp.type=1')
            else:line=line.replace('flak_test','invalid_image')
            h.globals().FleetCombat22.receive(line)
            self.assertEqual(h.globals().spawned,0)
            self.assertNotIn('COMBAT|ACK|testepoch|1',list(h.globals().sent.values()))
    def test_multiple_friendly_artillery_is_in_loadout(self):
        for count in (1,2):
            h=test_combat.LuaCombatTests();l=h.lua();l.globals().count=count
            l.execute("Hyperspace.ships.player.artillerySystems=vec({[0]={projectileFactory={blueprint={name='ARTILLERY',type=2}}},[1]={projectileFactory={blueprint=bp}}},count);Hyperspace.ships.player.HasSystem=function(self,id)return id==11 end")
            l.execute('callbacks.key(6);for i=1,30 do FleetCombat22.tick()end')
            arms=[x for x in l.globals().sent.values() if '|ARM|' in x]
            self.assertIn('ARTILLERY',arms[0])
    def test_payload_rejects_nonfinite_huge_and_damaging_fake(self):
        line=self.fire(self.setup_lua(4));p=line.split('|')
        for idx,value in ((12,'9'),(14,'nan'),(15,'999999'),(11,'0.5'),(17,'1'),(19,'9')):
            with self.subTest(idx=idx):
                q=p.copy();q[idx]=value
                with self.assertRaises(ValueError):parse('|'.join(q))
    def test_flak_volley_fits_rate_budget_but_flood_stops(self):
        r=CombatRoom();out=[];send=lambda cid,s:out.append((cid,s));members={1:None,2:None};guards={1:42,2:42}
        for cid in members:r.receive(cid,'COMBAT|ARM|42|enemy|player|TEST_WEAPON',1,members,guards,send,10)
        base=self.fire(self.setup_lua(4)).replace('testepoch',r.active['epoch']).split('|')
        for seq in range(1,130):
            base[3]=str(seq);r.receive(2,'|'.join(base),1,members,guards,send,10)
            if seq==64:self.assertIsNotNone(r.active)
        self.assertIsNone(r.active);self.assertTrue(any('shot_rate' in line for _,line in out))
    def test_extended_beam_duplicate_relay_and_host_spawn_once(self):
        g=self.setup_lua(2);line=self.fire(g)
        r=CombatRoom();out=[];send=lambda cid,s:out.append((cid,s));members={1:None,2:None};guards={1:42,2:42}
        for cid in members:r.receive(cid,'COMBAT|ARM|42|enemy|player|TEST_WEAPON',1,members,guards,send,10)
        line=line.replace('testepoch',r.active['epoch'])
        r.receive(2,line,1,members,guards,send,10);r.receive(2,line,1,members,guards,send,10)
        self.assertEqual(out.count((1,line)),1)
        h=self.setup_lua(2,'H');line=line.replace(r.active['epoch'],'testepoch')
        h.globals().FleetCombat22.receive(line);h.globals().FleetCombat22.receive(line)
        self.assertEqual(h.globals().spawned,1)

if __name__=='__main__':unittest.main()
