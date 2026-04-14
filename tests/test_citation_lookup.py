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

    def test_lookup_auto_has_openalex_client(self):
        """CitationLookup should instantiate an OpenAlexClient for Scopus EID resolution."""
        from modules.openalex_client import OpenAlexClient
        lookup = CitationLookup()
        assert hasattr(lookup, 'openalex_client')
        assert isinstance(lookup.openalex_client, OpenAlexClient)

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
        # Methods that formatters call
        self.mock_article.get_first_author_label = Mock(return_value="SmithJ")
        self.mock_article.format_authors_vancouver = Mock(return_value="Smith J, Jones B")

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


class TestExtractTitleFromCitationText:
    """Tests for _extract_title_from_citation_text helper."""

    def setup_method(self):
        self.lookup = CitationLookup()

    def test_period_delimited_vancouver(self):
        result = self.lookup._extract_title_from_citation_text(
            "Yusuf S, Hawken S. Effect of potentially modifiable risk factors. Lancet. 2004;364(9438):937-52"
        )
        assert result == "Effect of potentially modifiable risk factors"

    def test_dash_delimited(self):
        result = self.lookup._extract_title_from_citation_text(
            "Sirugo G 2019 - The Missing Diversity in Human Genetic Studies - Cell 177"
        )
        assert result == "The Missing Diversity in Human Genetic Studies"

    def test_returns_none_for_short_candidate(self):
        result = self.lookup._extract_title_from_citation_text(
            "Smith J. Short. Journal. 2020"
        )
        assert result is None

    def test_returns_none_for_plain_title(self):
        result = self.lookup._extract_title_from_citation_text(
            "Effect of potentially modifiable risk factors"
        )
        assert result is None


class TestLookupAutoFullCitation:
    """Tests for --auto flag with full citation text input."""

    def setup_method(self):
        self.lookup = CitationLookup()

    def test_auto_detects_citation_text_and_extracts_title(self):
        """--auto should extract title from full citation text and search by it."""
        citation = (
            "Magavern EF, Jacobs B, Warren H. CYP2C19 genotype prevalence and "
            "association with recurrent myocardial infarction. JACC Adv. 2023;2(7):100573"
        )
        success_result = LookupResult(
            success=True, identifier="37808344", identifier_type="pmid",
            inline_mark="[^test]", endnote_citation="test", full_citation="test"
        )
        with patch.object(self.lookup, 'lookup_title', return_value=success_result) as mock_title:
            result = self.lookup.lookup_auto(citation)
            assert result.success is True
            call_args = mock_title.call_args_list
            extracted = call_args[0][0][0]
            assert "CYP2C19 genotype prevalence" in extracted
            assert "Magavern" not in extracted

    def test_auto_falls_through_if_extraction_fails(self):
        """If extracted title search fails, fall through to full-text lookup_title."""
        citation = (
            "Smith J, Jones K. Some very specific long title about things. "
            "Journal X. 2023;1:1-10"
        )
        fail_result = LookupResult(
            success=False, identifier="", identifier_type="title",
            error="Not found"
        )
        with patch.object(self.lookup, 'lookup_title', return_value=fail_result) as mock_title:
            result = self.lookup.lookup_auto(citation)
            assert mock_title.call_count == 2


class TestLookupAutoNewPaths:
    """Tests for new resolution paths added in v2: proxy URLs, Scholar URLs, Scopus EIDs."""

    def setup_method(self):
        self.lookup = CitationLookup()
        # Build a minimal successful LookupResult for use as mock return value
        self.mock_success = LookupResult(
            success=True,
            identifier="30110588",
            identifier_type="pmid",
            inline_mark="[^MaronBJ-2018-30110588]",
            endnote_citation="[^MaronBJ-2018-30110588]: Maron BJ...",
            full_citation="[^MaronBJ-2018-30110588]: Maron BJ...",
        )

    def test_proxy_doi_url_is_resolved(self):
        """Proxy-wrapped DOI URL should resolve via DOI path, not title search."""
        proxied_url = "https://doi-org.proxy.lib.ohio-state.edu/10.1056/nejmra1710575"

        with patch.object(self.lookup, 'lookup_doi', return_value=self.mock_success) as mock_doi, \
             patch.object(self.lookup, 'lookup_title') as mock_title:
            result = self.lookup.lookup_auto(proxied_url)

        mock_doi.assert_called_once()
        # lookup_doi should be called with the canonical DOI, not the proxy URL
        call_arg = mock_doi.call_args[0][0]
        assert call_arg == "10.1056/nejmra1710575"
        mock_title.assert_not_called()
        assert result.success is True

    def test_scholar_lookup_url_uses_extracted_title(self):
        """Scholar lookup URL should extract title params, not pass raw URL as title."""
        scholar_url = (
            "https://scholar.google.com/scholar_lookup"
            "?title=Clinical%20course%20and%20management%20of%20hypertrophic%20cardiomyopathy"
            "&publication_year=2018"
            "&author=B.J.%20Maron"
        )

        with patch.object(self.lookup, 'lookup_title', return_value=self.mock_success) as mock_title:
            result = self.lookup.lookup_auto(scholar_url)

        mock_title.assert_called_once()
        title_arg = mock_title.call_args[0][0]
        # The title argument should be the clean decoded title, not the full URL
        assert 'scholar.google.com' not in title_arg
        assert 'hypertrophic cardiomyopathy' in title_arg.lower()

    def test_scopus_url_tries_openalex_eid(self):
        """Scopus URL should try OpenAlex EID lookup before falling back to title search."""
        scopus_url = "https://www.scopus.com/inward/record.url?eid=2-s2.0-85051788505"

        from modules.openalex_client import OpenAlexWork
        mock_oa_work = Mock(spec=OpenAlexWork)
        mock_oa_work.doi = "10.1056/nejmra1710575"
        mock_oa_work.pmid = "30110588"

        with patch.object(self.lookup.openalex_client, 'fetch_by_scopus_eid', return_value=mock_oa_work) as mock_eid, \
             patch.object(self.lookup, 'lookup_doi', return_value=self.mock_success) as mock_doi:
            result = self.lookup.lookup_auto(scopus_url)

        mock_eid.assert_called_once_with("2-s2.0-85051788505")
        assert result.success is True

    def test_scopus_url_falls_back_to_title_when_eid_fails(self):
        """When OpenAlex EID lookup returns None, fall through to title search."""
        scopus_url = (
            "https://scholar.google.com/scholar_lookup"
            "?title=Some%20rare%20article%20not%20in%20openalex"
            "&publication_year=2020"
            "&author=J.%20Smith"
        )
        with patch.object(self.lookup, 'lookup_title', return_value=self.mock_success) as mock_title:
            result = self.lookup.lookup_auto(scopus_url)

        mock_title.assert_called_once()

    def test_plain_doi_still_works(self):
        """Existing plain DOI path must not regress."""
        with patch.object(self.lookup, 'lookup_doi', return_value=self.mock_success) as mock_doi:
            result = self.lookup.lookup_auto("10.1056/nejmra1710575")

        mock_doi.assert_called_once()
        assert result.success is True
