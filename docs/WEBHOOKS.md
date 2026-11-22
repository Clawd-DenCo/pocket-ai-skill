# Webhook verification and reconciliation utilities

`pocket_webhooks.py` is a library, not a deployed HTTP server. It performs no Pocket requests, stores no transcripts, and does not configure jobs or forward messages.

`verify_event(raw_body, signature, timestamp_ms, secret)` validates HMAC-SHA256 over the exact `timestamp.rawBody` bytes, checks signature shape, enforces a five-minute timestamp freshness window, rejects unsigned events and bodies over 2 MB, and parses JSON only after verification. Provision the signing secret through a secret manager. Legacy unsigned Pocket webhooks must be rotated/recreated rather than accepted silently.

`ReconciliationInbox(path, user_id=..., organization_id=...)` binds one SQLite database to one user/organization. Provision its directory privately (0700); keep it outside Git and backups intended for public sharing. It stores account identifiers, recording IDs, monotonically increasing generations, payload hashes, and receipt times—not payloads, titles, transcripts, signatures, or secrets.

A receiver passes verified deliveries through `receive(...)` before acknowledging them. Exact payload duplicates are suppressed for 24 hours; a retry with a changed payload timestamp may legitimately queue another reconciliation. There is no assumed global event ID or guaranteed ordering. Old delivery hashes are pruned on intake.

Each pending recording is an invalidation, not an instruction to apply the event's state. A separate authorized consumer should:

1. Read `(recording_id, generation)` from `pending()`.
2. Retrieve and persist current authoritative state through a scoped read-only client. Treat auth, rate-limit, and transient errors as failures, never deletions. Only a verified authoritative not-found response may justify a tombstone in the consumer's private cache.
3. Call `acknowledge(recording_id, generation)` only after that persistence succeeds. If another event arrived, the generation guard leaves it pending. The monotonically increasing counter prevents stale acknowledgments from deleting a later generation after an earlier row was cleared.

Deletion/merge/edit events also invalidate the source recording. A production reconciliation consumer must additionally handle merged target IDs according to a verified live payload contract, perform periodic inventory reconciliation to recover missed events, and define retention/deletion policy. Those deployment-specific behaviors are not represented as completed here.

No listener, scheduler, private cache, account access, or external effects are enabled by this library. Production delivery and end-to-end recovery remain unqualified until separately configured and tested.

Source: [Pocket webhooks](https://docs.heypocketai.com/docs/api/webhooks), inspected 2026-11-22.
