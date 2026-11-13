import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from authority.encounter import Encounter,Rejected

def state():
    def ship():return dict(hull=30,maximum=30,shields=2,rooms=[0,1],crew=[dict(id=1,room=0,x=10,y=10,health=100,maximum=100)],weapons=[dict(id=0,charge=10,required=10,enabled=True)])
    return {k:ship() for k in ('ally_a','ally_b','enemy')}
class AuthorityTests(unittest.TestCase):
    def setUp(self):self.e=Encounter('alice','bob',(7062026,0,43,168),state())
    def command(self,seq=1,ship='ally_b',kind='fire',args=None):return dict(encounter=self.e.id,seq=seq,ship=ship,kind=kind,args=args or dict(weapon=0,target='enemy',room=1))
    def test_both_captains_target_same_enemy(self):
        self.e.submit('alice',self.command(ship='ally_a'));self.e.submit('bob',self.command())
        commands=self.e.commands('alice');self.assertEqual(len(commands),2)
        self.assertEqual({c['args']['target'] for c in commands},{'enemy'})
        self.assertEqual(self.e.state['enemy']['hull'],30) # queue does not invent damage
    def test_duplicate_intent_executed_only_once(self):
        c=self.command();self.e.submit('bob',c);self.e.submit('bob',c)
        self.assertEqual(len(self.e.commands('alice')),1)
        s=state();s['enemy']['hull']=28
        self.e.publish('alice',self.e.id,1,s,[dict(actor='bob',seq=1,status='executed')])
        self.assertEqual(self.e.submit('bob',c)['status'],'executed')
        self.assertEqual(len(self.e.commands('alice')),0)
        self.assertEqual(self.e.state['enemy']['hull'],28)
    def test_wrong_owner_and_client_damage_rejected(self):
        for command in [self.command(ship='ally_a'),self.command(ship='enemy'),self.command(kind='damage')]:
            with self.assertRaises(Rejected):self.e.submit('bob',command)
        with self.assertRaises(Rejected):self.e.publish('bob',self.e.id,1,state())
        with self.assertRaises(Rejected):self.e.commands('bob')
    def test_sequence_reuse_stale_encounter_and_old_tick(self):
        self.e.submit('bob',self.command())
        c=self.command();c['args']['room']=0
        with self.assertRaises(Rejected):self.e.submit('bob',c)
        c=self.command(seq=2);c['encounter']='previous run'
        with self.assertRaises(Rejected):self.e.submit('bob',c)
        self.e.publish('alice',self.e.id,1,state())
        with self.assertRaises(Rejected):self.e.publish('alice',self.e.id,1,state())
    def test_bad_batch_is_atomic(self):
        self.e.submit('bob',self.command());before=self.e.snapshot()
        s=state();s['enemy']['hull']=0
        with self.assertRaises(Rejected):self.e.publish('alice',self.e.id,1,s,[dict(actor='bob',seq=99,status='executed')])
        self.assertEqual(self.e.snapshot(),before)
    def test_pause_dead_ship_and_charge(self):
        self.e.pause('alice',True)
        with self.assertRaises(Rejected):self.e.submit('bob',self.command())
        self.e.pause('alice',False);s=state();s['ally_b']['weapons'][0]['charge']=0
        self.e.publish('alice',self.e.id,1,s)
        with self.assertRaises(Rejected):self.e.submit('bob',self.command())
        s['ally_b']['hull']=0;self.e.publish('alice',self.e.id,2,s)
        with self.assertRaises(Rejected):self.e.submit('bob',self.command(kind='move',args=dict(crew=1,room=1)))
    def test_events_order_and_end_invalidate_commands(self):
        event=dict(id=1,kind='projectile',source='ally_b',target='enemy')
        self.e.publish('alice',self.e.id,1,state(),events=[event])
        with self.assertRaises(Rejected):self.e.publish('alice',self.e.id,2,state(),events=[event])
        self.e.submit('bob',self.command());self.e.end('alice')
        self.assertTrue(self.e.snapshot()['closed']);self.assertEqual(self.e.commands('alice'),[])
        with self.assertRaises(Rejected):self.e.submit('bob',self.command(seq=2))
    def test_reject_nan_and_external_mutation(self):
        s=state();s['ally_a']['crew'][0]['x']=float('nan')
        with self.assertRaises(Rejected):self.e.publish('alice',self.e.id,1,s)
        snap=self.e.snapshot();snap['ships']['enemy']['hull']=0
        self.assertEqual(self.e.state['enemy']['hull'],30)
    def test_one_pending_fire_per_weapon(self):
        self.e.submit('bob',self.command())
        with self.assertRaises(Rejected):self.e.submit('bob',self.command(seq=2))
if __name__=='__main__':unittest.main()
