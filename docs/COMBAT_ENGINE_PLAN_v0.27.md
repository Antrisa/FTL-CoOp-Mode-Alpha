# Shared combat: implementation boundary and required work

User target: own playable ship below, connected playable ship above, both can
target ONE enemy and see the same attacks/effects. v0.27.3 retains the live
read-only partner view and extends the opt-in shared-enemy alpha to all five
vanilla weapon families. Friendly ship simulations remain local.

Verified source boundary (official Hyperspace v1.20.0):
- Global::GetShipManager in Global.cpp returns enemy for1 and player for otherIDs;
  ID2 is not an allied slot.
- WorldManager.playerShip/bossShip CompleteShip attachment is not exposed in Lua
  (hyperspace.i commented bindings). ShipGenerator allocation alone lacks world
  attachment, ownership, rendering/targeting and save/load integration.
- Native FTL input/render relationships assume player/enemy roles. Moving just
  an image cannot move rooms, weapon origins, selection hitboxes or targeting.
The v0.27.3 custom Windows DLL adds a native map gate and advances guest enemy weapons. v0.27.3 extends the shared-enemy
lab with guest native enemy simulation frozen and guest projectiles created by
the host. This is not the complete three-ship architecture below.

Required native implementation, in dependency order:
1. Define host-authoritative encounter lifecycle: encounter ID, seed, enemy
   blueprint, full initial systems/crew/shields/hull, and monotonic tick IDs.
2. Extend native world ownership for two friendly ships and one enemy. Maintain
   distinct ship IDs/team relationships throughout projectiles, crew, drones,
   boarding, hacking, mind control and targeting; explicit lifecycle cleanup.
3. Place both playable ships using shared render AND input transforms, preserving
   room hitboxes, weapon origins, beams and right-side enemy targeting controls.
4. Send player intent (aim, fire, system power, crew orders). Host validates it;
   clients never apply independent damage rolls. Host simulates enemy decisions,
   weapon charge, shield impacts, misses, beams, hull/system/crew damage, fires,
   breaches, oxygen, stun, drones and repairs, then broadcasts results/state.
5. Render matching projectile/effect timelines on both clients; reconcile from
   authoritative state without replaying damage. Tie every command to encounter
   and tick IDs to discard old messages after jumps/reconnections.
6. Synchronize rewards, destruction, escape/jump, save/load and reconnection.
   Decide pause rules explicitly; the current local F7 pause is not that system.
7. Build for the exact Windows FTL executable/Hyperspace version. Test offline
   ownership cleanup first, then2-PC combat under latency/loss/duplicate messages.

First native combat acceptance test:
Two different friendly hulls and one enemy. Both players target a chosen room.
Host computes damage once per projectile. Both clients show the same projectile
IDs, shield/hull/system deltas and final enemy state. Then test misses, shields,
beam multi-room hits, fire/breach/crew damage and simultaneous destruction.

Do not substitute health mirroring, forced identical seeds, duplicated local
hulls or independent random battles for this acceptance test. No native combat
implementation is claimed complete by this document or the fleet-view prototype.
