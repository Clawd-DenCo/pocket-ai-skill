# Maintenance roadmap

## Completed locally verified candidate

Version 0.2.0 implements the review's code hardening, date-correct retrieval, structured summaries/tasks, read-only MCP adapter, packaging, active documentation, and offline webhook verification/invalidation primitives. See [implementation status](docs/IMPLEMENTATION-STATUS.md) for exact evidence and limits.

## Qualification before operational use

- Authorized live REST/MCP smoke test against a selected account; capture only sanitized response-shape fixtures.
- Confirm real search/tag/summary schemas and account plan/scope behavior.
- Install and verify discovery in the intended OpenClaw runtime if operational use is requested.
- Review live smoke results before making a ClawHub release.

## Optional future deployment

- Deploy a signed webhook receiver only for an authorized destination and account.
- Integrate the metadata inbox with an authoritative-state consumer, merge/deletion handling, periodic missed-event reconciliation, and a private retention policy.
- Add task writes or external forwarding only as separately scoped features, not implicit behavior of retrieval.

The [original review](docs/PROJECT-REVIEW-2026-11-22.md) describes the historical baseline; it is not a list of still-unfixed bugs. The original seven-file source import remains available in commit `5e4fca7` with its published hashes.

## 0.3.0 documented interface expansion

Implemented the documented REST catalog, personal/organization MCP tools, structured task updates with explicit opt-in, CLI access, and local stdio MCP server. See [coverage](docs/API-COVERAGE.md). Authenticated qualification and deployment remain separate.
