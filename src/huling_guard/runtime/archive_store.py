from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any, Iterable

from huling_guard.runtime.session_report import format_session_report_markdown


class RuntimeArchiveStore:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()
        self.sessions_dir = self.root / "sessions"
        self.database_path = self.root / "runtime_sessions.sqlite3"
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _ensure_schema(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    archived_at TEXT NOT NULL,
                    session_name TEXT,
                    dominant_state TEXT,
                    duration_seconds REAL NOT NULL,
                    incident_total INTEGER NOT NULL,
                    peak_risk_score REAL NOT NULL,
                    report_fingerprint TEXT,
                    report_json TEXT NOT NULL,
                    report_markdown TEXT NOT NULL,
                    json_path TEXT NOT NULL,
                    markdown_path TEXT NOT NULL
                )
                """
            )
            columns = {
                str(row["name"])
                for row in connection.execute("PRAGMA table_info(sessions)").fetchall()
            }
            if "report_fingerprint" not in columns:
                connection.execute("ALTER TABLE sessions ADD COLUMN report_fingerprint TEXT")
                rows = connection.execute(
                    "SELECT session_id, report_json FROM sessions",
                ).fetchall()
                for row in rows:
                    payload = json.loads(str(row["report_json"]))
                    connection.execute(
                        "UPDATE sessions SET report_fingerprint = ? WHERE session_id = ?",
                        (
                            self._compute_report_fingerprint(payload),
                            str(row["session_id"]),
                        ),
                    )
            connection.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_sessions_report_fingerprint
                ON sessions(report_fingerprint)
                """
            )
            connection.commit()

    def _build_session_id(self) -> str:
        return datetime.now().strftime("%Y%m%d_%H%M%S_%f")

    def _json_path(self, session_id: str) -> Path:
        return self.sessions_dir / f"{session_id}.json"

    def _markdown_path(self, session_id: str) -> Path:
        return self.sessions_dir / f"{session_id}.md"

    def _compute_report_fingerprint(self, report: dict[str, Any]) -> str:
        canonical_payload = dict(report)
        canonical_payload.pop("session_id", None)
        canonical_payload.pop("archived_at", None)
        encoded = json.dumps(
            canonical_payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def _select_record(self, session_id: str) -> dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    session_id,
                    archived_at,
                    session_name,
                    dominant_state,
                    duration_seconds,
                    incident_total,
                    peak_risk_score,
                    json_path,
                    markdown_path
                FROM sessions
                WHERE session_id = ?
                """,
                (session_id,),
            ).fetchone()
        if row is None:
            raise FileNotFoundError(session_id)
        return dict(row)

    def _select_record_by_fingerprint(self, fingerprint: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT session_id FROM sessions WHERE report_fingerprint = ?",
                (fingerprint,),
            ).fetchone()
        if row is None:
            return None
        return self._select_record(str(row["session_id"]))

    def store_report(self, report: dict[str, Any]) -> tuple[dict[str, Any], bool]:
        report_payload = dict(report)
        fingerprint = self._compute_report_fingerprint(report_payload)
        existing = self._select_record_by_fingerprint(fingerprint)
        if existing is not None:
            return existing, False

        session_id = str(report_payload.get("session_id") or self._build_session_id())
        report_payload["session_id"] = session_id
        report_payload["archived_at"] = str(
            report_payload.get("archived_at") or datetime.now().isoformat(timespec="seconds")
        )

        json_path = self._json_path(session_id)
        markdown_path = self._markdown_path(session_id)
        markdown_text = format_session_report_markdown(report_payload)
        json_path.write_text(
            json.dumps(report_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        markdown_path.write_text(
            markdown_text,
            encoding="utf-8",
        )

        record = {
            "session_id": session_id,
            "archived_at": report_payload["archived_at"],
            "session_name": report_payload.get("session_name"),
            "dominant_state": report_payload.get("dominant_state"),
            "duration_seconds": float(report_payload.get("duration_seconds") or 0.0),
            "incident_total": int(report_payload.get("incident_total") or 0),
            "peak_risk_score": float((report_payload.get("peak_risk") or {}).get("risk_score") or 0.0),
            "json_path": str(json_path),
            "markdown_path": str(markdown_path),
        }
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO sessions (
                    session_id,
                    archived_at,
                    session_name,
                    dominant_state,
                    duration_seconds,
                    incident_total,
                    peak_risk_score,
                    report_fingerprint,
                    report_json,
                    report_markdown,
                    json_path,
                    markdown_path
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    record["archived_at"],
                    record["session_name"],
                    record["dominant_state"],
                    record["duration_seconds"],
                    record["incident_total"],
                    record["peak_risk_score"],
                    fingerprint,
                    json.dumps(report_payload, ensure_ascii=False),
                    markdown_text,
                    record["json_path"],
                    record["markdown_path"],
                ),
            )
            connection.commit()
        return record, True

    def archive_report(self, report: dict[str, Any]) -> dict[str, Any]:
        record, _ = self.store_report(report)
        return record

    def import_report_file(self, path: str | Path) -> tuple[dict[str, Any], bool]:
        report_path = Path(path).resolve()
        payload = json.loads(report_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"report payload must be an object: {report_path}")
        return self.store_report(payload)

    def import_report_files(self, inputs: Iterable[str | Path]) -> dict[str, Any]:
        input_list = [Path(item).resolve() for item in inputs]
        discovered: list[Path] = []
        seen: set[Path] = set()
        for candidate in input_list:
            paths = sorted(candidate.rglob("*.json")) if candidate.is_dir() else [candidate]
            for path in paths:
                if path in seen or not path.is_file():
                    continue
                seen.add(path)
                discovered.append(path)

        imported: list[dict[str, Any]] = []
        skipped: list[dict[str, Any]] = []
        errors: list[dict[str, str]] = []
        for path in discovered:
            try:
                record, created = self.import_report_file(path)
            except Exception as error:  # pragma: no cover
                errors.append({"path": str(path), "error": str(error)})
                continue
            if created:
                imported.append(record)
            else:
                skipped.append(record)

        return {
            "input_count": len(input_list),
            "discovered_count": len(discovered),
            "imported_count": len(imported),
            "skipped_count": len(skipped),
            "error_count": len(errors),
            "imported": imported,
            "skipped": skipped,
            "errors": errors,
        }

    def list_archives(
        self,
        limit: int = 20,
        *,
        dominant_state: str | None = None,
        incidents_only: bool = False,
    ) -> list[dict[str, Any]]:
        conditions: list[str] = []
        parameters: list[Any] = []
        if dominant_state:
            conditions.append("dominant_state = ?")
            parameters.append(dominant_state)
        if incidents_only:
            conditions.append("incident_total > 0")
        where_clause = ""
        if conditions:
            where_clause = "WHERE " + " AND ".join(conditions)
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT
                    session_id,
                    archived_at,
                    session_name,
                    dominant_state,
                    duration_seconds,
                    incident_total,
                    peak_risk_score,
                    json_path,
                    markdown_path
                FROM sessions
                {where_clause}
                ORDER BY archived_at DESC
                LIMIT ?
                """,
                (*parameters, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def summarize_archives(self) -> dict[str, Any]:
        with self._connect() as connection:
            totals = connection.execute(
                """
                SELECT
                    COUNT(*) AS archive_total,
                    COALESCE(SUM(incident_total), 0) AS total_incidents,
                    COALESCE(AVG(duration_seconds), 0.0) AS mean_duration_seconds,
                    COALESCE(MAX(peak_risk_score), 0.0) AS max_peak_risk_score,
                    COALESCE(SUM(CASE WHEN incident_total > 0 THEN 1 ELSE 0 END), 0) AS sessions_with_incidents
                FROM sessions
                """
            ).fetchone()
            dominant_state_rows = connection.execute(
                """
                SELECT dominant_state, COUNT(*) AS count
                FROM sessions
                GROUP BY dominant_state
                ORDER BY count DESC, dominant_state ASC
                """
            ).fetchall()
            latest = connection.execute(
                """
                SELECT session_id, session_name, archived_at, dominant_state
                FROM sessions
                ORDER BY archived_at DESC
                LIMIT 1
                """
            ).fetchone()

        return {
            "archive_total": int(totals["archive_total"] or 0),
            "total_incidents": int(totals["total_incidents"] or 0),
            "mean_duration_seconds": float(totals["mean_duration_seconds"] or 0.0),
            "max_peak_risk_score": float(totals["max_peak_risk_score"] or 0.0),
            "sessions_with_incidents": int(totals["sessions_with_incidents"] or 0),
            "dominant_state_counts": {
                str(row["dominant_state"] or "unknown"): int(row["count"] or 0)
                for row in dominant_state_rows
            },
            "latest_archive": dict(latest) if latest is not None else None,
        }

    def load_archive_report(self, session_id: str) -> dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT report_json FROM sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        if row is None:
            raise FileNotFoundError(session_id)
        return json.loads(str(row["report_json"]))

    def load_archive_markdown(self, session_id: str) -> str:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT report_markdown FROM sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        if row is None:
            raise FileNotFoundError(session_id)
        return str(row["report_markdown"])
