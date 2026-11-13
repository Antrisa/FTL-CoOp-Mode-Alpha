import copy,json,unittest
from pathlib import Path
from event_vote import EventVote,personal_trade
import test_native
ROOT=Path(__file__).resolve().parents[1]
EVENTS=json.loads((ROOT/'tests/trade2812_fixture.json').read_text())
class TradeTests(unittest.TestCase):
 def view(self,event):
  l=test_native.NativeLuaTests().lua()
  l.execute('script.on_init=function(f)callbacks.init=f end')
  l.execute((ROOT/'local_trade.lua').read_text())
  l.globals().main=event['text'];l.globals().labels=l.table_from([c['text'] for c in event['choices']]);l.globals().types=l.table_from([c['type'] for c in event['choices']])
  l.execute("state.count=4;state.content='7062026|0|621,405|text|choices';box.mainText=main;choices={};for i=0,3 do choices[i]={text=labels[i+1],type=types[i+1]}end;box.GetChoices=function()return choices end")
  return l
 def test_actual_logs_are_personal_trade_not_shared_ballot(self):
  self.assertEqual([c['type'] for c in EVENTS[0]['choices']],[0,1,1,0])
  self.assertEqual([c['type'] for c in EVENTS[1]['choices']],[1,1,1,0])
  v=EventVote();v.sync([dict(id=i,event=e,event_seen=100) for i,e in enumerate(EVENTS)],100)
  self.assertIsNone(v.ballot);self.assertIn('Personal trade',v.message)
 def test_host_sells_guest_declines_without_vote_or_inventory_copy(self):
  for e,key in zip(EVENTS,[49,52]):
   l=self.view(e)
   self.assertEqual(l.globals().FleetNative15.key(key),0)
   self.assertFalse(any('NATIVE_VOTE' in x for x in l.globals().logs.values()))
 def test_mouse_passes_to_native_including_disabled_native_cost_checks(self):
  for e in EVENTS:
   l=self.view(e);self.assertEqual(l.globals().callbacks[1](20,30),0)
 def test_only_next_single_continue_is_local_then_normal_votes_resume(self):
  l=self.view(EVENTS[0]);l.globals().FleetNative15.key(49)
  l.execute("state.token=43;state.count=1;box.mainText='Trade complete';choices={[0]={text='Continue...',type=0}}")
  self.assertEqual(l.globals().FleetNative15.key(49),0)
  l.execute('state=nil;callbacks[4]()')
  l.execute("state={token=44,count=1,content='7062026|0|621,405|other',box=box}")
  self.assertEqual(l.globals().FleetNative15.key(49),1)
 def test_trade_permission_cannot_follow_jump_or_multichoice_branch(self):
  for change in ["state.content='7062026|0|43,73|other'",'state.count=2',"choices[0].text='Attack'",'choices[0].type=1']:
   l=self.view(EVENTS[0]);l.globals().FleetNative15.key(49)
   l.execute("state.token=43;state.count=1;choices={[0]={text='Continue...',type=0}};box.mainText='result'")
   l.execute(change)
   self.assertFalse(l.globals().FleetTrade2812.localEvent(l.globals().state))
 def test_similar_unrecognized_trade_still_requires_vote(self):
  l=self.view(EVENTS[0]);l.execute("box.mainText=box.mainText..' changed'")
  self.assertEqual(l.globals().FleetNative15.key(49),1)
 def test_shared_event_availability_allows_common_choice_only(self):
  es=copy.deepcopy(EVENTS)
  for e in es:e['text']='Other shared event'
  ps=[dict(id=i,event=e,event_seen=100)for i,e in enumerate(es)]
  v=EventVote();v.sync(ps,100);r=v.round
  with self.assertRaises(ValueError):v.vote(0,r,1)
  v.vote(0,r,4);v.vote(1,r,4);self.assertEqual(v.prepare(0,0,r)[0],'CHOICE_4')
  ps[0]['event']['choices'][3]['type']=1;v.sync(ps,101)
  self.assertNotEqual(v.round,r);self.assertEqual(v.ballot['votes'],{})
  with self.assertRaises(ValueError):v.vote(0,r,4)
 def test_changed_text_order_or_location_remains_blocked(self):
  for field in ['text','order','position']:
   es=copy.deepcopy(EVENTS)
   for e in es:e['text']='Other shared event'
   if field=='text':es[1]['text']='Different'
   if field=='order':es[1]['choices'].reverse()
   if field=='position':es[1]['position']=[0,0]
   v=EventVote();v.sync([dict(id=i,event=e,event_seen=100) for i,e in enumerate(es)],100)
   self.assertIsNone(v.ballot)

class TradeJumpBarrierTests(unittest.TestCase):
 def test_open_event_cancels_old_vote_and_refuses_prepare_commit(self):
  import test_jump_vote
  for field in ['choiceBoxOpen','event_pause']:
   l=test_jump_vote.JumpLuaTests().lua();m=l.globals().FleetJump24
   m.receive('JUMP|PREPARE|1|42|7')
   l.execute('Hyperspace.App.gui.'+field+'=true')
   m.receive('JUMP|COMMIT|1|42|7')
   self.assertEqual(l.globals().commits,0)
   m.tick();self.assertIn('JUMP|CLEAR',list(l.globals().sent.values()))
