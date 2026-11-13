"""Exact event comparison, voting and guarded execution state."""
import time
from shared_map import integer

def parse_event_state(text):
    if text=='EVENT_NONE':return {'kind':'event_state','event':None}
    if not text.startswith('EVENT|'):return None
    try:
        _,token,seed,level,pos,main,options=text.split('|')
        def unhex(s,limit):
            if len(s)>limit*2:raise ValueError('Text too long')
            return bytes.fromhex(s).decode('utf-8')
        choices=[]
        for part in options.split(';'):
            typ,label=part.split(',',1)
            choices.append({'type':integer(typ,-1000,1000),'text':unhex(label,2000)})
        data={'token':integer(token,1,4294967295),'seed':integer(seed,0,4294967295),
              'level':integer(level,0,1000),'position':[integer(x,-10000,10000) for x in pos.split(',')],
              'text':unhex(main,8000),'choices':choices}
        return {'kind':'event_state','event':validate_event(data)}
    except (ValueError,TypeError,KeyError,UnicodeError):return None

def validate_event(e):
    if e is None:return None
    if not isinstance(e,dict):raise ValueError('Invalid event')
    if not isinstance(e['text'],str) or len(e['text'].encode())>8000:raise ValueError('Invalid text')
    if not isinstance(e['position'],list) or len(e['position'])!=2:raise ValueError('Invalid position')
    if not isinstance(e['choices'],list) or not 1<=len(e['choices'])<=9:raise ValueError('Invalid choices')
    choices=[]
    for c in e['choices']:
        if not isinstance(c,dict) or not isinstance(c['text'],str) or len(c['text'].encode())>2000:raise ValueError('Invalid choice')
        choices.append(dict(type=integer(c['type'],-1000,1000),text=c['text']))
    return dict(token=integer(e['token'],1,4294967295),seed=integer(e['seed'],0,4294967295),
                level=integer(e['level'],0,1000),position=[integer(x,-10000,10000) for x in e['position']],
                text=e['text'],choices=choices)

TRADE_TEXT='There is a black market hub here. You receive a message, "These are dangerous times. If you have extra military-grade explosives, we\'ll gladly pay you for them."'
TRADE_CHOICES=['Sell 5 missiles for 15 scrap.', 'Sell 10 missiles for 30 scrap.', 'Sell 15 missiles for 45 scrap.', 'Ignore the station.']

def personal_trade(e):
    return bool(e and e['text']==TRADE_TEXT and [c['text'] for c in e['choices']]==TRADE_CHOICES
                and all(c['type'] in (0,1) for c in e['choices']))

def identity(e):
    # Only normal enabled/disabled rows share an identity. Preserve labels,
    # order, location and special choice types; never remap numeric indices.
    choices=[(0 if c['type'] in (0,1) else c['type'],c['text']) for c in e['choices']]
    return (e['seed'],e['level'],e['position'],e['text'],choices)

class EventVote:
    def __init__(self):
        self.round=0;self.signature=None;self.ballot=None;self.message='Waiting for matching event screens.'
    def sync(self,players,now):
        reason=None
        if len(players)!=2:reason='Connect both captains.'
        elif any(not p.get('event') or now-p.get('event_seen',0)>20 for p in players):reason='Both games need an open event and fresh event data.'
        elif any(personal_trade(p['event']) for p in players):reason='Personal trade: close F8 and sell or decline separately in FTL. Finish both trades before jumping.'
        elif identity(players[0]['event'])!=identity(players[1]['event']):reason='Event text or option order differs. Voting blocked; collect both logs.'
        if reason:
            self.signature=None;self.ballot=None;self.message=reason;return
        signature=tuple((p['id'],p['event']['token'],repr(p['event'])) for p in players)
        if signature!=self.signature:
            self.round+=1;self.signature=signature
            e=players[0]['event']
            choices=[dict(c,type=1 if any(p['event']['choices'][i]['type']==1 for p in players) else c['type']) for i,c in enumerate(e['choices'])]
            self.ballot={'round':self.round,'text':e['text'],'choices':choices,'votes':{},'agreed':None,'applied':False,
                         'guards':{str(p['id']):p['event']['token'] for p in players}}
            self.message='Vote for an option available to both ships. Unavailable trades stay blocked.'
    def vote(self,sender,round_id,index):
        b=self.require(round_id)
        if str(sender) not in b['guards']:raise ValueError('Captain not in ballot.')
        if type(index) is not int or not 1<=index<=len(b['choices']):raise ValueError('Invalid choice.')
        if b['choices'][index-1]['type']==1:raise ValueError('Option unavailable to one or both ships. Choose a shared available option.')
        b['votes'][str(sender)]=index;b['agreed']=None
        if len(b['votes'])==2:
            votes=list(b['votes'].values())
            if votes[0]==votes[1]:b['agreed']=votes[0];self.message='Agreement reached. Host may apply the agreed choice.'
            else:self.message='Tie: host can use their vote, or either captain can change their vote.'
    def require(self,round_id):
        if not self.ballot or type(round_id) is not int or round_id!=self.ballot['round']:raise ValueError('Event changed; review the current ballot.')
        if self.ballot['applied']:raise ValueError('This ballot has already been sent. No automatic retry.')
        return self.ballot
    def break_tie(self,sender,host,round_id):
        if sender!=host:raise ValueError('Only the host resolves ties.')
        b=self.require(round_id)
        if len(b['votes'])!=2 or str(host) not in b['votes']:raise ValueError('Both players must vote first.')
        b['agreed']=b['votes'][str(host)];self.message='Host resolved the tie. Review the choice, then apply.'
    def prepare(self,sender,host,round_id):
        if sender!=host:raise ValueError('Only the host applies the agreed choice.')
        b=self.require(round_id)
        if b['agreed'] is None:raise ValueError('Both votes and an agreed choice are required.')
        if b['choices'][b['agreed']-1]['type']==1:raise ValueError('Agreed option unavailable to one or both ships.')
        return 'CHOICE_'+str(b['agreed']),dict(b['guards'])
    def public(self):return {'ballot':self.ballot,'message':self.message}
