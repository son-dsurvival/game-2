"""Small browser frontend for the resumable campaign pipeline.

Run:
    python web_frontend.py
Then open http://127.0.0.1:8000/
"""
from __future__ import annotations

import argparse
import html
import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlparse

from pipeline import _initial_state, _player_text, process_input
from brain.game_runtime import CampaignPipeline


FILE_DESCRIPTIONS = {
    'Branch Registry.md': 'Tracks discovered, candidate, and unlocked world branches.',
    'Experimentation Register.md': 'Records experiments, safe background status, and experimentation rules.',
    'Ledger Resources.md': 'Tracks character resources, money, materials, facilities, and changes.',
    'TERMS_AND_NOMENCLATURE.md': 'Shared campaign terminology and canonical names.',
    'TEMP_MEMORY.md': 'Temporary session facts and working records awaiting canon promotion.',
    'character relationship.md': 'Player, party, and non-party relationship records.',
    'game rules (1).md': 'The campaign rules and resolution systems.',
    'status sheet.md': 'Character identity, stats, derived values, modifiers, skills, and equipment.',
    '🌍 CORE WORLD FRAME (REFINED).md': 'Established world lore, history, setting conditions, and canon frame.',
}


HTML = r'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Campaign Terminal</title>
  <style>
    :root { color-scheme: dark; --bg:#101318; --panel:#191e27; --panel2:#222936; --text:#edf2f7; --muted:#9ba8b7; --accent:#73b7ff; --line:#303b4a; }
    * { box-sizing:border-box; }
    body { margin:0; min-height:100vh; background:var(--bg); color:var(--text); font:15px/1.5 system-ui, sans-serif; }
    .file-bar { position:sticky; top:0; z-index:30; display:flex; align-items:center; gap:16px; min-height:52px; padding:9px 18px; background:var(--panel2); border-bottom:1px solid var(--line); }
    .file-bar strong { flex:0 0 auto; color:var(--text); font-size:13px; }
    .file-bar strong a { color:var(--text); text-decoration:none; }
    .file-links { display:flex; gap:14px; min-width:0; overflow-x:auto; white-space:nowrap; }
    .file-links a { color:var(--accent); font-size:13px; text-decoration:none; }
    .file-links a:hover { text-decoration:underline; }
    .shell { display:grid; grid-template-columns:270px minmax(0,1fr); height:calc(100vh - 52px); min-height:calc(100vh - 52px); }
    aside { position:sticky; top:52px; height:calc(100vh - 52px); overflow-y:auto; z-index:10; padding:24px 18px; background:var(--panel); border-right:1px solid var(--line); }
    h1 { margin:0 0 4px; font-size:21px; }
    .subtitle { margin:0 0 28px; color:var(--muted); }
    .label { margin:18px 0 6px; color:var(--muted); font-size:11px; letter-spacing:.1em; text-transform:uppercase; }
    #status { color:var(--accent); font-weight:650; }
    #position { color:var(--muted); font-size:13px; }
    .actions { display:grid; gap:7px; }
    button { border:1px solid var(--line); border-radius:7px; padding:9px 10px; background:var(--panel2); color:var(--text); cursor:pointer; text-align:left; }
    button:disabled { cursor:wait; opacity:.55; }
    button:hover { border-color:var(--accent); }
    #preview { display:none; margin-bottom:18px; border:1px solid var(--line); border-radius:8px; background:var(--panel); overflow:auto; max-height:42vh; }
    #preview.visible { display:block; }
    #preview h2 { margin:0; padding:12px 14px; font-size:15px; border-bottom:1px solid var(--line); }
    #preview details { border-bottom:1px solid var(--line); }
    #preview details:last-child { border-bottom:0; }
    #preview summary { padding:10px 14px; cursor:pointer; color:var(--accent); }
    #preview pre { margin:0; padding:14px; overflow:auto; white-space:pre-wrap; color:var(--text); font:12px/1.45 ui-monospace, monospace; }
    main { display:flex; flex-direction:column; min-height:0; height:calc(100vh - 52px); width:min(100%, 1000px); padding:28px clamp(18px, 5vw, 64px); }
    #transcript { flex:1; min-height:0; overflow:auto; padding:4px 0 24px; }
    .entry { margin:0 0 18px; white-space:pre-wrap; }
    .entry.user { color:var(--accent); }
    .entry.system { color:var(--text); }
    .entry.error { color:#ff9d9d; }
    .entry .tag { display:block; margin-bottom:3px; color:var(--muted); font-size:11px; text-transform:uppercase; letter-spacing:.08em; }
    form { display:flex; gap:10px; border-top:1px solid var(--line); padding-top:18px; }
    textarea { flex:1; min-height:48px; max-height:160px; resize:vertical; border:1px solid var(--line); border-radius:8px; padding:12px; background:var(--panel); color:var(--text); font:inherit; }
    form button { align-self:stretch; background:var(--accent); color:#07111d; border-color:var(--accent); font-weight:700; text-align:center; min-width:82px; }
    @media (max-width:700px) { .file-bar { min-height:52px; } .shell { display:block; height:calc(100vh - 52px); } aside { top:52px; height:auto; max-height:44vh; border-right:0; border-bottom:1px solid var(--line); } .actions { grid-template-columns:repeat(2, 1fr); } main { height:56vh; min-height:56vh; } }
  </style>
</head>
<body>
  <nav class="file-bar" aria-label="Campaign Markdown navigation">
    <strong><a href="/">Campaign terminal</a></strong>
    <div id="file-links" class="file-links">Campaign files: Loading…</div>
  </nav>
  <div class="shell">
    <aside>
      <h1>Campaign Terminal</h1>
      <p class="subtitle">A resumable world</p>
      <div class="label">Status</div><div id="status">Connecting…</div>
      <div class="label">Position</div><div id="position">—</div>
      <div class="label">Quick actions</div>
      <div class="actions">
        <button data-command="/new-game">New game</button>
        <button data-command="/new-character">New character</button>
        <button data-command="/new-party-member">New party member</button>
        <button data-command="/review">Review</button>
        <button data-command="/approve">Approve</button>
        <button data-command="/approve-reset">Approve reset</button>
        <button data-command="/end-day">End day</button>
        <button data-command="/specialists">Specialists</button>
        <button data-command="/retry">Retry</button>
      </div>
    </aside>
    <main>
      <section id="preview" aria-label="Proposed campaign changes"></section>
      <section id="transcript" aria-live="polite"></section>
      <form id="input-form">
        <textarea id="input" placeholder="Describe what you do, or answer the current question…" autofocus></textarea>
        <button type="submit">Send</button>
      </form>
    </main>
  </div>
<script>
  const transcript = document.querySelector('#transcript');
  const input = document.querySelector('#input');
  const statusEl = document.querySelector('#status');
  const positionEl = document.querySelector('#position');
  const fileLinksEl = document.querySelector('#file-links');
  const previewEl = document.querySelector('#preview');

  function addEntry(kind, text) {
    if (!text) return null;
    const entry = document.createElement('div');
    entry.className = `entry ${kind}`;
    const tag = document.createElement('span');
    tag.className = 'tag';
    tag.textContent = kind === 'user' ? 'You' : kind === 'error' ? 'Error' : 'System';
    entry.append(tag, document.createTextNode(text));
    transcript.appendChild(entry);
    transcript.scrollTop = transcript.scrollHeight;
    return entry;
  }

  function setBusy(busy) {
    input.disabled = busy;
    document.querySelectorAll('button').forEach(button => button.disabled = busy);
  }

  function renderPreview(preview) {
    previewEl.replaceChildren();
    if (!Array.isArray(preview) || !preview.length) {
      previewEl.classList.remove('visible');
      return;
    }
    previewEl.classList.add('visible');
    const heading = document.createElement('h2');
    heading.textContent = 'Proposed campaign records — review before approval';
    previewEl.appendChild(heading);
    for (const item of preview) {
      const details = document.createElement('details');
      details.open = true;
      const summary = document.createElement('summary');
      summary.textContent = `${item.action || 'update'}: ${item.target_file}`;
      const pre = document.createElement('pre');
      pre.textContent = item.content || '';
      details.append(summary, pre);
      previewEl.appendChild(details);
    }
  }

  function applyState(data) {
    statusEl.textContent = (data.status || 'unknown').replaceAll('_', ' ');
    const p = data.position || {};
    positionEl.textContent = p.day ? `Day ${p.day} — ${p.phase}` : '—';
    renderPreview(data.preview);
    addEntry(data.error ? 'error' : 'system', data.text || 'Done.');
  }

  async function send(text) {
    text = text.trim();
    if (!text || input.disabled) return;
    input.value = '';
    addEntry('user', text);
    const thinking = addEntry('system', 'The system is thinking…');
    setBusy(true);
    try {
      const response = await fetch('/api/input', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({text}) });
      const data = await response.json();
      if (thinking) thinking.remove();
      applyState(data);
    } catch (error) {
      if (thinking) thinking.remove();
      addEntry('error', 'The frontend could not reach the game server.');
    } finally { setBusy(false); }
  }

  document.querySelector('#input-form').addEventListener('submit', event => { event.preventDefault(); send(input.value); });
  input.addEventListener('keydown', event => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      document.querySelector('#input-form').requestSubmit();
    }
    // Shift+Enter keeps the browser's default textarea behavior: insert a newline.
  });
  document.querySelectorAll('[data-command]').forEach(button => button.addEventListener('click', () => send(button.dataset.command)));
  setBusy(true);
  fetch('/api/state').then(response => response.json()).then(data => applyState(data)).catch(() => addEntry('error', 'The game server is unavailable.')).finally(() => setBusy(false));
  fetch('/api/files').then(response => response.json()).then(data => {
    fileLinksEl.replaceChildren();
    for (const item of data.files || []) {
      const name = typeof item === 'string' ? item : item.name;
      const link = document.createElement('a');
      link.href = `/api/file?name=${encodeURIComponent(name)}`;
      link.title = typeof item === 'string' ? '' : (item.description || '');
      link.textContent = name;
      fileLinksEl.appendChild(link);
    }
    if (!fileLinksEl.children.length) fileLinksEl.textContent = 'No Markdown files found.';
  }).catch(() => { fileLinksEl.textContent = 'Campaign files unavailable.'; });
</script>
</body>
</html>'''


class FrontendService:
    def __init__(self, root: Path, *, auto: bool = True):
        self.pipeline = CampaignPipeline(root)
        self.auto = auto

    @staticmethod
    def _public(result: dict[str, Any]) -> dict[str, Any]:
        """Expose only player-safe state; never send raw proposals or backend data."""
        public: dict[str, Any] = {
            'status': result.get('status', ''),
            'position': result.get('position', {}),
            'text': _player_text(result, include_preview=False),
        }
        preview = result.get('proposal_preview')
        if isinstance(preview, list) and preview:
            public['preview'] = preview
        question = result.get('question')
        if isinstance(question, dict):
            public['question'] = {'question': question.get('question', '')}
        draft = result.get('draft')
        if isinstance(draft, dict):
            characters = draft.get('characters') or []
            public['draft'] = {
                'mode': draft.get('mode'),
                'question': draft.get('question'),
                'characters': [item.get('identity', {}).get('name') for item in characters if isinstance(item, dict)],
            }
        proposals = result.get('specialist_proposals')
        if isinstance(proposals, list):
            public['specialist_proposals'] = [
                {'name': item.get('name'), 'purpose': item.get('purpose')}
                for item in proposals if isinstance(item, dict)
            ]
        return public

    def state(self) -> dict[str, Any]:
        return self._public(_initial_state(self.pipeline, auto=self.auto, start_new_game=True))

    def input(self, text: str) -> dict[str, Any]:
        try:
            return self._public(process_input(self.pipeline, text, auto=self.auto))
        except (ValueError, RuntimeError) as exc:
            return {'status': 'error', 'position': {}, 'text': str(exc), 'error': True}

    def list_files(self) -> list[dict[str, str]]:
        directory = self.pipeline.root / 'markdown_files'
        if not directory.is_dir():
            return []
        names = sorted(
            path.relative_to(directory).as_posix()
            for path in directory.rglob('*.md')
            if path.is_file()
        )
        return [{'name': name, 'description': FILE_DESCRIPTIONS.get(name, 'Campaign Markdown document.')} for name in names]

    def read_file(self, name: str) -> str:
        if not name or Path(name).is_absolute() or '..' in Path(name).parts:
            raise ValueError('Invalid campaign file.')
        directory = (self.pipeline.root / 'markdown_files').resolve()
        path = (directory / Path(name)).resolve()
        try:
            path.relative_to(directory)
        except ValueError as exc:
            raise ValueError('Invalid campaign file.') from exc
        if path.suffix.casefold() != '.md' or not path.is_file():
            raise FileNotFoundError('Campaign file not found.')
        return path.read_text(encoding='utf-8')

    def file_page(self, name: str) -> str:
        content = self.read_file(name)
        links = []
        for item in self.list_files():
            href = '/api/file?name=' + quote(item['name'])
            current = ' aria-current="page"' if item['name'] == name else ''
            links.append(f'<a href="{html.escape(href, quote=True)}"{current}>{html.escape(item["name"])}</a>')
        description = FILE_DESCRIPTIONS.get(name, 'Campaign Markdown document.')
        return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(name)} — Campaign files</title>
<style>
:root {{ color-scheme: dark; --bg:#101318; --panel:#191e27; --text:#edf2f7; --muted:#9ba8b7; --accent:#73b7ff; --line:#303b4a; }}
* {{ box-sizing:border-box; }} body {{ margin:0; background:var(--bg); color:var(--text); font:15px/1.5 system-ui,sans-serif; }}
nav {{ position:sticky; top:0; z-index:2; display:flex; gap:14px; align-items:center; overflow-x:auto; padding:12px 18px; background:var(--panel); border-bottom:1px solid var(--line); white-space:nowrap; }}
nav strong {{ flex:0 0 auto; }} nav a {{ color:var(--accent); text-decoration:none; font-size:13px; }} nav a:hover, nav a[aria-current="page"] {{ text-decoration:underline; }}
main {{ width:min(1100px,100%); margin:0 auto; padding:28px 20px 60px; }} h1 {{ margin:0 0 6px; font-size:25px; }} .description {{ margin:0 0 22px; color:var(--muted); }}
pre {{ margin:0; padding:20px; overflow:auto; border:1px solid var(--line); border-radius:9px; background:var(--panel); white-space:pre-wrap; font:13px/1.55 ui-monospace,SFMono-Regular,Consolas,monospace; }}
</style></head><body>
<nav aria-label="Campaign Markdown navigation"><strong><a href="/" style="color:inherit;text-decoration:none">Campaign terminal</a></strong>{''.join(links)}</nav>
<main><h1>{html.escape(name)}</h1><p class="description">{html.escape(description)}</p><pre>{html.escape(content)}</pre></main>
</body></html>'''


class Handler(BaseHTTPRequestHandler):
    service: FrontendService

    def _send(self, status: int, content_type: str, body: bytes) -> None:
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == '/':
            self._send(HTTPStatus.OK, 'text/html; charset=utf-8', HTML.encode('utf-8'))
        elif path == '/api/state':
            self._send(HTTPStatus.OK, 'application/json; charset=utf-8', json.dumps(self.service.state(), ensure_ascii=False).encode('utf-8'))
        elif path == '/api/files':
            body = json.dumps({'files': self.service.list_files()}, ensure_ascii=False).encode('utf-8')
            self._send(HTTPStatus.OK, 'application/json; charset=utf-8', body)
        elif path == '/api/file':
            from urllib.parse import parse_qs
            name = parse_qs(urlparse(self.path).query).get('name', [''])[0]
            try:
                content = self.service.read_file(name)
            except FileNotFoundError:
                self._send(HTTPStatus.NOT_FOUND, 'text/plain; charset=utf-8', b'Campaign file not found.')
            except ValueError:
                self._send(HTTPStatus.BAD_REQUEST, 'text/plain; charset=utf-8', b'Invalid campaign file.')
            else:
                self._send(HTTPStatus.OK, 'text/html; charset=utf-8', self.service.file_page(name).encode('utf-8'))
        else:
            self._send(HTTPStatus.NOT_FOUND, 'text/plain; charset=utf-8', b'Not found')

    def do_POST(self) -> None:  # noqa: N802
        if urlparse(self.path).path != '/api/input':
            self._send(HTTPStatus.NOT_FOUND, 'text/plain; charset=utf-8', b'Not found')
            return
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if length <= 0 or length > 64 * 1024:
                raise ValueError('Request is empty or too large.')
            payload = json.loads(self.rfile.read(length).decode('utf-8'))
            text = payload.get('text') if isinstance(payload, dict) else None
            if not isinstance(text, str):
                raise ValueError('Input must be text.')
            result = self.service.input(text)
            self._send(HTTPStatus.OK if not result.get('error') else HTTPStatus.BAD_REQUEST,
                       'application/json; charset=utf-8', json.dumps(result, ensure_ascii=False).encode('utf-8'))
        except (ValueError, json.JSONDecodeError) as exc:
            body = json.dumps({'status': 'error', 'text': str(exc), 'error': True}).encode('utf-8')
            self._send(HTTPStatus.BAD_REQUEST, 'application/json; charset=utf-8', body)

    def log_message(self, format: str, *args: object) -> None:
        print(f'[web] {format % args}')


def main() -> None:
    parser = argparse.ArgumentParser(description='Browser frontend for the campaign pipeline')
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8000)
    parser.add_argument('--no-auto', action='store_true', help='disable safe automatic pipeline behavior')
    args = parser.parse_args()

    Handler.service = FrontendService(args.root.resolve(), auto=not args.no_auto)
    # One campaign has one writer. Queue browser requests instead of allowing
    # concurrent clicks to race for the runtime lease.
    server = HTTPServer((args.host, args.port), Handler)
    print(f'Campaign frontend: http://{args.host}:{args.port}/')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nFrontend stopped.')
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
