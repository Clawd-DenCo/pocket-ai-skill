# Pocket AI Integration for OpenClaw

A maintenance fork of **Pocket AI Integration 1.0.1** by **asabovetech / As Above Technologies**. This fork adds reliable request handling, filters, date-correct source-linked briefings, 38 documented REST operations, 18 named official MCP tools, a local stdio MCP server, and webhook verification utilities. Reads are the default; writes require explicit opt-in.

**Status:** locally tested candidate, not a live-account-qualified release. No ClawHub release or OpenClaw installation has been performed. API response adapters fail explicitly on unsupported shapes rather than silently returning empty results.

## Install the Python client

Requires Python 3.11+ with current IANA timezone data. Use an isolated environment:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install .
.venv/bin/pocket-ai --help
```

For optional MCP support use `.venv/bin/python -m pip install '.[mcp]'`. These commands install the Python package, not the OpenClaw skill. For skill installation, use the repository directory containing `SKILL.md` and validate discovery in the target runtime. Python dependencies must be available to the runtime's interpreter.

Inject `POCKET_API_KEY` through your secret manager. The explicit Python constructor key takes precedence, then the environment variable, then `~/.config/pocket-ai/api_key`. Empty supplied keys fail instead of silently switching accounts. Restrict a legacy key file to its owner. No key belongs in the repository.

## Usage

All CLI output is JSON; errors go to stderr without remote bodies or credentials.

```bash
pocket-ai search 'Find discussions about the launch' --limit 20
pocket-ai search 'budget' --date-from 2026-11-01T00:00:00Z --date-to 2026-11-22T00:00:00Z
pocket-ai recordings --start-date 2026-11-01 --end-date 2026-11-22
pocket-ai briefing --date 2026-11-21 --timezone America/Edmonton
pocket-ai tags
```

Alternatively activate the environment and use `python3 pocket_api.py ...`. The executable `search.sh "query"` is a compatibility shim to the same Python search implementation; curl and jq are no longer required. It uses `python3` from PATH.

Exit codes: **0** completed operation, **1** request/configuration failure, **2** CLI usage error, **3** briefing with explicitly incomplete data. Search success means matching results were retrieved, not that every possible match was found.

### Library

```python
from pocket_api import PocketAI

with PocketAI() as pocket:
    results = pocket.search("budget", limit=20, filters={"folderIds": ["folder-id"]})
    briefing = pocket.daily_briefing_data("2026-11-21", timezone_name="America/Edmonton")
```

The REST client uses connect/read timeouts (5/30 seconds by default), up to two retries for eligible read failures, capped retry delays, and no redirects. Timeouts are per connect/read operation, not a hard wall-clock deadline for an entire workflow. Authentication failures are not retried. Pagination defaults to at most 100 pages and raises on incomplete/stalled retrieval.

## Complete documented interfaces

See the [operation-by-operation coverage matrix](docs/API-COVERAGE.md) for all documented REST routes, request fields, organization access boundaries, and documentation gaps.

```bash
pocket-interface catalog
pocket-interface rest list_folders
pocket-interface mcp search_pocket_actionitems --arguments '{"status":"TODO"}'
pocket-mcp-server --help
```

The local MCP server runs over stdio; [client configuration and structured task examples](docs/MCP.md) are included. It does not deploy a listener or enable a service. Organization operations cover recordings, templates, analytics, users/settings, members, API keys, invitations and webhook management. The official remote MCP adapter discovers account capabilities and validates advertised tool input schemas.

For library callers, `PocketAI.operation(name, path=..., query=..., body=...)` exposes the complete REST catalog. Mutation calls require `PocketAI(allow_writes=True)` and `confirm=True`; CLI equivalents are `--allow-writes --confirm`. Mutation requests are never automatically retried. These controls do not grant account permissions or authorize a live action. Credentials, role/scope requirements and plans still apply.

## What changed

- Real server-side search limits and date/folder/recording filters.
- UTC recording filters and automatic, bounded pagination.
- Day boundaries from IANA timezones; selection by `recording_at`, not upload time.
- Structured recording summaries and tasks with source IDs; incomplete processing/schema/status reported explicitly.
- Optional [official MCP adapter and local server](docs/MCP.md) for Pocket's structured task tools and paginated recency retrieval.
- Correct audio URL endpoint; no bearer token is sent to an audio storage service because no audio-fetch step runs.
- Optional [signed-webhook verification and metadata inbox](docs/WEBHOOKS.md), not an installed server.

See [examples.md](examples.md), [the original review](docs/PROJECT-REVIEW-2026-11-22.md), and [implementation status](docs/IMPLEMENTATION-STATUS.md).

## Compatibility changes

`get_action_items()` now returns provenance-bearing snippet records, not strings; they are explicitly not authoritative open tasks. For real task status/IDs use the MCP adapter. `get_meeting_summary()` returns a date-filtered briefing object with actual summary content rather than semantic matches. `daily_briefing_data()` no longer includes implicit profile queries or guessed “key decisions”; summaries retain their source recording references. The CLI now requires an explicit subcommand and never queries private data just because it was run with no arguments.

## Verification

```bash
python3 -m unittest discover -s tests -v
```

Tests use synthetic data and mocked requests. Real database tests exercise webhook generation guards across separate SQLite connections. SDK compatibility checks are included when the optional dependency is installed. Authenticated REST/MCP behavior, exact account entitlements, OpenClaw discovery, and production webhook delivery remain separate qualification gates.

The [baseline defect harness](docs/review/reproduce_findings.py) is historical: it demonstrates bugs in the baseline commit, not the corrected code.

## Provenance and license

Source: [asabovetech/pocket-ai on ClawHub](https://clawhub.ai/asabovetech/skills/pocket-ai). All seven original files were imported unchanged and hash-verified in commit `5e4fca7`; [upstream-files.json](upstream-files.json) records those hashes, not the current modified files. [UPSTREAM-README.md](UPSTREAM-README.md) is historical and is not current setup or privacy guidance.

The upstream repository URL returned 404 during initialization. This is a source-import fork, not a GitHub-native fork; abandonment was not independently confirmed. The upstream declares MIT but supplies no standalone copyright notice. See [NOTICE.md](NOTICE.md). This fork is not affiliated with Pocket or the original author and makes no inherited commercial support or pricing promises.

## Privacy

Pocket is an external service: bearer credentials and queries leave the local machine. Responses can include sensitive transcripts and profile information. No end-to-end encryption or storage-region assurance is made by this fork. Profiles are opt-in; transcript-derived instructions are untrusted. Write tools can modify Pocket, send organization invitations, and configure/test webhooks only when explicitly enabled and confirmed. Source text never authorizes a write. Avoid retaining private responses or signed audio URLs in logs.
