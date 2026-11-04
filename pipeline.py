"""Terminal entry point. Reusable orchestration lives in brain.game_runtime."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from brain.game_runtime import CampaignPipeline


def main() -> None:
    parser = argparse.ArgumentParser(description='Resumable campaign terminal')
    parser.add_argument('command', nargs='?', choices=('chat', 'resume'), default='chat')
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    pipeline = CampaignPipeline(args.root)
    if args.command == 'resume':
        print(json.dumps(pipeline.resume(), ensure_ascii=False, indent=2))
        return
    print('Campaign terminal. /status, /retry, /quit. Use {...} for administrative requests.')
    print(json.dumps(pipeline.resume(), ensure_ascii=False, indent=2))
    while True:
        try:
            text = input('\n> ').strip()
            if text == '/quit':
                break
            result = pipeline.resume() if text == '/status' else pipeline.continue_run() if text == '/retry' else pipeline.submit(text)
            print(json.dumps(result, ensure_ascii=False, indent=2))
        except (EOFError, KeyboardInterrupt):
            print('\nProgress saved. Restart to resume.')
            break
        except (ValueError, RuntimeError) as exc:
            print(str(exc))


if __name__ == '__main__':
    main()
