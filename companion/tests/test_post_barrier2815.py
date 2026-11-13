"""v0.28.16 relay check: a stale reward barrier must not block the next fight. No Lua needed."""
import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from combat import CombatRoom

class PostBarrier(unittest.TestCase):
    def run_fight(self,room,guard,sent):
        send=lambda cid,line:sent.append((cid,line))
        guards={1:guard,2:guard}
        for cid in (1,2):room.receive(cid,f'COMBAT|ARM|{guard}|sig|p{cid}|LASER_BURST_1',1,[1,2],guards,send,now=10)
        return [l for c,l in sent if l.startswith('COMBAT|START|')]
    def test_stale_barrier_dropped_at_new_beacon(self):
        room=CombatRoom();sent=[]
        starts=self.run_fight(room,111,sent)
        self.assertEqual(len(starts),2)
        epoch=starts[0].split('|')[2]
        send=lambda cid,line:sent.append((cid,line));guards={1:111,2:111}
        finish=f'COMBAT|FINISH|{epoch}|5|0|10|0|0||0|0'
        room.receive(1,finish,1,[1,2],guards,send,now=11)
        room.receive(2,f'COMBAT|FINISH_ACK|{epoch}|5',1,[1,2],guards,send,now=11)
        self.assertIsNotNone(room.post);self.assertFalse(room.post['released'])
        # same beacon: barrier still refuses a new fight
        sent.clear();self.assertEqual(self.run_fight(room,111,sent),[])
        # both ships left without POST_RELEASE (sector jump): next beacon must arm
        sent.clear();self.assertEqual(len(self.run_fight(room,222,sent)),2)
        self.assertIsNone(room.post)

if __name__=='__main__':unittest.main()
