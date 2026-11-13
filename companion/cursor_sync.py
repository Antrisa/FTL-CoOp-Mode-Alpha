"""Bounded, display-only cursor matching. Only menus and exact event contexts."""
from event_vote import identity

def validate_cursor(c):
    if not isinstance(c,dict):raise ValueError('Invalid cursor')
    bounds={'x':(0,1279),'y':(0,719),'panel':(0,1),'token':(-1,4294967295)}
    out={}
    for k,(lo,hi) in bounds.items():
        v=c[k]
        if type(v) is not int or not lo<=v<=hi:raise ValueError('Invalid cursor field')
        out[k]=v
    return out

def parse_cursor(s):
    try:
        _,x,y,panel,token=s.split('|')
        return {'kind':'cursor','cursor':validate_cursor(dict(x=int(x),y=int(y),panel=int(panel),token=int(token)))}
    except (ValueError,TypeError,KeyError):return None

def partner_cursor(players,me,now):
    if len(players)!=2:return None
    local=next((p for p in players if p['id']==me),None)
    peer=next((p for p in players if p['id']!=me),None)
    if not local or not peer:return None
    a,b=local.get('cursor'),peer.get('cursor')
    if not a or not b or any(now-c.get('seen',0)>2 for c in (a,b)):return None
    if a['token']<0 or b['token']<0 or a['panel']!=b['panel']:return None
    if a['token']==0 and b['token']==0:return b['x'],b['y'],b['panel'],0
    ea,eb=local.get('event'),peer.get('event')
    if not ea or not eb or ea['token']!=a['token'] or eb['token']!=b['token']:return None
    if any(now-p.get('event_seen',0)>20 for p in (local,peer)):return None
    if identity(ea)!=identity(eb):return None
    return b['x'],b['y'],b['panel'],a['token']
