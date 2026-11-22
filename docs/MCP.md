# Read only Pocket MCP adapter

The official endpoint is `https://public.heypocketai.com/mcp`. Install the optional `mcp` extra. `pocket_mcp.connect()` uses the official Python SDK's Streamable HTTP transport, initializes a session, and reads the key using the same precedence as the REST client. No protocol is reimplemented and no token is persisted by the adapter.

Pocket recommends OAuth when supported by the host MCP client. This Python helper uses an API key; it does not implement OAuth enrollment. If the host already manages an authorized SDK session, wrap it with `PocketMCP(session)`.

The allowlist includes account info, folders, conversation search, action-item search, conversation details, and synthesized meeting queries. Writes are rejected before dispatch. Capability discovery checks advertised tools, not actual plan entitlement; call failures remain explicit. Official docs list conversation details and synthesized meeting queries as Pro-only. Do not silently fall back to broader or less restrictive operations.

`search_action_items(**filters)` forwards structured query/status/priority/category/due/recording-date filters and preserves the response payload. `recent_recordings(**filters)` uses recency mode without a query, follows `data.meta.nextCursor`, and returns collected pages. Missing metadata, repeated cursors, and budget exhaustion are errors. The API may change: unsupported response envelopes are not guessed.

SDK compatibility and adapter behavior are tested offline. The installed SDK version is recorded in the implementation status. Live authentication, tool schemas, plan access, and responses still need a selected account's authorized smoke test.

Source: [Pocket MCP reference](https://docs.heypocketai.com/docs/mcp), inspected 2026-11-22.
