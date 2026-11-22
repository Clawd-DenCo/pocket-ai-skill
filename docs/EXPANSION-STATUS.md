# API and MCP expansion status

Version 0.3.0, 2026-11-22. Owner: Zandr.

## Implemented

- Source-backed catalog of all 38 individually published REST routes, including personal retrieval/upload URLs, organization recordings/templates/analytics, users/settings, members, API keys, invitations and webhooks.
- Official MCP adapter expanded to 18 named personal and organization tools, with account capability/input-schema discovery, structured action-item search and explicit task updates.
- Local stdio MCP server with typed structured task-search filters, structured results, REST tools, remote MCP proxies, and daily briefings. No HTTP listener or background service is installed.
- JSON CLI for every cataloged REST operation and official MCP tool. Private output is reserved before network calls; key creation requires a new mode-0600 result file.
- Writes disabled by default, require per-call confirmation, and have no automatic retry. No scope escalation, credential generation or live mutation was performed during development.
- [Coverage matrix and source references](API-COVERAGE.md), [MCP setup](MCP.md), updated skill instructions and package version.

## Direct verification

Implementation and review were direct, not independent; the existing worker-route qualification hold was not changed. No workers or unattended jobs are active.

- 61 tests pass in the project Python 3.12 environment with MCP SDK 1.30.0.
- Every cataloged REST method/path checked against independently transcribed documented route expectations.
- Write controls checked with valid payloads; real loopback HTTP verifies single-attempt mutations and JSON serialization.
- SDK in-memory calls verify structured task results, separate task IDs with duplicate titles, exposed tools and write rejection.
- Actual stdio subprocess initialize/discovery succeeds without credentials or Pocket network calls.
- Existing date, pagination, error, webhook signature and concurrent SQLite tests remain passing.
- Dependency check, CLI entrypoints, wheel build and static skill validation pass.
- GitHub publication/CI result is reported separately after push; local checks are not remote CI proof.

## Remaining limits

Live account authentication, exact service response shapes, role/scope/plan entitlements, OpenClaw skill installation, MCP client configuration and webhook deployment remain unqualified. This is repository implementation, not a production deployment or a ClawHub/package-index release.

Webhook create/update routes lack published request-body schemas; explicit payloads are passed without invented field names. The org MCP documentation says 12 tools but names 11; only the named tools are implemented. Signed storage upload/download transfer and OAuth enrollment are separate from the documented API URL operations. See the coverage guide for details.

Authority boundary: changes are limited to this project and its existing GitHub repository. No private recordings or real Pocket credentials were used. No live account actions, scopes, devices, runtime settings, or webhook destinations were changed.
