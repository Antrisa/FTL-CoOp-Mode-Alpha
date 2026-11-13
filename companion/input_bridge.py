"""Foreground-only Windows input with explicit target selection and diagnostics."""
import ntpath
import os
import time
import threading
INPUT_LOCK=threading.Lock()
OPS={'PING':1,'PAUSE':2,'RESUME':3,**{'CHOICE_'+str(i):16+i for i in range(1,10)}}

def packet_keys(command,nonce,guard=0):
    if command not in OPS or type(nonce) is not int or not 1<=nonce<2**24:
        raise ValueError('Invalid bridge command')
    if type(guard) is not int or not 0<=guard<2**32:raise ValueError('Invalid event guard')
    value=(OPS[command]<<24)|nonce
    return [0x7C]+[0x7E if value&(1<<bit) else 0x7D for bit in range(31,-1,-1)]+[0x7E if guard&(1<<bit) else 0x7D for bit in range(31,-1,-1)]

def target_status(state,expected_exe=''):
    if state.get('error'):return state['error']
    exe=state.get('exe','')
    if expected_exe:
        if ntpath.normcase(ntpath.normpath(exe))!=ntpath.normcase(ntpath.normpath(expected_exe)):
            return 'Wrong foreground executable: '+exe+'; expected '+expected_exe
    elif ntpath.basename(exe).lower()!='ftlgame.exe':
        return 'Foreground executable is '+exe+'; select your actual FTL .exe if its name differs.'
    if state.get('held'):return 'Modifier keys detected as held: '+', '.join(state['held'])
    return ''

class WindowsInput:
    def __init__(self):
        if os.name!='nt':raise RuntimeError('Windows is required for foreground inspection/input.')
        import ctypes as c
        from ctypes import wintypes as w
        self.c=c;self.w=w
        u=c.WinDLL('user32',use_last_error=True);k=c.WinDLL('kernel32',use_last_error=True)
        self.u=u;self.k=k
        class MOUSE(c.Structure):
            _fields_=[('dx',w.LONG),('dy',w.LONG),('data',w.DWORD),('flags',w.DWORD),('time',w.DWORD),('extra',c.c_size_t)]
        class KEY(c.Structure):
            _fields_=[('vk',w.WORD),('scan',w.WORD),('flags',w.DWORD),('time',w.DWORD),('extra',c.c_size_t)]
        class HARD(c.Structure):_fields_=[('msg',w.DWORD),('lo',w.WORD),('hi',w.WORD)]
        class UNION(c.Union):_fields_=[('mi',MOUSE),('ki',KEY),('hi',HARD)]
        class INPUT(c.Structure):_fields_=[('type',w.DWORD),('u',UNION)]
        self.INPUT=INPUT
        u.GetForegroundWindow.argtypes=[];u.GetForegroundWindow.restype=w.HWND
        u.GetWindowThreadProcessId.argtypes=[w.HWND,c.POINTER(w.DWORD)];u.GetWindowThreadProcessId.restype=w.DWORD
        u.GetWindowTextW.argtypes=[w.HWND,w.LPWSTR,c.c_int];u.GetWindowTextW.restype=c.c_int
        u.GetAsyncKeyState.argtypes=[c.c_int];u.GetAsyncKeyState.restype=c.c_short
        u.SendInput.argtypes=[w.UINT,c.POINTER(INPUT),c.c_int];u.SendInput.restype=w.UINT
        k.OpenProcess.argtypes=[w.DWORD,w.BOOL,w.DWORD];k.OpenProcess.restype=w.HANDLE
        k.QueryFullProcessImageNameW.argtypes=[w.HANDLE,w.DWORD,w.LPWSTR,c.POINTER(w.DWORD)]
        k.QueryFullProcessImageNameW.restype=w.BOOL
        k.CloseHandle.argtypes=[w.HANDLE];k.CloseHandle.restype=w.BOOL

    def inspect(self):
        c,w,u,k=self.c,self.w,self.u,self.k
        hwnd=u.GetForegroundWindow()
        if not hwnd:return {'error':'Windows returned no foreground window.'}
        pid=w.DWORD();title=c.create_unicode_buffer(512)
        u.GetWindowTextW(hwnd,title,512)
        if not u.GetWindowThreadProcessId(hwnd,c.byref(pid)):
            return {'error':f'Cannot read foreground process ID; Windows error {c.get_last_error()}.'}
        state={'hwnd':hwnd,'pid':pid.value,'title':title.value,'exe':'','held':[]}
        handle=k.OpenProcess(0x1000,False,pid.value)
        if not handle:
            state['error']=f'Cannot inspect foreground process {pid.value} ({title.value}); OpenProcess error {c.get_last_error()}.'
            return state
        try:
            size=w.DWORD(32768);buf=c.create_unicode_buffer(size.value)
            if not k.QueryFullProcessImageNameW(handle,0,buf,c.byref(size)):
                state['error']=f'Cannot read executable for PID {pid.value}; QueryFullProcessImageName error {c.get_last_error()}.'
                return state
            state['exe']=buf.value
        finally:k.CloseHandle(handle)
        state['held']=[name for vk,name in [(0x10,'Shift'),(0x11,'Ctrl'),(0x12,'Alt'),(0x5B,'Left Windows'),(0x5C,'Right Windows')] if u.GetAsyncKeyState(vk)&0x8000]
        return state

    def send_key_pair(self,vk):
        events=(self.INPUT*2)()
        events[0].type=events[1].type=1
        events[0].u.ki.vk=events[1].u.ki.vk=vk
        events[1].u.ki.flags=2
        if self.u.SendInput(2,events,self.c.sizeof(self.INPUT))!=2:
            raise RuntimeError(f'SendInput rejected the key pair; Windows error {self.c.get_last_error()}. Check FTL and link privilege levels.')

def transmit(backend,keys,allowed,expected_exe='',report=lambda s:None,clock=time.monotonic,sleep=time.sleep,timeout=30,interval=.012):
    end=clock()+timeout;last='';state=None;reason='No foreground observation yet.'
    while clock()<end:
        if not allowed():raise RuntimeError('Delivery cancelled: bridge disabled, disconnected, or request ended.')
        state=backend.inspect();reason=target_status(state,expected_exe)
        detail=f"Foreground: {state.get('exe','unknown')} | PID {state.get('pid','?')} | {reason or 'TARGET ACCEPTED'}"
        if detail!=last:report(detail);last=detail
        if not reason:break
        sleep(.1)
    else:raise RuntimeError('Not sent after 30 seconds. '+reason)
    identity=(state['hwnd'],state['pid'])
    for vk in keys:
        if not allowed():raise RuntimeError('Delivery cancelled before packet completed.')
        current=backend.inspect();reason=target_status(current,expected_exe)
        if reason or (current.get('hwnd'),current.get('pid'))!=identity:
            raise RuntimeError('Delivery stopped: '+(reason or 'foreground window/process changed')+'. No automatic retry.')
        backend.send_key_pair(vk);sleep(interval)

def send_packet(command,nonce,allowed=lambda:True,expected_exe='',report=lambda s:None,guard=0):
    keys=packet_keys(command,nonce,guard)
    with INPUT_LOCK:
        transmit(WindowsInput(),keys,allowed,expected_exe,report)


def send_choice_digit(index,allowed,expected_exe='',report=lambda s:None):
    if type(index) is not int or not 1<=index<=9:raise ValueError('Invalid choice index')
    with INPUT_LOCK:
        transmit(WindowsInput(),[0x30+index],allowed,expected_exe,report,timeout=8)


def status_packet_keys(payload,token):
    if type(payload) is not int or not 1<=payload<2**24 or type(token) is not int or not 0<=token<2**32:
        raise ValueError('Invalid display status')
    value=(40<<24)|payload
    return [0x7C]+[0x7E if value&(1<<bit) else 0x7D for bit in range(31,-1,-1)]+[0x7E if token&(1<<bit) else 0x7D for bit in range(31,-1,-1)]

def send_status(payload,token,allowed,expected_exe=''):
    # Low priority: never queue behind an actual command or steal foreground.
    if not INPUT_LOCK.acquire(blocking=False):return False
    try:
        transmit(WindowsInput(),status_packet_keys(payload,token),allowed,expected_exe,timeout=.2)
        return True
    finally:INPUT_LOCK.release()


def cursor_packet_keys(x,y,panel,token):
    if type(x) is not int or not 0<=x<1280 or type(y) is not int or not 0<=y<720 or type(panel) is not int or panel not in (0,1):
        raise ValueError('Invalid cursor coordinates')
    keys=status_packet_keys(1+x+(y<<11)+(panel<<21),token)
    value=(41<<24)|(1+x+(y<<11)+(panel<<21))
    return [0x7C]+[0x7E if value&(1<<bit) else 0x7D for bit in range(31,-1,-1)]+keys[33:]

def send_cursor(x,y,panel,token,allowed,expected_exe=''):
    if not INPUT_LOCK.acquire(blocking=False):return False
    try:
        transmit(WindowsInput(),cursor_packet_keys(x,y,panel,token),allowed,expected_exe,timeout=.2)
        return True
    finally:INPUT_LOCK.release()


def ship_packet_keys(ship_id,hull,maximum,guard):
    if any(type(v) is not int for v in (ship_id,hull,maximum)) or not 0<=ship_id<=30 or not 0<=hull<=maximum<=255 or maximum<1:
        raise ValueError('Invalid ship view')
    payload=1+ship_id+(hull<<5)+(maximum<<13)
    keys=status_packet_keys(payload,guard)
    value=(42<<24)|payload
    return [0x7C]+[0x7E if value&(1<<bit) else 0x7D for bit in range(31,-1,-1)]+keys[33:]

def send_ship(ship_id,hull,maximum,guard,allowed,expected_exe=''):
    if not INPUT_LOCK.acquire(blocking=False):return False
    try:
        transmit(WindowsInput(),ship_packet_keys(ship_id,hull,maximum,guard),allowed,expected_exe,timeout=.2)
        return True
    finally:INPUT_LOCK.release()
