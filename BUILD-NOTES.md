# OMF build notes

## Prominent human-review decisions / ambiguities

1. **Version acceptance:** OMF requires an `X.Y.Z` `omf_version`, while this repository implements the version in `omf/__init__.py`. The validator accepts any semantic version shape and warns when it differs from that version, matching sibling validator behavior; it does not require an exact patch version.
2. **Calendar source detection:** `source.authority` values containing `calendar` (such as `google_calendar`) are treated as calendar-sourced. They require UID, recurrence-id key, sequence, DTSTAMP, and `invite/original.ics`. A series occurrence additionally needs a non-null recurrence id.
3. **Capture binding:** `capture.<slot>: present` is treated as requiring an `artifacts/*.md` pointer whose `kind` equals that slot. `absent` and `not_attempted` do not require a pointer.
4. **Agent authorship fields:** Agent authorship is read from the semantically specific field first (`decided_by`, `authored_by`, `proposed_by`, then `by` / `verified.by`). This makes the authored-by gate work for both concise and fully-provenanced documents.
5. **Catalogue scope:** A directory without its own meeting face is a catalogue. Every descendant `index.md` whose document is `type: meeting` or `profile: omf` is validated, and duplicate `omf_id` values are compared across those packs. Multiple CLI paths are also compared.
6. **Secret detector:** The detector mirrors OPFF's conservative classes (private-key headers, password/secret/token assignments, bearer tokens, common live token prefixes, password URLs) and adds long high-entropy hex/base64-like token detection. This heuristic intentionally may need tuning as real fixtures reveal false positives.
7. **Trust ladder scope:** Prefix enforcement applies to fields that carry a trust/authority principal: `verified.by`, top-level or attendance `by`, `decided_by`, `owner`, `proposed_by`, and `authored_by`. It deliberately does not constrain `retrieved_as`, which is an external retrieval principal and is exemplified as an email address.
8. **iCalendar validation boundary:** The validator performs a structural VEVENT identity check, not full RFC 5545 parsing. It requires the identity fields and rejects `RRULE` in an occurrence invite, while the series document owns recurrence rules.

## Specification rule coverage

| SPEC rule / location | Enforcement function(s) |
|---|---|
| §4: OKF 0.2, OMF semver, face profile/type/id/title/status/sensitivity | `validate_common`, `validate_face` |
| §4: required start except proposed; UTC-only face times; end not before start | `validate_face`, `_is_utc_timestamp`, `_parse_utc` |
| §4: face source authority and calendar projection identity fields | `validate_face` |
| §4: face `series` key and required verified block | `validate_face` |
| §5: OMF id shape and recurring occurrence `#<recurrence_id>` | `ID_RE`, `validate_face` |
| §5: duplicate imports in a catalogue or across CLI paths | `_meeting_roots`, `_duplicates`, `validate_path`, `main` |
| §6: held/capturing/reconciling/closed capture map with all three enumerated states | `validate_face` |
| §6: `present` capture must have matching pointer artifact | `validate_pack` |
| §6: artifact locator, bytes, kind, retrieval principal | `validate_artifact` |
| §6: raw non-Markdown artifact over 1 MiB | `validate_pack` |
| §6: basic original VEVENT identity and RRULE-free occurrence | `validate_pack` |
| §6: optional segment JSONL has required fields and confidence range | `validate_transcript_segments` |
| §7: RSVP cannot populate attendance; observed attendance requires evidence or human tier | `validate_participant` |
| §8: agent cannot author a binding decision | `validate_outcome` |
| §8: open commitment requires owner; agent-derived commitment requires quote | `validate_outcome` |
| §8: conflict preserves at least two positions; `resolution: null` accepted | `validate_outcome` |
| §9: agent cannot author `type: intent` | `validate_outcome`, `validate_pack` generic-document branch |
| §9: secret-shaped strings anywhere in textual pack files | `secret_problems`, `validate_pack`, `validate_path` |
| §9: wrong-profile `verdict`, `postings`, ORF evidence grades warn | `validate_common`; `--strict` escalation in `validate_pack` / `validate_path` |
| §9: `log.md` has no frontmatter requirement | `validate_pack` explicitly skips frontmatter validation for `log.md` |
| §9: trust ladder prefixes | `_problems_for_trust`, `has_tier` |

The closed-pack commitment gate is enforced by the stronger invariant in `validate_outcome`: **every** `state: open` commitment must have an owner. Therefore a closed pack cannot contain an ownerless open commitment, and the focused negative pack emits one precise `owner` error.

## Rules not fully implementable in a stateless document validator

| Rule | Why / current boundary |
|---|---|
| OMF id immutability across reschedules, title edits, and re-imports | A single working tree has no trusted prior revision or import ledger. The validator checks stable shape, recurrence identity, and duplicate ids; producers/CI must compare the prior committed face or maintain an idempotency map. |
| Reschedule must bump `source.sequence` and append to `log.md` | Detecting a reschedule needs the prior calendar revision. The validator requires the calendar sequence field and checks that `log.md` exists, but cannot infer whether a specific change was a move. |
| Cancellation must be a soft delete with `deleted_at` | File removal cannot be detected without Git history or a prior pack manifest. |
| Distinguishing a knowingly false `absent` from `not_attempted` | This is producer-context knowledge; the validator enforces the three explicit states but cannot know whether a capture system was enabled. |
| Write-once modification of `invite/original.ics` and `transcript/segments.jsonl` | Requires a previous content hash in CI, Git history, or a producer-side append-only store. This validator checks current iCalendar/JSONL structure only. |
| Transcript index must not paraphrase speech | This is a semantic content rule and cannot be determined reliably from frontmatter or text pattern checks. |
| Default exclusion of restricted packs from shared renders | OMF ships no renderer. The face validates the required sensitivity enum; rendering consumers must apply the exclusion policy. |

## Commands executed

All commands were run from `/home/user/workspace/omf` after implementation.

```text
python3 -m omf.validate --selftest
status: 0
output: selftest OK — face gates, UTC times, capture honesty, attendance, outcomes, and secret detection

python3 -m omf.validate --strict examples/minimal
status: 0
output: 15 path(s), 0 with errors

python3 -m omf.validate examples/bad-closed-without-owner
status: 1 (expected)
output: ownerless.md:owner: error: open commitment requires a non-null owner; 3 path(s), 1 with errors

python3 -m omf.validate examples/bad-rsvp-as-attendance
status: 1 (expected)
output: agent-inference.md:attended.observed: error: observed attendance needs evidence or a human: by tier; 3 path(s), 1 with errors

python3 -m unittest discover -s tests -v
status: 0
output: Ran 18 tests; OK
```
