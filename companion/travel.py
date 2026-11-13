"""Server-owned travel proposals. Observes manual jumps; never controls FTL."""
from shared_map import fingerprint, SHARED_SEED, integer

FRESH_SECONDS = 20
PLAN_SECONDS = 180

class Travel:
    def __init__(self):
        self.plan = None
        self.next_id = 1
        self.message = 'Host: select a neighboring beacon after both maps match.'

    def cancel(self, reason):
        self.plan = None
        self.message = reason

    def eligible(self, players, now):
        if len(players) != 2: raise ValueError('Both captains must be connected.')
        if any(not p.get('snapshot') or now-p.get('seen',0)>FRESH_SECONDS for p in players):
            raise ValueError('Both games need fresh map data. Resume FTL if paused.')
        a,b = (p['snapshot'] for p in players)
        if a['seed'] != SHARED_SEED or b['seed'] != SHARED_SEED: raise ValueError('Both games must use the shared seed.')
        if a['level'] != b['level'] or fingerprint(a) != fingerprint(b): raise ValueError('Both maps must match.')
        if a['position'] != b['position']: raise ValueError('Meet at the same beacon before planning a jump.')
        return a

    def propose(self, sender, host, players, target, now):
        if sender != host: raise ValueError('Only the host selects the destination.')
        if self.plan and self.plan['phase']=='go': raise ValueError('Finish or cancel the current jump first.')
        a = self.eligible(players, now)
        if not isinstance(target, list) or len(target)!=2: raise ValueError('Choose a beacon.')
        target = [integer(v,-10000,10000) for v in target]
        origin = next(n for n in a['nodes'] if n[:2]==a['position'])
        if target not in [a['nodes'][e][:2] for e in origin[3]] or target==a['position']:
            raise ValueError('Destination must be a connected neighboring beacon.')
        self.plan = dict(id=self.next_id, phase='ready', target=target,
                         origin=list(a['position']), seed=a['seed'],level=a['level'],
                         layout=fingerprint(a),ready=[],arrived=[],expires=now+PLAN_SECONDS,
                         members=sorted(p['id'] for p in players))
        self.next_id += 1
        self.message = 'Destination proposed. Both captains: check FTL can jump, then click Ready.'

    def ready(self, sender, plan_id, players, now):
        self.tick(players, now)
        p=self.plan
        if not p or type(plan_id) is not int or p['id'] != plan_id:
            raise ValueError('That travel plan expired or changed. Review the current destination.')
        if sender not in p['members']: raise ValueError('Captain is not part of this plan.')
        if p['phase'] != 'ready': return
        self.eligible(players, now)
        if sender not in p['ready']: p['ready'].append(sender)
        if len(p['ready'])==2:
            p['phase']='go'
            p['expires']=now+PLAN_SECONDS
            self.message='GO — both captains manually select the marked beacon in FTL.'

    def tick(self, players, now):
        p=self.plan
        if not p or p['phase']=='done': return
        if sorted(x['id'] for x in players)!=p['members']:
            return self.cancel('Travel cancelled: a captain disconnected.')
        if now>=p['expires']: return self.cancel('Travel cancelled: plan timed out. Propose again.')
        for player in players:
            s=player.get('snapshot')
            if not s or now-player.get('seen',0)>FRESH_SECONDS:
                return self.cancel('Travel cancelled: game data missing or stale. Resume FTL and propose again.')
            if s['seed']!=p['seed'] or s['level']!=p['level'] or fingerprint(s)!=p['layout']:
                return self.cancel('Travel cancelled: map or sector changed.')
            pos=s['position']
            if p['phase']=='ready' and pos!=p['origin']:
                return self.cancel('Travel cancelled: someone moved before both captains were ready.')
            if p['phase']=='go' and pos not in [p['origin'],p['target']]:
                return self.cancel('Travel cancelled: a captain reached a different beacon. Meet up manually.')
        if p['phase']=='go':
            p['arrived']=[x['id'] for x in players if x['snapshot']['position']==p['target']]
            if len(p['arrived'])==2:
                p['phase']='done'
                self.message='ARRIVED — both captains are at the agreed beacon.'

    def public(self):
        return {'plan':self.plan,'message':self.message}
