# Pocket interface coverage

Version 0.3.0, documentation inspected 2026-11-22. Coverage means callable repository interfaces with synthetic verification, **not authenticated service qualification**. All 38 routes individually published by the Pocket API reference and linked organization/webhook pages are represented below. Device UI features, billing and undocumented endpoints are not invented.

## REST usage

Use `PocketAI.operation(name, path={}, query={}, body={})` or `pocket-interface rest NAME`. Existing convenience methods and the original `pocket-ai` CLI remain available. `pocket-interface catalog` lists methods, routes, fields, required fields and documentation sources without credentials.

```bash
pocket-interface rest list_folders
pocket-interface rest get_recording --path '{"recording_id":"recording-id"}' --query '{"include_transcript":true,"include_summarizations":false}'
pocket-interface rest get_org_analytics --path '{"org_id":"org-id"}' --query '{"start_date":"2026-11-01","end_date":"2026-11-22"}'
pocket-interface mcp search_pocket_actionitems --arguments '{"status":"TODO","priority":"HIGH"}'
pocket-interface mcp capabilities
```

Arguments accept JSON objects or `@file`. Use private files for sensitive request bodies rather than shell arguments. Results default to JSON stdout; `--output FILE` creates a new mode-0600 file before sending any request. API-key creation requires that private output. Existing files are never overwritten.

Writes require both constructor/CLI `allow_writes` and per-call `confirm` (`--allow-writes --confirm`). They are sent exactly once with no automatic retries, including on 429, 5xx, timeouts or connection failures. Reconcile unknown effects before retrying. Read failures retain bounded retries. Redirects are refused. Service errors do not include remote bodies.

Organization responses are preserved rather than forced into the personal `data` envelope. Success-only and empty 204 mutation responses are supported. Catalog dispatch returns one page; pass the documented page/cursor for the next page and inspect returned pagination. Existing personal `iter_recordings` and MCP `recent_recordings` provide bounded iteration.

## Documented REST operation inventory

| Operation | Method and path relative to `/api/v1` | Access | Source |
|---|---|---|---|
| `search` | `POST /public/search` | read | [docs](https://docs.heypocketai.com/docs/api/search/search-recordings) |
| `list_recordings` | `GET /public/recordings` | read | [docs](https://docs.heypocketai.com/docs/api/recordings/list-recordings) |
| `get_recording` | `GET /public/recordings/{recording_id}` | read | [docs](https://docs.heypocketai.com/docs/api/recordings/get-recording-details) |
| `get_audio_url` | `GET /public/recordings/{recording_id}/audio-url` | read | [docs](https://docs.heypocketai.com/docs/api/recordings/get-audio-download-url) |
| `create_upload_url` | `POST /public/recordings/upload-url` | write opt-in | [docs](https://docs.heypocketai.com/docs/api/recordings/create-upload-url) |
| `list_folders` | `GET /public/folders` | read | [docs](https://docs.heypocketai.com/docs/api/folders/list-folders-and-spaces) |
| `list_tags` | `GET /public/tags` | read | [docs](https://docs.heypocketai.com/docs/api/tags/list-tags) |
| `list_users` | `GET /public/users` | read | [docs](https://docs.heypocketai.com/docs/api/users/list-organization-users) |
| `get_user_settings` | `GET /public/users/{user_id}/settings` | read | [docs](https://docs.heypocketai.com/docs/api/users/get-an-organization-member-s-settings-bundle) |
| `update_user_settings` | `PATCH /public/users/{user_id}/settings` | write opt-in | [docs](https://docs.heypocketai.com/docs/api/organization/users) |
| `list_org_api_keys` | `GET /organization/{org_id}/api-keys` | read | [docs](https://docs.heypocketai.com/docs/api/organization/api-keys) |
| `get_org_api_key` | `GET /organization/{org_id}/api-keys/{key_id}` | read | [docs](https://docs.heypocketai.com/docs/api/organization/api-keys) |
| `create_org_api_key` | `POST /organization/{org_id}/api-keys` | write opt-in | [docs](https://docs.heypocketai.com/docs/api/organization/api-keys) |
| `delete_org_api_key` | `DELETE /organization/{org_id}/api-keys/{key_id}` | write opt-in | [docs](https://docs.heypocketai.com/docs/api/organization/api-keys) |
| `list_org_templates` | `GET /organization/{org_id}/templates` | read | [docs](https://docs.heypocketai.com/docs/api/organization/templates) |
| `get_org_template` | `GET /organization/{org_id}/templates/{template_id}` | read | [docs](https://docs.heypocketai.com/docs/api/organization/templates) |
| `create_org_template` | `POST /organization/{org_id}/templates` | write opt-in | [docs](https://docs.heypocketai.com/docs/api/organization/templates) |
| `delete_org_template` | `DELETE /organization/{org_id}/templates/{template_id}` | write opt-in | [docs](https://docs.heypocketai.com/docs/api/organization/templates) |
| `update_org_template` | `PATCH /organization/{org_id}/templates/{template_id}` | write opt-in | [docs](https://docs.heypocketai.com/docs/api/organization/templates) |
| `get_org_analytics` | `GET /organization/{org_id}/analytics` | read | [docs](https://docs.heypocketai.com/docs/api/organization/analytics) |
| `list_org_recordings` | `GET /organization/{org_id}/recordings` | read | [docs](https://docs.heypocketai.com/docs/api/organization/recordings) |
| `get_org_recording` | `GET /organization/{org_id}/recordings/{recording_id}` | read | [docs](https://docs.heypocketai.com/docs/api/organization/recordings) |
| `update_org_recording` | `PUT /organization/{org_id}/recordings/{recording_id}` | write opt-in | [docs](https://docs.heypocketai.com/docs/api/organization/recordings) |
| `delete_org_recording` | `DELETE /organization/{org_id}/recordings/{recording_id}` | write opt-in | [docs](https://docs.heypocketai.com/docs/api/organization/recordings) |
| `update_org_member` | `PATCH /organization/{org_id}/members/{user_id}` | write opt-in | [docs](https://docs.heypocketai.com/docs/api/organization/members) |
| `list_org_users` | `GET /organization/{org_id}/users` | read | [docs](https://docs.heypocketai.com/docs/api/organization/users) |
| `get_org_user_settings` | `GET /organization/{org_id}/users/{user_id}/settings` | read | [docs](https://docs.heypocketai.com/docs/api/organization/users) |
| `update_org_user_settings` | `PATCH /organization/{org_id}/users/{user_id}/settings` | write opt-in | [docs](https://docs.heypocketai.com/docs/api/organization/users) |
| `send_org_invite` | `POST /organization/{org_id}/invites` | write opt-in | [docs](https://docs.heypocketai.com/docs/api/organization/invites) |
| `accept_org_invite` | `POST /organization/invites/accept` | write opt-in | [docs](https://docs.heypocketai.com/docs/api/organization/invites) |
| `revoke_org_invite` | `DELETE /organization/{org_id}/invites/{invite_id}` | write opt-in | [docs](https://docs.heypocketai.com/docs/api/organization/invites) |
| `resend_org_invite` | `POST /organization/{org_id}/invites/{invite_id}/resend` | write opt-in | [docs](https://docs.heypocketai.com/docs/api/organization/invites) |
| `list_org_webhooks` | `GET /organization/{org_id}/webhooks` | read | [docs](https://docs.heypocketai.com/docs/api/webhooks) |
| `get_org_webhook` | `GET /organization/{org_id}/webhooks/{webhook_id}` | read | [docs](https://docs.heypocketai.com/docs/api/webhooks) |
| `create_org_webhook` | `POST /organization/{org_id}/webhooks` | write opt-in | [docs](https://docs.heypocketai.com/docs/api/webhooks) |
| `update_org_webhook` | `PUT /organization/{org_id}/webhooks/{webhook_id}` | write opt-in | [docs](https://docs.heypocketai.com/docs/api/webhooks) |
| `delete_org_webhook` | `DELETE /organization/{org_id}/webhooks/{webhook_id}` | write opt-in | [docs](https://docs.heypocketai.com/docs/api/webhooks) |
| `test_org_webhook` | `POST /organization/{org_id}/webhooks/{webhook_id}/test` | write opt-in | [docs](https://docs.heypocketai.com/docs/api/webhooks) |

## Details and limits

- Public upload creates a signed upload URL with optional `content_type`, `duration`, `file_name`, `recording_at`, `title`; it requires a user key with `recordings:write`. Org keys are not supported for this route. This package does not automatically upload a local file or fetch signed audio URLs. Storage transfer is separate from API coverage.
- Public audio URLs support `expires_in` from 60 to 86400 seconds. Recording detail filters include `include_transcript`, `include_summarizations`, and `summarization_id`.
- Organization users/settings require org credentials and matching `users:read`/`users:write` scopes. Personal keys are rejected by Pocket. Settings/profile/preferences field-level validation and permission checks remain server-owned. Sensitive optional sections must be explicitly requested.
- Creating an API key requires an explicit nonempty scope list in this client even though the service defaults omitted scopes to all scopes. Key values are returned once. No scope escalation occurs automatically.
- Recording deletion supports `permanent=true`; callers must obtain explicit authority for permanent deletion. Template updates replace supplied sections; setting member role/status may change access. Invitations and webhook tests cause external effects.
- Webhook docs specify six management routes but do not publish create/update body schemas. Those two operations accept an explicit JSON object without inventing field names. Their payload compatibility is unqualified until verified with service documentation or an authorized account. No listener or recurring reconciliation is deployed.
- REST/org/MCP/webhook schemas differ. Responses are retained as delivered; only the existing recording adapter normalizes its recognized summary schema. No fabricated cross-interface task schema is assumed.
- API-key roles/scopes, plan entitlement, exact payload shapes and actual service effects require a selected account's authorized smoke tests. The same credential resolver accepts an explicit bearer token for documented Firebase-authenticated routes; this package does not mint/refresh Firebase tokens or implement OAuth login.

## Official MCP tools

The adapter and local server support these individually documented tools after live capability discovery. See [MCP setup and authority boundaries](MCP.md).

- `create_org_template` — write opt-in
- `delete_org_template` — write opt-in
- `get_account_info` — read
- `get_org_analytics` — read
- `get_org_recording` — read
- `get_org_recording_audio_url` — read
- `get_org_template` — read
- `get_pocket_conversation` — read
- `list_org_recordings` — read
- `list_org_tags` — read
- `list_org_templates` — read
- `list_pocket_folders` — read
- `query_pocket_meetings` — read
- `search_org_recordings` — read
- `search_pocket_actionitems` — read
- `search_pocket_conversations` — read
- `update_org_template` — write opt-in
- `update_pocket_actionitem` — write opt-in

Sources: [documentation index](https://docs.heypocketai.com/llms.txt), [personal MCP](https://docs.heypocketai.com/docs/mcp), [organization MCP](https://docs.heypocketai.com/docs/api/organization/mcp). The org page claims 12 tools but names 11; coverage is based on names, not that inconsistent total.
