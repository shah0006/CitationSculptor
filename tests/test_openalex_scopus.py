"""
Tests for OpenAlexClient.fetch_by_scopus_eid().

OpenAlex does NOT support Scopus EID filtering (ids.scopus returns 400).
The method normalizes the EID and returns None, allowing callers to fall
through to alternative resolvers. These tests verify that contract.
"""

import pytest
from unittest.mock import Mock, patch
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from modules.openalex_client import OpenAlexClient


class TestFetchByScopusEid:
    """Tests for OpenAlexClient.fetch_by_scopus_eid."""

    def setup_method(self):
        self.client = OpenAlexClient(email="test@example.com")

    def test_full_eid_returns_none(self):
        """Full EID with standard prefix should return None (API not supported)."""
        with patch.object(self.client.session, 'get') as mock_get:
            result = self.client.fetch_by_scopus_eid("2-s2.0-85051788505")
        assert result is None
        mock_get.assert_not_called()

    def test_numeric_only_eid_returns_none(self):
        """EID without prefix should also return None after normalization."""
        with patch.object(self.client.session, 'get') as mock_get:
            result = self.client.fetch_by_scopus_eid("85051788505")
        assert result is None
        mock_get.assert_not_called()

    def test_empty_eid_returns_none(self):
        """Empty EID string should return None without making API call."""
        with patch.object(self.client.session, 'get') as mock_get:
            result = self.client.fetch_by_scopus_eid("")
        assert result is None
        mock_get.assert_not_called()

    def test_none_eid_returns_none(self):
        """None EID should return None without making API call."""
        with patch.object(self.client.session, 'get') as mock_get:
            result = self.client.fetch_by_scopus_eid(None)
        assert result is None
        mock_get.assert_not_called()

    def test_malformed_eid_returns_none(self):
        """EID with wrong prefix format should return None."""
        with patch.object(self.client.session, 'get') as mock_get:
            result = self.client.fetch_by_scopus_eid("invalid-eid-format")
        assert result is None
        mock_get.assert_not_called()

    def test_no_network_call_made(self):
        """Confirms no HTTP requests are made regardless of EID validity."""
        eids = [
            "2-s2.0-85051788505",
            "85051788505",
            "2-s2.0-99999999999",
            "",
            None,
        ]
        with patch.object(self.client.session, 'get') as mock_get:
            for eid in eids:
                self.client.fetch_by_scopus_eid(eid)
        mock_get.assert_not_called()
