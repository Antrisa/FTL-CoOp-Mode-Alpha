"""Bounded FIFO socket writer. Never wait for network I/O on a caller thread."""
import diagnostics as diag
from priority_updates import UpdateQueue,wire_key
import queue
import socket
import threading

class AsyncSender:
    def __init__(self, sock, capacity=64, label="socket"):
        self.sock=sock
        # Bound bytes handed to TCP so queued scene frames cannot grow unchecked.
        try:sock.setsockopt(socket.SOL_SOCKET,socket.SO_SNDBUF,65536)
        except (OSError,AttributeError):pass
        self.label=label
        self.pending=UpdateQueue(capacity,key=wire_key)
        self.closed=threading.Event()
        self.thread=threading.Thread(target=self._run,daemon=True)
        self.thread.start()

    def send(self,data):
        if self.closed.is_set():raise OSError('connection writer closed')
        try:self.pending.put_nowait(data)
        except queue.Full:
            diag.record(self.label+' OUTPUT FULL capacity='+str(self.pending.maxsize))
            self.close()
            raise OSError('connection output queue full')

    def _run(self):
        try:
            while not self.closed.is_set():
                try:data=self.pending.get(timeout=.1)
                except queue.Empty:continue
                if data is None:
                    while True:
                        try:rest=self.pending.get_nowait()
                        except queue.Empty:break
                        if rest is not None:self.sock.sendall(rest)
                    break
                self.sock.sendall(data)
        except OSError:diag.exception('Socket writer failed: '+self.label)
        finally:self.close()

    def finish(self):
        try:self.pending.put_nowait(None)
        except queue.Full:pass
        self.thread.join(timeout=.2)
        self.close()

    def close(self):
        if not self.closed.is_set():
            self.closed.set()
            try:self.sock.shutdown(socket.SHUT_RDWR)
            except OSError:pass
