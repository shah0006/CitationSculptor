"""
Tests for citation_lookup.py - the main CLI tool.

Tests cover:
- CitationLookup class functionality
- Identifier auto-detection
- Various lookup methods (PMID, DOI, PMC ID, title)
- Batch processing
- Output formatting
- Caching integration
"""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from dataclasses import dataclass

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from citation_lookup import (
    CitationLookup,
    LookupResult,
    format_output,
)


class TestLookupResult:
    """Test cases for LookupResult dataclass."""

    def test_successful_result(self):
        """Test creating a successful lookup result."""
        result = LookupResult(
            success=True,
            identifier="32089132",
            identifier_type="pmid",
            inline_mark="[^KramerCM-2020-32089132]",
            endnote_citation="[^KramerCM-2020-32089132]: Kramer CM...",
            full_citation="[^KramerCM-2020-32089132]: Kramer CM...",
            metadata={"pmid": "32089132", "title": "Test"},
            error=None
        )
        assert result.success is True
        assert result.identifier == "32089132"
        assert result.error is None

    def test_failed_result(self):
        """Test creating a failed lookup result."""
        result = LookupResult(
            success=False,
            identifier="invalid",
            identifier_type="unknown",
            error="Not found"
        )
        assert result.success is False
        assert result.error == "Not found"
        assert result.inline_mark == ""  # Default is empty string

    def test_result_defaults(self):
        """Test default values in LookupResult."""
        result = LookupResult(
            success=True,
            identifier="test",
            identifier_type="pmid"
        )
        assert result.inline_mark == ""  # Default is empty string
        assert result.endnote_citation == ""
        assert result.full_citation == ""
        assert result.metadata is None
        assert result.error is None


class TestIdentifierTypeDetection:
    """Test cases for identifier type detection via lookup_auto."""

    def setup_method(self):
        """Set up test fixtures."""
        self.lookup = CitationLookup()

    @patch.object(CitationLookup, 'lookup_pmid')
    def test_detect_pmid(self, mock_lookup):
        """Test PMID detection routes correctly."""
        mock_lookup.return_value = LookupResult(success=True, identifier="32089132", identifier_type="pmid")
        self.lookup.lookup_auto("32089132")
        mock_lookup.assert_called_once_with("32089132")

    @patch.object(CitationLookup, 'lookup_doi')
    def test_detect_doi(self, mock_lookup):
        """Test DOI detection routes correctly."""
        mock_lookup.return_value = LookupResult(success=True, identifier="10.1186/test", identifier_type="doi")
        self.lookup.lookup_auto("10.1186/test")
        mock_lookup.assert_called_once()

    @patch.object(CitationLookup, 'lookup_pmcid')
    def test_detect_pmcid(self, mock_lookup):
        """Test PMC ID detection routes correctly."""
        mock_lookup.return_value = LookupResult(success=True, identifier="PMC7039045", identifier_type="pmcid")
        self.lookup.lookup_auto("PMC7039045")
        mock_lookup.assert_called_once()

    @patch.object(CitationLookup, 'lookup_title')
    def test_detect_title(self, mock_lookup):
        """Test title detection (fallback) routes correctly."""
        mock_lookup.return_value = LookupResult(success=True, identifier="test query", identifier_type="title")
        self.lookup.lookup_auto("Heart failure treatment guidelines review")
        mock_lookup.assert_called_once()


class TestCitationLookup:
    """Test cases for CitationLookup class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.lookup = CitationLookup()

    def test_initialization(self):
        """Test CitationLookup initialization."""
        assert self.lookup.pubmed_client is not None
        assert self.lookup.formatter is not None

    @patch.object(CitationLookup, 'lookup_pmid')
    def test_lookup_auto_pmid(self, mock_lookup):
        """Test auto lookup routes to PMID lookup."""
        mock_lookup.return_value = LookupResult(
            success=True,
            identifier="32089132",
            identifier_type="pmid"
        )
        
        result = self.lookup.lookup_auto("32089132")
        mock_lookup.assert_called_once_with("32089132")

    @patch.object(CitationLookup, 'lookup_doi')
    def test_lookup_auto_doi(self, mock_lookup):
        """Test auto lookup routes to DOI lookup."""
        mock_lookup.return_value = LookupResult(
            success=True,
            identifier="10.1234/test",
            identifier_type="doi"
        )
        
        result = self.lookup.lookup_auto("10.1234/test")
        mock_lookup.assert_called_once_with("10.1234/test")

    @patch.object(CitationLookup, 'lookup_pmcid')
    def test_lookup_auto_pmcid(self, mock_lookup):
        """Test auto lookup routes to PMC ID lookup."""
        mock_lookup.return_value = LookupResult(
            success=True,
            identifier="PMC7039045",
            identifier_type="pmcid"
        )
        
        result = self.lookup.lookup_auto("PMC7039045")
        mock_lookup.assert_called_once_with("PMC7039045")

    @patch.object(CitationLookup, 'lookup_title')
    def test_lookup_auto_title(self, mock_lookup):
        """Test auto lookup routes to title lookup."""
        mock_lookup.return_value = LookupResult(
            success=True,
            identifier="heart failure guidelines",
            identifier_type="title"
        )
        
        result = self.lookup.lookup_auto("heart failure guidelines")
        mock_lookup.assert_called_once_with("heart failure guidelines")

    def test_format_output_full(self):
        """Test formatting result as full citation."""
        result = LookupResult(
            success=True,
            identifier="32089132",
            identifier_type="pmid",
            inline_mark="[^Test-2024-32089132]",
            endnote_citation="[^Test-2024-32089132]: Full citation...",
            full_citation="[^Test-2024-32089132]: Full citation...",
        )
        
        formatted = format_output(result, "full")
        assert "[^Test-2024-32089132]" in formatted
        assert "Full citation" in formatted

    def test_format_output_inline(self):
        """Test formatting result as inline only."""
        result = LookupResult(
            success=True,
            identifier="32089132",
            identifier_type="pmid",
            inline_mark="[^Test-2024-32089132]",
            endnote_citation="[^Test-2024-32089132]: Full citation...",
            full_citation="[^Test-2024-32089132]: Full citation...",
        )
        
        formatted = format_output(result, "inline")
        assert "[^Test-2024-32089132]" in formatted

    def test_format_output_json(self):
        """Test formatting result as JSON."""
        result = LookupResult(
            success=True,
            identifier="32089132",
            identifier_type="pmid",
            inline_mark="[^Test-2024-32089132]",
            metadata={"title": "Test Article"}
        )
        
        formatted = format_output(result, "json")
        parsed = json.loads(formatted)
        assert parsed["success"] is True
        assert parsed["identifier"] == "32089132"

    def test_format_output_error(self):
        """Test formatting error result."""
        result = LookupResult(
            success=False,
            identifier="invalid",
            identifier_type="unknown",
            error="Article not found"
        )
        
        formatted = format_output(result, "full")
        assert "Error" in formatted or "not found" in formatted.lower()

    @patch.object(CitationLookup, 'lookup_auto')
    def test_batch_lookup(self, mock_lookup):
        """Test batch lookup processes multiple identifiers."""
        mock_lookup.side_effect = [
            LookupResult(success=True, identifier="1", identifier_type="pmid"),
            LookupResult(success=True, identifier="2", identifier_type="pmid"),
            LookupResult(success=False, identifier="3", identifier_type="unknown", error="Not found"),
        ]
        
        results = self.lookup.batch_lookup(["1", "2", "3"])
        
        assert len(results) == 3
        assert results[0].success is True
        assert results[1].success is True
        assert results[2].success is False

    @patch.object(CitationLookup, 'lookup_auto')
    def test_batch_lookup_empty(self, mock_lookup):
        """Test batch lookup with empty list."""
        results = self.lookup.batch_lookup([])
        assert results == []
        mock_lookup.assert_not_called()


class TestCitationLookupWithMockedClient:
    """Test CitationLookup with mocked PubMed client."""

    def setup_method(self):
        """Set up test fixtures with mocked client."""
        self.lookup = CitationLookup()
        self.mock_article = Mock()
        self.mock_article.pmid = "32089132"
        self.mock_article.title = "Test Article Title"
        self.mock_article.authors = ["Smith J", "Jones M"]
        self.mock_article.journal = "Test Journal"
        self.mock_article.journal_abbreviation = "Test J"
        self.mock_article.year = "2024"
        self.mock_article.month = "Jan"
        self.mock_article.volume = "10"
        self.mock_article.issue = "1"
        self.mock_article.pages = "1-10"
        self.mock_article.doi = "10.1234/test"
        self.mock_article.abstract = "Test abstract"

    @patch('citation_lookup.CitationLookup')
    def test_lookup_pmid_success(self, MockLookup):
        """Test successful PMID lookup."""
        # This tests that the lookup pipeline works
        lookup = CitationLookup()
        lookup.pubmed_client = Mock()
        lookup.pubmed_client.fetch_article_by_pmid = Mock(return_value=self.mock_article)
        
        result = lookup.lookup_pmid("32089132")
        
        assert result.success is True
        assert result.identifier == "32089132"
        assert result.identifier_type == "pmid"
        assert result.inline_mark is not None
        assert "32089132" in result.inline_mark

    @patch('citation_lookup.CitationLookup')
    def test_lookup_pmid_not_found(self, MockLookup):
        """Test PMID lookup when article not found."""
        lookup = CitationLookup()
        lookup.pubmed_client = Mock()
        lookup.pubmed_client.fetch_article_by_pmid = Mock(return_value=None)
        
        result = lookup.lookup_pmid("99999999")
        
        assert result.success is False
        assert "not found" in result.error.lower() or "No article" in result.error


class TestSearchMultiple:
    """Test cases for search_multiple functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.lookup = CitationLookup()

    def test_search_multiple_returns_results(self):
        """Test search_multiple returns list of articles."""
        # Mock the return value of search_pubmed (returns list of dicts)
        mock_results = [{"pmid": "12345", "title": "Test Article"}]
        
        # Replace the pubmed_client on the instance
        self.lookup.pubmed_client = Mock()
        self.lookup.pubmed_client.search_pubmed = Mock(return_value=mock_results)
        
        results = self.lookup.search_multiple("test query")
        
        assert len(results) == 1
        assert results[0]["pmid"] == "12345"

    def test_search_multiple_empty_query(self):
        """Test search_multiple with empty query."""
        results = self.lookup.search_multiple("")
        assert results == []


class TestConnectionTest:
    """Test cases for connection testing."""

    def setup_method(self):
        """Set up test fixtures."""
        self.lookup = CitationLookup()

    def test_connection_success(self):
        """Test successful connection test."""
        # Replace the pubmed_client on the instance
        self.lookup.pubmed_client = Mock()
        self.lookup.pubmed_client.test_connection = Mock(return_value=True)
        
        result = self.lookup.test_connection()
        assert result is True

    def test_connection_failure(self):
        """Test failed connection test."""
        # Replace the pubmed_client on the instance
        self.lookup.pubmed_client = Mock()
        self.lookup.pubmed_client.test_connection = Mock(return_value=False)
        
        result = self.lookup.test_connection()
        assert result is False


class TestCacheIntegration:
    """Test caching functionality integration."""

    def setup_method(self):
        """Set up test fixtures."""
        self.lookup = CitationLookup()

    def test_cache_stats_available(self):
        """Test that cache stats are accessible."""
        stats = self.lookup.pubmed_client.get_cache_stats()
        
        assert 'pmid_cache_size' in stats
        assert 'conversion_cache_size' in stats
        assert 'crossref_cache_size' in stats

