"""SQLite persistence and full-text search."""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import Any

from src.models import Alert, DetectedObject, Frame


class Indexer:
    """Persist the patrol stream and expose indexed frame/object/alert queries."""

    def __init__(
        self,
        database_path: str | Path = ":memory:",
        *,
        check_same_thread: bool = True,
    ) -> None:
        self.database_path = str(database_path)
        if self.database_path != ":memory:":
            Path(self.database_path).parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(
            self.database_path, check_same_thread=check_same_thread
        )
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self._create_schema()

    def _create_schema(self) -> None:
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS frames (
                id TEXT PRIMARY KEY,
                ts TEXT NOT NULL,
                zone TEXT NOT NULL,
                lat REAL NOT NULL,
                lon REAL NOT NULL,
                altitude REAL NOT NULL,
                battery REAL NOT NULL,
                description TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS objects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                frame_id TEXT NOT NULL REFERENCES frames(id) ON DELETE CASCADE,
                type TEXT NOT NULL,
                color TEXT,
                make_model TEXT,
                activity TEXT NOT NULL,
                label TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                frame_id TEXT NOT NULL REFERENCES frames(id) ON DELETE CASCADE,
                ts TEXT NOT NULL,
                rule TEXT NOT NULL,
                severity TEXT NOT NULL,
                message TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_frames_ts ON frames(ts);
            CREATE INDEX IF NOT EXISTS idx_objects_type ON objects(type);
            CREATE INDEX IF NOT EXISTS idx_objects_label ON objects(label);
            CREATE VIRTUAL TABLE IF NOT EXISTS frames_fts USING fts5(
                frame_id UNINDEXED,
                description
            );
            """
        )
        self.connection.commit()

    def add_frame(
        self, frame: Frame, objects: list[DetectedObject], alerts: list[Alert]
    ) -> None:
        """Insert or replace one frame and all data associated with it."""
        telemetry = frame.telemetry
        with self.connection:
            self.connection.execute("DELETE FROM frames_fts WHERE frame_id = ?", (frame.frame_id,))
            self.connection.execute("DELETE FROM frames WHERE id = ?", (frame.frame_id,))
            self.connection.execute(
                """
                INSERT INTO frames(id, ts, zone, lat, lon, altitude, battery, description)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    frame.frame_id,
                    frame.timestamp.isoformat(),
                    telemetry.zone,
                    telemetry.lat,
                    telemetry.lon,
                    telemetry.altitude_m,
                    telemetry.battery_pct,
                    frame.description,
                ),
            )
            self.connection.executemany(
                """
                INSERT INTO objects(frame_id, type, color, make_model, activity, label)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        frame.frame_id,
                        obj.type,
                        obj.color,
                        obj.make_model,
                        obj.activity,
                        obj.label,
                    )
                    for obj in objects
                ],
            )
            self.connection.executemany(
                """
                INSERT INTO alerts(frame_id, ts, rule, severity, message)
                VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (
                        alert.frame_id,
                        alert.timestamp.isoformat(),
                        alert.rule,
                        alert.severity,
                        alert.message,
                    )
                    for alert in alerts
                ],
            )
            self.connection.execute(
                "INSERT INTO frames_fts(frame_id, description) VALUES (?, ?)",
                (frame.frame_id, frame.description),
            )

    def _frame_results(self, frame_ids: list[str]) -> list[dict[str, Any]]:
        if not frame_ids:
            return []
        placeholders = ",".join("?" for _ in frame_ids)
        frame_rows = self.connection.execute(
            f"SELECT * FROM frames WHERE id IN ({placeholders}) ORDER BY ts, id",
            frame_ids,
        ).fetchall()
        object_rows = self.connection.execute(
            f"SELECT * FROM objects WHERE frame_id IN ({placeholders}) ORDER BY id",
            frame_ids,
        ).fetchall()
        objects_by_frame: dict[str, list[dict[str, Any]]] = {}
        for row in object_rows:
            objects_by_frame.setdefault(row["frame_id"], []).append(dict(row))
        results = []
        for row in frame_rows:
            item = dict(row)
            item["objects"] = objects_by_frame.get(row["id"], [])
            results.append(item)
        return results

    def query_by_time(self, start: str, end: str) -> list[dict[str, Any]]:
        """Return frames whose local clock time falls in the inclusive range."""
        start_time = start[-8:-3] if len(start) > 5 else start
        end_time = end[-8:-3] if len(end) > 5 else end
        if start_time <= end_time:
            rows = self.connection.execute(
                "SELECT id FROM frames WHERE substr(ts, 12, 5) BETWEEN ? AND ? ORDER BY ts",
                (start_time, end_time),
            ).fetchall()
        else:
            rows = self.connection.execute(
                "SELECT id FROM frames WHERE substr(ts, 12, 5) >= ? OR substr(ts, 12, 5) <= ? ORDER BY ts",
                (start_time, end_time),
            ).fetchall()
        return self._frame_results([row["id"] for row in rows])

    def query_by_object(
        self,
        type: str | None = None,
        color: str | None = None,
        make: str | None = None,
        activity: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return frames containing objects matching any supplied attributes."""
        conditions: list[str] = []
        parameters: list[str] = []
        if type:
            normalized_type = type.lower()
            if normalized_type in {"truck", "van", "car", "sedan", "pickup"}:
                conditions.append("o.type = 'vehicle'")
                terms = {
                    "truck": ("truck", "f150", "pickup"),
                    "pickup": ("pickup", "truck", "f150"),
                    "van": ("van",),
                    "car": ("car", "sedan"),
                    "sedan": ("sedan",),
                }[normalized_type]
                conditions.append(
                    "("
                    + " OR ".join(
                        "(lower(o.make_model) LIKE ? OR lower(o.label) LIKE ?)"
                        for _ in terms
                    )
                    + ")"
                )
                for term in terms:
                    parameters.extend((f"%{term}%", f"%{term}%"))
            else:
                conditions.append("lower(o.type) = ?")
                parameters.append(normalized_type)
        if color:
            conditions.append("lower(o.color) LIKE ?")
            parameters.append(f"%{color.lower()}%")
        if make:
            conditions.append(
                "(lower(o.make_model) LIKE ? OR lower(o.label) LIKE ?)"
            )
            parameters.extend((f"%{make.lower()}%", f"%{make.lower()}%"))
        if activity:
            conditions.append("lower(o.activity) LIKE ?")
            parameters.append(f"%{activity.lower()}%")
        if not conditions:
            rows = self.connection.execute("SELECT id FROM frames ORDER BY ts").fetchall()
        else:
            where_clause = " AND ".join(conditions)
            rows = self.connection.execute(
                f"SELECT DISTINCT f.id FROM frames f JOIN objects o ON o.frame_id = f.id "
                f"WHERE {where_clause} ORDER BY f.ts",
                parameters,
            ).fetchall()
        return self._frame_results([row["id"] for row in rows])

    def search_text(self, query: str) -> list[dict[str, Any]]:
        """Search frame descriptions with safely quoted FTS5 terms."""
        terms = re.findall(r"[A-Za-z0-9_]+", query)
        if not terms:
            return []
        match_expression = " AND ".join(f'"{term.replace(chr(34), chr(34) * 2)}"' for term in terms)
        rows = self.connection.execute(
            """
            SELECT frame_id FROM frames_fts
            WHERE frames_fts MATCH ?
            ORDER BY bm25(frames_fts), frame_id
            """,
            (match_expression,),
        ).fetchall()
        return self._frame_results([row["frame_id"] for row in rows])

    def count_object_events(self, label: str, activity: str | None = None) -> int:
        """Count matching object detections, optionally restricted to an activity."""
        query = """
            SELECT COUNT(*) FROM objects
            WHERE (lower(label) LIKE ? OR lower(make_model) LIKE ?)
        """
        parameters: list[str] = [f"%{label.lower()}%", f"%{label.lower()}%"]
        if activity:
            query += " AND lower(activity) = ?"
            parameters.append(activity.lower())
        return int(self.connection.execute(query, parameters).fetchone()[0])

    def list_alerts(self, severity: str | None = None) -> list[dict[str, Any]]:
        query = "SELECT * FROM alerts"
        parameters: tuple[str, ...] = ()
        if severity:
            query += " WHERE severity = ?"
            parameters = (severity.upper(),)
        query += " ORDER BY ts, id"
        return [dict(row) for row in self.connection.execute(query, parameters).fetchall()]

    def close(self) -> None:
        self.connection.close()
