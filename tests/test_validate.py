from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from omf.validate import (
    OMF_VERSION,
    Problem,
    parse_frontmatter,
    secret_problems,
    validate_artifact,
    validate_common,
    validate_face,
    validate_outcome,
    validate_pack,
    validate_participant,
    validate_path,
)

ROOT = Path(__file__).resolve().parents[1]
MINIMAL = ROOT / "examples" / "minimal"


def rules(problems: list[Problem]) -> set[str]:
    return {p.rule for p in problems if p.level == "error"}


def face(**changes: object) -> dict:
    result = {
        "okf_version": "0.2", "omf_version": OMF_VERSION, "profile": "omf", "type": "meeting",
        "omf_id": "omf:test:fixture#2026-07-06T02:00:00Z", "title": "Fixture", "status": "closed",
        "sensitivity": "internal", "starts_at_utc": "2026-07-06T02:00:00Z", "ends_at_utc": "2026-07-06T03:00:00Z",
        "series": "series/test.md", "source": {"authority": "human"},
        "capture": {"recording": "absent", "transcript": "not_attempted", "notes": "absent"},
        "verified": {"by": "human:fixture", "at": "2026-08-17", "method": "test", "stale_after": "2027-08-17"},
    }
    result.update(changes)
    return result


class OMFValidatorTests(unittest.TestCase):
    def copy_minimal(self, target: Path) -> Path:
        shutil.copytree(MINIMAL, target)
        return target

    def test_face_identity_profile_and_versions_bite(self) -> None:
        p = rules(validate_face(face(okf_version="0.1", omf_version="broken", profile="orf", type="claim", omf_id="changed id")))
        self.assertTrue({"okf_version", "omf_version", "profile", "type", "omf_id"} <= p)

    def test_status_and_sensitivity_enums_bite(self) -> None:
        p = rules(validate_face(face(status="done", sensitivity="secret")))
        self.assertIn("status", p)
        self.assertIn("sensitivity", p)

    def test_held_requires_utc_start_and_all_capture_slots(self) -> None:
        p = rules(validate_face(face(status="held", starts_at_utc=None, capture={"recording": "maybe"})))
        self.assertIn("starts_at_utc", p)
        self.assertIn("capture.recording", p)
        self.assertIn("capture.transcript", p)
        self.assertIn("capture.notes", p)

    def test_timestamps_must_be_utc_and_in_order(self) -> None:
        p = rules(validate_face(face(starts_at_utc="2026-07-06T02:00:00-05:00", ends_at_utc="2026-07-06T01:00:00Z")))
        self.assertIn("starts_at_utc", p)
        # An independently valid UTC start makes the chronological ordering gate observable.
        self.assertIn("ends_at_utc", rules(validate_face(face(ends_at_utc="2026-07-06T01:00:00Z"))))

    def test_series_requires_recurrence_identity_and_id_shape(self) -> None:
        p = rules(validate_face(face(omf_id="omf:test:fixture")))
        self.assertIn("series_identity", p)
        self.assertIn("omf_id", rules(validate_face(face(omf_id="not-an-omf-id"))))

    def test_duplicate_omf_id_across_catalogue_is_error(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.copy_minimal(root / "one")
            self.copy_minimal(root / "two")
            reports = validate_path(root)
            duplicate = [p for r in reports for p in r.problems if p.rule == "omf_id_duplicate"]
            self.assertEqual(2, len(duplicate))

    def test_artifact_requires_locator_and_bytes(self) -> None:
        p = rules(validate_artifact({"okf_version": "0.2", "omf_version": OMF_VERSION, "type": "artifact", "kind": "recording", "retrieved_as": "fixture@example.test"}))
        self.assertTrue({"locator", "bytes"} <= p)

    def test_large_non_markdown_artifact_is_error(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            pack = self.copy_minimal(Path(td) / "pack")
            (pack / "artifacts" / "recording.mp4").write_bytes(b"0" * (1024 * 1024 + 1))
            p = {x.rule for r in validate_pack(pack) for x in r.problems}
            self.assertIn("artifact_media", p)

    def test_observed_attendance_needs_evidence_or_human(self) -> None:
        p = rules(validate_participant({"okf_version": "0.2", "omf_version": OMF_VERSION, "type": "participant", "attended": {"observed": True, "by": "agent:import"}}))
        self.assertIn("attended.observed", p)
        rsvp = rules(validate_participant({"okf_version": "0.2", "omf_version": OMF_VERSION, "type": "participant", "attended": {"partstat": "ACCEPTED"}}))
        self.assertIn("attended", rsvp)

    def test_open_commitment_requires_owner_and_agent_quote(self) -> None:
        p = rules(validate_outcome({"okf_version": "0.2", "omf_version": OMF_VERSION, "type": "commitment", "state": "open", "owner": None, "authored_by": "agent:writer"}))
        self.assertTrue({"owner", "quotes"} <= p)

    def test_agent_cannot_author_binding_decision_or_intent(self) -> None:
        decision = rules(validate_outcome({"okf_version": "0.2", "omf_version": OMF_VERSION, "type": "decision", "binding": True, "decided_by": "agent:writer"}))
        intent = rules(validate_outcome({"okf_version": "0.2", "omf_version": OMF_VERSION, "type": "intent", "authored_by": "agent:writer"}))
        self.assertIn("binding", decision)
        self.assertIn("intent_agent", intent)

    def test_closed_negative_example_has_only_owner_error(self) -> None:
        reports = validate_pack(ROOT / "examples" / "bad-closed-without-owner")
        errors = [p.rule for r in reports for p in r.problems if p.level == "error"]
        self.assertEqual(["owner"], errors)

    def test_conflict_requires_two_positions_and_null_resolution_is_valid(self) -> None:
        p = rules(validate_outcome({"okf_version": "0.2", "omf_version": OMF_VERSION, "type": "conflict", "positions": [{"value": "one"}], "resolution": None}))
        self.assertIn("positions", p)
        good = validate_outcome({"okf_version": "0.2", "omf_version": OMF_VERSION, "type": "conflict", "positions": [{"value": "one"}, {"value": "two"}], "resolution": None})
        self.assertNotIn("positions", rules(good))

    def test_secret_shaped_string_anywhere_in_pack_is_error(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            pack = self.copy_minimal(Path(td) / "pack")
            (pack / "evidence").mkdir()
            (pack / "evidence" / "note.md").write_text("---\nokf_version: \"0.2\"\nomf_version: \"0.1.0\"\ntype: evidence\n---\nBearer abcdefghijklmnopqrstuvwxyz123456\n", encoding="utf-8")
            p = {x.rule for r in validate_pack(pack) for x in r.problems}
            self.assertIn("secrets", p)

    def test_wrong_profile_keys_warn_and_strict_escalates(self) -> None:
        p = validate_common({"okf_version": "0.2", "omf_version": OMF_VERSION, "type": "question", "verdict": "PASS", "postings": [], "evidence": "CONFIRMED"})
        warnings = {x.rule for x in p if x.level == "warn"}
        self.assertEqual({"verdict_wrong_profile", "postings_wrong_profile", "evidence_wrong_profile"}, warnings)

    def test_trust_ladder_values_require_prefixes(self) -> None:
        p = rules(validate_outcome({"okf_version": "0.2", "omf_version": OMF_VERSION, "type": "decision", "decided_by": "Daniel"}))
        self.assertIn("decided_by", p)

    def test_focused_rsvp_negative_example_fails_for_one_reason(self) -> None:
        reports = validate_pack(ROOT / "examples" / "bad-rsvp-as-attendance")
        errors = [p.rule for r in reports for p in r.problems if p.level == "error"]
        self.assertEqual(["attended.observed"], errors)

    def test_frontmatter_parser_reads_list_maps(self) -> None:
        fm = parse_frontmatter("---\npositions:\n  - value: one\n    source: x\n  - value: two\n    source: y\n---\n")
        self.assertEqual("x", fm["positions"][0]["source"])
        self.assertEqual(2, len(fm["positions"]))


if __name__ == "__main__":
    unittest.main()


class SecretDetectorRegression(unittest.TestCase):
    """Regression: v0.1.0 flagged every real Drive locator as a credential while
    missing canonical cloud keys. Reported by kai during first integration."""

    REQUIRED_LOCATORS = [
        "locator: https://drive.google.com/file/d/1uWsiUUP43X9istnbmF8ALhALoECOWoZk/view",
        "locator: https://docs.google.com/document/d/1HDC2Umnem0iWLxprwgOlDZ-18T1tNnjEebTzEkkQh1k/edit",
        "locator: gdrive://file/1uWsiUUP43X9istnbmF8ALhALoECOWoZk",
        "locator: https://meet.google.com/hjr-jczn-ixk",
    ]

    REAL_CREDENTIALS = [
        "aws_key: AKIAIOSFODNN7EXAMPLE",
        "ghp_16C7e42F292c6912E7710c838347Ae178B4a1b2c",
        "token: ya29.a0AfB_byC3xample-token-value-here-long",
        "AIzaSyD-1234567890abcdefghijklmnopqrstu",
        "sk-proj-abcdefghijklmnopqrstuvwxyz123456",
        "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.sig",
        "-----BEGIN RSA PRIVATE KEY-----",
        "0123456789abcdef0123456789abcdef0123456789ab",
    ]

    def test_locators_are_not_secrets(self):
        for text in self.REQUIRED_LOCATORS:
            with self.subTest(text=text):
                self.assertEqual(secret_problems(text), [], "a locator is required content, never a credential")

    def test_known_credentials_are_caught(self):
        for text in self.REAL_CREDENTIALS:
            with self.subTest(text=text):
                self.assertTrue(secret_problems(text), "known credential shape must be rejected")

    def test_credential_inside_a_url_still_caught(self):
        self.assertTrue(secret_problems("https://api.example.com/v1?access_token=AKIAIOSFODNN7EXAMPLE"))

    def test_uri_masking_does_not_hide_adjacent_secret(self):
        self.assertTrue(secret_problems("see https://drive.google.com/file/d/abc/view then AKIAIOSFODNN7EXAMPLE"))
