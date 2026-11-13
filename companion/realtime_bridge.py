"""Socket-thread forwarding; never accesses Tk or waits for UI polling."""
import diagnostics as diag

def forward(msg,local,enabled,report):
    kind=msg.get('type')
    if kind not in ('pause','jump','combat','scene'):return False
    if kind in ('combat','scene') and not enabled:return True
    try:
        if kind=='scene':local.set_scene(msg['scene'])
        else:
            line=msg.get('line','');local.send_combat(line)
            if kind!='pause' and '|SNAP|' not in line and '|EFFECT|' not in line:
                report(kind.upper()+': '+line)
    except (ValueError,TypeError,KeyError):
        diag.exception('Realtime input rejected')
        raise ValueError('invalid realtime message')
    return True
