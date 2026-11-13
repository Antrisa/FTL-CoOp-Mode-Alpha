import threading
import time
import unittest
from async_sender import AsyncSender

class BlockedSocket:
    def __init__(self):
        self.started=threading.Event();self.release=threading.Event();self.received=[]
    def sendall(self,data):
        self.started.set();self.release.wait(2);self.received.append(data)
    def shutdown(self,how):self.release.set()

class SenderTests(unittest.TestCase):
    def test_blocked_network_does_not_block_caller(self):
        sock=BlockedSocket();writer=AsyncSender(sock)
        writer.send(b'first');self.assertTrue(sock.started.wait(1))
        start=time.monotonic();writer.send(b'second')
        self.assertLess(time.monotonic()-start,.1)
        sock.release.set();writer.finish()
        self.assertEqual(sock.received,[b'first',b'second'])
    def test_overflow_closes_instead_of_dropping_commands(self):
        sock=BlockedSocket();writer=AsyncSender(sock,capacity=1)
        writer.send(b'first');self.assertTrue(sock.started.wait(1));writer.send(b'second')
        with self.assertRaises(OSError):writer.send(b'third')
        self.assertTrue(writer.closed.is_set())
        writer.thread.join(1);self.assertFalse(writer.thread.is_alive())

if __name__=='__main__':unittest.main()
