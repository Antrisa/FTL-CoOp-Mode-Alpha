"""Acknowledged fleet commands; client send success is NOT game success."""
import secrets
import time
from input_bridge import OPS

class Bridge:
    def __init__(self):
        self.enabled=set();self.loaded={};self.pending=None
    def command(self,sender,host,ids,op,now):
        if sender!=host:raise ValueError('Only the host sends fleet commands.')
        if op not in OPS:raise ValueError('Unknown command.')
        if len(ids)!=2:raise ValueError('Connect both captains first.')
        if any(i not in self.enabled or now-self.loaded.get(i,0)>30 for i in ids):
            raise ValueError('Both captains must enable the bridge and have recent BRIDGE_READY game messages.')
        if self.pending and self.pending['status']=='waiting':raise ValueError('Wait for the current command to finish.')
        self.pending={'nonce':secrets.randbelow(2**24-1)+1,'op':op,'members':list(ids),
                      'acks':{},'armed':[],'status':'waiting','deadline':now+60}
    def ack(self,sender,event):
        p=self.pending
        if not p or p['status']!='waiting' or sender not in p['members']:return
        try:
            _,nonce,op,status=event.split('|')
            if int(nonce)!=p['nonce'] or op!=p['op'] or status not in {'OK','FAILED','ARMED'}:return
        except (ValueError,TypeError):return
        if status=='ARMED':
            if not p['op'].startswith('CHOICE_'):return
            if sender not in p['armed']:p['armed'].append(sender)
            return
        p['acks'][str(sender)]=status
        if status=='FAILED':p['status']='failed'
        elif len(p['acks'])==len(p['members']):p['status']='confirmed'
    def delivery_failed(self,sender,nonce,op):
        p=self.pending
        if not p or p['status']!='waiting' or sender not in p['members']:return
        if type(nonce) is not int or nonce!=p['nonce'] or op!=p['op']:return
        if p['acks'].get(str(sender))=='OK':return
        p['acks'][str(sender)]='FAILED'
        p['status']='failed'

    def cancel(self):
        if self.pending and self.pending['status']=='waiting':self.pending['status']='cancelled'
    def tick(self,ids,now):
        p=self.pending
        if not p or p['status']!='waiting':return
        if set(ids)!=set(p['members']) or not set(ids)<=self.enabled:p['status']='cancelled'
        elif now>p['deadline']:p['status']='unconfirmed'
    def public(self):
        return {'enabled':sorted(self.enabled),'loaded':sorted(self.loaded),'pending':self.pending}
