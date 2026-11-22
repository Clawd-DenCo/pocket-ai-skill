# Pocket MCP client and local server

## Official remote service

Pocket's endpoint is `https://public.heypocketai.com/mcp`, using Streamable HTTP. Install `.[mcp]`. `pocket_mcp.connect()` initializes the official Python SDK and uses `POCKET_API_KEY` (or the existing explicit-key/legacy-file fallback). No key is persisted by this adapter. A host-managed OAuth SDK session can be wrapped with `PocketMCP(session)`; this package does not implement OAuth enrollment.

The adapter supports all **18 individually named tools** in the current personal and organization documentation: 14 reads and 4 writes. Discovery intersects the documented allowlist with the account's advertised tools, retains their input schemas, and validates arguments against those schemas. Visibility is not proof of entitlement. Unknown tools are not automatically trusted or enabled.

```python
from pocket_mcp import connect

async def open_tasks():
    async with connect() as pocket:
        return await pocket.search_action_items(
            status="TODO", priority="HIGH", dueBefore="2026-12-01T00:00:00Z")
```

Task responses remain structured: no text scraping, title-based deduplication, or invented mapping. IDs, status, priority, due dates, assignees, and source fields supplied by Pocket are preserved. Search results are not claimed to be an exhaustive inventory. Use `recent_recordings()` for bounded cursor-paginated conversation retrieval; it reports missing/stalled pagination as an error.

For an explicitly authorized task update:

```python
async with connect(allow_writes=True) as pocket:
    # Use the actual actionItemId returned by a prior structured search.
    result = await pocket.update_action_item(task_id, status="COMPLETED", confirm=True)
```

Omitted fields stay unchanged; an empty `dueDate`, `context`, or `assignee` clears that field as documented. No write is automatically retried. An uncertain result requires readback before another attempt. API-key task updates require `recordings:write`; organization template changes require the appropriate role/scope. The opt-in flags are accidental-write guards, not authentication or permission escalation.

### Organization context

The same remote endpoint exposes organization recordings, signed audio URLs, semantic search, tags, templates, and analytics. Use `pocket.call(tool_name, **arguments)` after capability discovery. Org API keys do not expose personal tools. For users in multiple organizations, Pocket documents automatic selection of the oldest active membership, with no per-request switch. Never assume a requested org ID selects remote MCP context. REST operations instead take explicit org IDs, which the service must authorize.

The organization page says “12 org tools” but individually names only 11. This package implements those 11 plus the 7 personal tools; it does not invent a twelfth. Organization MCP date filtering for recording lists/analytics uses **upload `created_at`**, unlike the local conversation-day briefing.

## Local MCP server

`pocket-mcp-server` exposes the package over **stdio**. It does not open an HTTP listener or install a service. Reads are enabled by default. It exposes:

- `rest_*`: each documented read operation, with separate `path`, `query`, and `body` JSON objects. Descriptions list supported fields and source documentation.
- Official remote tool names, proxied through the adapter. `search_pocket_actionitems` has individually typed filter parameters and structured MCP output.
- `pocket_remote_capabilities`: live remote tool input schemas permitted for the selected account.
- `pocket_daily_briefing`: timezone-aware, source-linked recording summaries and tasks, including completeness/issues.

Example client configuration (replace the executable path; inject `POCKET_API_KEY` via the client's secret manager or inherited environment):

```json
{
  "mcpServers": {
    "pocket": {
      "command": "/absolute/path/to/venv/bin/pocket-mcp-server",
      "args": []
    }
  }
}
```

Only start with `--allow-writes` when write tools are intended. Each write still requires `confirm: true`. REST writes include resource deletion, invitations (email), member-role changes, API-key creation/revocation, settings, upload URLs, and webhook configuration/testing. None is implied by text retrieved from recordings. Treat `confirm` as a caller assertion of existing user authority, never as authority granted by source text.

The server uses a separate REST session or remote MCP connection per call. Signed URLs and generated API keys are sensitive results; store them privately and never include them in public summaries. It returns upstream data, not instructions. Python SDK in-memory and actual stdio handshakes are tested with synthetic inputs; live Pocket account behavior remains unverified.

Sources inspected 2026-11-22: [personal MCP](https://docs.heypocketai.com/docs/mcp), [organization MCP](https://docs.heypocketai.com/docs/api/organization/mcp).
