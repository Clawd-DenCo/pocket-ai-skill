# Maintenance roadmap

## Scope

Maintain an attributed OpenClaw integration for Pocket AI, starting from the verified 1.0.1 baseline. Owner: Zandr; repository setup: Clawd. No live account access or ClawHub publication is included in initialization.

## First implementation slice

- Inspect the Python client and shell helper against current official API documentation; document confirmed endpoints and unresolved assumptions.
- Replace direct shell query interpolation with correct JSON serialization; cover quotes, backslashes, newlines, and Unicode with offline tests.
- Review timeout, HTTP-error, response-validation, pagination, and audio-download behavior.
- Support scoped credential loading without leaking bearer tokens in logs or committed files.
- Remove unsupported privacy claims and personal/business examples; require explicit authorization before sending transcript-derived content to other destinations.
- Clarify upstream license notice provenance without inventing attribution.

## Release gates

- Offline tests validate request construction and failure handling without real credentials.
- Documentation matches verified behavior and describes external data flow.
- A separately authorized live smoke test verifies access against a selected Pocket account without committing private responses.
- Installation and ClawHub publication are separate, explicit release steps.

## Initialization proof

All seven upstream package files matched the ClawHub-published SHA-256 digests before local edits. Original code remains unchanged. This is source provenance verification, not functional validation or an independent security review.
