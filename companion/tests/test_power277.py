import unittest
import test_combat

class PowerSnapshotTests(unittest.TestCase):
 def make(self):
  helper=test_combat.LuaCombatTests();l=helper.lua();helper.start(l,'G')
  l.execute('''lockCalls=0
   local power={first=2,second=3}
   sys={healthState={first=3,second=3},iLockCount=0,
    powerState=setmetatable({}, {__index=power,__newindex=function()error('unsafe raw power write')end})}
   function sys:LockSystem(n)lockCalls=lockCalls+1;self.iLockCount=n;timerInitialized=true end
   Hyperspace.ships.enemy.GetSystem=function(_,id)if id==3 then return sys end end
  ''');return l
 def test_host_power_does_not_overwrite_guest_weapon_allocation(self):
  l=self.make()
  l.globals().FleetCombat22.receive('COMBAT|SNAP|testepoch|1|28|30|0|0|3,2,3,0,0')
  self.assertEqual(l.globals().sys.powerState.first,2)
  self.assertEqual(l.globals().sys.healthState.first,2)
  self.assertIsNone(l.globals().FleetCombat22.pauseBlock())
 def test_ion_sync_uses_native_lock_method_once_per_change(self):
  l=self.make()
  for seq in (1,2):l.globals().FleetCombat22.receive(f'COMBAT|SNAP|testepoch|{seq}|28|30|0|0|3,2,3,0,1')
  self.assertEqual(l.globals().lockCalls,1);self.assertTrue(l.globals().timerInitialized)
  l.globals().FleetCombat22.receive('COMBAT|SNAP|testepoch|3|28|30|0|0|3,2,3,0,0')
  self.assertEqual(l.globals().lockCalls,2);self.assertEqual(l.globals().sys.iLockCount,0)
 def test_stale_snapshot_cannot_restore_old_ion_state(self):
  l=self.make()
  l.globals().FleetCombat22.receive('COMBAT|SNAP|testepoch|2|28|30|0|0|3,2,3,0,1')
  l.globals().FleetCombat22.receive('COMBAT|SNAP|testepoch|1|30|30|0|0|3,3,3,3,0')
  self.assertEqual(l.globals().sys.iLockCount,1);self.assertEqual(l.globals().sys.healthState.first,2)
