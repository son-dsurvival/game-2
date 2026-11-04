"""Run one prompt through the real pipeline and print a concise result."""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pipeline import CampaignPipeline


def summarize(result):
    keys = ('status', 'play_gate')
    out = {k: result.get(k) for k in keys}
    out['position'] = result.get('position')
    if result.get('question'):
        out['question'] = result['question']
    if result.get('proposal'):
        prop = result['proposal']
        out['proposal_summary'] = {
            'status': prop.get('status'),
            'answer': prop.get('answer'),
            'changes': [c.get('target_file') for c in prop.get('changes', [])],
        }
    msg = result.get('message', '')
    out['message'] = msg if len(msg) < 1600 else msg[:1600] + '…'
    return out


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    if len(sys.argv) < 2:
        print('usage: python trial/run_prompt.py "<message>" [continue_run|end_day]')
        return
    action = sys.argv[2] if len(sys.argv) > 2 else 'submit'
    pipeline = CampaignPipeline(ROOT)
    t0 = time.time()
    try:
        if action == 'end_day':
            result = pipeline.end_day()
        elif action == 'continue':
            result = pipeline.continue_run()
        else:
            result = pipeline.submit(sys.argv[1])
        print(json.dumps(summarize(result), ensure_ascii=False, indent=2))
    except Exception as exc:
        print(json.dumps({'ERROR': type(exc).__name__, 'detail': str(exc)[:500]}, ensure_ascii=False, indent=2))
    finally:
        print(f'[elapsed {time.time()-t0:.1f}s]')
        pipeline.close()


if __name__ == '__main__':
    main()
