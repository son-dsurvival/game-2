"""Terminal entry point. Reusable orchestration lives in brain.game_runtime."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

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

Automation is enabled by default: unfinished work is resumed, transient
failures are retried a few times, and completed single-character drafts move
into review automatically. Use --no-auto for manual/debug mode.
"""

AUTO_RETRIES = 3
AUTO_RESUMABLE = {'running', 'retry', 'background_pending'}


def _position_text(position: object) -> str:
    if not isinstance(position, dict):
        return ''
    day = position.get('day')
    phase = position.get('phase')
    progress = position.get('progress')
    if day is None and phase is None:
        return ''
    return f'Day {day} — {phase} ({float(progress or 0) * 100:.0f}% through phase)'


def _player_text(value: object) -> str:
    """Render pipeline results as player-facing prose, never backend JSON."""
    if isinstance(value, str):
        return value
    if not isinstance(value, dict):
        return str(value)

    status = str(value.get('status', ''))
    lines: list[str] = []
    message = value.get('message')
    position = _position_text(value.get('position'))
    draft = value.get('draft')
    question = value.get('question')

    if status == 'setup_draft':
        lines.append('Character setup')
        if isinstance(draft, dict):
            characters = draft.get('characters') or []
            names = [str(item.get('identity', {}).get('name')) for item in characters if isinstance(item, dict)]
            if names:
                lines.append('Drafted characters: ' + ', '.join(names))
        if message:
            lines.append(str(message))
    elif status == 'awaiting_clarification':
        lines.append('I need one clarification before continuing:')
        if isinstance(question, dict):
            prompt = question.get('question') or question.get('message')
            if prompt:
                lines.append(str(prompt))
            conflicts = question.get('conflicts') or []
            if conflicts:
                lines.append('Details: ' + '; '.join(str(item) for item in conflicts))
        elif question:
            lines.append(str(question))
    elif status in {'setup_review', 'character_review', 'admin_review', 'day_end_review'}:
        lines.append('Review ready.')
        proposal = value.get('proposal')
        if isinstance(proposal, dict) and proposal.get('answer'):
            lines.append(str(proposal['answer']))
        if isinstance(proposal, dict):
            changes = proposal.get('changes') or []
            files = [str(change.get('target_file')) for change in changes if isinstance(change, dict) and change.get('target_file')]
            if files:
                lines.append('Files affected: ' + ', '.join(files))
        if status == 'setup_review':
            lines.append('Approve the new campaign with /approve-reset, or revise it with a message.')
        elif status == 'day_end_review':
            lines.append('Approve day-end promotion with /approve, or revise it with a message.')
        else:
            lines.append('Approve with /approve, or revise it with a message.')
    elif status == 'retry':
        lines.append('The game paused safely while processing.')
        lines.append('It will retry automatically; use /retry to try again manually.')
        if message:
            lines.append(str(message))
    elif status == 'setup_required':
        lines.append('No campaign has been created yet.')
        lines.append('Starting a new game...')
    elif status == 'specialists' or value.get('specialist_proposals'):
        proposals = value.get('specialist_proposals') or []
        lines.append('Specialist proposals:')
        if isinstance(proposals, list) and proposals:
            for proposal in proposals:
                if isinstance(proposal, dict):
                    name = proposal.get('name', 'unnamed')
                    purpose = proposal.get('purpose', 'no purpose recorded')
                    lines.append(f'  - {name}: {purpose}')
        else:
            lines.append('  None stored.')
    elif message:
        lines.append(str(message))

    if position and status not in {'setup_draft', 'setup_review', 'character_review', 'admin_review', 'day_end_review'}:
        lines.append(position)

    if not lines:
        if status:
            lines.append(status.replace('_', ' ').capitalize() + '.')
        else:
            lines.append('Done.')
    return '\n'.join(lines)


def _print(value: object) -> None:
    print(_player_text(value))


def _stabilize(pipeline: CampaignPipeline, result: dict[str, Any], enabled: bool = True) -> dict[str, Any]:
    """Finish safe resumable work without bypassing approval gates."""
    if not enabled:
        return result
    for _ in range(AUTO_RETRIES):
        if result.get('status') not in AUTO_RESUMABLE:
            break
        result = pipeline.continue_run()
    return result


def _auto_review_after_main(pipeline: CampaignPipeline, result: dict[str, Any], enabled: bool) -> dict[str, Any]:
    """Move a deliberately completed draft into review automatically."""
    if enabled and result.get('status') == 'setup_draft' and result.get('draft'):
        return _stabilize(pipeline, pipeline.review_setup(), enabled)
    return result


def _auto_addition_review(pipeline: CampaignPipeline, result: dict[str, Any], enabled: bool) -> dict[str, Any]:
    """NPC/player additions are single-character operations, so review them once drafted."""
    draft = result.get('draft')
    if not isinstance(draft, dict):
        return result
    if (enabled and result.get('status') == 'setup_draft'
            and draft.get('mode') in {'new_character', 'new_party_member'}
            and draft.get('question') == 'party' and draft.get('characters')):
        name = draft['characters'][0]['identity']['name']
        result = pipeline.select_main(name)
        result = _stabilize(pipeline, pipeline.review_setup(), enabled)
    return result


def _initial_state(pipeline: CampaignPipeline, *, auto: bool, start_new_game: bool) -> dict[str, Any]:
    result = _stabilize(pipeline, pipeline.resume(), auto)
    if auto and start_new_game and result.get('status') == 'setup_required':
        result = pipeline.begin_setup()
    return result


def main() -> None:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description='Resumable campaign terminal')
    parser.add_argument('command', nargs='?', choices=('chat', 'resume'), default='chat')
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument('--no-auto', action='store_true', help='disable safe automatic resume/retry/review behavior')
    args = parser.parse_args()
    pipeline = CampaignPipeline(args.root)
    auto = not args.no_auto
    if args.command == 'resume':
        _print(_initial_state(pipeline, auto=auto, start_new_game=False))
        return
    print('Campaign terminal. Type /help for commands.')
    _print(_initial_state(pipeline, auto=auto, start_new_game=True))
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
            conversation: dict[str, Any] = {
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
                continue

            result: dict[str, Any]
            if command == '/main':
                result = pipeline.select_main(argument.strip())
                result = _auto_review_after_main(pipeline, result, auto)
            elif command == '/install':
                result = pipeline.propose_specialist(argument.strip())
            elif command in conversation and not argument:
                result = conversation[command]()
            else:
                result = pipeline.submit(text)
                result = _auto_addition_review(pipeline, result, auto)

            _print(_stabilize(pipeline, result, auto))
        except (ValueError, RuntimeError) as exc:
            print(f'Error: {exc}')


if __name__ == '__main__':
    main()
