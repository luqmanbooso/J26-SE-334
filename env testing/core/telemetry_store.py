"""Relational telemetry store for Component 1 (Proposal Section 4 & Functional Spec #6).

Supports PostgreSQL when configured via ``HEART_PG_DSN`` or ``DATABASE_URL``
(using psycopg/psycopg2 if installed) and falls back cleanly to local SQLite
in WAL mode so air-gapped environments persist millisecond-precision logs and
failure attributions with zero external infrastructure dependencies.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from typing import Any, Dict, List, Optional


class TelemetryStore:
    """Thread-safe relational store persisting C1 events and attribution reports."""

    def __init__(
        self,
        sqlite_path: Optional[str] = None,
        pg_dsn: Optional[str] = None,
    ) -> None:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        default_db = os.path.join(base_dir, "results", "heart_telemetry.db")
        self.sqlite_path = sqlite_path or default_db
        self.pg_dsn = pg_dsn or os.environ.get("HEART_PG_DSN") or os.environ.get("DATABASE_URL")
        self._lock = threading.Lock()
        self.backend = "sqlite"
        self._pg_mod = None

        if self.pg_dsn and self.pg_dsn.startswith("postgres"):
            for mod_name in ("psycopg", "psycopg2"):
                try:
                    self._pg_mod = __import__(mod_name)
                    self.backend = "postgresql"
                    break
                except ImportError:
                    continue

        self._init_schema()

    def _connect_sqlite(self) -> sqlite3.Connection:
        parent = os.path.dirname(os.path.abspath(self.sqlite_path))
        if parent:
            os.makedirs(parent, exist_ok=True)
        conn = sqlite3.connect(self.sqlite_path, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _connect(self):
        if self.backend == "postgresql" and self._pg_mod is not None:
            return self._pg_mod.connect(self.pg_dsn)
        return self._connect_sqlite()

    def _placeholder(self) -> str:
        return "%s" if self.backend == "postgresql" else "?"

    def _init_schema(self) -> None:
        id_col = "SERIAL PRIMARY KEY" if self.backend == "postgresql" else "INTEGER PRIMARY KEY AUTOINCREMENT"
        ddl_events = f"""
        CREATE TABLE IF NOT EXISTS perturbation_events (
            id {id_col},
            epoch_ms BIGINT NOT NULL,
            timestamp_iso TEXT NOT NULL,
            category TEXT NOT NULL,
            action TEXT NOT NULL,
            parameters_json TEXT NOT NULL,
            status TEXT NOT NULL,
            injection_latency_ms REAL NOT NULL,
            latency_compliant INTEGER NOT NULL,
            host_cpu_pct REAL NOT NULL,
            host_mem_pct REAL NOT NULL,
            overhead_compliant INTEGER NOT NULL
        )
        """
        ddl_attr = f"""
        CREATE TABLE IF NOT EXISTS failure_attributions (
            id {id_col},
            analysis_timestamp TEXT NOT NULL,
            failure_id TEXT NOT NULL,
            failure_type TEXT NOT NULL,
            primary_trigger TEXT NOT NULL,
            confidence REAL NOT NULL,
            report_json TEXT NOT NULL
        )
        """
        with self._lock:
            conn = self._connect()
            try:
                cur = conn.cursor()
                cur.execute(ddl_events)
                cur.execute(ddl_attr)
                conn.commit()
            finally:
                conn.close()

    def insert_event(self, entry: Dict[str, Any]) -> None:
        """Persists a single millisecond-timestamped perturbation event."""
        ph = self._placeholder()
        over = entry.get("host_overhead", {})
        sql = f"""
        INSERT INTO perturbation_events (
            epoch_ms, timestamp_iso, category, action, parameters_json, status,
            injection_latency_ms, latency_compliant, host_cpu_pct, host_mem_pct, overhead_compliant
        ) VALUES ({', '.join([ph] * 11)})
        """
        mem_val = over.get("process_mem_percent", over.get("mem_percent", 0.0))
        params = (
            int(entry.get("epoch_ms", 0)),
            str(entry.get("timestamp", "")),
            str(entry.get("category", "")),
            str(entry.get("action", "")),
            json.dumps(entry.get("parameters", {})),
            str(entry.get("status", "APPLIED")),
            float(entry.get("injection_latency_ms", 0.0)),
            1 if entry.get("latency_compliant", True) else 0,
            float(over.get("cpu_percent", 0.0)),
            float(mem_val),
            1 if over.get("compliant", True) else 0,
        )
        with self._lock:
            conn = self._connect()
            try:
                cur = conn.cursor()
                cur.execute(sql, params)
                conn.commit()
            finally:
                conn.close()

    def query_events(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Retrieves recent perturbation events ordered newest-first."""
        ph = self._placeholder()
        sql = f"""
        SELECT epoch_ms, timestamp_iso, category, action, parameters_json, status,
               injection_latency_ms, latency_compliant, host_cpu_pct, host_mem_pct, overhead_compliant
        FROM perturbation_events
        ORDER BY epoch_ms DESC, id DESC
        LIMIT {ph}
        """
        with self._lock:
            conn = self._connect()
            try:
                cur = conn.cursor()
                cur.execute(sql, (int(limit),))
                rows = cur.fetchall()
            finally:
                conn.close()
        out: List[Dict[str, Any]] = []
        for r in reversed(rows):
            out.append({
                "epoch_ms": r[0],
                "timestamp": r[1],
                "category": r[2],
                "action": r[3],
                "parameters": json.loads(r[4]),
                "status": r[5],
                "injection_latency_ms": r[6],
                "latency_compliant": bool(r[7]),
                "host_overhead": {
                    "cpu_percent": r[8],
                    "process_mem_percent": r[9],
                    "compliant": bool(r[10]),
                },
            })
        return out

    def insert_attribution_report(self, report: Dict[str, Any]) -> None:
        """Stores failure attribution entries from an analysis report."""
        attributions = report.get("attributions", [])
        if not attributions:
            return
        ph = self._placeholder()
        sql = f"""
        INSERT INTO failure_attributions (
            analysis_timestamp, failure_id, failure_type, primary_trigger, confidence, report_json
        ) VALUES ({', '.join([ph] * 6)})
        """
        ts = str(report.get("analysis_timestamp", ""))
        with self._lock:
            conn = self._connect()
            try:
                cur = conn.cursor()
                for attr in attributions:
                    cur.execute(sql, (
                        ts,
                        str(attr.get("failure_id", "")),
                        str(attr.get("failure_type", "")),
                        str(attr.get("primary_trigger", "")),
                        float(attr.get("confidence", 0.0)),
                        json.dumps(attr),
                    ))
                conn.commit()
            finally:
                conn.close()

    def clear_events(self) -> None:
        """Clears stored perturbation events (useful for clean test isolation)."""
        with self._lock:
            conn = self._connect()
            try:
                cur = conn.cursor()
                cur.execute("DELETE FROM perturbation_events")
                conn.commit()
            finally:
                conn.close()
