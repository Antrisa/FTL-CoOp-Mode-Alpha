# Architecture and code map

## Execution model
Each Windows PC runs FTL with the .ftl Lua scripts and a matching custom Hyperspace.dll, plus one Python companion. Native transport connects only to the local companion. The host's Python relay accepts both captains over Hamachi. The companion tails FTL_HS.log for event/map telemetry and also uses the faster native channel for ship/combat/pause/jump/scene messages. The keyboard bridge remains for guarded event execution/fallback operations.

The .ftl is a ZIP assembled by `companion/build_mod.py`. Its hyperspace.xml.append lists script load order. Python sources are not installed through the mod manager; run the matching companion package.

## Files to start with
| Area | Files under current/ | Responsibility |
|---|---|---|
| UI/server | companion/fleet_link.py | Tk UI, relay Room, client, socket writers, telemetry routing |
| Local channel | companion/fast_local.py, fast_link.lua; native/fleet_transport.* | Native localhost messages, bounded delivery and acknowledgment |
| Scheduling | companion/priority_updates.py, realtime_bridge.py | Reliable control FIFO, replaceable latest snapshots, off-UI forwarding |
| Events | companion/events.lua, event_vote.py | Local event screen/token, exact content/context checks, ballots |
| Input execution | companion/bridge.lua, bridge_room.py, input_bridge.py | Per-screen guards, command nonce, ARMED/OK confirmation |
| Native votes | companion/native_vote.lua, panel.lua, panel_status.py | Native clicks, optional F8 ballot/status and visual feedback |
| Personal trade | companion/local_trade.lua | Explicit missile-station allowlist and bounded immediate Continue |
| Shared enemy | companion/combat.lua, combat.py | Setup, host/guest roles, SHOT/SPAWN, ACK, snapshots, finish/reward barriers |
| Native combat | native/fleet_combat.cpp, fleet_effects.cpp, fleet_boarding.* | Replica handling, native effects and boarding roster/lifecycle |
| Pause | companion/fleet_pause.lua, fleet_pause.py | Revisions, local HOLD/READY, both-captain resume barrier |
| Travel | companion/jump_vote.lua, jump_vote.py | Native map selection, agreement, PREPARE/COMMIT and arrival |
| Legacy travel | companion/travel.py | Earlier manual planning protocol, retained internally but removed from main UI |
| Map/ship state | companion/shared_map.py, ship_view.py, fleet_coop_v07.lua, interior.* | Seed/map comparison, ship stats and fallback interior telemetry |
| Live graphics | native/fleet_scene.cpp, fleet_scene_codec.hpp; companion/scene.lua, scene.py | Native capture/replay, validated/compressed draw lists, render smoothing |
| Ship UI | companion/ships.lua, ui_theme.lua | Partner status, inspector, labels and common text helpers |
| Install | companion/launch_game.py, build_mod.py; native/install_patch.py | .ftl generation, DLL verification/backups/launch, upstream patch installation |

## Events and personal trades
`events.lua` captures seed, sector, beacon, main text and ordered choices with choice types. Screen tokens change with screen/context/content. `EventVote` keeps per-captain token guards; never substitute the host token for both PCs.

For ordinary shared events, labels/order/context must match. v0.28.12 normalizes only normal enabled/disabled type 0/1 for identity comparison. A row disabled for either player is unavailable in the shared ballot. Other special choice-type differences stay exact. Content changes invalidate ballots even if a token is unexpectedly reused.

The personal missile event is matched against exact observed English text and four exact labels. `local_trade.lua` allows native input for that offer and one subsequent enabled `Continue...` screen at the same context. It clears permission on close, new context, unexpected branch or later screen. Python suppresses a shared ballot for the recognized offer. It does not copy resources or force a choice. FTL handles affordability and actual transaction effects.

Other local exceptions are narrowly scoped: the observed enemy escape warning, and a single Continue during acknowledged post-combat rewards. Do not permit arbitrary single-choice events globally; they can change progression or resources.

## Combat authority and safety
Read the state machine in combat.lua/combat.py before editing. Guest offensive fire is captured and sent to the host; the host creates/applies it once and sends ordered visual/result state back. Retries must not duplicate damage. Player inventories and friendly systems are not broad-copied from the host.

Friendly combat drone `DRONE_FIRE` interception returns PREEMPT for guest projectiles. Upstream SpaceDrone::GetNextProjectile deletes that projectile on PREEMPT before insertion. Do not manually delete/Kill it or retain its userdata. Player gun/drone shots share the monotonic shot-ID sequence; host duplicate suppression and ACKs are essential.

Finish is a coordinated phase. Reward Continue may appear at different wall-clock times; post-ready/release gates prevent travel until both finish required reward state and remaining host boarders are handled. A local informational popup must not permanently stop partner progression. Do not solve reward mismatch by globally disabling votes or forcing enemy hull to zero without the correct finish semantics.

## Graphics and flow control
FS26 contains asset paths and float vertices; Python validates bounds and compresses it for the relay. No arbitrary file path or unbounded payload acceptance. It uses latest-frame replacement with local SCENE_ACK flow control. Control messages take precedence over unsent snapshots.

v0.28.13 capture is every second native render; Lua dispatch every second game tick; relay scene limit 0.025 s; local delivery interval 0.02 s; socket receive chunk 65536 bytes and timeout 0.005 s. Those are separate gates, not a guarantee of 30 fps. Preserve backpressure when optimizing.

Crew interpolation blends only bounded rigid translations of the same `people/` texture with matching vertices/UV/color, unchanged scene bounds and draw count. It skips unknown changes; it does not predict gameplay. Stale frames (>0.25 s between accepts) skip interpolation; blend interval is capped at 0.08 s.

Native sampler changes are scoped to friendly rendering and restore prior texture min/mag settings and binding. Validate FTL/OpenGL behavior on Windows; portable tests do not exercise this path. Local crew input uses inverse scaling and treats partner area as read-only.
