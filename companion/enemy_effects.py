"""Validate relay payload; native code also checks current enemy geometry."""
import re,math
TOKEN=re.compile(r'[A-Za-z0-9_.-]{1,100}\Z')
def validate(s):
    if not isinstance(s,str) or len(s)>48000:raise ValueError('effects size')
    p=s.split();i=0
    def take():
        nonlocal i
        if i>=len(p):raise ValueError('effects truncated')
        x=p[i];i+=1;return x
    def num(lo,hi,integer=False):
        t=take()
        if not re.fullmatch(r'-?\d+(?:\.\d+)?',t):raise ValueError('effects number')
        x=float(t)
        if not math.isfinite(x) or not lo<=x<=hi or integer and x!=int(x):raise ValueError('effects range')
        return int(x) if integer else x
    header=take()
    if header not in ('E26','E28'):raise ValueError('effects header')
    nc,nb,nr=num(0,64,True),num(0,1024,True),num(0,64,True);seen=set();ended=False
    while i<len(p):
        kind=take()
        if kind=='END':ended=True;break
        idx=num(0,4096,True);key=(kind,idx)
        if kind=='C':
            if idx>=nc or not TOKEN.fullmatch(take()):raise ValueError('effects crew')
            num(-2048,4096);num(-2048,4096);hp=num(0,1000);mx=num(1,1000)
            if hp>mx:raise ValueError('effects hp')
            room=num(-1,nr-1,True);dead=num(0,1,True)
            location=num(-1,1,True) if header=='E28' else 1
            away=location!=1
            if room==-1 and not dead and not away or away and room!=-1:raise ValueError("effects crew room")
        elif kind=='F':key+=(num(0,4096,True),);num(0,1000)
        elif kind=='B':
            if idx>=nb:raise ValueError('effects breach')
            num(0,1000)
        elif kind=='O':
            if idx>=nr:raise ValueError('effects oxygen')
            num(0,100)
        elif kind=='R':
            if idx>20:raise ValueError('effects system')
            num(0,10000);num(0,10000);num(0,1,True);num(0,1,True)
        else:raise ValueError('effects kind')
        if key in seen:raise ValueError('effects duplicate')
        seen.add(key)
        if len(seen)>4096:raise ValueError('effects rows')
    if not ended or i!=len(p) or any(('C',j) not in seen for j in range(nc)) or any(('B',j) not in seen for j in range(nb)):raise ValueError('effects incomplete')
    return s
