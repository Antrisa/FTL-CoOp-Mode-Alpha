"""Bounded native draw-list protocol. Contains asset names/vertices, not pixels."""
import struct, math, re, zlib, base64
MAX_BYTES=196608
PATH=re.compile(r'[A-Za-z0-9_./-]{0,180}\Z')
def validate(data):
    if not isinstance(data,dict) or type(data.get('guard')) is not int or not 0<=data['guard']<2**32:raise ValueError('scene guard')
    s=data.get('data')
    if not isinstance(s,str) or len(s)>MAX_BYTES*2 or not re.fullmatch(r'[0-9a-f]*',s):raise ValueError('scene data')
    raw=bytes.fromhex(s);p=0
    def read(fmt):
        nonlocal p
        size=struct.calcsize(fmt)
        if p+size>len(raw):raise ValueError('truncated scene')
        v=struct.unpack_from(fmt,raw,p);p+=size;return v
    magic,x,y,w,h,n=read('<4s4fI')
    if magic!=b'FS26' or not all(math.isfinite(v) for v in (x,y,w,h)) or abs(x)>4096 or abs(y)>4096 or not 16<=w<=2048 or not 16<=h<=2048 or not 1<=n<=1024:raise ValueError('scene header')
    total=0
    for _ in range(n):
        l,=read('<I')
        if l>180 or p+l>len(raw):raise ValueError('scene asset')
        name=raw[p:p+l].decode('ascii');p+=l
        if not PATH.fullmatch(name) or '..' in name:raise ValueError('scene asset')
        count,=read('<I');total+=count
        if not count or count%3 or count>4096 or total>6000:raise ValueError('scene vertices')
        for _ in range(count):
            a,b,u,v,r,g,b_,alpha=read('<8f')
            if not all(math.isfinite(z) for z in (a,b,u,v,r,g,b_,alpha)) or abs(a)>8192 or abs(b)>8192 or abs(u)>32 or abs(v)>32 or any(not 0<=c<=1 for c in (r,g,b_,alpha)):raise ValueError('scene vertex')
    if p!=len(raw):raise ValueError('scene trailing data')
    return {'guard':data['guard'],'data':s}
def parse(line):
    p=line.split('|')
    if len(p)!=3 or p[0]!='SCENE' or not p[1].isdigit():raise ValueError('scene line')
    return validate(dict(guard=int(p[1]),data=p[2]))
def line(data):
    d=validate(data);return f"SCENE|{d['guard']}|{d['data']}\n"
def pack(data):
    d=validate(data);return dict(guard=d['guard'],z=base64.b64encode(zlib.compress(bytes.fromhex(d['data']),1)).decode('ascii'))
def unpack(data):
    if not isinstance(data,dict) or not isinstance(data.get('z'),str) or len(data['z'])>MAX_BYTES*2:raise ValueError('compressed scene')
    try:
        z=zlib.decompressobj();raw=z.decompress(base64.b64decode(data['z'],validate=True),MAX_BYTES+1)
    except (zlib.error,ValueError) as exc:raise ValueError('scene compression') from exc
    if len(raw)>MAX_BYTES or not z.eof or z.unused_data or z.unconsumed_tail:raise ValueError('scene decompression')
    return validate(dict(guard=data.get('guard'),data=raw.hex()))
