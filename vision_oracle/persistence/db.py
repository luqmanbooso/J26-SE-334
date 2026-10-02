"""
Local SQLite database connection manager and schema migrations.
Ensures durable persistence with atomic writes, WAL mode, and crash safety.
"""

import sqlite3
import threading
from pathlib import Path
from typing import Optional

DB_FILE_PATH = Path("results/oracle_store.db")


class DatabaseManager:
    """Manages SQLite connections with WAL mode and schema initialization."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DB_FILE_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._local = threading.local()
        self.init_schema()

    def get_connection(self) -> sqlite3.Connection:
        """Returns thread-local SQLite connection with foreign keys and WAL mode."""
        if not hasattr(self._local, "conn") or self._local.conn is None:
            conn = sqlite3.connect(str(self.db_path), timeout=30.0)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            conn.execute("PRAGMA foreign_keys=ON;")
            self._local.conn = conn
        return self._local.conn

    def init_schema(self) -> None:
        """Applies initial schema migrations idempotently."""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path), timeout=30.0)
            try:
                with conn:
                    conn.execute("PRAGMA journal_mode=WAL;")
                    conn.execute("""
                        CREATE TABLE IF NOT EXISTS sessions (
                            session_id TEXT PRIMARY KEY,
                            created_at TEXT NOT NULL,
                            metadata_json TEXT
                        );
                    """)
                    conn.execute("""
                        CREATE TABLE IF NOT EXISTS captures (
                            capture_id TEXT PRIMARY KEY,
                            session_id TEXT,
                            app_package TEXT,
                            device_serial TEXT,
                            image_path TEXT NOT NULL,
                            image_sha256 TEXT NOT NULL,
                            width INTEGER NOT NULL,
                            height INTEGER NOT NULL,
                            hierarchy_xml TEXT,
                            hierarchy_status TEXT NOT NULL,
                            inter_modality_skew_ms REAL,
                            created_at TEXT NOT NULL,
                            FOREIGN KEY(session_id) REFERENCES sessions(session_id)
                        );
                    """)
                    conn.execute("""
                        CREATE TABLE IF NOT EXISTS jobs (
                            job_id TEXT PRIMARY KEY,
                            capture_id TEXT NOT NULL,
                            session_id TEXT,
                            state TEXT NOT NULL,
                            policy TEXT NOT NULL,
                            planned_views INTEGER NOT NULL,
                            completed_views INTEGER NOT NULL,
                            created_at TEXT NOT NULL,
                            started_at TEXT,
                            completed_at TEXT,
                            error_message TEXT,
                            FOREIGN KEY(capture_id) REFERENCES captures(capture_id)
                        );
                    """)
                    conn.execute("""
                        CREATE TABLE IF NOT EXISTS verdicts (
                            verdict_id TEXT PRIMARY KEY,
                            job_id TEXT NOT NULL,
                            session_id TEXT,
                            capture_id TEXT NOT NULL,
                            schema_version TEXT NOT NULL,
                            decision TEXT NOT NULL,
                            analysis_status TEXT NOT NULL,
                            model_run_id TEXT NOT NULL,
                            coverage_json TEXT NOT NULL,
                            screenshot_json TEXT NOT NULL,
                            timings_json TEXT NOT NULL,
                            errors_json TEXT NOT NULL,
                            metadata_json TEXT,
                            created_at TEXT NOT NULL,
                            FOREIGN KEY(job_id) REFERENCES jobs(job_id),
                            FOREIGN KEY(capture_id) REFERENCES captures(capture_id)
                        );
                    """)
                    conn.execute("""
                        CREATE TABLE IF NOT EXISTS findings (
                            finding_id TEXT PRIMARY KEY,
                            verdict_id TEXT NOT NULL,
                            defect_type TEXT NOT NULL,
                            x1 INTEGER,
                            y1 INTEGER,
                            x2 INTEGER,
                            y2 INTEGER,
                            element_ref TEXT,
                            explanation TEXT NOT NULL,
                            source TEXT NOT NULL,
                            confidence REAL,
                            confidence_method TEXT NOT NULL,
                            view_ids_json TEXT NOT NULL,
                            review_status TEXT NOT NULL,
                            FOREIGN KEY(verdict_id) REFERENCES verdicts(verdict_id)
                        );
                    """)
                    conn.execute("""
                        CREATE TABLE IF NOT EXISTS reviews (
                            review_id TEXT PRIMARY KEY,
                            verdict_id TEXT NOT NULL,
                            finding_id TEXT,
                            review_status TEXT NOT NULL,
                            reviewer_notes TEXT,
                            created_at TEXT NOT NULL,
                            FOREIGN KEY(verdict_id) REFERENCES verdicts(verdict_id)
                        );
                    """)
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_captures_session ON captures(session_id);")
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_capture ON jobs(capture_id);")
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_state ON jobs(state);")
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_verdicts_job ON verdicts(job_id);")
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_verdicts_session ON verdicts(session_id);")
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_findings_verdict ON findings(verdict_id);")
            finally:
                conn.close()


_DB_MANAGER: Optional[DatabaseManager] = None


def get_database(db_path: Optional[Path] = None) -> DatabaseManager:
    """Returns the singleton DatabaseManager instance."""
    global _DB_MANAGER
    if _DB_MANAGER is None or (db_path is not None and _DB_MANAGER.db_path != db_path):
        _DB_MANAGER = DatabaseManager(db_path)
    return _DB_MANAGER
