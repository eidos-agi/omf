"""omf.validate — check documents and packs against OMF v0.1.0.

A format without a checker is a suggestion. Stdlib only: this module parses the
small YAML frontmatter subset used by OMF without requiring PyYAML.

    python3 -m omf.validate <file-or-pack-dir>...
    python3 -m omf.validate --selftest
    python3 -m omf.validate --strict examples/minimal
"""
from __future__ import annotations

import argparse
import base64
import json
import math
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator

from . import OKF_VERSION, OMF_VERSION

FACE_TYPE = "meeting"
STATUSES = {"proposed", "scheduled", "cancelled", "held", "capturing", "reconciling", "closed", "archived"}
SENSITIVITIES = {"public", "internal", "confidential", "restricted"}
CAPTURE_VALUES = {"present", "absent", "not_attempted"}
CAPTURE_SLOTS = ("recording", "transcript", "notes")
OPEN_STATES = {"open", "done", "dropped", "superseded"}
ARTIFACT_KINDS = {"recording", "transcript", "notes", "deck", "whiteboard", "chat_log", "attachment"}
TIERS = {"human", "job", "agent"}
ID_RE = re.compile(r"^omf:[a-z0-9][a-z0-9._-]*:[^\s#]+(?:#[^\s#]+)?$")
VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")
# Kept deliberately conservative; the long opaque-token check adds the entropy gate.
SECRETISH = re.compile(r"(?i)(-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|\b(?:api[_-]?key|secret|token|password)\s*[:=]\s*['\"]?[^\s'\"]{8,}|\bBearer\s+[A-Za-z0-9._~+/-]{16,}|\b(?:sk_live_|sk_test_|xox[baprs]-)[A-Za-z0-9_-]+|(?:postgres(?:ql)?|mysql)://[^\s:]+:[^\s@]+@)")


@dataclass
class Problem:
    level: str
    rule: str
    detail: str


@dataclass
class Report:
    path: Path
    problems: list[Problem] = field(default_factory=list)

    @property
    def errors(self) -> list[Problem]:
        return [p for p in self.problems if p.level == "error"]


def _scalar(value: str) -> Any:
    value = value.strip()
    if len(value) >= 2 and value[0] in "'\"" and value[-1] == value[0]:
        value = value[1:-1]
    low = value.lower()
    if low in {"null", "~", "none"}:
        return None
    if low == "true":
        return True
    if low == "false":
        return False
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    if re.fullmatch(r"-?\d+\.\d+", value):
        return float(value)
    return value


def _split_flow(value: str) -> list[str]:
    out, buf, depth, quote = [], [], 0, ""
    for ch in value:
        if ch in "'\"":
            quote = "" if quote == ch else (ch if not quote else quote)
        elif not quote and ch in "[{":
            depth += 1
        elif not quote and ch in "]}":
            depth -= 1
        if ch == "," and not quote and depth == 0:
            out.append("".join(buf).strip()); buf = []
        else:
            buf.append(ch)
    if buf:
        out.append("".join(buf).strip())
    return out


def _flow_map(value: str) -> dict[str, Any]:
    inner = value.strip()[1:-1].strip()
    return {k.strip(): _value(v.strip()) for item in _split_flow(inner) if ":" in item for k, _, v in [item.partition(":")]}


def _value(value: str) -> Any:
    value = value.strip()
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        return [] if not inner else [_value(x) for x in _split_flow(inner)]
    if value.startswith("{") and value.endswith("}"):
        return _flow_map(value)
    return _scalar(value)


def parse_frontmatter(text: str) -> dict[str, Any]:
    """Parse OMF's small YAML subset: maps, lists, list maps, and flow values."""
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end < 0:
        return {}
    lines = text[3:end].splitlines()
    root: dict[str, Any] = {}
    stack: list[tuple[int, dict[str, Any] | list[Any]]] = [(-1, root)]
    i = 0
    while i < len(lines):
        raw = lines[i]
        if not raw.strip() or raw.lstrip().startswith("#"):
            i += 1; continue
        indent = len(raw) - len(raw.lstrip())
        line = raw.strip()
        while len(stack) > 1 and indent <= stack[-1][0]:
            stack.pop()
        container = stack[-1][1]
        if line.startswith("- "):
            if not isinstance(container, list):
                i += 1; continue
            item = line[2:].strip()
            if not item:
                child: dict[str, Any] = {}; container.append(child); stack.append((indent, child))
            elif ":" in item and not item.startswith(("'", '"')):
                k, _, v = item.partition(":")
                child = {k.strip(): _value(v.strip()) if v.strip() else {}}
                container.append(child); stack.append((indent, child))
            else:
                container.append(_value(item))
            i += 1; continue
        if not isinstance(container, dict) or ":" not in line:
            i += 1; continue
        key, _, value = line.partition(":")
        key, value = key.strip(), value.strip()
        if value:
            container[key] = _value(value); i += 1; continue
        # An empty value becomes a list or map based on next indented real line.
        kind = "map"
        for next_raw in lines[i + 1:]:
            if not next_raw.strip() or next_raw.lstrip().startswith("#"):
                continue
            next_indent = len(next_raw) - len(next_raw.lstrip())
            if next_indent <= indent:
                kind = "empty"; break
            kind = "list" if next_raw.strip().startswith("- ") else "map"; break
        if kind == "list":
            child_list: list[Any] = []; container[key] = child_list; stack.append((indent, child_list))
        elif kind == "map":
            child_map: dict[str, Any] = {}; container[key] = child_map; stack.append((indent, child_map))
        else:
            container[key] = None
        i += 1
    return root


def tier_of(value: Any) -> str:
    return str(value or "").split(":", 1)[0]


def has_tier(value: Any) -> bool:
    s = str(value or "")
    return bool(re.fullmatch(r"(?:human|job|agent):[^\s:]+", s))


def author_of(fm: dict[str, Any], *fields: str) -> Any:
    for name in fields:
        if fm.get(name) is not None:
            return fm[name]
    verified = fm.get("verified")
    return verified.get("by") if isinstance(verified, dict) else None


def _nested(fm: dict[str, Any], key: str) -> dict[str, Any]:
    value = fm.get(key)
    return value if isinstance(value, dict) else {}


def _problems_for_trust(fm: dict[str, Any]) -> list[Problem]:
    problems: list[Problem] = []
    verified = _nested(fm, "verified")
    for label, value in (("verified.by", verified.get("by")), ("by", fm.get("by")), ("attended.by", _nested(fm, "attended").get("by")), ("decided_by", fm.get("decided_by")), ("owner", fm.get("owner")), ("proposed_by", fm.get("proposed_by")), ("authored_by", fm.get("authored_by"))):
        if value is not None and not has_tier(value):
            problems.append(Problem("error", label, f"{label}={value!r} — trust-ladder values must start human:, job:, or agent:"))
    return problems


def _is_utc_timestamp(value: Any) -> bool:
    return isinstance(value, str) and value.endswith("Z") and _parse_utc(value) is not None


def _parse_utc(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.endswith("Z"):
        return None
    try:
        return datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        return None


def _high_entropy_token(token: str) -> bool:
    if len(token) < 40 or re.fullmatch(r"[0-9a-fA-F]+", token) is None and re.fullmatch(r"[A-Za-z0-9+/=_-]+", token) is None:
        return False
    alphabet = len(set(token))
    return alphabet >= 10 and any(c.isdigit() for c in token) and any(c.isalpha() for c in token)


def secret_problems(text: str) -> list[Problem]:
    if SECRETISH.search(text):
        return [Problem("error", "secrets", "secret-shaped string detected — use a credential-plane locator, never a credential")]
    for token in re.findall(r"[A-Za-z0-9+/=_-]{40,}", text):
        if _high_entropy_token(token):
            return [Problem("error", "secrets", "long high-entropy hex/base64-shaped string detected")]
    return []


def validate_common(fm: dict[str, Any], *, require_frontmatter: bool = True) -> list[Problem]:
    if not fm:
        return [Problem("error", "frontmatter", "OMF document needs YAML frontmatter")] if require_frontmatter else []
    p: list[Problem] = []
    if str(fm.get("okf_version") or "") != OKF_VERSION:
        p.append(Problem("error", "okf_version", f"okf_version={fm.get('okf_version')!r} — expected {OKF_VERSION!r}"))
    ver = fm.get("omf_version")
    if ver is None:
        p.append(Problem("error", "omf_version", "OMF document must set omf_version"))
    elif not VERSION_RE.fullmatch(str(ver)):
        p.append(Problem("error", "omf_version", f"omf_version={ver!r} — expected X.Y.Z"))
    elif str(ver) != OMF_VERSION:
        p.append(Problem("warn", "omf_version", f"document declares {ver}; this validator implements {OMF_VERSION}"))
    if not str(fm.get("type") or "").strip():
        p.append(Problem("error", "type", "OKF concept needs type"))
    p.extend(_problems_for_trust(fm))
    for key in ("verdict", "postings"):
        if key in fm:
            p.append(Problem("warn", f"{key}_wrong_profile", f"{key} belongs to another profile, not OMF"))
    if str(fm.get("evidence") or "").upper() in {"CONFIRMED", "REASONED", "UNVERIFIED"}:
        p.append(Problem("warn", "evidence_wrong_profile", "ORF evidence grades belong to another profile, not OMF"))
    return p


def validate_face(fm: dict[str, Any]) -> list[Problem]:
    p = validate_common(fm)
    if not fm:
        return p
    if str(fm.get("profile") or "") != "omf":
        p.append(Problem("error", "profile", "pack face profile must be omf"))
    if str(fm.get("type") or "") != FACE_TYPE:
        p.append(Problem("error", "type", "pack face type must be meeting"))
    omf_id = str(fm.get("omf_id") or "")
    if not omf_id:
        p.append(Problem("error", "omf_id", "omf_id is required"))
    elif not ID_RE.fullmatch(omf_id):
        p.append(Problem("error", "omf_id", f"omf_id={omf_id!r} — expected omf:<pack>:<id>[#<recurrence_id>]"))
    if not str(fm.get("title") or "").strip():
        p.append(Problem("error", "title", "pack face needs title"))
    status = str(fm.get("status") or "")
    if status not in STATUSES:
        p.append(Problem("error", "status", f"status={status!r} not in {sorted(STATUSES)}"))
    sensitivity = str(fm.get("sensitivity") or "")
    if sensitivity not in SENSITIVITIES:
        p.append(Problem("error", "sensitivity", f"sensitivity={sensitivity!r} not in {sorted(SENSITIVITIES)}"))
    if "series" not in fm:
        p.append(Problem("error", "series", "series key is required; use explicit null for one-off"))
    elif fm.get("series") is not None and "#" not in omf_id:
        p.append(Problem("error", "series_identity", "non-null series requires omf_id with #<recurrence_id>"))
    start, end = fm.get("starts_at_utc"), fm.get("ends_at_utc")
    if status != "proposed" and start is None:
        p.append(Problem("error", "starts_at_utc", f"status={status} requires non-null starts_at_utc"))
    if start is not None and not _is_utc_timestamp(start):
        p.append(Problem("error", "starts_at_utc", "face timestamps must be complete UTC timestamps ending Z"))
    if end is not None and not _is_utc_timestamp(end):
        p.append(Problem("error", "ends_at_utc", "face timestamps must be complete UTC timestamps ending Z"))
    if _parse_utc(start) and _parse_utc(end) and _parse_utc(end) < _parse_utc(start):
        p.append(Problem("error", "ends_at_utc", "ends_at_utc is before starts_at_utc"))
    source = _nested(fm, "source")
    if not source or not str(source.get("authority") or "").strip():
        p.append(Problem("error", "source", "face source needs authority"))
    elif "calendar" in str(source.get("authority")).lower():
        for key in ("icalendar_uid", "sequence", "dtstamp"):
            if source.get(key) is None or str(source.get(key)).strip() == "":
                p.append(Problem("error", f"source.{key}", f"calendar-sourced meeting needs source.{key}"))
        if "recurrence_id" not in source:
            p.append(Problem("error", "source.recurrence_id", "calendar-sourced meeting needs source.recurrence_id (use null for a series record)"))
        if fm.get("series") is not None and not str(source.get("recurrence_id") or "").strip():
            p.append(Problem("error", "source.recurrence_id", "calendar occurrence with series needs source.recurrence_id"))
    if status in {"held", "capturing", "reconciling", "closed"}:
        capture = _nested(fm, "capture")
        if not capture:
            p.append(Problem("error", "capture", f"status={status} requires capture"))
        else:
            for slot in CAPTURE_SLOTS:
                if slot not in capture:
                    p.append(Problem("error", f"capture.{slot}", "every capture slot must be explicitly present, absent, or not_attempted"))
                elif capture[slot] not in CAPTURE_VALUES:
                    p.append(Problem("error", f"capture.{slot}", f"must be one of {sorted(CAPTURE_VALUES)}"))
    verified = _nested(fm, "verified")
    if not verified:
        p.append(Problem("error", "verified", "pack face requires OKF verified block"))
    else:
        for key in ("by", "at", "method", "stale_after"):
            if verified.get(key) is None or str(verified.get(key)).strip() == "":
                p.append(Problem("error", f"verified.{key}", "verified block requires by, at, method, and stale_after"))
    return p

def validate_artifact(fm: dict[str, Any]) -> list[Problem]:
    p = validate_common(fm)
    if not fm:
        return p
    if str(fm.get("type") or "") != "artifact":
        p.append(Problem("error", "type", "artifact document type must be artifact"))
    if str(fm.get("kind") or "") not in ARTIFACT_KINDS:
        p.append(Problem("error", "kind", f"kind={fm.get('kind')!r} not in {sorted(ARTIFACT_KINDS)}"))
    if not str(fm.get("locator") or "").strip():
        p.append(Problem("error", "locator", "artifact needs locator"))
    if "bytes" not in fm or not isinstance(fm.get("bytes"), int) or fm["bytes"] < 0:
        p.append(Problem("error", "bytes", "artifact needs non-negative integer bytes"))
    if not str(fm.get("retrieved_as") or "").strip():
        p.append(Problem("error", "retrieved_as", "artifact needs retrieved_as principal"))
    return p


def validate_participant(fm: dict[str, Any]) -> list[Problem]:
    p = validate_common(fm)
    if not fm:
        return p
    if str(fm.get("type") or "") != "participant":
        p.append(Problem("error", "type", "participant document type must be participant"))
    attended = _nested(fm, "attended")
    if "partstat" in attended or str(attended.get("observed") or "").upper() in {"ACCEPTED", "DECLINED", "TENTATIVE", "NEEDS-ACTION"}:
        p.append(Problem("error", "attended", "invited.partstat is invite-class and must not be copied into attended"))
    if attended.get("observed") is True:
        evidence = attended.get("evidence")
        by = attended.get("by")
        if not str(evidence or "").strip() and tier_of(by) != "human":
            p.append(Problem("error", "attended.observed", "observed attendance needs evidence or a human: by tier"))
    return p


def _quotes(fm: dict[str, Any]) -> list[Any]:
    q = fm.get("quotes")
    return q if isinstance(q, list) else []


def validate_outcome(fm: dict[str, Any]) -> list[Problem]:
    p = validate_common(fm)
    if not fm:
        return p
    typ = str(fm.get("type") or "")
    if typ == "decision":
        binding = fm.get("binding") is True
        by = author_of(fm, "decided_by", "authored_by")
        if binding and tier_of(by) == "agent":
            p.append(Problem("error", "binding", "agents MUST NOT author binding decisions"))
    elif typ == "commitment":
        state = str(fm.get("state") or "")
        if state not in OPEN_STATES:
            p.append(Problem("error", "state", f"state={state!r} not in {sorted(OPEN_STATES)}"))
        if state == "open" and not str(fm.get("owner") or "").strip():
            p.append(Problem("error", "owner", "open commitment requires a non-null owner"))
        by = author_of(fm, "authored_by", "proposed_by", "by")
        if tier_of(by) == "agent" and not _quotes(fm):
            p.append(Problem("error", "quotes", "agent-authored commitment derived from speech needs a quotes entry"))
    elif typ == "conflict":
        positions = fm.get("positions")
        if not isinstance(positions, list) or len(positions) < 2:
            p.append(Problem("error", "positions", "conflict requires at least two preserved positions"))
        # resolution: null is expressly valid; no rule applies to a non-null value.
    elif typ == "intent" and tier_of(author_of(fm, "authored_by", "proposed_by", "by")) == "agent":
        p.append(Problem("error", "intent_agent", "agents MUST NOT author type: intent"))
    return p


def validate_transcript_segments(path: Path) -> list[Problem]:
    p: list[Problem] = []
    for n, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            p.append(Problem("error", "segments.jsonl", f"line {n} is not JSON")); continue
        if not isinstance(obj, dict) or any(k not in obj for k in ("id", "start_ms", "end_ms", "speaker", "speaker_confidence", "text")):
            p.append(Problem("error", "segments.jsonl", f"line {n} lacks required segment fields")); continue
        if not isinstance(obj["speaker_confidence"], (int, float)) or not 0 <= obj["speaker_confidence"] <= 1:
            p.append(Problem("error", "segments.jsonl", f"line {n} speaker_confidence must be 0..1"))
    return p


def _doc_role(path: Path, root: Path) -> str:
    rel = path.relative_to(root)
    if rel == Path("index.md"):
        return "face"
    if "artifacts" in rel.parts:
        return "artifact"
    if "participants" in rel.parts:
        return "participant"
    if "outcomes" in rel.parts or "conflicts" in rel.parts:
        return "outcome"
    return "common"


def validate_pack(root: Path, *, strict: bool = False) -> list[Report]:
    """Validate a single meeting-occurrence pack directory."""
    root = root.resolve()
    reports: list[Report] = []
    face_path = root / "index.md"
    if not face_path.is_file():
        return [Report(face_path, [Problem("error", "face", "pack needs index.md")])]
    face_text = face_path.read_text(encoding="utf-8", errors="replace")
    face = parse_frontmatter(face_text)
    reports.append(Report(face_path, validate_face(face) + secret_problems(face_text)))
    log = root / "log.md"
    if not log.is_file():
        reports.append(Report(log, [Problem("warn", "log", "OKF append-only log.md is missing")]))
    else:
        reports.append(Report(log, secret_problems(log.read_text(encoding="utf-8", errors="replace"))))

    # Calendar sources preserve the original VEVENT. Basic structural validation avoids
    # reinventing an iCalendar parser while detecting accidental non-calendar files.
    source = _nested(face, "source")
    if "calendar" in str(source.get("authority") or "").lower():
        ics = root / "invite" / "original.ics"
        if not ics.is_file():
            reports.append(Report(ics, [Problem("error", "original.ics", "calendar-sourced meeting requires verbatim invite/original.ics")]))
        else:
            raw = ics.read_text(encoding="utf-8", errors="replace")
            q = secret_problems(raw)
            required = ("BEGIN:VCALENDAR", "BEGIN:VEVENT", "UID:", "RECURRENCE-ID:", "SEQUENCE:", "DTSTAMP:", "END:VEVENT", "END:VCALENDAR")
            if not all(x in raw for x in required):
                q.append(Problem("error", "original.ics", "calendar invite must contain a syntactically complete VEVENT identity"))
            if "RRULE:" in raw:
                q.append(Problem("error", "original.ics", "occurrence VEVENT must be RRULE-free; RRULE belongs on the series document"))
            reports.append(Report(ics, q))

    artifact_kinds: set[str] = set()
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path == face_path or path == log:
            continue
        rel = path.relative_to(root)
        # Large raw files may never live under artifacts; Markdown pointer docs are allowed.
        if "artifacts" in rel.parts and path.suffix.lower() not in {".md", ".markdown"} and path.stat().st_size > 1024 * 1024:
            reports.append(Report(path, [Problem("error", "artifact_media", "non-Markdown file under artifacts exceeds 1 MiB; store a pointer document instead")]))
            continue
        if path.suffix.lower() == ".jsonl":
            probs = validate_transcript_segments(path) if rel == Path("transcript/segments.jsonl") else []
            probs += secret_problems(path.read_text(encoding="utf-8", errors="replace"))
            reports.append(Report(path, probs)); continue
        if path.suffix.lower() == ".ics":
            continue  # original.ics was inspected above; no requirements for other ICS files.
        if path.suffix.lower() not in {".md", ".markdown"}:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        fm = parse_frontmatter(text)
        role = _doc_role(path, root)
        if role == "artifact":
            probs = validate_artifact(fm)
            if str(fm.get("kind") or ""):
                artifact_kinds.add(str(fm.get("kind")))
        elif role == "participant":
            probs = validate_participant(fm)
        elif role == "outcome":
            probs = validate_outcome(fm)
        else:
            probs = validate_common(fm)
            # Agent intent rule applies no matter where it appears.
            if fm.get("type") == "intent" and tier_of(author_of(fm, "authored_by", "proposed_by", "by")) == "agent":
                probs.append(Problem("error", "intent_agent", "agents MUST NOT author type: intent"))
        reports.append(Report(path, probs + secret_problems(text)))

    capture = _nested(face, "capture")
    for slot in CAPTURE_SLOTS:
        if capture.get(slot) == "present" and slot not in artifact_kinds:
            reports.append(Report(face_path, [Problem("error", f"capture.{slot}", f"capture says present but no artifacts/ pointer with kind: {slot}" )]))
    # validate_outcome enforces an owner on every open commitment. That stronger
    # per-document invariant necessarily enforces the status: closed close gate too,
    # without duplicating the focused error on the commitment document.
    if strict:
        for report in reports:
            for prob in report.problems:
                if prob.level == "warn":
                    prob.level = "error"
    return reports


def _meeting_roots(directory: Path) -> Iterator[Path]:
    for index in directory.rglob("index.md"):
        fm = parse_frontmatter(index.read_text(encoding="utf-8", errors="replace"))
        if fm.get("type") == "meeting" or fm.get("profile") == "omf":
            yield index.parent


def _duplicates(reports: list[Report]) -> list[Report]:
    groups: dict[str, list[Report]] = {}
    for report in reports:
        if report.path.name != "index.md":
            continue
        fm = parse_frontmatter(report.path.read_text(encoding="utf-8", errors="replace"))
        value = fm.get("omf_id")
        if isinstance(value, str) and value:
            groups.setdefault(value, []).append(report)
    for omf_id, members in groups.items():
        if len(members) > 1:
            locations = ", ".join(str(x.path.parent) for x in members)
            for report in members:
                report.problems.append(Problem("error", "omf_id_duplicate", f"duplicate omf_id {omf_id!r} in catalogue: {locations}"))
    return reports


def validate_path(path: Path, *, strict: bool = False) -> list[Report]:
    path = path.resolve()
    if path.is_file():
        text = path.read_text(encoding="utf-8", errors="replace")
        fm = parse_frontmatter(text)
        if path.name == "index.md" and fm.get("type") == "meeting":
            reports = [Report(path, validate_face(fm) + secret_problems(text))]
        else:
            reports = [Report(path, validate_common(fm) + secret_problems(text))]
        if strict:
            for report in reports:
                for prob in report.problems:
                    if prob.level == "warn":
                        prob.level = "error"
        return reports
    if not path.exists():
        return [Report(path, [Problem("error", "path", "not found")])]
    if (path / "index.md").is_file():
        return validate_pack(path, strict=strict)
    roots = list(_meeting_roots(path))
    if not roots:
        return [Report(path, [Problem("error", "pack", "directory contains no OMF meeting packs")])]
    all_reports: list[Report] = []
    for root in roots:
        all_reports.extend(validate_pack(root, strict=strict))
    return _duplicates(all_reports)


def selftest() -> int:
    base = {
        "okf_version": OKF_VERSION, "omf_version": OMF_VERSION, "profile": "omf", "type": "meeting",
        "omf_id": "omf:test:uid#2026-01-01T10:00:00Z", "title": "Test", "status": "closed", "sensitivity": "internal",
        "starts_at_utc": "2026-01-01T10:00:00Z", "ends_at_utc": "2026-01-01T11:00:00Z", "series": "series/x.md",
        "source": {"authority": "human"}, "capture": {"recording": "absent", "transcript": "not_attempted", "notes": "absent"},
        "verified": {"by": "human:test", "at": "2026-01-01", "method": "selftest", "stale_after": "2027-01-01"},
    }
    errors = lambda d: {x.rule for x in validate_face(d) if x.level == "error"}
    assert not errors(base)
    assert "capture.notes" in errors({**base, "capture": {"recording": "absent", "transcript": "absent"}})
    assert "starts_at_utc" in errors({**base, "starts_at_utc": "2026-01-01T10:00:00-06:00"})
    assert "ends_at_utc" in errors({**base, "ends_at_utc": "2026-01-01T09:00:00Z"})
    assert "series_identity" in errors({**base, "omf_id": "omf:test:uid"})
    assert any(x.rule == "attended.observed" for x in validate_participant({"okf_version": "0.2", "omf_version": "0.1.0", "type": "participant", "attended": {"observed": True, "by": "agent:x"}}))
    assert any(x.rule == "owner" for x in validate_outcome({"okf_version": "0.2", "omf_version": "0.1.0", "type": "commitment", "state": "open", "owner": None}))
    assert any(x.rule == "binding" for x in validate_outcome({"okf_version": "0.2", "omf_version": "0.1.0", "type": "decision", "binding": True, "decided_by": "agent:x"}))
    assert secret_problems("Authorization: Bearer abcdefghijklmnopqrstuvwxyz123456")
    print("selftest OK — face gates, UTC times, capture honesty, attendance, outcomes, and secret detection")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="omf.validate", description=__doc__)
    ap.add_argument("paths", nargs="*", type=Path)
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--strict", action="store_true", help="treat warnings as errors")
    args = ap.parse_args(argv)
    if args.selftest:
        return selftest()
    if not args.paths:
        ap.error("give a file or pack directory")
    reports: list[Report] = []
    for path in args.paths:
        reports.extend(validate_path(path, strict=args.strict))
    _duplicates(reports)
    bad = 0
    for report in reports:
        bad += bool(report.errors)
        if not report.problems:
            print(f"ok: {report.path}")
        for prob in report.problems:
            print(f"{report.path}:{prob.rule}: {prob.level}: {prob.detail}")
    print(f"{len(reports)} path(s), {bad} with errors")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
