"""Offline lifecycle/gate test for setup, day-end, saved dice, and resume."""
from __future__ import annotations
import json, sys, tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from brain.runtime_state import RuntimeStateStore
from pipeline import CampaignPipeline

def main():
 with tempfile.TemporaryDirectory() as raw:
  root=Path(raw); (root/'outside game').mkdir(parents=True); (root/'brain/state').mkdir(parents=True)
  # Resume only recovers editor when the module exists; lifecycle test uses store directly through a patched instance.
  p=CampaignPipeline(root)
  p._recover_editor=lambda: None
  setup=p.begin_setup()
  review=p.resolve_day_end({'proposal_id':'day-1'})
  applied=p.accept_day_end_receipt({'status':'applied','receipt_id':'r1'})
  opened=p.schedule_world_event(d100=42,world_result={'selected_trigger':'People','encounter_condition':'market entry','latest_phase':'Evening'})
  resumed=p.resume()
  checks={'setup_gate':setup['play_gate']=='setup_draft','day_end_blocks':review['play_gate']=='day_end_review','receipt_requires_world':applied['play_gate']=='world_event_pending','world_roll_saved':opened['pending_world_event']['roll']==42,'play_opened':opened['play_gate']=='open','resume_exact':resumed==opened}
  if not all(checks.values()): raise AssertionError(checks)
  result={'status':'passed',**checks}; (ROOT/'trial/30_runtime_lifecycle_result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
if __name__=='__main__': main()
