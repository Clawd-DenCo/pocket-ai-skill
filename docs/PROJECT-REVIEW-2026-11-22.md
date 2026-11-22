# Pocket AI Integration project review

Reviewed 2026-11-22 for Zandr. Baseline: [`4fd6b7a`](https://github.com/Clawd-DenCo/pocket-ai-skill/tree/4fd6b7a0a95922d3f1c6b74358b280ab279bec18). Verification was direct, not an independent review.

## Executive assessment

**Keep the fork, but modernize it before installing or automating it.** It is a useful starting point for read-only access to Pocket, not a complete or reliable integration yet. The strongest product direction is an OpenClaw workflow layer over Pocket's supported interfaces: reliable retrieval, source-linked answers, structured action items, and date-correct briefings.

The existing code is small enough to harden without a large rewrite. However, expanding its text-scraping approach would duplicate capabilities that Pocket now exposes through its official MCP server. Evaluate that interface before building a custom task engine.

Twelve offline probes reproduced defects or missing safeguards. These are **baseline defect demonstrations, not passing acceptance tests**. No credentials, user recordings, authenticated API calls, installations, or behavior changes were involved. The report compares the code with current official documentation; it does not establish live account compatibility.

## What the project actually does

`pocket_api.py` provides a `requests.Session` wrapper for four REST operations: search, list tags, list recordings, and get a recording. Higher-level methods turn search results into lists of memories, action-item strings, profile insights, and a four-request briefing. The CLI prints selected results. `search.sh` provides a second search implementation using curl and jq.

Pocket, not this repository, performs audio processing, transcription, indexing, speaker analysis, and summary generation. The skill consumes remote results. It has no local transcription engine, local search index, durable sync state, webhook receiver, task synchronization, or audio-download implementation.

Strengths worth preserving:

- Small, understandable code surface and explicit API destination.
- Python search uses structured JSON serialization and checks HTTP error status.
- A reusable HTTP session and an explicit-key constructor already exist.
- The fork preserves upstream provenance and original files in Git history.

## Confirmed defects and prioritized repairs

Priority meanings: **P1** before operational use; **P2** next hardening slice; **P3** cleanup. Locations refer to the reviewed baseline.

| ID | Priority | Finding and evidence | Recommended repair |
|---|---|---|---|
| B01 | P1 | `search.sh:11–14` interpolates query text directly into JSON. Quotes break the body; crafted text can add fields. Both reproduced. This is JSON injection, not demonstrated shell-command execution. | Use one supported Python CLI, or serialize with jq/Python rather than string concatenation. |
| B02 | P1 | `search.sh:8–14` lacks pipefail, curl HTTP-failure handling, and time bounds. A simulated curl connection failure produces overall exit 0 when the downstream consumer succeeds. `curl -s` also hides transport diagnostics. | Fail fast on missing credentials; propagate HTTP and transport errors; impose time bounds; return meaningful exit codes without sensitive bodies. |
| B03 | P1 | All four Python HTTP calls omit `timeout` (`pocket_api.py:70,152,171,188`). Search omission reproduced with a mock. A stalled dependency can block a briefing or worker indefinitely. | Central request helper with configurable connect/read timeouts and a bounded total retry budget. Retry only eligible transient failures; do not retry authentication failures. |
| B04 | P1 | `get_meeting_summary(date)` only inserts the date into query text (`216–227`). Briefing action items and decisions are unfiltered; CLI prints “Today's Action Items” for an all-time query (`276`). Date behavior reproduced. | Use documented date filters and explicit timezone boundaries. Describe semantic hits as matches, not a complete daily inventory. |
| B05 | P1 | `get_action_items` parses only the exact text `Action item:` and discards everything after a repeated marker (`90–98`). It loses IDs, completion state, due dates, assignees, and recording provenance. Case and truncation defects reproduced. | Prefer structured action-item retrieval. Retain stable IDs and status; keep a clearly labeled snippet fallback only if needed. |
| B06 | P1 | Result handling assumes non-null dictionaries/lists. `data: null` raises TypeError; an application-level error object without data becomes an empty action list. Both reproduced. Other unexpected shapes can also fail. | Validate envelopes and field types. Distinguish no results, unavailable processing, permission errors, and invalid responses. Whether the service actually returns logical errors under HTTP 200 remains unverified. |
| B07 | P2 | `get_memories(limit=20)` never forwards the limit (`118–143`); it merely slices the response. REST search documents a default of 8 and maximum of 20. Negative limits silently remove trailing items; reproduced. | Pass a validated server limit and enforce supported ranges. Explain that relevance search is bounded, not exhaustive. |
| B08 | P2 | `SKILL.md:60–66` points audio retrieval at `/public/recordings/{id}/audio`. Current docs specify `/audio-url` returning a pre-signed URL. There is no Python audio helper. | Correct the documentation and optionally add an explicit two-stage download. Do not send the Pocket bearer token to the storage URL; keep signed URLs out of logs. The old path was not live-tested, so this is a documentation mismatch, not a proven server 404. |
| B09 | P2 | `search.sh` is tracked as mode 100644, while upstream instructions use `./search.sh`; direct execution lacks permission on this checkout. No dependency manifest declares `requests`, curl, or jq. | Prefer a packaged CLI; otherwise document `bash search.sh`, set executable mode where intended, and declare dependencies. |
| B10 | P2 | `examples.md:110–113` lowercases item text but checks uppercase `ASAP`, so “ASAP please” is missed. Reproduced. | Normalize both operands. Prefer explicit due dates and priority fields over urgency keyword guessing. |
| B11 | P2 | `search_contact` promises “all mentions” but returns bounded semantic results. `get_meeting_summary` returns generic search memories, not a verified summary object. | Correct naming and claims; retrieve actual recording summaries and return source references. |
| B12 | P2 | CLI always prints profile insights for a search, echoes the query, and assumes tag keys exist (`250–282`). Empty key files are accepted. No explicit session close/context-manager API exists. | Default to minimal, requested output; make profile output opt-in; add JSON output, defensive rendering, blank-key rejection, and clean resource lifecycle. |

### Documentation and privacy defects

The new fork README warns about upstream claims, but the **active `SKILL.md` still says recordings are end-to-end encrypted and stored on US servers**, and suggests posting decisions to an operations channel. The archived upstream README says no data leaves the user's infrastructure even though the client sends bearer-authenticated queries to Pocket.

Pocket's current product page describes **encryption in transit and at rest** [S8]. That does not establish end-to-end encryption or a universal storage-region guarantee. Replace unsupported claims in the active instructions, not just the repository landing page. Preserve archival originals explicitly as historical evidence.

Treat retrieved transcript content as untrusted source data, not agent instructions. Require a user-authorized destination before forwarding excerpts or inferred decisions. Avoid default profile/mental-state inference and automatic task creation from ambiguous conversation fragments.

The manifest still identifies the upstream repository, support contact, and a $49 one-time product. Those are inherited metadata, not this fork's support or pricing promises. Update fork-specific metadata before release while retaining author credit. The package declares MIT but lacks a standalone license notice; retain the declaration and clarify attribution provenance rather than inventing an upstream copyright statement.

`SKILL.md` has no YAML name/description header. Add standard skill metadata and validate discovery in the target OpenClaw runtime before claiming installability; this review did not test runtime acceptance.

## Current Pocket interfaces and capability gaps

The documented REST base URL and Bearer authentication match the client [S1]. The integration is behind the current interface, not obviously pointed at an entirely obsolete service.

| Area | Current official documentation | Fork gap or opportunity |
|---|---|---|
| REST search | `POST /public/search`; query, limit 1–20 (default 8); filters `dateFrom`, `dateTo`, `folderIds`, `recordingIds` [S2]. Nested filter names are present in the page's embedded schema. | Exposes only query; no filters or server-side limit. |
| Recording inventory | `GET /public/recordings`; `start_date`, `end_date`, `tag_ids`, page, limit up to 100; dates interpreted in UTC [S3]. | Exposes only page/limit; no iterator or date/tag filtering. |
| Recording details | Structured transcript segments, speaker labels/names, timestamps, processing/error fields, and summarizations [S4]. | Raw response only; no normalized transcript/summary accessor or processing-state handling. |
| Audio | `GET /public/recordings/{id}/audio-url`, optional `expires_in`; returns pre-signed S3 URL [S5]. | Stale path in docs, no helper. |
| Tags | List-tags endpoint is documented, but its rendered schema is generic and does not establish the CLI's exact `usage_count` assumption [S6]. | Validate with an authorized sanitized fixture before treating the tag shape as stable. |
| MCP conversations | Official Streamable HTTP endpoint; date/tag/folder filters; query mode returns up to 8 relevant section hits; recency mode has cursor pagination [S7]. | Could replace ad hoc natural-language date handling and support reliable recent-recording retrieval. |
| MCP action items | Structured search with status, priority, category, due-date and recording-date filters; update tool supports selected fields and requires write scope for API keys [S7]. | Far better basis for open-task lists and later authorized task updates than string parsing. |
| MCP authentication and plans | OAuth recommended; API-key headers supported. Search, action-item tools, account info, folders available on all plans; specific full-conversation and synthesized-query tools are Pro-only [S7]. | Add capability detection and clear entitlement errors; do not assume all tools are universally available. |
| Webhooks | Processing and user-edit events, at-least-once delivery, signing headers for current personal webhooks [S9]. | Optional event-driven updates, with deduplication and reconciliation rather than repeated broad searches. |

### Important schema caveat

REST, MCP, and webhook payloads are not interchangeable. REST details show `recording_at` and `transcript.segments`; MCP uses `recordingDate` and `transcriptSegments`; webhooks use `recording.recordingAt` and transcript arrays. Use separate adapters into one internal model.

The current REST search page does not provide a concrete typed success payload sufficient to confirm the legacy `userProfile.dynamicContext` and `relevantMemories` schema. Those fields are **unverified, not proven removed**. Record authorized sanitized fixtures before changing the parser based on assumptions.

## Recommended product direction

### First milestone Reliable read only client

Keep the existing REST client while fixing B01–B07, packaging, and active documentation. Implement a small centralized HTTP layer, explicit configuration, safe error types, date/folder/recording filters, and structured outputs with source IDs and timestamps. Support a secret-store-injected environment variable plus explicit constructor value; keep the legacy file as a documented fallback if needed.

Acceptance: offline tests cover quotes, Unicode, newlines, transport failures, HTTP 401/403/429/5xx, invalid JSON, null data, processing-incomplete responses, pagination, date boundaries, and result limits. Errors must not look like empty results or leak tokens/transcripts. Tests should assert corrected behavior, replacing these defect probes as appropriate.

### Second milestone Source linked briefings and structured tasks

Evaluate the official MCP server for action items and conversation retrieval before adding more custom REST code. Keep the skill focused on OpenClaw workflows and permission boundaries; retain REST for deterministic scripts and explicitly supported exports.

A useful briefing should include the selected interval, source recording IDs, relevant timestamps, open/completed status, and an indication of incomplete retrieval. Distinguish conversation time from upload time: delayed device sync must not move yesterday's meeting into today's conversation history.

For local-day reporting, construct timezone-aware day boundaries, convert them to UTC, and test daylight-saving transitions. REST listing's day-level UTC filters may require fetching a wider range and post-filtering `recording_at` precisely. Do not interpret the word “today” in a search string as a time filter.

Acceptance: reconcile a synthetic day's full recording inventory with the output; verify that completed tasks are excluded from open-task views; preserve separate tasks with the same title but different IDs; provide citations for extracted decisions. A user-authorized live smoke test then verifies the actual account's scopes, plan, and response shapes.

### Third milestone Optional incremental sync

Only after reliable read-only retrieval, consider webhook ingestion for `summary.completed`, edits, action-item changes, merges, and deletions [S9]. Validate HMAC over the raw body, validate signature length/encoding safely, enforce a timestamp freshness window, and reject unsigned legacy deliveries unless separately approved. Expect duplicates and out-of-order delivery. Deduplicate by stable resource/version information and reconcile periodically through supported retrieval.

Do not assume a universal event ID or ordering guarantee; the documented payload does not establish either. Track conversation timestamp, update timestamp, and delivery timestamp separately. Persist the minimum needed data and propagate deletions. Optional writes to Pocket or other task systems should remain separate from read-only retrieval and require appropriate user authority and scopes.

## Verification and unresolved questions

Run the baseline reproduction suite from the repository root:

```bash
python3 docs/review/reproduce_findings.py
```

The captured [baseline results](review/baseline-results.json) show 12 reproduced observations. The harness replaces HTTP calls and shell network operations with mocks; its key and records are synthetic. It uses the existing Python requests dependency and does not install packages. The application source is unchanged.

Before release, resolve:

- Real REST search success shape and availability of legacy profile fields.
- Exact tag payload shape and any plan-specific REST constraints.
- Account scopes and whether OAuth or a read-only API key is the intended integration route.
- Operational rate limits and retry headers; 429 is documented, but no universal numerical rate limit was established here.
- Actual OpenClaw skill discovery and MCP connectivity, neither tested in this review.
- Which requested workflows justify transcript retention or external task writes.

The user's description of the original project as abandoned is not independently verified. An inaccessible linked repository is evidence of source availability problems, not proof of maintenance intent.

## Sources

Official documentation inspected 2026-11-22. These document supported interfaces; authenticated behavior remains to be tested.

- **S1** [Pocket API reference](https://docs.heypocketai.com/docs/api)
- **S2** [Search recordings](https://docs.heypocketai.com/docs/api/search/search-recordings)
- **S3** [List recordings](https://docs.heypocketai.com/docs/api/recordings/list-recordings)
- **S4** [Recording details](https://docs.heypocketai.com/docs/api/recordings/get-recording-details)
- **S5** [Audio download URL](https://docs.heypocketai.com/docs/api/recordings/get-audio-download-url)
- **S6** [List tags](https://docs.heypocketai.com/docs/api/tags/list-tags)
- **S7** [Pocket MCP server and tool reference](https://docs.heypocketai.com/docs/mcp)
- **S8** [Pocket product site](https://heypocket.com/), encryption wording only; marketing claims are not independent security assurance.
- **S9** [Pocket webhooks](https://docs.heypocketai.com/docs/api/webhooks)
- [Official documentation index](https://docs.heypocketai.com/llms.txt)
- [Upstream package](https://clawhub.ai/asabovetech/skills/pocket-ai)
