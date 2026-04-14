"""Tests for Semantic Scholar API client.

[Using: TDD] RED phase — all tests written before implementation.
Tests cover: fetch_by_doi, fetch_by_pmid, search, input validation,
error handling, and auto-prefix behavior.
"""

import pytest
from unittest.mock import MagicMock, patch
import requests

from modules.semantic_scholar_client import SemanticScholarClient, SemanticScholarWork


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_PAPER_RESPONSE = {
    "paperId": "abc123def456",
    "externalIds": {
        "DOI": "10.1056/nejmra1710575",
        "PubMed": "30110588",
        "ArXiv": None,
    },
    "title": "Clinical Course and Management of Hypertrophic Cardiomyopathy",
    "authors": [
        {"name": "Barry J. Maron"},
        {"name": "Martin S. Maron"},
    ],
    "year": 2018,
    "venue": "New England Journal of Medicine",
    "publicationDate": "2018-08-16",
    "abstract": "Hypertrophic cardiomyopathy is a common genetic heart disease...",
    "citationCount": 1250,
    "openAccessPdf": {"url": "https://example.com/paper.pdf"},
}

SAMPLE_SEARCH_RESPONSE = {
    "total": 2,
    "data": [
        {
            "paperId": "aaa111",
            "externalIds": {"DOI": "10.1000/first", "PubMed": "11111"},
            "title": "First Result",
            "authors": [{"name": "Alice Author"}],
            "year": 2020,
            "venue": "Journal A",
            "publicationDate": "2020-01-15",
            "abstract": "Abstract one.",
            "citationCount": 100,
            "openAccessPdf": None,
        },
        {
            "paperId": "bbb222",
            "externalIds": {"DOI": "10.1000/second", "PubMed": None},
            "title": "Second Result",
            "authors": [{"name": "Bob Builder"}],
            "year": 2021,
            "venue": "Journal B",
            "publicationDate": "2021-06-01",
            "abstract": None,
            "citationCount": 50,
            "openAccessPdf": {"url": "https://example.com/second.pdf"},
        },
    ],
}


@pytest.fixture
def client():
    """Create a SemanticScholarClient with rate-limiting disabled."""
    return SemanticScholarClient(request_delay=0.0)


# ---------------------------------------------------------------------------
# fetch_by_doi
# ---------------------------------------------------------------------------

class TestFetchByDoi:
    """Tests for fetch_by_doi returning SemanticScholarWork."""

    def test_successful_doi_lookup(self, client):
        """Successful DOI lookup returns correct title, pmid, doi."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = SAMPLE_PAPER_RESPONSE
        mock_resp.raise_for_status = MagicMock()

        with patch.object(client.session, "get", return_value=mock_resp) as mock_get:
            result = client.fetch_by_doi("10.1056/nejmra1710575")

        assert isinstance(result, SemanticScholarWork)
        assert result.title == "Clinical Course and Management of Hypertrophic Cardiomyopathy"
        assert result.doi == "10.1056/nejmra1710575"
        assert result.pmid == "30110588"
        assert result.s2_id == "abc123def456"
        assert result.year == 2018
        assert result.journal == "New England Journal of Medicine"
        assert result.authors == ["Barry J. Maron", "Martin S. Maron"]
        assert result.citation_count == 1250
        assert result.open_access_url == "https://example.com/paper.pdf"
        assert result.publication_date == "2018-08-16"
        assert result.abstract.startswith("Hypertrophic")

        # Verify the URL contains DOI: prefix
        call_url = mock_get.call_args[0][0]
        assert "DOI:10.1056/nejmra1710575" in call_url

    def test_doi_auto_prefix(self, client):
        """DOI input auto-prefixed with 'DOI:' if not already present."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = SAMPLE_PAPER_RESPONSE
        mock_resp.raise_for_status = MagicMock()

        with patch.object(client.session, "get", return_value=mock_resp) as mock_get:
            client.fetch_by_doi("10.1056/nejmra1710575")

        call_url = mock_get.call_args[0][0]
        assert "DOI:10.1056/nejmra1710575" in call_url
        # Must NOT double-prefix
        assert "DOI:DOI:" not in call_url

    def test_doi_already_prefixed(self, client):
        """DOI already prefixed with 'DOI:' should not double-prefix."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = SAMPLE_PAPER_RESPONSE
        mock_resp.raise_for_status = MagicMock()

        with patch.object(client.session, "get", return_value=mock_resp) as mock_get:
            client.fetch_by_doi("DOI:10.1056/nejmra1710575")

        call_url = mock_get.call_args[0][0]
        assert "DOI:10.1056/nejmra1710575" in call_url
        assert "DOI:DOI:" not in call_url

    def test_doi_not_found_returns_none(self, client):
        """404 / not found returns None."""
        mock_resp = MagicMock()
        mock_resp.status_code = 404

        with patch.object(client.session, "get", return_value=mock_resp):
            result = client.fetch_by_doi("10.9999/nonexistent")

        assert result is None

    def test_doi_network_error_returns_none(self, client):
        """Network error returns None (never raises)."""
        with patch.object(
            client.session, "get", side_effect=requests.ConnectionError("network down")
        ):
            result = client.fetch_by_doi("10.1056/nejmra1710575")

        assert result is None

    def test_doi_none_input_returns_none(self, client):
        """None input returns None without making HTTP call."""
        with patch.object(client.session, "get") as mock_get:
            result = client.fetch_by_doi(None)

        assert result is None
        mock_get.assert_not_called()

    def test_doi_empty_string_returns_none(self, client):
        """Empty string input returns None without making HTTP call."""
        with patch.object(client.session, "get") as mock_get:
            result = client.fetch_by_doi("")

        assert result is None
        mock_get.assert_not_called()


# ---------------------------------------------------------------------------
# fetch_by_pmid
# ---------------------------------------------------------------------------

class TestFetchByPmid:
    """Tests for fetch_by_pmid returning SemanticScholarWork."""

    def test_successful_pmid_lookup(self, client):
        """Successful PMID lookup returns correct title."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = SAMPLE_PAPER_RESPONSE
        mock_resp.raise_for_status = MagicMock()

        with patch.object(client.session, "get", return_value=mock_resp):
            result = client.fetch_by_pmid("30110588")

        assert isinstance(result, SemanticScholarWork)
        assert result.title == "Clinical Course and Management of Hypertrophic Cardiomyopathy"

    def test_pmid_auto_prefix(self, client):
        """PMID input auto-prefixed with 'PMID:' if not already present."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = SAMPLE_PAPER_RESPONSE
        mock_resp.raise_for_status = MagicMock()

        with patch.object(client.session, "get", return_value=mock_resp) as mock_get:
            client.fetch_by_pmid("30110588")

        call_url = mock_get.call_args[0][0]
        assert "PMID:30110588" in call_url
        assert "PMID:PMID:" not in call_url

    def test_pmid_already_prefixed(self, client):
        """PMID already prefixed should not double-prefix."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = SAMPLE_PAPER_RESPONSE
        mock_resp.raise_for_status = MagicMock()

        with patch.object(client.session, "get", return_value=mock_resp) as mock_get:
            client.fetch_by_pmid("PMID:30110588")

        call_url = mock_get.call_args[0][0]
        assert "PMID:30110588" in call_url
        assert "PMID:PMID:" not in call_url

    def test_pmid_not_found_returns_none(self, client):
        """404 returns None."""
        mock_resp = MagicMock()
        mock_resp.status_code = 404

        with patch.object(client.session, "get", return_value=mock_resp):
            result = client.fetch_by_pmid("99999999")

        assert result is None

    def test_pmid_network_error_returns_none(self, client):
        """Network error returns None."""
        with patch.object(
            client.session, "get", side_effect=requests.Timeout("timed out")
        ):
            result = client.fetch_by_pmid("30110588")

        assert result is None

    def test_pmid_none_input_returns_none(self, client):
        """None input returns None without HTTP call."""
        with patch.object(client.session, "get") as mock_get:
            result = client.fetch_by_pmid(None)

        assert result is None
        mock_get.assert_not_called()

    def test_pmid_empty_string_returns_none(self, client):
        """Empty string returns None without HTTP call."""
        with patch.object(client.session, "get") as mock_get:
            result = client.fetch_by_pmid("")

        assert result is None
        mock_get.assert_not_called()


# ---------------------------------------------------------------------------
# search
# ---------------------------------------------------------------------------

class TestSearch:
    """Tests for search returning List[SemanticScholarWork]."""

    def test_search_returns_list_of_results(self, client):
        """Search returns list of SemanticScholarWork results."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = SAMPLE_SEARCH_RESPONSE
        mock_resp.raise_for_status = MagicMock()

        with patch.object(client.session, "get", return_value=mock_resp):
            results = client.search("hypertrophic cardiomyopathy")

        assert isinstance(results, list)
        assert len(results) == 2
        assert all(isinstance(r, SemanticScholarWork) for r in results)
        assert results[0].title == "First Result"
        assert results[1].title == "Second Result"

    def test_search_respects_max_results(self, client):
        """Search passes limit param correctly."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"total": 0, "data": []}
        mock_resp.raise_for_status = MagicMock()

        with patch.object(client.session, "get", return_value=mock_resp) as mock_get:
            client.search("test query", max_results=3)

        call_params = mock_get.call_args[1].get("params", {})
        assert call_params.get("limit") == 3

    def test_empty_search_returns_empty_list(self, client):
        """Empty search results returns empty list."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"total": 0, "data": []}
        mock_resp.raise_for_status = MagicMock()

        with patch.object(client.session, "get", return_value=mock_resp):
            results = client.search("xyznonexistentquery12345")

        assert results == []

    def test_search_network_error_returns_empty_list(self, client):
        """Network error during search returns empty list."""
        with patch.object(
            client.session, "get", side_effect=requests.ConnectionError("fail")
        ):
            results = client.search("some query")

        assert results == []

    def test_search_none_input_returns_empty_list(self, client):
        """None query returns empty list without HTTP call."""
        with patch.object(client.session, "get") as mock_get:
            results = client.search(None)

        assert results == []
        mock_get.assert_not_called()

    def test_search_empty_string_returns_empty_list(self, client):
        """Empty string query returns empty list without HTTP call."""
        with patch.object(client.session, "get") as mock_get:
            results = client.search("")

        assert results == []
        mock_get.assert_not_called()


# ---------------------------------------------------------------------------
# SemanticScholarWork dataclass
# ---------------------------------------------------------------------------

class TestSemanticScholarWork:
    """Tests for the SemanticScholarWork dataclass fields."""

    def test_dataclass_fields(self):
        """SemanticScholarWork has all required fields."""
        work = SemanticScholarWork(
            s2_id="abc123",
            doi="10.1056/test",
            pmid="12345",
            title="Test Paper",
            authors=["Author One"],
            year=2023,
            journal="Test Journal",
            publication_date="2023-01-01",
            abstract="Test abstract.",
            citation_count=42,
            open_access_url="https://example.com/paper.pdf",
        )
        assert work.s2_id == "abc123"
        assert work.doi == "10.1056/test"
        assert work.pmid == "12345"
        assert work.title == "Test Paper"
        assert work.authors == ["Author One"]
        assert work.year == 2023
        assert work.journal == "Test Journal"
        assert work.publication_date == "2023-01-01"
        assert work.abstract == "Test abstract."
        assert work.citation_count == 42
        assert work.open_access_url == "https://example.com/paper.pdf"

    def test_optional_fields_default_to_none(self):
        """Optional fields default to None."""
        work = SemanticScholarWork(
            s2_id="abc",
            doi=None,
            pmid=None,
            title="Minimal",
            authors=[],
            year=None,
            journal=None,
            publication_date=None,
            abstract=None,
            citation_count=0,
            open_access_url=None,
        )
        assert work.doi is None
        assert work.pmid is None
        assert work.year is None
        assert work.journal is None
        assert work.abstract is None
        assert work.open_access_url is None
