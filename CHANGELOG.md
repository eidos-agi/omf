# Changelog

## 0.1.1 — 2026-08-17

First-integration fixes. Every item below came from `kai` attempting a real import against
`0.1.0` and reporting what the spec got wrong, rather than routing around it.

### Fixed

- **The secret detector rejected required content.** `/` sat inside the entropy-scan character
  class, so `com/file/d/<id>/view` fused into one 46-character token and *every* real Drive,
  Docs, and `gdrive://` locator was reported as a credential. A pack describing real files could
  not pass `--strict`. URIs are now masked before the entropy sweep.
- **It also missed real credentials.** `AKIAIOSFODNN7EXAMPLE` — a canonical AWS access key id —
  passed cleanly, being too short for the 40-character gate. Detection is now pattern-first for
  AWS, GitHub PAT/OAuth/fine-grained, Google OAuth and API keys, OpenAI, Slack app, GitLab, and
  JWT shapes, with the length+entropy sweep kept as backstop. Pattern checks run against the
  unmasked text, so a credential in a query string is still caught.

### Clarified in the spec

- **§5.1** — deterministic producer-scoped slug derivation for calendar-less packs
  (conferencing code, else `notes-<starts_at_utc>`); slugs derived from mutable fields are
  non-conforming.
- **§5.2** — grouping is now distinct from identity, with an ordered rule: exact `starts_at_utc`,
  then conferencing code, then stop and emit separate packs. Title similarity is barred at every
  step, including as a tiebreak.
- **§6** — a non-`present` capture slot MUST omit its directory. `examples/minimal/` previously
  shipped an empty `transcript/index.md` alongside `transcript: not_attempted`, which taught
  implementers to write placeholder containers that read as attempted-and-empty. Directory
  removed from the example.
- **§4** — `tree` added to the face table; `source.*` is explicitly open for source-system scoping
  keys such as `drive_parent_id`; an importer building a pack from past evidence MUST write
  `status: held`, never `closed`.

## 0.1.0 — 2026-08-17

Initial OMF scaffold: specification, stdlib validator, fictional valid example, focused negative examples, tests, and CI workflow.
