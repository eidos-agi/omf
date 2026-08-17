# Contributing

Read [INTENTION.md](INTENTION.md) and [SPEC.md](SPEC.md) before proposing a change. OMF is a protocol repository: changes must preserve the invite-class, record-class, and outcome-class boundaries.

- Use fictional, sanitized fixtures only. Never add real calendar exports, recordings, transcripts, credentials, or restricted material.
- Keep the validator pure Python standard library; do not add a YAML dependency.
- Add a test for every rule that becomes normative or changes behavior.
- Run `python3 -m omf.validate --selftest`, `python3 -m omf.validate --strict examples/minimal`, and `python3 -m unittest discover -s tests -v` before submitting.
- Keep negative examples focused: one failing reason per pack.
