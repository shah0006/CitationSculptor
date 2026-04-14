"""
Tests for PersistentCitationCache - SQLite-backed citation cache.

Tests cover:
- Basic get/set roundtrip
- TTL expiry
- Error resilience (bad db path)
- Invalidation
- Expired entry cleanup
- Stats reporting
- Key collision avoidance between lookup types
"""

import pytest
import time
import json
import sqlite3
from pathlib import Path
from unittest.mock import patch

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from modules.citation_cache import PersistentCitationCache, TTL_DAYS


SAMPLE_RESULT = {
    "success": True,
    "identifier": "32089132",
    "identifier_type": "pmid",
    "inline_mark": "[^KramerCM-2020-32089132]",
    "endnote_citation": "[^KramerCM-2020-32089132]: Kramer CM...",
    "full_citation": "[^KramerCM-2020-32089132]: Kramer CM...",
    "metadata": {"pmid": "32089132", "title": "Test Article"},
    "error": None,
}


class TestPersistentCitationCache:
    """Test suite for PersistentCitationCache."""

    def test_get_returns_none_for_missing_key(self, tmp_path):
        """Cache miss returns None."""
        cache = PersistentCitationCache(db_path=tmp_path / "test.db")
        assert cache.get("pmid", "99999999") is None

    def test_set_and_get_roundtrip(self, tmp_path):
        """Store a result and retrieve it."""
        cache = PersistentCitationCache(db_path=tmp_path / "test.db")
        cache.set("pmid", "32089132", SAMPLE_RESULT)
        result = cache.get("pmid", "32089132")
        assert result is not None
        assert result["identifier"] == "32089132"
        assert result["success"] is True
        assert result["metadata"]["title"] == "Test Article"

    def test_expired_entry_returns_none(self, tmp_path):
        """Entries older than TTL_DAYS are treated as cache misses."""
        cache = PersistentCitationCache(db_path=tmp_path / "test.db")
        cache.set("pmid", "32089132", SAMPLE_RESULT)

        # Mock time to be 91 days in the future
        future_time = time.time() + (TTL_DAYS + 1) * 86400
        with patch("modules.citation_cache.time") as mock_time:
            mock_time.time.return_value = future_time
            result = cache.get("pmid", "32089132")
        assert result is None

    def test_set_silently_ignores_errors(self, tmp_path):
        """Writing to an invalid path raises no exception."""
        # Use a path that cannot be created (file as parent dir)
        bad_file = tmp_path / "blocker.txt"
        bad_file.write_text("I am a file, not a directory")
        bad_db_path = bad_file / "subdir" / "test.db"

        cache = PersistentCitationCache(db_path=bad_db_path)
        # This should NOT raise
        cache.set("pmid", "12345", SAMPLE_RESULT)
        # get should return None gracefully
        assert cache.get("pmid", "12345") is None

    def test_invalidate_removes_entry(self, tmp_path):
        """Invalidate removes a specific cached entry."""
        cache = PersistentCitationCache(db_path=tmp_path / "test.db")
        cache.set("pmid", "32089132", SAMPLE_RESULT)
        assert cache.get("pmid", "32089132") is not None

        cache.invalidate("pmid", "32089132")
        assert cache.get("pmid", "32089132") is None

    def test_clear_expired_removes_old_entries(self, tmp_path):
        """clear_expired deletes entries older than TTL_DAYS."""
        cache = PersistentCitationCache(db_path=tmp_path / "test.db")
        cache.set("pmid", "11111111", SAMPLE_RESULT)
        cache.set("pmid", "22222222", SAMPLE_RESULT)

        # Manually backdate the first entry
        conn = sqlite3.connect(str(tmp_path / "test.db"))
        old_time = time.time() - (TTL_DAYS + 5) * 86400
        conn.execute(
            "UPDATE citation_cache SET created_at = ? WHERE cache_key = ?",
            (old_time, "pmid:11111111:vancouver"),
        )
        conn.commit()
        conn.close()

        deleted = cache.clear_expired()
        assert deleted == 1
        assert cache.get("pmid", "11111111") is None
        assert cache.get("pmid", "22222222") is not None

    def test_stats_returns_correct_counts(self, tmp_path):
        """stats() reports total entries, expired count, and db size."""
        cache = PersistentCitationCache(db_path=tmp_path / "test.db")
        cache.set("pmid", "11111111", SAMPLE_RESULT)
        cache.set("doi", "10.1234/test", SAMPLE_RESULT)

        # Backdate one entry to make it expired
        conn = sqlite3.connect(str(tmp_path / "test.db"))
        old_time = time.time() - (TTL_DAYS + 5) * 86400
        conn.execute(
            "UPDATE citation_cache SET created_at = ? WHERE cache_key = ?",
            (old_time, "pmid:11111111:vancouver"),
        )
        conn.commit()
        conn.close()

        stats = cache.stats()
        assert stats["total_entries"] == 2
        assert stats["expired_entries"] == 1
        assert stats["db_size_bytes"] > 0

    def test_different_lookup_types_dont_collide(self, tmp_path):
        """pmid:123 and doi:123 are distinct cache entries."""
        cache = PersistentCitationCache(db_path=tmp_path / "test.db")

        result_pmid = {**SAMPLE_RESULT, "identifier_type": "pmid", "identifier": "123"}
        result_doi = {**SAMPLE_RESULT, "identifier_type": "doi", "identifier": "123"}

        cache.set("pmid", "123", result_pmid)
        cache.set("doi", "123", result_doi)

        got_pmid = cache.get("pmid", "123")
        got_doi = cache.get("doi", "123")

        assert got_pmid["identifier_type"] == "pmid"
        assert got_doi["identifier_type"] == "doi"

    def test_uses_temp_db_path_in_tests(self, tmp_path):
        """Verify test isolation -- DB lives in tmp_path, not .cache/."""
        db_path = tmp_path / "isolated.db"
        cache = PersistentCitationCache(db_path=db_path)
        cache.set("pmid", "99999", SAMPLE_RESULT)

        assert db_path.exists()
        # The default .cache/citations.db should NOT be touched
        default_db = Path(__file__).parent.parent / ".cache" / "citations.db"
        # We can't assert it doesn't exist (it might from production use),
        # but we can verify our db_path is the one that was written to
        conn = sqlite3.connect(str(db_path))
        row = conn.execute("SELECT COUNT(*) FROM citation_cache").fetchone()
        conn.close()
        assert row[0] == 1

    def test_get_with_style_parameter(self, tmp_path):
        """Style parameter creates distinct cache keys (drop-in compat with CitationCache)."""
        cache = PersistentCitationCache(db_path=tmp_path / "test.db")

        result_van = {**SAMPLE_RESULT, "full_citation": "Vancouver format"}
        result_apa = {**SAMPLE_RESULT, "full_citation": "APA format"}

        cache.set("pmid", "32089132", result_van, style="vancouver")
        cache.set("pmid", "32089132", result_apa, style="apa")

        got_van = cache.get("pmid", "32089132", style="vancouver")
        got_apa = cache.get("pmid", "32089132", style="apa")

        assert got_van["full_citation"] == "Vancouver format"
        assert got_apa["full_citation"] == "APA format"

    def test_set_overwrites_existing_entry(self, tmp_path):
        """Setting the same key twice overwrites the previous value."""
        cache = PersistentCitationCache(db_path=tmp_path / "test.db")
        cache.set("pmid", "32089132", {**SAMPLE_RESULT, "full_citation": "v1"})
        cache.set("pmid", "32089132", {**SAMPLE_RESULT, "full_citation": "v2"})

        result = cache.get("pmid", "32089132")
        assert result["full_citation"] == "v2"
