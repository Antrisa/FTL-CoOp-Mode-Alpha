"""v0.28.16: a game that stops reading for a moment must not drop the local link. No Lua needed."""
import socket,sys,time,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from fast_local import LocalCompanion

class SlowGame(unittest.TestCase):
    def test_stalled_reader_keeps_link(self):
        lc=LocalCompanion(lambda ship:None,port=0);lc.start()
        game=socket.create_connection(('127.0.0.1',lc.port))
        game.setsockopt(socket.SOL_SOCKET,socket.SO_RCVBUF,4096)
        try:
            game.sendall(b'HELLO|1\n')
            self.assertEqual(game.recv(64),b'HELLO|1\n')
            big=b'STATE|1|10|10|1|'+b'ab'*40000+b'\n'   # about the size of a scene frame
            end=time.monotonic()+1.5
            while time.monotonic()<end:               # game reads nothing for 1.5 s
                with lc.lock:lc.latest=(time.monotonic(),big)
                time.sleep(.01)
            self.assertEqual(lc.error,'')
            self.assertIsNotNone(lc.peer,'link was dropped while the game was not reading')
            game.settimeout(2);got=b''
            while b'\n' not in got:got+=game.recv(65536)   # game wakes up and drains
            lc.send_combat('PAUSE|LOCAL_HOLD')
            end=time.monotonic()+3;seen=False
            while time.monotonic()<end and not seen:
                with lc.lock:lc.latest=None
                try:got+=game.recv(65536)
                except socket.timeout:pass
                seen=b'PAUSE|LOCAL_HOLD\n' in got
            self.assertTrue(seen,'control message not delivered after the stall')
            self.assertEqual(lc.error,'')
        finally:
            game.close();lc.stop()

if __name__=='__main__':unittest.main()
