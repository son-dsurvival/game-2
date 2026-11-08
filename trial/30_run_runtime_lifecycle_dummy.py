"""Offline lifecycle gate test for the private resumable runtime state."""
from __future__ import annotations
import json, tempfile
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from brain.runtime_state import RuntimeStateStore

def main():
 with tempfile.TemporaryDirectory() as raw:
  root=Path(raw); store=RuntimeStateStore(root)
  setup=store.transition(play_gate="setup_draft",setup_status="character_draft")
  review=store.transition(play_gate="day_end_review",day_end={"status":"review_prepared","proposal":{"proposal_id":"day-1"}})
  applied=store.transition(play_gate="world_event_pending",day_end={"status":"applied","receipt":{"receipt_id":"r1"}})
  event={"roll":42,"selected_trigger":"People","encounter_condition":"market entry","latest_phase":"Evening","status":"pending"}
  opened=store.transition(play_gate="open",pending_world_event=event)
  resumed=store.load()
  checks={'setup_gate':setup['play_gate']=='setup_draft','day_end_blocks':review['play_gate']=='day_end_review','receipt_requires_world':applied['play_gate']=='world_event_pending','world_roll_saved':opened['pending_world_event']['roll']==42,'play_opened':opened['play_gate']=='open','resume_exact':resumed==opened}
  if not all(checks.values()): raise AssertionError(checks)
  result={'status':'passed',**checks}; (ROOT/'trial/30_runtime_lifecycle_result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
if __name__=='__main__': main()
