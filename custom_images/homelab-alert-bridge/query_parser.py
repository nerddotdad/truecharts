"""Mini JQL-style query language for incident and alert lists."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Literal

SEVERITY_RANK = {"critical": 0, "warning": 1, "info": 2, "unknown": 3}

TOKEN_RE = re.compile(
    r"""
    (\w+)\s*~\s*"([^"]+)" |
    (\w+)\s*~\s*'([^']+)' |
    (\w+)\s*~\s*(\S+) |
    (\w+)\s*>=\s*(\S+) |
    (\w+)\s*in\s*\(\s*([^)]+)\) |
    (\w+):(\S+) |
    "([^"]+)" |
    '([^']+)' |
    (\S+)
    """,
    re.VERBOSE | re.IGNORECASE,
)


@dataclass
class ParsedQuery:
    mode: Literal["incidents", "alerts"]
    clauses: list[str] = field(default_factory=list)
    params: list[Any] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def _glob_to_like(value: str) -> str:
    if value.endswith("*"):
        return value[:-1] + "%"
    if "*" in value:
        return value.replace("*", "%")
    return value


def _split_or_groups(raw: str) -> list[str]:
    parts = re.split(r"\s+OR\s+", raw, flags=re.IGNORECASE)
    return [p.strip() for p in parts if p.strip()]


def _parse_tokens(group: str) -> list[tuple[str, str, str]]:
    """Return list of (field, op, value). op: eq, contains, gte, in."""
    tokens: list[tuple[str, str, str]] = []
    for match in TOKEN_RE.finditer(group):
        if match.group(1):
            tokens.append((match.group(1).lower(), "contains", match.group(2)))
        elif match.group(3):
            tokens.append((match.group(3).lower(), "contains", match.group(4)))
        elif match.group(5):
            tokens.append((match.group(5).lower(), "contains", match.group(6)))
        elif match.group(7):
            tokens.append((match.group(7).lower(), "gte", match.group(8)))
        elif match.group(9):
            tokens.append((match.group(9).lower(), "in", match.group(10)))
        elif match.group(11):
            tokens.append((match.group(11).lower(), "eq", match.group(12)))
        elif match.group(13):
            tokens.append(("text", "contains", match.group(13)))
        elif match.group(14):
            tokens.append(("text", "contains", match.group(14)))
        elif match.group(15):
            val = match.group(15)
            if ":" in val:
                field, _, rhs = val.partition(":")
                tokens.append((field.lower(), "eq", rhs))
            else:
                tokens.append(("text", "contains", val))
    return tokens


def _severity_lte_sql(column: str, minimum: str) -> tuple[str, list[Any]]:
    rank = SEVERITY_RANK.get(minimum.lower(), 99)
    allowed = [k for k, v in SEVERITY_RANK.items() if v <= rank]
    placeholders = ",".join("?" for _ in allowed)
    return f"{column} IN ({placeholders})", allowed


def _apply_incident_token(field: str, op: str, value: str, out: ParsedQuery) -> None:
    if field == "text":
        pattern = f"%{value}%"
        out.clauses.append(
            "(i.title LIKE ? COLLATE NOCASE OR i.summary LIKE ? COLLATE NOCASE OR i.id LIKE ? COLLATE NOCASE)"
        )
        out.params.extend([pattern, pattern, pattern])
        return

    if field == "manual":
        truth = value.lower() in ("true", "1", "yes")
        out.clauses.append("json_extract(i.enrichment, '$.manual') = ?")
        out.params.append(1 if truth else 0)
        return

    if field == "tag":
        pattern = f'%"{value}"%'
        out.clauses.append("i.enrichment LIKE ? ESCAPE '\\'")
        out.params.append(pattern)
        return

    if field in ("alertname", "namespace", "severity", "job_name", "pod"):
        col = f"$.labels.{field}"
        if op == "contains":
            out.clauses.append(
                f"""EXISTS (
                    SELECT 1 FROM alerts a
                    WHERE a.incident_id = i.id
                      AND json_extract(a.payload, '{col}') LIKE ? COLLATE NOCASE
                )"""
            )
            out.params.append(f"%{value}%")
        elif op == "eq":
            out.clauses.append(
                f"""EXISTS (
                    SELECT 1 FROM alerts a
                    WHERE a.incident_id = i.id
                      AND json_extract(a.payload, '{col}') = ?
                )"""
            )
            out.params.append(_glob_to_like(value) if "*" in value else value)
        return

    column_map = {
        "status": "i.status",
        "severity": "i.severity",
        "title": "i.title",
        "summary": "i.summary",
        "id": "i.id",
    }
    column = column_map.get(field)
    if not column:
        out.errors.append(f"unknown field: {field}")
        return

    if field == "severity" and op == "gte":
        clause, params = _severity_lte_sql(column, value)
        out.clauses.append(clause)
        out.params.extend(params)
        return

    if op == "contains":
        out.clauses.append(f"{column} LIKE ? COLLATE NOCASE")
        out.params.append(f"%{value}%")
    elif op == "in":
        values = [v.strip().strip("'\"") for v in value.split(",") if v.strip()]
        if not values:
            out.errors.append(f"empty in () for {field}")
            return
        placeholders = ",".join("?" for _ in values)
        out.clauses.append(f"{column} IN ({placeholders})")
        out.params.extend(values)
    else:
        if "*" in value:
            out.clauses.append(f"{column} LIKE ? COLLATE NOCASE")
            out.params.append(_glob_to_like(value))
        else:
            out.clauses.append(f"{column} = ?")
            out.params.append(value)


def _apply_alert_token(field: str, op: str, value: str, out: ParsedQuery) -> None:
    if field == "text":
        pattern = f"%{value}%"
        out.clauses.append(
            """(
                json_extract(payload, '$.labels.alertname') LIKE ? COLLATE NOCASE OR
                json_extract(payload, '$.annotations.summary') LIKE ? COLLATE NOCASE OR
                json_extract(payload, '$.annotations.description') LIKE ? COLLATE NOCASE OR
                fingerprint LIKE ? COLLATE NOCASE
            )"""
        )
        out.params.extend([pattern, pattern, pattern, pattern])
        return

    if field == "fingerprint":
        out.clauses.append("fingerprint LIKE ? COLLATE NOCASE" if op == "contains" else "fingerprint = ?")
        out.params.append(f"%{value}%" if op == "contains" else value)
        return

    if field in ("alertname", "namespace", "severity", "job_name", "pod", "status"):
        if field == "status":
            col = "alerts.status"
        else:
            col = f"json_extract(payload, '$.labels.{field}')"
        if op == "contains":
            out.clauses.append(f"{col} LIKE ? COLLATE NOCASE")
            out.params.append(f"%{value}%")
        elif op == "in":
            values = [v.strip().strip("'\"") for v in value.split(",") if v.strip()]
            placeholders = ",".join("?" for _ in values)
            out.clauses.append(f"{col} IN ({placeholders})")
            out.params.extend(values)
        elif field == "severity" and op == "gte":
            clause, params = _severity_lte_sql(col, value)
            out.clauses.append(clause)
            out.params.extend(params)
        else:
            if "*" in value:
                out.clauses.append(f"{col} LIKE ? COLLATE NOCASE")
                out.params.append(_glob_to_like(value))
            else:
                out.clauses.append(f"{col} = ?")
                out.params.append(value)
        return

    out.errors.append(f"unknown alert field: {field}")


def parse_query(raw: str, *, mode: Literal["incidents", "alerts"]) -> ParsedQuery:
    out = ParsedQuery(mode=mode)
    text = (raw or "").strip()
    if not text:
        return out

    groups = _split_or_groups(text)
    or_parts: list[str] = []
    for group in groups:
        and_clauses: list[str] = []
        and_params: list[Any] = []
        sub = ParsedQuery(mode=mode)
        for field, op, value in _parse_tokens(group):
            if mode == "incidents":
                _apply_incident_token(field, op, value, sub)
            else:
                _apply_alert_token(field, op, value, sub)
        if sub.errors:
            out.errors.extend(sub.errors)
            continue
        if sub.clauses:
            and_clauses.append("(" + " AND ".join(sub.clauses) + ")")
            and_params.extend(sub.params)
        if and_clauses:
            or_parts.append(and_clauses[0])
            out.params.extend(and_params)

    if or_parts:
        out.clauses.append("(" + " OR ".join(or_parts) + ")")
    return out
