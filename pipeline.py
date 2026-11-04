"""Terminal entry point. Reusable orchestration lives in brain.game_runtime."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from brain.game_runtime import CampaignPipeline


HELP = """Commands:
  <message>            play a turn (or answer a character question)
  {message}            out-of-game administrative request
  /status              show the saved stage
  /retry               resume unfinished work
  /new-game            start a new campaign (replaces the current one on approve)
  /new-character       add a player character to the active campaign
  /new-party-member    add an NPC companion to the active campaign
  /add                 draft another character (new game only)
  /main NAME           choose the main character
  /review              review the drafted party/character
  /approve             approve the pending proposal
  /approve-reset       approve a full-campaign replacement
  /cancel-setup        cancel drafting; the active campaign is preserved
  /end-day             sleep until tomorrow / end the day
  /specialists         list stored Create Specialist proposals
  /install NAME        propose installing a stored specialist
  /quit                exit (progress is saved)
"""


def _print(value: object) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, default=str))


def main() -> None:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description='Resumable campaign terminal')
    parser.add_argument('command', nargs='?', choices=('chat', 'resume'), default='chat')
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    pipeline = CampaignPipeline(args.root)
    if args.command == 'resume':
        _print(pipeline.resume())
        return
    print('Campaign terminal. Type /help for commands.')
    _print(pipeline.resume())
    while True:
        try:
            text = input('\n> ').strip()
        except (EOFError, KeyboardInterrupt):
            print('\nProgress saved. Restart to resume.')
            break
        if not text:
            continue
        if text == '/quit':
            print('Progress saved.')
            break
        try:
            command, _, argument = text.partition(' ')
            conversation = {
                '/status': pipeline.resume,
                '/retry': pipeline.continue_run,
                '/new-game': pipeline.begin_setup,
                '/new-character': pipeline.new_character,
                '/new-party-member': pipeline.new_party_member,
                '/add': pipeline.another_character,
                '/review': pipeline.review_setup,
                '/approve': pipeline.approve,
                '/approve-reset': lambda: pipeline.approve(confirm_reset=True),
                '/cancel-setup': pipeline.cancel_setup,
                '/end-day': pipeline.end_day,
                '/specialists': pipeline.specialist_proposals,
            }
            if text == '/help':
                print(HELP)
            elif command == '/main':
                _print(pipeline.select_main(argument.strip()))
            elif command == '/install':
                _print(pipeline.propose_specialist(argument.strip()))
            elif command in conversation and not argument:
                _print(conversation[command]())
            else:
                _print(pipeline.submit(text))
        except (ValueError, RuntimeError) as exc:
            print(f'Error: {exc}')


if __name__ == '__main__':
    main()
