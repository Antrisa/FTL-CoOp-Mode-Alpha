"""Rebuild the distributable mod from the included Lua source."""
from pathlib import Path
import zipfile
ROOT = Path(__file__).resolve().parent

def build():
    target = ROOT / 'FleetCoop_Ingame_Panel_v0.28.16.ftl'
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('data/hyperspace.xml.append', '''<mod:findLike type="scripts">
    <mod-append:script>data/fleet_ui_v0281.lua</mod-append:script>
    <mod-append:script>data/fleet_coop_v07.lua</mod-append:script>
    <mod-append:script>data/fleet_events_v010.lua</mod-append:script>
    <mod-append:script>data/fleet_bridge_v09.lua</mod-append:script>
    <mod-append:script>data/fleet_panel_v011.lua</mod-append:script>
    <mod-append:script>data/fleet_cursor_v014.lua</mod-append:script>
    <mod-append:script>data/fleet_trade_v02812.lua</mod-append:script>
    <mod-append:script>data/fleet_native_v015.lua</mod-append:script>
    <mod-append:script>data/fleet_interior_v019.lua</mod-append:script>
    <mod-append:script>data/fleet_fast_v0280.lua</mod-append:script>
    <mod-append:script>data/fleet_combat_v0280.lua</mod-append:script>
    <mod-append:script>data/fleet_jump_v0280.lua</mod-append:script>
    <mod-append:script>data/fleet_scene_v0280.lua</mod-append:script>
    <mod-append:script>data/fleet_pause_v0280.lua</mod-append:script>
    <mod-append:script>data/fleet_ships_v017.lua</mod-append:script>
</mod:findLike>
<mod:findLike type="events">
    <mod-append:event name="FLEET_COOP_COMBAT_SYNC">
        <disableSurrender force="true"/>
        <disableEscape force="true"/>
    </mod-append:event>
</mod:findLike>
''')
        # Textless event: loading it shows no screen. Hyperspace applies the
        # custom tags above to this game's enemy (see combat.lua lockOutcome).
        z.writestr('data/events.xml.append', '''<event name="FLEET_COOP_COMBAT_SYNC">
</event>
''')
        z.write(ROOT/'ui_theme.lua', 'data/fleet_ui_v0281.lua')
        z.write(ROOT/'fleet_coop_v07.lua', 'data/fleet_coop_v07.lua')
        z.write(ROOT/'events.lua', 'data/fleet_events_v010.lua')
        z.write(ROOT/'bridge.lua', 'data/fleet_bridge_v09.lua')
        z.write(ROOT/'panel.lua', 'data/fleet_panel_v011.lua')
        z.write(ROOT/'cursor.lua', 'data/fleet_cursor_v014.lua')
        z.write(ROOT/'local_trade.lua', 'data/fleet_trade_v02812.lua')
        z.write(ROOT/'native_vote.lua', 'data/fleet_native_v015.lua')
        z.write(ROOT/'interior.lua', 'data/fleet_interior_v019.lua')
        z.write(ROOT/'fast_link.lua', 'data/fleet_fast_v0280.lua')
        z.write(ROOT/'combat.lua', 'data/fleet_combat_v0280.lua')
        z.write(ROOT/'jump_vote.lua', 'data/fleet_jump_v0280.lua')
        z.write(ROOT/'scene.lua', 'data/fleet_scene_v0280.lua')
        z.write(ROOT/'fleet_pause.lua', 'data/fleet_pause_v0280.lua')
        z.write(ROOT/'ships.lua', 'data/fleet_ships_v017.lua')
    return target

if __name__ == '__main__': print(build())
