"""Read-only ship telemetry; no combat commands or state mutations."""
from shared_map import integer
BASES=['HARD','STEALTH','MANTIS','CIRCLE','FED','JELLY','ROCK','ENERGY','CRYSTAL','ANAEROBIC']
CATALOG=['PLAYER_SHIP_'+base+suffix for base in BASES for suffix in ('','_2','_3')]
def validate_ship(s):
    bounds={'id':(0,30),'hull':(0,255),'maximum':(1,255),'seed':(0,4294967295),'level':(0,1000),'x':(-10000,10000),'y':(-10000,10000)}
    if not isinstance(s,dict):raise ValueError('Invalid ship report')
    out={k:integer(s[k],lo,hi) for k,(lo,hi) in bounds.items()}
    if out['hull']>out['maximum']:raise ValueError('Invalid hull')
    if s.get('interior'):
        from interior import decode
        decode(s['interior']);out['interior']=s['interior'].lower()
    return out

def parse_ship(line):
    try:
        v=line.split('|')
        if len(v) not in (9,10) or v[-1]!='END':return None
        values=dict(zip(('id','hull','maximum','seed','level','x','y'),v[1:8]))
        if len(v)==10:values['interior']=v[8]
        return {'kind':'ship_view','ship':validate_ship(values)}
    except (ValueError,TypeError,KeyError):return None

def context(s):return s['seed'],s['level'],s['x'],s['y']
def guard(s):
    h=0
    for c in '|'.join(map(str,context(s))).encode('ascii'):h=(h*65599+c)%2**32
    return h

def partner_ship(players,me,now):
    if len(players)!=2:return None
    a=next((p.get('ship_view') for p in players if p['id']==me),None)
    b=next((p.get('ship_view') for p in players if p['id']!=me),None)
    if not a or not b or any(now-s.get('seen',0)>5 for s in (a,b)) or context(a)!=context(b):return None
    return b['id'],b['hull'],b['maximum'],guard(a)
