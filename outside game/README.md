# Outside-Game Administrative Layer

This is the player's out-of-roleplay conversation channel with the AI DM. A request wrapped in `{...}` is routed as an admin request rather than roleplay.

## Flow

```text
TurnRouter → EvidenceBundleBuilder → SpecialistRunner → admin_agent.py
                                                       ↓
                                             answer or edit proposal
                                                       ↓
                                             player approval
                                                       ↓
                                             admin_editor.py
```

`admin_agent.py` is model-facing and read-only. It answers questions, checks claims against the frozen evidence bundle, and prepares exact Markdown proposals or brain/backend instructions. It never writes campaign files.

`admin_editor.py` is deterministic. It accepts only an approved proposal, uses registered Markdown templates for document creation/filling, allows only exact Markdown changes under `markdown_files/`, checks old text hashes, writes atomically, rejects JSON blobs in campaign documents, and appends an audit entry. Numeric changes remain readable exact line updates such as `Score: 4` to `Score: 5`; descriptions are updated in place rather than duplicated.

`template_renderer.py` expands readable templates and repeatable blocks for characters, relationships, resources, experiments, modifiers, skills, equipment, and nested Modifier Groups. Modifier Group additions require per-placement Admin Agent defense before approval. Templates define structure only; approved evidence supplies facts.

Use `approval.py` to mark a proposal approved; approval does not itself apply the change. Use `admin_editor.py --dry-run` to preview an approved proposal.

The actual campaign state remains under `markdown_files/`. Requests, plans, reports, and audit records belong under this folder. No file here contains credentials.
