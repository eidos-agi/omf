# OMF — Open Meeting Format

[![CI](https://github.com/eidos-agi/omf/actions/workflows/validate.yml/badge.svg)](https://github.com/eidos-agi/omf/actions/workflows/validate.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**A protocol / standard — not a meeting warehouse.** This repository is the **spec + validator + fictional examples**. Meeting packs live next to the work (for example under `.meetings/<omf_id>/`); this repository does not own meeting records.

**OMF v0.1.0** is an additive profile of [OKF v0.2](https://github.com/eidos-agi/okflify). Every OMF document is a valid OKF document. Renderers that know only OKF display the document and ignore OMF profile keys.

```text
OKF  — knowledge and trust                 https://github.com/eidos-agi/okflify
EMF  — human intent and durable memory     https://github.com/eidos-agi/emf
ORF  — research / investigation packs      https://github.com/eidos-agi/orf
OPF  — product graph                       https://github.com/eidos-agi/opf
OPFF — personal finance packs              https://github.com/eidos-agi/opff
OMF  — meeting occurrences                 (this repo)
```

Read [SPEC.md](SPEC.md) and [INTENTION.md](INTENTION.md) first. The intention is load-bearing.

## Three truth classes

| Class | What it records | Rule |
|---|---|---|
| Invite-class | Calendar event, guest list, RSVP | Calendar-owned; preserve the original VEVENT. |
| Record-class | Recording, transcript, observed attendance | Write once; RSVP is never evidence of attendance. |
| Outcome-class | Decisions, commitments, open questions | Humans decide; agents may only propose. |

## Install

```bash
git clone https://github.com/eidos-agi/omf.git
cd omf
python3 -m pip install -e .
```

## Validate

```bash
python3 -m omf.validate --selftest
python3 -m omf.validate --strict examples/minimal
omf-validate --strict examples/minimal

# Negative examples (each must fail)
python3 -m omf.validate examples/bad-closed-without-owner; echo exit=$?
python3 -m omf.validate examples/bad-rsvp-as-attendance; echo exit=$?
```

## What it checks

| Rule | Level |
|---|---|
| `okf_version: "0.2"`, `omf_version: X.Y.Z`, `profile: omf`, `type: meeting` | error |
| Required status, sensitivity, UTC timing, source, series, and verified fields | error |
| Held/closed capture slots explicitly recorded | error |
| Recurrence identity and duplicate `omf_id` imports | error |
| Pointer artifact locator, bytes, identity, and no large media under `artifacts/` | error |
| RSVP presented as attendance without record evidence | error |
| Agent binding decisions, agent intent, ownerless open commitments | error |
| Secret-shaped strings | error |
| ODDF `verdict`, OPFF `postings`, ORF evidence grades | warn (error under `--strict`) |

## Minimal layout

```text
meeting-occurrence/
  index.md                         # face: type: meeting
  log.md                           # append-only timeline
  invite/original.ics              # calendar source, preserved verbatim
  invite/calendar.md               # normalized projection
  participants/*.md                # invited versus observed attendance
  agenda/*.md
  artifacts/*.md                   # pointer docs; no media bytes
  transcript/index.md              # provenance and coverage
  outcomes/decisions/*.md
  outcomes/commitments/*.md
  outcomes/questions/*.md
  conflicts/*.md
  series/*.md                      # optional co-located series document
```

See [examples/minimal](examples/minimal) for a complete sanitized occurrence. It intentionally says `transcript: not_attempted` and stores recording and notes as pointers.

## Relationship to siblings

OMF is the meeting-occurrence profile. Use **EMF** for durable policy or a promoted human intent, **ORF** for research, and Linear or `docket.md` for task execution. An OMF commitment captures what the room agreed; `tracked_as` points to the system that owns work state.

## Privacy

Public fixtures are fictional and sanitized. Never commit a real recording, transcript, credential, personal data, or restricted meeting pack to this protocol repository.

## License

MIT — Eidos AGI
