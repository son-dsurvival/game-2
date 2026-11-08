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
  /retry               retry the most recently failed stage
  {pause}              pause roleplay and enter outside-game mode
  {resume}             resume roleplay from a paused/new-day gate
  /new-game            immediately reset and start a new campaign
  /new-character       add a player character to the active campaign
  /new-party-member    add an NPC companion to the active campaign
  /add                 draft another character (new game only)
  /main NAME           choose the main character
  /review              review the drafted party/character
  /next-file           review the next proposed Markdown file
  /approve             approve the pending proposal
  /approve-reset       approve a full-campaign replacement
  /cancel-setup        cancel drafting; the active campaign is preserved
  /cancel-operation    cancel an unapplied review/proposal without file changes
  /end-day             sleep until tomorrow / end the day
  /specialists         list stored Create Specialist proposals
  /install NAME        propose installing a stored specialist
  /quit                exit (progress is saved)

Automation is enabled by default: active background work continues and
completed single-character drafts move into review automatically. Failed tasks stop for an explicit /retry, which retries the most recently failed stage from its saved pre-stage snapshot.
Use --no-auto for manual/debug mode.
"""

AUTO_RETRIES = 3
AUTO_RESUMABLE = {'running', 'background_pending'}


def _position_text(position: object) -> str:
    if not isinstance(position, dict):
        return ''
    day = position.get('day')
    phase = position.get('phase')
    progress = position.get('progress')
    if day is None and phase is None:
        return ''
    return f'Day {day} — {phase} ({float(progress or 0) * 100:.0f}% through phase)'


def _player_text(value: object, *, include_preview: bool = True) -> str:
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

    if status == 'status':
        operation_type = value.get('operation_type', 'gameplay')
        identifier_label = 'Request ID' if operation_type == 'out_of_game' else 'Turn ID'
        identifier = value.get('operation_id') or 'none'
        lines.append(f'{identifier_label}: {identifier}')
        lines.append(f'Type: {operation_type}')
        lines.append(f'Current stage: {value.get("current_stage") or "none"}')
        if value.get('previous_stage'):
            lines.append(f'Previous stage: {value["previous_stage"]}')
        if value.get('next_stage'):
            lines.append(f'Next stage: {value["next_stage"]}')
        lines.append(f'Status: {value.get("request_status", "completed")}')
        if value.get('original_input'):
            lines.append(f'Original input: {value["original_input"]}')
    elif status == 'setup_draft':
        lines.append('Character setup')
        if isinstance(draft, dict):
            characters = draft.get('characters') or []
            names = [str(item.get('identity', {}).get('name')) for item in characters if isinstance(item, dict)]
            if names:
                lines.append('Drafted characters: ' + ', '.join(names))
        if message:
            lines.append(str(message))
        if isinstance(draft, dict):
            characters = draft.get('characters') or []
            if characters and not draft.get('main_character'):
                available_names = ', '.join(str(item.get('identity', {}).get('name')) for item in characters if isinstance(item, dict))
                lines.append(f'When the party is complete, choose the main character with /main NAME. Available: {available_names}')
            elif characters and draft.get('main_character') and not draft.get('party_done'):
                lines.append('Finish adding characters, then use /main NAME to complete the party.')
    elif status == 'awaiting_clarification':
        lines.append('I need one clarification before continuing:')
        if isinstance(question, dict):
            prompt = question.get('question') or question.get('message')
            prompt_text = str(prompt) if prompt else ''
            if prompt_text:
                lines.append(prompt_text)
            if question.get('issue') and str(question['issue']).casefold() not in prompt_text.casefold():
                lines.append('Issue: ' + str(question['issue']))
            if question.get('why') and str(question['why']).casefold() not in prompt_text.casefold():
                lines.append('Why: ' + str(question['why']))
            conflicts = question.get('conflicts') or []
            if conflicts:
                lines.append('Details: ' + '; '.join(str(item) for item in conflicts))
        elif question:
            lines.append(str(question))
    elif status in {'setup_review', 'character_review', 'admin_review', 'day_end_review'}:
        file_info = value.get('proposal_file')
        total = value.get('proposal_files_total', 0)
        reviewed = value.get('proposal_files_reviewed', 0)
        lines.append('New campaign setup proposal.' if status == 'setup_review' else 'Campaign change proposal.')
        if isinstance(file_info, dict):
            lines.append(f"File {file_info.get('number')} of {file_info.get('total')}: {file_info.get('filename')}")
            lines.append(f"The game wants to {file_info.get('action', 'update')} this file.")
            lines.append(str(file_info.get('summary', '')))
            preview = file_info.get('preview')
            if include_preview and isinstance(preview, list) and preview:
                lines.append('Planned player-facing changes:')
                lines.extend(f'  {line}' for line in preview)
            lines.append('Required next step: send /next-file to review the next Markdown file.')
        elif total and reviewed >= total:
            lines.append('All proposed Markdown files have been reviewed.')
        if status == 'setup_review':
            lines.append('After reviewing every file, required approval: /approve-reset. You may revise the proposal instead.')
        else:
            lines.append('After reviewing every file, required approval: /approve. You may revise the proposal instead.')
    elif status in {'new_game_pending', 'new_day_pending', 'paused', 'day_end_pending'}:
        lines.append('Outside-game mode.')
        if message:
            lines.append(str(message))
        if status == 'day_end_pending':
            lines.append('Use /review to prepare the completed day for approval.')
        elif status in {'new_game_pending', 'new_day_pending', 'paused'}:
            lines.append('Use {resume} when you have finished reviewing the saved state.')
    elif status in {'running', 'background_pending'}:
        lines.append('The system is thinking…')
    elif status == 'retry':
        lines.append('The game paused safely while processing.')
        lines.append('No player clarification is currently pending. Use /retry to retry the most recently failed stage.')
        failure_reason = value.get('failure_reason')
        if failure_reason:
            lines.append('Reason: ' + str(failure_reason))
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
    if (enabled and result.get('status') == 'setup_draft'
            and isinstance(result.get('draft'), dict)
            and result['draft'].get('party_done')
            and result['draft'].get('main_character')):
        return _stabilize(pipeline, pipeline.review_setup(), enabled)
    return result


def _auto_setup_review(pipeline: CampaignPipeline, result: dict[str, Any], enabled: bool) -> dict[str, Any]:
    """Review a new-game party once the chatbot records an explicit completion."""
    draft = result.get('draft')
    if (enabled and result.get('status') == 'setup_draft' and isinstance(draft, dict)
            and draft.get('mode') == 'new_game' and draft.get('party_done') and draft.get('main_character')):
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


def _process_input(pipeline: CampaignPipeline, text: str, *, auto: bool = True) -> dict[str, Any]:
    """Route one input after the player interaction journal has been opened."""
    text = text.strip()
    if not text:
        raise ValueError('Enter a message.')
    if text == '/help':
        return {'status': 'help', 'message': HELP}
    if text.casefold() in {'{pause}', '/pause'}:
        pipeline.record_command(text)
        return pipeline.pause()
    if text.casefold() in {'{resume}', '/resume'}:
        pipeline.record_command(text)
        return pipeline.resume_play()
    if text == '/quit':
        pipeline.close_session()
        return {'status': 'quit', 'message': 'Progress saved.'}

    command, _, argument = text.partition(' ')
    manual_retry = command == '/retry'
    conversation: dict[str, Any] = {
        '/status': pipeline.status_report,
        '/retry': pipeline.retry,
        '/new-game': pipeline.begin_setup,
        '/new-character': pipeline.new_character,
        '/new-party-member': pipeline.new_party_member,
        '/add': pipeline.another_character,
        '/review': pipeline.review_current,
        '/next-file': pipeline.next_proposal_file,
        '/approve': pipeline.approve,
        '/approve-reset': lambda: pipeline.approve(confirm_reset=True),
        '/cancel-setup': pipeline.cancel_setup,
        '/cancel-operation': pipeline.cancel_pending,
        '/end-day': pipeline.end_day,
        '/specialists': pipeline.specialist_proposals,
    }
    if command == '/main':
        pipeline.record_command(text)
        result = pipeline.select_main(argument.strip())
        result = _auto_review_after_main(pipeline, result, auto)
    elif command == '/install':
        pipeline.record_command(text)
        result = pipeline.propose_specialist(argument.strip())
    elif command in conversation and not argument:
        pipeline.record_command(text)
        result = conversation[command]()
    else:
        result = pipeline.submit(text)
        result = _auto_setup_review(pipeline, result, auto)
        result = _auto_addition_review(pipeline, result, auto)
    return result if manual_retry else _stabilize(pipeline, result, auto)


def process_input(pipeline: CampaignPipeline, text: str, *, auto: bool = True) -> dict[str, Any]:
    """Process one input and persist its exact player-facing output."""
    interaction_id = pipeline.begin_player_interaction(text)
    try:
        result = _process_input(pipeline, text, auto=auto)
    except (ValueError, RuntimeError) as exc:
        pipeline.fail_player_interaction(interaction_id, text, exc)
        raise
    pipeline.complete_player_interaction(interaction_id, text, result, _player_text(result))
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
        print('Campaign terminal resumed. Type /help for commands.')
        _print(_initial_state(pipeline, auto=auto, start_new_game=False))
    else:
        print('Campaign terminal. Type /help for commands.')
        _print(_initial_state(pipeline, auto=auto, start_new_game=True))
    while True:
        try:
            text = input("""\n> """).strip()
        except (EOFError, KeyboardInterrupt):
            print('\nProgress saved. Restart to resume.')
            break
        if not text:
            continue
        try:
            if text not in {'/help', '/quit'}:
                print('System: thinking…')
            result = process_input(pipeline, text, auto=auto)
            if result.get('status') == 'quit':
                print(result.get('message', 'Progress saved.'))
                break
            _print(result)
        except (ValueError, RuntimeError) as exc:
            print(f'Error: {exc}')


if __name__ == '__main__':
    main()
