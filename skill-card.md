# Pocket AI Integration Maintenance Fork

Read-only-by-default retrieval and source-linked briefings for Pocket recordings. Maintainer: Clawd-DenCo. Original author: As Above Technologies (`asabovetech`).

Version: 0.3.0 candidate. License provenance: [NOTICE.md](NOTICE.md).

Local regression and packaging checks do not establish live API compatibility. See [expansion status](docs/EXPANSION-STATUS.md) for qualification and remaining gates.

Queries and bearer credentials are sent to Pocket. Retrieved content may be sensitive. No automatic task writes, forwarding, live webhook deployment, or profile inference are enabled. See [SKILL.md](SKILL.md) for operating boundaries.

Version 0.3.0 expands documented REST and official MCP coverage, with a local stdio MCP server. Mutations are disabled by default and require per-call confirmation. See [API coverage](docs/API-COVERAGE.md).
