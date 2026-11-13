"""Bounded, read-only interior snapshots. Coordinates quantized to seven pixels."""
import re
from input_bridge import INPUT_LOCK, WindowsInput, transmit

def decode(value):
    if not isinstance(value,str) or not re.fullmatch('[0-9a-fA-F]{8,1024}',value) or len(value)%2:
        raise ValueError('Invalid interior encoding')
    b=bytes.fromhex(value)
    version,nr,nc,ns=b[:4]
    if version not in (1,2) or not 1<=nr<=32 or nc>16 or ns>20 or len(b)!=(8 if version==2 else 4)+nr*5+nc*4+ns*5:
        raise ValueError('Invalid interior counts')
    rooms={};crew=[];systems=[];i=8 if version==2 else 4
    if version==2 and (not b[6] or not b[7]):raise ValueError('Invalid hull dimensions')
    for _ in range(nr):
        rid,x,y,w,h=b[i:i+5];i+=5
        if rid>31 or rid in rooms or not w or not h:raise ValueError('Invalid room')
        rooms[rid]=(x,y,w,h)
    for _ in range(nc):
        x,y,hp,flags=b[i:i+4];i+=4
        if hp>100 or flags>1:raise ValueError('Invalid crew')
        crew.append((x,y,hp,flags))
    for _ in range(ns):
        rid,kind,hp,maximum,power=b[i:i+5];i+=5
        if rid not in rooms or kind>20 or not 1<=maximum<=16 or hp>maximum or power>16:
            raise ValueError('Invalid system')
        systems.append((rid,kind,hp,maximum,power))
    return rooms,crew,systems

def checksum(data):
    h=0
    for byte in data:h=(h*65599+byte)%2**32
    return h

def packet(op,payload,word):
    header=(op<<24)|payload
    return [0x7c]+[0x7e if header&(1<<b) else 0x7d for b in range(31,-1,-1)]+[0x7e if word&(1<<b) else 0x7d for b in range(31,-1,-1)]

def frames(value,sequence,guard):
    decode(value)
    if type(sequence)is not int or not 1<=sequence<2**24 or type(guard)is not int or not 0<=guard<2**32:
        raise ValueError('Invalid interior frame')
    data=bytes.fromhex(value)
    raw=len(data).to_bytes(2,'big')+data
    raw+=bytes((-len(raw))%7)
    out=[packet(50,sequence,guard)]
    for i in range(0,len(raw),7):
        chunk=raw[i:i+7];out.append(packet(51,int.from_bytes(chunk[:3],'big'),int.from_bytes(chunk[3:],'big')))
    out.append(packet(52,sequence,checksum(data)))
    return out

def send_interior(value,sequence,guard,allowed,expected_exe=''):
    blocks=frames(value,sequence,guard)
    if not INPUT_LOCK.acquire(blocking=False):return False
    try:
        # Faster only for display packets. Existing action timing stays unchanged.
        transmit(WindowsInput(),[k for b in blocks for k in b],allowed,expected_exe,timeout=.2,interval=.002)
        return True
    finally:INPUT_LOCK.release()
