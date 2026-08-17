# OMF v0.1.1 — Open Meeting Format

**An additive profile of [OKF v0.2](https://github.com/eidos-agi/okflify).** Every OMF document
is a valid OKF document. Renderers that know only OKF display it correctly and ignore profile
keys; `okflify` needs no changes.

If a requirement conflicts with OKF v0.2, **OKF wins for base structure**. OMF only adds
required frontmatter, pack layout conventions, and meeting gates.

Read **[INTENTION.md](INTENTION.md)** first — including the **invite-class vs record-class vs
outcome-class** split.

OMF is the OKF face for **one meeting occurrence**: what was scheduled, who was actually there,
what was said, what was decided, and who owes what. It is not durable org memory (EMF), not an
investigation (ORF), and not a task tracker (Linear / docket.md).

```yaml
---
okf_version: "0.2"
omf_version: "0.1.1"
profile: omf
type: meeting
omf_id: omf:founders:20260701T180411Z-1a2b3c@eidosagi.com#2026-07-06T02:00:00Z
title: "Founder call — two founders"
status: closed
sensitivity: internal
starts_at_utc: 2026-07-06T02:00:00Z
ends_at_utc: 2026-07-06T03:00:00Z
series: series/founder-weekly.md      # null for one-off meetings
source:
  authority: google_calendar
  icalendar_uid: 20260701T180411Z-1a2b3c@eidosagi.com
  recurrence_id: 2026-07-06T02:00:00Z  # null when this pack IS the series
  sequence: 3
  dtstamp: 2026-07-01T18:04:11Z
capture:
  recording: present                   # present | absent | not_attempted
  transcript: not_attempted            # ← honest: Admin never enabled it
  notes: present
imports: []
policy: []          # optional emf:<pack>:<object>@<rev>
research: []        # optional orf:<pack>:<object>@<rev>
non_goals: ["task state of record", "speaker sentiment scoring", "CRM writes"]
verified:
  by: human:daniel
  at: 2026-08-17
  method: "reconciled Calendar VEVENT against Drive artifacts; attendance confirmed from recording"
  stale_after: 2027-08-17
---
```

---

## 1. Why OMF exists (measured failures)

Each addition exists because a failure was felt or measured — same discipline as EMF and ORF.

| Failure | Therefore |
|---------|-----------|
| A Gemini notes Doc existed with no recording beside it; agents reported "import failed" | **Independently nullable capture slots** — a missing artifact is a state, not an error |
| Drive held zero transcripts, and agents wrote `transcript: []` as if empty | **`not_attempted` ≠ `absent` ≠ `present`** — never conflate "never captured" with "captured nothing" |
| A 341 MB Meet mp4 was a candidate for the record body | **Artifacts are pointers with `bytes`** — media never enters the pack |
| Recording titled by Meet code + `GMT`; notes titled with local `CDT`; nothing joined them | **Normalized `starts_at_utc` is the join key**, and `source.*` is preserved verbatim |
| Weekly founder call: 52 near-identical packs, or one pack that overwrote itself | **Occurrence is the unit; `series` is a separate document** |
| A reschedule minted a second meeting | **`omf_id` is immutable**; a move bumps `source.sequence` |
| RSVP `ACCEPTED` was reported as "attended" | **`invited` and `attended` are separate fields with separate provenance** |
| kai's `kind: conference` chat card became the system of record | **Cards and LiveViews are projections**; the pack is authority |
| A meeting produced four commitments and no owners | **Close gate**: cannot reach `status: closed` with an ownerless open commitment |
| An agent summarized a hedge into a decision | **Agents MUST NOT author binding `decision`** |
| Two sources disagreed and the later import won | **`conflicts/` keeps both**; no overwrite |
| A recording contained a spoken API key, then went into a shared bundle | **`sensitivity` is required**; `restricted` packs are excluded from shared renders |

---

## 2. Relationship to siblings

```
OKF v0.2
├── EMF    — intent / policy / durable memory
├── ORF    — research / investigation packs
├── ODDF   — capital diligence
├── OPF    — product graph
├── ODWF   — spreadsheet → bronze warehouse proof
├── OPFF   — personal finance packs
└── OMF    — meeting occurrences (this profile)
```

**Compose, don't merge.**

| External pin (optional) | Field | Profile / system |
|-------------------------|-------|------------------|
| Policy / durable memory | `policy` | EMF only |
| Research | `research` | ORF only |
| Work item for a commitment | `tracked_as` | Linear / docket.md — **not** OKF |

Pinned form, same spirit as OPF/OPFF:

```text
emf:<pack>:<object>@<revision>
orf:<pack>:<object>@<revision>
okf:<pack>:<object>@<revision>
```

External trackers use their own scheme and are **not** validated for content:

```text
linear:EID-878
docket:2026-08/omf-close-gate
```

A meeting **promotes** outward: a `decision` may later become an EMF `intent` (authored by a
human, never by an agent); a `commitment` may be tracked as a Linear issue. OMF stays authority
for *what was said in the room*. The tracker stays authority for *the state of the work*.

### Explicit non-relationship to iCalendar

OMF does **not** replace [RFC 5545](https://datatracker.ietf.org/doc/html/rfc5545). iCalendar
already solved calendar events. OMF preserves the original VEVENT byte-for-byte under
`invite/original.ics` and carries a normalized projection beside it. The RFC 5545 identity
properties are load-bearing and are mapped, not reinvented:

| RFC 5545 property | OMF field | Why it matters |
|---|---|---|
| `UID` — "the persistent, globally unique identifier for the calendar component" ([RFC 5545](https://datatracker.ietf.org/doc/html/rfc5545)) | `source.icalendar_uid` | Stable across reschedules; the correlation key for later replies and modifications |
| `RECURRENCE-ID` — identifies "a specific instance of a recurring VEVENT" ([RFC 5545](https://datatracker.ietf.org/doc/html/rfc5545)) | `source.recurrence_id` | Distinguishes this Tuesday from the series |
| `SEQUENCE` — "the revision sequence number of the calendar component" ([RFC 5545](https://datatracker.ietf.org/doc/html/rfc5545)) | `source.sequence` | A reschedule is a revision, not a new meeting |
| `DTSTAMP` — when the component was last revised in the calendar store ([RFC 5545](https://datatracker.ietf.org/doc/html/rfc5545)) | `source.dtstamp` | Import ordering without trusting file mtime |
| `STATUS` | `calendar_status` on the projection | `TENTATIVE` / `CONFIRMED` / `CANCELLED` |
| `ATTENDEE;PARTSTAT` — "the participation status for the calendar user" ([RFC 5545](https://datatracker.ietf.org/doc/html/rfc5545)) | `participant.invited.partstat` | Intent to attend — **not** attendance |
| `ORGANIZER` | `participant.role: organizer` | Who called the meeting |
| `RRULE` | `series.rrule` | Lives on the series document only |

A pack whose only source is a human note has `source.authority: human` and no `.ics`. That is
valid; the calendar is a common source, not a required one.

---

## 3. Bundle unit and layout

**Unit of distribution: one meeting occurrence.** One thing that happened (or was scheduled to)
at one point in time.

```
path/to/meeting/
  index.md                 # REQUIRED face (type: meeting)
  log.md                   # REQUIRED append-only timeline (OKF; no frontmatter required)
  invite/
    original.ics           # REQUIRED when source.authority is a calendar — verbatim, write-once
    calendar.md            # normalized projection (type: calendar_event)
  participants/            # meeting.participant concepts — one file per person
    *.md
  agenda/                  # meeting.agenda_item concepts — pre-meeting intent
    *.md
  artifacts/               # meeting.artifact pointer docs — NEVER media bytes
    *.md
  transcript/
    index.md               # type: transcript — provenance + coverage, not content
    segments.jsonl         # optional verbatim segments, append-only, write-once
  outcomes/
    decisions/*.md         # meeting.decision
    commitments/*.md       # meeting.commitment
    questions/*.md         # meeting.question — raised, unresolved
  conflicts/               # meeting.conflict — two sources disagree; both kept
    *.md
  evidence/                # optional small extracts, quotes — no secrets, no media
  series/                  # optional: the series doc, when co-located
    *.md
  meeting.json             # optional machine sidecar (import cursor, backends, session_id)
```

Producers MAY place packs under `.meetings/<omf_id>/` next to the work (kai default). Declare the
path in the pack index when reseated. **Never** commit real packs into this protocol repository.

### Series is a document, not a pack

A recurring meeting is **not** a pack containing 52 sub-packs. It is one small `type: series`
document that N occurrence packs point at:

```yaml
---
okf_version: "0.2"
omf_version: "0.1.1"
type: series
omf_id: omf:founders:20260701T180411Z-1a2b3c@eidosagi.com
title: "Founder call — weekly"
rrule: "FREQ=WEEKLY;BYDAY=SU"
icalendar_uid: 20260701T180411Z-1a2b3c@eidosagi.com
status: active            # active | paused | ended
occurrences: 47           # optional convenience count; never authority
---
```

Occurrence packs carry the same `icalendar_uid` and differ by `source.recurrence_id`.

---

## 4. Pack face (`index.md`) — required fields

| Field | Required | Meaning |
|-------|----------|---------|
| `okf_version` | MUST | `"0.2"` |
| `omf_version` | MUST | `"0.1.1"` (this profile) |
| `profile` | MUST | `omf` |
| `type` | MUST | `meeting` |
| `omf_id` | MUST | Stable, immutable id (see §5) |
| `title` | MUST | Display title |
| `status` | MUST | `proposed` \| `scheduled` \| `cancelled` \| `held` \| `capturing` \| `reconciling` \| `closed` \| `archived`. An importer creating a pack from past evidence MUST write `held` — never `closed`, which asserts a human close that did not happen |
| `sensitivity` | MUST | `public` \| `internal` \| `confidential` \| `restricted` |
| `starts_at_utc` | MUST unless `status: proposed` | Normalized UTC start — the cross-source join key |
| `ends_at_utc` | SHOULD | Normalized UTC end |
| `source` | MUST | `authority`, plus RFC 5545 fields when calendar-sourced. Producers MAY add source-system scoping keys (e.g. `drive_parent_id`) — unrecognized `source.*` keys are preserved, not errors |
| `capture` | MUST when `status` ∈ {held, capturing, reconciling, closed} | Per-slot `present` \| `absent` \| `not_attempted` |
| `series` | MUST be present as key | Path to series doc, or explicit `null` for one-offs |
| `verified` | MUST | OKF trust block (`by`, `at`, `method`, `stale_after`) |
| `tree` | SHOULD | Declared pack tree convention (see §12), so a reader never guesses |
| `imports` | MAY | Declared external pack closures |
| `policy` / `research` | MAY | Pinned EMF / ORF refs |
| `non_goals` | SHOULD | Explicit exclusions |

`ends_at_utc` before `starts_at_utc` is an **error**. Local-time-only timestamps on the face are
an **error** — normalize to UTC and keep the original in `invite/original.ics` or `source`.

---

## 5. Identity — the rule that does the most work

```text
omf_id = "omf:" <pack> ":" <icalendar_uid> [ "#" <recurrence_id> ]
```

When there is no calendar source:

```text
omf_id = "omf:" <pack> ":" <producer-scoped-slug> "#" <starts_at_utc>
```

Rules that bite:

1. `omf_id` is **immutable** for the life of the pack. It MUST NOT change on reschedule,
   rename, title edit, or re-import.
2. A **reschedule** bumps `source.sequence` and rewrites `starts_at_utc` / `ends_at_utc`, and
   MUST append to `log.md`. It MUST NOT mint a new `omf_id`.
3. A **cancellation** sets `status: cancelled`. It MUST NOT delete the pack. Soft delete only —
   `deleted_at` on the face, never file removal.
4. An occurrence pack MUST NOT omit `#<recurrence_id>` when `series` is non-null.
5. Two packs sharing an `omf_id` are a **duplicate-import error**. Importers MUST key their
   idempotency map on `omf_id`, not on filename, title, or Drive `fileId`.
6. Producers MUST NOT merge two occurrences because their titles match. Title similarity is
   never identity.

### 5.1 Producer-scoped slug (no calendar source)

When `<producer-scoped-slug>` applies, producers MUST derive it deterministically from source
evidence, never from a title. The reference derivation, which importers SHOULD follow:

| Available evidence | Slug |
| :----------------- | :--- |
| A conferencing code (e.g. Meet `xxx-yyyy-zzz`) | the code, lowercased |
| No code, only a timestamped artifact | `notes-<starts_at_utc>` |

The slug MUST be stable across re-imports of the same source object. A slug derived from a
mutable field (title, filename, display name) is non-conforming, because a rename would mint a
second pack for one meeting.

### 5.2 Grouping: deciding two artifacts are the same meeting

Joining is not the same as identity. `omf_id` names a meeting; grouping decides which artifacts
belong to it. Producers MUST apply these in order and MUST NOT skip to a weaker signal:

1. **Exact normalized `starts_at_utc`.** The only primary key.
2. **Conferencing code**, when present on both sides and step 1 disagrees. A shared Meet code
   with clashing clocks is one meeting with a **clock conflict**, not two meetings.
3. **Stop.** If neither resolves it, emit separate packs. An unresolved group is two honest packs;
   a wrong merge is unrecoverable, because the write-once rule means the loser's bytes are gone.

Title similarity MUST NOT be used at any step, including as a tiebreak. When step 2 resolves a
group whose clocks disagree, the producer MUST write a `conflicts/` document holding both
readings (see §8) rather than electing a winner.

---

## 6. Capture, artifacts, and the honesty rules

### Three-state capture

Every slot in `capture` is one of:

| Value | Meaning |
|-------|---------|
| `present` | The artifact exists and is bound in `artifacts/` |
| `absent` | Capture was configured and ran, but produced nothing (nobody spoke; recording failed) |
| `not_attempted` | Capture was never enabled or never run |

Writing `absent` when the truth is `not_attempted` is an **error** if the producer can tell them
apart. This distinction exists because a tenant with Meet transcripts disabled in Admin will
otherwise report an infinite series of empty transcripts as real evidence.

The `capture` face value is the normative record of a slot's state. A slot that is not `present`
requires **no directory and no placeholder document** — `transcript/` and `invite/` MUST be omitted
entirely when their slot is `absent` or `not_attempted`. Producers MUST NOT write an empty
`transcript/index.md` to mirror a fuller example: an empty container invites a later reader, human
or agent, to treat the slot as attempted-and-empty rather than never-run.

### Artifacts are pointers

Each file under `artifacts/` is an OKF concept describing **one bound file**. It MUST NOT contain
the file's bytes.

```yaml
---
okf_version: "0.2"
omf_version: "0.1.1"
type: artifact
title: "Meet recording — abc-defg-hij"
kind: recording            # recording | transcript | notes | deck | whiteboard | chat_log | attachment
locator: "gdrive://file/1EXAMPLEfileIdNotReal000000000"
web_view_link: "https://drive.google.com/file/d/1EXAMPLEfileIdNotReal000000000/view"
mime: video/mp4
bytes: 357864481
checksum: null             # sha256 when computable; null is honest
generated_by: google_meet
retrieved_at: 2026-08-17T15:59:00Z
retrieved_as: kai@eidosagi.com
---
```

Rules:

1. `locator` and `bytes` MUST be present. A pointer that cannot say how big the thing is has not
   inspected it.
2. Media MUST NOT be committed into the pack. Any file under `artifacts/` larger than **1 MiB**
   that is not Markdown is an **error**.
3. `retrieved_as` MUST name the principal that fetched it. Importing as the wrong identity is the
   failure this field is designed to make visible.
4. `checksum: null` is valid and preferred over a fabricated value.

### Speech is immutable

`invite/original.ics` and `transcript/segments.jsonl` are **write-once**. Once a byte is written:

1. No producer — human, job, or agent — may edit or reflow them.
2. Corrections are new documents under `evidence/` or `conflicts/` that reference the segment id.
3. `transcript/index.md` describes coverage and provenance **when the slot is `present`**; it MUST
   NOT paraphrase the content. When the slot is `absent` or `not_attempted`, omit `transcript/`
   entirely and let the face carry the state.
4. Diarization labels are claims, not facts. A `segment.speaker` carries its own `confidence`.

Segment shape (JSONL, one object per line, append-only):

```json
{"id":"seg-0001","start_ms":0,"end_ms":4120,"speaker":"cofounder","speaker_confidence":0.71,"text":"…"}
```

---

## 7. Participants — invited is not attended

One file per person under `participants/`.

```yaml
---
okf_version: "0.2"
omf_version: "0.1.1"
type: participant
title: "Second founder"
identity: cofounder@example.com
role: attendee              # organizer | attendee | optional | observer | absent
invited:
  partstat: ACCEPTED        # RFC 5545 PARTSTAT — intent only
  source: google_calendar
attended:
  observed: true
  evidence: artifacts/recording-abc-defg-hij.md
  by: job:omf-import
---
```

Rules:

1. `invited.partstat` MUST NOT be used to populate `attended.observed`. RSVP is intent; a
   recording, a join log, or a human statement is evidence.
2. `attended.observed: true` MUST carry `evidence` or a `human:` tier `by`.
3. `attended` MAY be entirely absent — unknown attendance is an honest state.
4. Unknown participants stay unknown. Producers MUST NOT infer attendees from the guest list.

---

## 8. Outcomes — the part that becomes work

### Decisions

```yaml
---
okf_version: "0.2"
omf_version: "0.1.1"
type: decision
title: "kai imports Meet records as kai@, not as Daniel"
binding: true
decided_by: human:daniel
supersedes: null            # omf:<pack>:<object> of an earlier decision
quotes:
  - segment: seg-0184
    text: "Daniel's Takeout and Daniel's SSO context are the wrong jar."
---
```

**Agents MUST NOT author a document with `type: decision` and `binding: true`.** An agent may
write `binding: false` with `proposed_by: agent:<name>`; a human promotes it. This mirrors ORF's
prohibition on agent-authored `type: intent`, and the tabletop thesis: *everything said in the
room becomes a record; only a person turns a record into work.*

### Commitments

```yaml
---
okf_version: "0.2"
omf_version: "0.1.1"
type: commitment
title: "Enable Meet transcripts in Workspace Admin"
owner: human:daniel          # MUST NOT be null when state is open
state: open                  # open | done | dropped | superseded
due: 2026-08-24
tracked_as: linear:EID-901   # optional; the tracker owns work state, not OMF
quotes:
  - segment: seg-0210
---
```

Rules:

1. A `commitment` with `state: open` MUST have a non-null `owner`. An ownerless open commitment is
   an **error**, not a warning.
2. OMF MUST NOT mirror tracker state. `state` here records what the room agreed; `tracked_as`
   points at the system that owns execution. Divergence is expected and is not a conflict.
3. Deriving a commitment from speech requires a `quotes` entry. A commitment with no quote and an
   `agent:` tier author is an **error**.

### Conflicts

When two sources disagree about the same fact, record both:

```yaml
---
okf_version: "0.2"
omf_version: "0.1.1"
type: conflict
title: "Start time disagreement between recording title and notes title"
about: starts_at_utc
positions:
  - value: 2026-05-26T03:28:00Z
    source: artifacts/recording-abc-defg-hij.md
  - value: 2026-05-26T08:28:00Z
    source: artifacts/notes-2026-05-26.md
    note: "title labelled CDT; likely mislabelled UTC"
resolution: null             # null until a human decides
---
```

Producers MUST NOT resolve a conflict by overwriting. Later imports do not win by being later.

---

## 9. Conformance

- Every OMF document MUST be a valid OKF v0.2 document (`okf_version: "0.2"`).
- Pack face MUST carry `omf_version` when claiming OMF conformance.
- `omf_version` MUST use `X.Y.Z`. OMF-only revisions increment `Z`.
- `status: closed` ⇒ every `commitment` with `state: open` has a non-null `owner`.
- `status: closed` ⇒ `capture` is present and every slot is explicitly one of the three states.
- `status` ∈ {held, capturing, reconciling, closed} ⇒ non-null `starts_at_utc`.
- `ends_at_utc` < `starts_at_utc` ⇒ error.
- Non-null `series` ⇒ `omf_id` contains `#<recurrence_id>`.
- Duplicate `omf_id` within a catalogue ⇒ error.
- Agents MUST NOT author `type: decision` with `binding: true`.
- Agents MUST NOT author `type: intent` (OKF/EMF rule, inherited).
- `attended.observed: true` without `evidence` and without `human:` tier `by` ⇒ error.
- `commitment` with `state: open` and null `owner` ⇒ error.
- Non-Markdown file over 1 MiB under `artifacts/` ⇒ error.
- `artifact` without `locator` or `bytes` ⇒ error.
- Modification of `transcript/segments.jsonl` or `invite/original.ics` after first write ⇒ error
  (enforced by producers and by CI content hash, not by the document schema).
- Secret-shaped strings anywhere in the pack ⇒ error (inherited from the OPFF gate; meeting
  recordings routinely contain spoken credentials). Detection is **pattern-first** for known
  credential formats (AWS, GitHub, Google OAuth/API, JWT, private-key headers), with a length +
  entropy sweep as backstop. A **`locator` is required content and MUST NOT be reported as a
  credential**: URIs are excluded from the entropy sweep, so real `https://drive.google.com/...`
  and `gdrive://...` values pass. Pattern checks still run against the unmasked text, so a
  credential smuggled into a query string is caught. A validator that rejects real locators is
  non-conforming — it teaches producers to strip provenance to satisfy the linter, which defeats
  the point of the field.
- `sensitivity: restricted` packs MUST be excluded from shared renders by default.
- Capital `verdict` (ODDF), finance `postings` (OPFF), or research `evidence` grades (ORF) present
  on an OMF face ⇒ warn (wrong profile).
- `log.md` has no frontmatter requirement (OKF append-only convention).

Validate:

```bash
python3 -m omf.validate <pack-or-file>...
python3 -m omf.validate --selftest
python3 -m omf.validate --strict examples/minimal
```

---

## 10. Placement (not part of the document schema)

OMF is a **format**. It does not define a global meeting warehouse.

| Default | Reseat |
|---------|--------|
| `.meetings/<omf_id>/` next to the work (kai default) | `docs/omf/`, tabletop record trees — declare in index |

**This repository** (`eidos-agi/omf`) ships **spec, validator, examples**. It is not the org
meeting corpus. kai, tabletop, and Workspace importers are consumers that write packs.

---

## 11. Prior art

| | |
|--|--|
| **OKF v0.2** | Bundle tree, `index.md` / `log.md`, trust ladder, `verified` block |
| **EMF** | Additive-profile pattern — dual version stamps, measured failures, biting conformance |
| **ORF** | Producer-authority prohibition (`agents MUST NOT author type: intent`), gates that bite |
| **OPFF** | Import-class vs judgment-class split; secret-string validation; pinned external refs |
| **RFC 5545** | iCalendar identity and revision model — mapped, never reinvented |
| **tabletop** | "Everything said in the room becomes a record. Only a person turns a record into work." |
| **kai `kind: conference`** | The chat card that must become a projection, not the store |

---

## 12. Version

| | |
|--|--|
| Profile | OMF **0.1.1** |
| Base | OKF **0.2** |
| Status | Draft — dogfood with kai Workspace import |
