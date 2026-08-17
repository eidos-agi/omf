# Why OMF exists

## The mistake OMF is built to avoid

A meeting looks like a document and is actually a **process with three different classes of truth
inside it**. Every tool that treats a meeting as one blob eventually corrupts one class with
another: the summary overwrites the transcript, the RSVP becomes attendance, the agent's inference
becomes the decision.

OMF's whole job is to keep the three classes separate and mark the seams.

| Class | What it is | Who may write it | Mutability |
|---|---|---|---|
| **Invite-class** | What was scheduled: VEVENT, guest list, RRULE, RSVP | The calendar system | Revised via `SEQUENCE`; original preserved verbatim |
| **Record-class** | What happened: recording, transcript segments, chat log, observed attendance | Capture systems, as evidence | **Write-once.** Never edited, never reflowed |
| **Outcome-class** | What it means: decisions, commitments, open questions | Humans decide; agents may only propose | Mutable, versioned, superseded — never silently |

Corruption across these boundaries is the failure mode. A summary is outcome-class; it must never
be written into record-class. An RSVP is invite-class; it must never be read as record-class.

## Why this is a profile, not a new file format

The instinct was "a new file format, like xlsx — a foldered package of stuff plus tons of
metadata." That instinct is right about the *shape* and wrong about the *work required*, because
OKF v0.2 already **is** that container: a directory of Markdown documents, YAML frontmatter for
identity and trust, Markdown links as edges, Git for history, `index.md` and `log.md` reserved.

ORF is not a sibling of OKF. ORF is an additive **profile** of OKF v0.2 — as are EMF, OPFF, ODWF,
ODDF, and OPF. Writing OMF as a fresh format would mean rebuilding the tree contract, the trust
ladder, the `verified` block, and the renderer, and would lose `okflify` for free.

So the container is solved. The real effort — and it is real — is in three places:

1. **Identity under recurrence and reschedule.** A weekly call is one series and N occurrences. A
   moved meeting is a revision, not a new meeting. Getting this wrong produces either 52
   near-duplicate packs or one pack that overwrites its own history. RFC 5545 already solved it
   with `UID` + `RECURRENCE-ID` + `SEQUENCE`; OMF maps those instead of inventing keys.
2. **Reconciliation across sources that do not share a key.** The same meeting arrives as a
   Calendar VEVENT, a Meet recording named by meeting code and GMT, a Gemini notes Doc named with a
   local timezone, and possibly a human note. Nothing joins them natively. OMF normalizes to
   `starts_at_utc`, preserves every original, and keeps disagreements in `conflicts/` rather than
   letting the last import win.
3. **The honesty gates.** Absent capture is not empty capture. Invited is not attended. A proposal
   is not a decision. An open commitment with no owner is not a commitment. These are cheap to
   state and are exactly what agents get wrong at scale.

## Non-goals

- **Not a task tracker.** A `commitment` records what the room agreed. Linear or docket.md owns
  the state of the work. `tracked_as` points outward; OMF never mirrors tracker state.
- **Not durable org memory.** A decision may be promoted into an EMF `intent` by a human. The
  meeting face stays OMF.
- **Not a media store.** Recordings are hundreds of megabytes. OMF holds pointers with byte counts
  and retrieval provenance. Bytes stay where the capture system put them.
- **Not a calendar implementation.** OMF does not parse RRULE for you, does not resolve timezones
  for you, and does not replace RFC 5545. It preserves the invite and records a normalized
  projection beside it.
- **Not a summarizer.** OMF is a place to put a summary with its provenance attached. It has no
  opinion about how good the summary is.
- **Not a warehouse.** Packs live next to the work. This repository ships spec, validator, and
  examples only.

## The identity boundary

Import provenance is a first-class field because the wrong-jar failure is the most common one.
`artifact.retrieved_as` names the principal that fetched the file. A pack imported as a founder's
personal account when the design says the agent identity is the principal is not a cosmetic
problem — it silently makes the record unshareable and the provenance wrong. Making the principal
explicit means the mistake is visible in a diff rather than discovered a year later.

## Sensitivity is not optional

Meeting recordings contain things nobody would write down: credentials spoken aloud, salary
figures, unfiltered opinions about people. `sensitivity` is a required field with four values, and
`restricted` packs are excluded from shared renders by default. The secret-string validator
inherited from OPFF is not paranoia here; it is the expected case.

## What "done" looks like for v0.1

A real founder call exists as one pack with: the original `.ics` preserved, a normalized face, the
recording and notes bound as pointers with sizes and retrieval identity, `transcript:
not_attempted` stated honestly because the tenant never enabled it, participants with RSVP and
attendance separated, one decision authored by a human with a quote, one commitment with an owner
and a Linear pin, and a `log.md` that shows the reschedule that happened along the way. A second
import of the same meeting changes nothing. `okflify` renders it without modification.
