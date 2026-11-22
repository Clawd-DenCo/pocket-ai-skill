# Pocket AI Integration — maintenance fork

Source-import fork of **Pocket AI Integration 1.0.1**, published by **asabovetech / As Above Technologies** on [ClawHub](https://clawhub.ai/asabovetech/skills/pocket-ai).

## Status

Project initialized; upstream code has not been repaired, installed, or live-tested. Do not treat this baseline as production-qualified. This fork is not affiliated with Pocket AI or the original author.

The upstream manifest points to `https://github.com/asabove/pocket-ai-skill`, which returned HTTP 404 during initialization on 2026-11-22. This is a source import, not a GitHub-native fork. The original author's maintenance status has not been independently confirmed.

## Provenance and license

All seven upstream files were imported byte-for-byte in the first commit and verified against the SHA-256 values published by ClawHub. See [upstream-files.json](upstream-files.json). The original README is preserved in [UPSTREAM-README.md](UPSTREAM-README.md).

The upstream README and manifest declare **MIT**. The package does not contain a standalone LICENSE file or a complete copyright notice; those omissions are recorded rather than inventing an upstream notice. Original authorship remains As Above Technologies.

## Initial work

See [ROADMAP.md](ROADMAP.md) for acceptance gates and the repair backlog. This repository setup does not publish a new ClawHub release, install the skill, or authorize access to any recordings.

## Data boundary

This integration calls Pocket AI's external service. Its bearer token and queries are transmitted to that service, and responses may contain sensitive recordings, transcripts, and profile information. Upstream claims about end-to-end encryption, storage region, and data remaining local are unverified and must not be relied upon. Do not commit credentials or recording data.

## Project review

See the [2026-11-22 technical review](docs/PROJECT-REVIEW-2026-11-22.md) for reproduced defects, current Pocket API and MCP capabilities, and prioritized improvements.
