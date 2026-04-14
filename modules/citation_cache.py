"""Persistent SQLite-backed citation cache.

Stores LookupResult objects by (lookup_type, identifier) key so results
survive between CitationSculptor runs. Cache entries expire after TTL_DAYS.
"""

import sqlite3
import json
import time
from pathlib import Path
from typing import Optional
from loguru import logger

TTL_DAYS = 90  # cache entries expire after 90 days

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS citation_cache (
    cache_key TEXT PRIMARY KEY,
    result_json TEXT NOT NULL,
    created_at REAL NOT NULL
)
"""


class PersistentCitationCache:
    """SQLite-backed citation result cache.

    Drop-in replacement for CitationCache. Persists results to disk
    so lookups survive between CitationSculptor runs.
    """

    DB_PATH = Path(__file__).parent.parent / ".cache" / "citations.db"

    def __init__(self, db_path: Optional[Path] = None):
        """Initialize cache, creating DB and table if needed."""
        self.db_path = db_path or self.DB_PATH
        self._conn: Optional[sqlite3.Connection] = None
        try:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(
                str(self.db_path), check_same_thread=False
            )
            self._conn.execute(_CREATE_TABLE_SQL)
            self._conn.commit()
        except Exception as e:
            logger.debug(f"Citation cache init failed: {e}")
            self._conn = None

    @staticmethod
    def _make_key(
        lookup_type: str, identifier: str, style: str = "vancouver"
    ) -> str:
        return f"{lookup_type}:{identifier}:{style}"

    # ------------------------------------------------------------------
    # Public API -- mirrors CitationCache signature for drop-in use
    # ------------------------------------------------------------------

    def get(
        self,
        identifier_type: str,
        identifier: str,
        style: str = "vancouver",
    ) -> Optional[dict]:
        """Return cached result dict or None if missing/expired."""
        if self._conn is None:
            return None
        try:
            key = self._make_key(identifier_type, identifier, style)
            row = self._conn.execute(
                "SELECT result_json, created_at FROM citation_cache WHERE cache_key = ?",
                (key,),
            ).fetchone()
            if row is None:
                return None
            result_json, created_at = row
            if time.time() - created_at > TTL_DAYS * 86400:
                return None
            return json.loads(result_json)
        except Exception as e:
            logger.debug(f"Citation cache get failed: {e}")
            return None

    def set(
        self,
        identifier_type: str,
        identifier: str,
        result_dict: dict,
        style: str = "vancouver",
    ) -> None:
        """Store result dict. Silently no-ops on any error."""
        if self._conn is None:
            return
        try:
            key = self._make_key(identifier_type, identifier, style)
            self._conn.execute(
                "INSERT OR REPLACE INTO citation_cache (cache_key, result_json, created_at) VALUES (?, ?, ?)",
                (key, json.dumps(result_dict), time.time()),
            )
            self._conn.commit()
        except Exception as e:
            logger.debug(f"Citation cache set failed: {e}")

    def invalidate(
        self, lookup_type: str, identifier: str, style: str = "vancouver"
    ) -> None:
        """Remove a specific cache entry."""
        if self._conn is None:
            return
        try:
            key = self._make_key(lookup_type, identifier, style)
            self._conn.execute(
                "DELETE FROM citation_cache WHERE cache_key = ?", (key,)
            )
            self._conn.commit()
        except Exception as e:
            logger.debug(f"Citation cache invalidate failed: {e}")

    def clear_expired(self) -> int:
        """Delete entries older than TTL_DAYS. Returns count deleted."""
        if self._conn is None:
            return 0
        try:
            cutoff = time.time() - TTL_DAYS * 86400
            cursor = self._conn.execute(
                "DELETE FROM citation_cache WHERE created_at < ?", (cutoff,)
            )
            self._conn.commit()
            return cursor.rowcount
        except Exception as e:
            logger.debug(f"Citation cache clear_expired failed: {e}")
            return 0

    def stats(self) -> dict:
        """Return {total_entries, expired_entries, db_size_bytes}."""
        if self._conn is None:
            return {"total_entries": 0, "expired_entries": 0, "db_size_bytes": 0}
        try:
            total = self._conn.execute(
                "SELECT COUNT(*) FROM citation_cache"
            ).fetchone()[0]
            cutoff = time.time() - TTL_DAYS * 86400
            expired = self._conn.execute(
                "SELECT COUNT(*) FROM citation_cache WHERE created_at < ?",
                (cutoff,),
            ).fetchone()[0]
            db_size = self.db_path.stat().st_size if self.db_path.exists() else 0
            return {
                "total_entries": total,
                "expired_entries": expired,
                "db_size_bytes": db_size,
            }
        except Exception as e:
            logger.debug(f"Citation cache stats failed: {e}")
            return {"total_entries": 0, "expired_entries": 0, "db_size_bytes": 0}
