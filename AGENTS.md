# Open Meeting Format

OMF is an additive OKF profile for **one meeting occurrence** — not a calendar implementation, media store, task tracker, or meeting warehouse.

Read **[INTENTION.md](INTENTION.md)** first.

- Preserve the invite-class / record-class / outcome-class boundary.
- Calendar RSVP is intent, never attendance evidence.
- Record-class files (`invite/original.ics`, transcript segments) are write-once.
- Decisions become binding only through a human; agents never author binding decisions or intent.
- An open commitment needs an owner. Track execution externally through `tracked_as`.
- Artifacts are pointers with locator, bytes, and retrieval identity — never media bytes.
- Required sensitivity is not optional; never put credentials or real meeting data in this repo.
- OMF is a profile of OKF v0.2; compose with EMF and ORF rather than merging their jobs.
- Validator is stdlib-only: run `python3 -m omf.validate --strict examples/minimal` before publishing changes.
