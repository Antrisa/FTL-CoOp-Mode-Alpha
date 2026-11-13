"""Bounded telemetry parsing and exact layout comparison; no game control."""
import hashlib
import json
import re
import time

SHARED_SEED = 7062026
SIMPLE = {'V0_7_MOD_LOADED', 'RUN_NEW', 'RUN_LOADED', 'JUMP_LEAVE', 'JUMP_ARRIVE', 'MAIN_MENU', 'LINK_TEST'}

def integer(text, low, high):
    if isinstance(text, bool) or not re.fullmatch(r'-?\d{1,10}(?:\.0{1,6})?', str(text)):
        raise ValueError('Expected integer')
    n = int(str(text).split('.')[0])
    if not low <= n <= high: raise ValueError('Integer out of range')
    return n

def validate_snapshot(data):
    if not isinstance(data, dict): raise ValueError('Expected snapshot')
    seed = integer(data['seed'], 0, 4294967295)
    level = integer(data['level'], 0, 1000)
    nodes = data['nodes']
    if not isinstance(nodes, list) or not 1 <= len(nodes) <= 128: raise ValueError('Bad map size')
    clean = []
    for node in nodes:
        if not isinstance(node, list) or len(node) != 4: raise ValueError('Bad beacon')
        x, y = (integer(v, -10000, 10000) for v in node[:2])
        nebula = integer(node[2], 0, 1)
        edges = node[3]
        if not isinstance(edges, list) or len(edges) > len(nodes): raise ValueError('Bad links')
        edges = sorted(set(integer(e, 0, len(nodes)-1) for e in edges))
        clean.append([x, y, nebula, edges])
    if sum(len(n[3]) for n in clean) > 1024: raise ValueError('Too many links')
    positions = {(n[0], n[1]) for n in clean}
    if len(positions) != len(clean): raise ValueError('Duplicate coordinates')
    position = data['position']
    if not isinstance(position, list) or len(position) != 2: raise ValueError('Bad position')
    position = [integer(v, -10000, 10000) for v in position]
    if tuple(position) not in positions: raise ValueError('Position outside map')
    return dict(seed=seed, level=level, position=position, nodes=clean)

def parse_line(line):
    if '[FleetCoop7] ' not in line: return None
    s = line.split('[FleetCoop7] ', 1)[1].strip()
    if len(s) > 60000: return None
    if s.startswith('SHIP|'):
        from ship_view import parse_ship
        return parse_ship(s)
    if s.startswith('COMBAT22|'):return s[:500]
    if s.startswith('SHIP_DIAG|'):return s[:500]
    if s.startswith(('NATIVE_VOTE|','NATIVE_DIAG|')):return s[:500]
    if s.startswith('CURSOR_DIAG|'):return s[:200]
    if s.startswith('CURSOR|'):
        from cursor_sync import parse_cursor
        return parse_cursor(s)
    if s.startswith('EVENT|') or s=='EVENT_NONE':
        from event_vote import parse_event_state
        return parse_event_state(s)
    if s in {'V0_10_BRIDGE_LOADED','BRIDGE10_READY','V0_9_BRIDGE_LOADED','BRIDGE_READY'} or s.startswith('BRIDGE_ACK|'): return s[:200]
    if s.startswith('PANEL_REJECT|'):return s[:500]
    if s.startswith('PANEL_ACTION|') and len(s)<100:return s
    if s in SIMPLE: return s
    if s.startswith('ERROR|'): return s[:500]
    if s.startswith('SEED_FORCED|'):
        try: return 'SEED_FORCED|' + str(integer(s.split('|')[1], 0, 4294967295))
        except ValueError: return None
    if not s.startswith('SNAP|'): return None
    try:
        _, seed, level, pos, layout = s.split('|')
        nodes = []
        for part in layout.split(';'):
            xyz, edges = part.split(':')
            values = xyz.split(',')
            if len(values) != 3: return None
            nodes.append(values + [edges.split(',') if edges else []])
        return validate_snapshot(dict(seed=seed, level=level, position=pos.split(','), nodes=nodes))
    except (ValueError, KeyError, TypeError): return None

def fingerprint(s):
    # Compare coordinates and adjacency, independent of C++ vector ordering.
    nodes = s['nodes']
    canonical = sorted((n[0], n[1], n[2], sorted((nodes[e][0], nodes[e][1]) for e in n[3])) for n in nodes)
    return hashlib.sha256(json.dumps(canonical, separators=(',', ':')).encode()).hexdigest()

def compare(players, now=None):
    now = time.time() if now is None else now
    if len(players) != 2: return 'WAITING — connect both captains.'
    if any(not p.get('snapshot') for p in players): return 'WAITING — both players must start a run with this co-op mod.'
    if any(now - p.get('seen', 0) > 20 for p in players): return 'STALE — waiting for fresh game data; check FTL, the companion and game link.'
    a, b = (p['snapshot'] for p in players)
    if a['seed'] != b['seed']: return 'SEED MISMATCH — both start NEW runs with the same co-op version.'
    if a['seed'] != SHARED_SEED: return 'WRONG SEED — old saves are not converted; start NEW runs.'
    if a['level'] != b['level']: return 'DIFFERENT SECTORS — choose the same sector route.'
    if fingerprint(a) != fingerprint(b): return 'MAP MISMATCH — check mod versions, settings and sector route.'
    if a['position'] != b['position']: return 'MAP MATCH — different beacons; stop and check both games.'
    return 'MAP MATCH + SAME BEACON — location confirmed.'
