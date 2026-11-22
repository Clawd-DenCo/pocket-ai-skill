# Pocket integration examples

Run these commands with the project environment active and a secret-manager-injected `POCKET_API_KEY`.

## Search within an explicit scope

```bash
pocket-ai search 'project decisions' --limit 20 --folder-id folder-id
pocket-ai search 'follow up' --recording-id recording-id
```

These are bounded relevance matches, not complete task lists. To include legacy profile data explicitly, add `--include-profile`.

## A source linked daily briefing

```bash
pocket-ai briefing --date 2026-11-21 --timezone America/Edmonton
```

Inspect `complete` and `issues`. `recordings[].summary` contains the actual summary and recording reference. `action_items` includes only known TODO/IN_PROGRESS tasks from those summaries. `unknown_status_action_items` stays separate. A missing transcript or unsupported summary schema marks the briefing incomplete.

## Structured task search through MCP

```python
import asyncio
from pocket_mcp import connect

async def run():
    async with connect() as pocket:
        capabilities = await pocket.capabilities()
        tasks = await pocket.search_action_items(status="TODO", priority="HIGH")
        return tasks

# Handle the returned data privately; do not dump transcripts to shared logs.
tasks = asyncio.run(run())
```

The adapter preserves the official structured payload and stable task IDs. It rejects write tools even if the server advertises them. See [MCP details](docs/MCP.md).

## Optional snippet fallback

```python
from pocket_api import PocketAI

with PocketAI() as pocket:
    snippets = pocket.get_action_items("follow-up actions", limit=20)
```

These records include `source: search_snippet`, `status: null`, and `complete: false`. Do not interpret them as open tasks or deduplicate distinct tasks merely because their title matches. The old ASAP keyword heuristic has been removed; use structured priority and due dates instead.
