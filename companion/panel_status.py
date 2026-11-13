"""Display-only status payload. No arbitrary text or executable operations."""
def encode_status(me,host,players,bridge,event_data):
    local=next((p for p in players if p['id']==me),{})
    token=(local.get('event') or {}).get('token',0)
    b=event_data.get('ballot')
    if not b or b.get('guards',{}).get(str(me))!=token:b=None
    votes=b.get('votes',{}) if b else {}
    own=votes.get(str(me),0)
    peer=next((votes.get(str(p['id']),0) for p in players if p['id']!=me),0)
    agreed=b.get('agreed') or 0 if b else 0
    # bits: own4 peer4 agreement4 captains2 enabled2 host1 matched1
    value=own+(peer<<4)+(agreed<<8)+(min(2,len(players))<<12)+(min(2,len(bridge.get('enabled',[])))<<14)+(int(me==host)<<16)+(int(b is not None)<<17)
    pending=bridge.get('pending') or {}
    outcome={'waiting':1,'confirmed':2,'failed':3,'cancelled':3,'unconfirmed':3}.get(pending.get('status'),0)
    value+=outcome<<18
    return value+1,token
