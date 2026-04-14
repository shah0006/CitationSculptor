"""Tests for the Europe PMC Client module.

Tests cover:
- Successful PMID lookup with correct metadata
- Successful DOI lookup with correct title
- Author list parsing from authorString
- Empty results (hitCount: 0) return None
- Network errors return None (never raise)
- Search returns list of results
- None/empty string input returns None without HTTP call
- pubYear correctly cast to int

All tests mock session.get -- never hit the real API.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

from modules.europe_pmc_client import EuropePMCClient, EuropePMCWork


# ---------------------------------------------------------------------------
# Fixtures: reusable API response shapes
# ---------------------------------------------------------------------------

def _make_result(**overrides):
    """Build a single Europe PMC result dict with sensible defaults."""
    base = {
        "id": "30110588",
        "source": "MED",
        "pmid": "30110588",
        "pmcid": "PMC6298001",
        "doi": "10.1056/nejmra1710575",
        "title": "Hypertrophic Cardiomyopathy: A Systematic Review",
        "authorString": "Maron BJ, Desai MY, Nishimura RA",
        "journalTitle": "The New England journal of medicine",
        "journalVolume": "379",
        "issue": "7",
        "pageInfo": "655-668",
        "pubYear": "2018",
        "pubType": "review",
        "abstractText": "Hypertrophic cardiomyopathy is the most common genetic heart disease.",
    }
    base.update(overrides)
    return base


def _wrap_results(results, hit_count=None):
    """Wrap result list in the Europe PMC envelope."""
    if hit_count is None:
        hit_count = len(results)
    return {
        "resultList": {"result": results},
        "hitCount": hit_count,
    }


def _mock_response(json_data, status_code=200):
    """Create a mock requests.Response."""
    resp = Mock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.raise_for_status.return_value = None
    return resp


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestFetchByPMID:
    """Tests for fetch_by_pmid."""

    def test_successful_pmid_lookup_returns_correct_metadata(self):
        """A valid PMID returns an EuropePMCWork with correct title, doi, authors."""
        client = EuropePMCClient()
        client.session = Mock()
        client.session.get.return_value = _mock_response(
            _wrap_results([_make_result()])
        )

        work = client.fetch_by_pmid("30110588")

        assert work is not None
        assert work.title == "Hypertrophic Cardiomyopathy: A Systematic Review"
        assert work.doi == "10.1056/nejmra1710575"
        assert work.pmid == "30110588"
        assert work.pmcid == "PMC6298001"
        assert work.source == "MED"

    def test_pmid_not_found_returns_none(self):
        """hitCount 0 / empty resultList returns None."""
        client = EuropePMCClient()
        client.session = Mock()
        client.session.get.return_value = _mock_response(
            _wrap_results([], hit_count=0)
        )

        result = client.fetch_by_pmid("99999999")
        assert result is None

    def test_none_input_returns_none_without_http(self):
        """None input returns None and makes no HTTP call."""
        client = EuropePMCClient()
        client.session = Mock()

        assert client.fetch_by_pmid(None) is None
        client.session.get.assert_not_called()

    def test_empty_string_returns_none_without_http(self):
        """Empty string returns None and makes no HTTP call."""
        client = EuropePMCClient()
        client.session = Mock()

        assert client.fetch_by_pmid("") is None
        client.session.get.assert_not_called()

    def test_network_error_returns_none(self):
        """Network failure returns None -- never raises."""
        import requests as req
        client = EuropePMCClient()
        client.session = Mock()
        client.session.get.side_effect = req.ConnectionError("timeout")

        result = client.fetch_by_pmid("30110588")
        assert result is None


class TestFetchByDOI:
    """Tests for fetch_by_doi."""

    def test_successful_doi_lookup_returns_correct_title(self):
        """A valid DOI returns the correct title."""
        client = EuropePMCClient()
        client.session = Mock()
        client.session.get.return_value = _mock_response(
            _wrap_results([_make_result()])
        )

        work = client.fetch_by_doi("10.1056/nejmra1710575")

        assert work is not None
        assert work.title == "Hypertrophic Cardiomyopathy: A Systematic Review"

    def test_none_input_returns_none_without_http(self):
        """None DOI returns None and makes no HTTP call."""
        client = EuropePMCClient()
        client.session = Mock()

        assert client.fetch_by_doi(None) is None
        client.session.get.assert_not_called()

    def test_empty_string_returns_none_without_http(self):
        """Empty DOI string returns None without HTTP call."""
        client = EuropePMCClient()
        client.session = Mock()

        assert client.fetch_by_doi("") is None
        client.session.get.assert_not_called()

    def test_network_error_returns_none(self):
        """Network failure returns None."""
        import requests as req
        client = EuropePMCClient()
        client.session = Mock()
        client.session.get.side_effect = req.ConnectionError("refused")

        result = client.fetch_by_doi("10.1056/nejmra1710575")
        assert result is None


class TestAuthorParsing:
    """Tests for authorString parsing into authors list."""

    def test_authors_parsed_from_author_string(self):
        """authorString is split on ', ' into a list."""
        client = EuropePMCClient()
        client.session = Mock()
        client.session.get.return_value = _mock_response(
            _wrap_results([_make_result(
                authorString="Maron BJ, Desai MY, Nishimura RA"
            )])
        )

        work = client.fetch_by_pmid("30110588")
        assert work.authors == ["Maron BJ", "Desai MY", "Nishimura RA"]

    def test_single_author(self):
        """Single author without comma is returned as one-element list."""
        client = EuropePMCClient()
        client.session = Mock()
        client.session.get.return_value = _mock_response(
            _wrap_results([_make_result(authorString="Smith J")])
        )

        work = client.fetch_by_pmid("12345678")
        assert work.authors == ["Smith J"]

    def test_missing_author_string(self):
        """Missing authorString yields empty list."""
        result = _make_result()
        del result["authorString"]

        client = EuropePMCClient()
        client.session = Mock()
        client.session.get.return_value = _mock_response(
            _wrap_results([result])
        )

        work = client.fetch_by_pmid("30110588")
        assert work.authors == []


class TestPubYearCasting:
    """Tests for pubYear -> int conversion."""

    def test_pub_year_cast_to_int(self):
        """pubYear string '2018' is stored as int 2018."""
        client = EuropePMCClient()
        client.session = Mock()
        client.session.get.return_value = _mock_response(
            _wrap_results([_make_result(pubYear="2018")])
        )

        work = client.fetch_by_pmid("30110588")
        assert work.year == 2018
        assert isinstance(work.year, int)

    def test_missing_pub_year_returns_none(self):
        """Missing pubYear yields None for year field."""
        result = _make_result()
        del result["pubYear"]

        client = EuropePMCClient()
        client.session = Mock()
        client.session.get.return_value = _mock_response(
            _wrap_results([result])
        )

        work = client.fetch_by_pmid("30110588")
        assert work.year is None


class TestSearch:
    """Tests for the search method."""

    def test_search_returns_list_of_results(self):
        """Search returns a list of EuropePMCWork objects."""
        client = EuropePMCClient()
        client.session = Mock()

        results_data = [
            _make_result(pmid="111", title="First Result"),
            _make_result(pmid="222", title="Second Result"),
        ]
        client.session.get.return_value = _mock_response(
            _wrap_results(results_data, hit_count=2)
        )

        works = client.search("hypertrophic cardiomyopathy")
        assert len(works) == 2
        assert works[0].title == "First Result"
        assert works[1].title == "Second Result"

    def test_search_empty_query_returns_empty_list(self):
        """Empty query returns empty list without HTTP call."""
        client = EuropePMCClient()
        client.session = Mock()

        result = client.search("")
        assert result == []
        client.session.get.assert_not_called()

    def test_search_none_query_returns_empty_list(self):
        """None query returns empty list without HTTP call."""
        client = EuropePMCClient()
        client.session = Mock()

        result = client.search(None)
        assert result == []
        client.session.get.assert_not_called()

    def test_search_network_error_returns_empty_list(self):
        """Network error during search returns empty list."""
        import requests as req
        client = EuropePMCClient()
        client.session = Mock()
        client.session.get.side_effect = req.ConnectionError("down")

        result = client.search("query")
        assert result == []

    def test_search_respects_max_results(self):
        """max_results is passed as pageSize parameter."""
        client = EuropePMCClient()
        client.session = Mock()
        client.session.get.return_value = _mock_response(
            _wrap_results([_make_result()])
        )

        client.search("test query", max_results=3)

        call_args = client.session.get.call_args
        params = call_args[1].get("params", call_args[0][1] if len(call_args[0]) > 1 else {})
        assert params.get("pageSize") == 3


class TestEuropePMCWorkDataclass:
    """Tests for the EuropePMCWork dataclass itself."""

    def test_all_optional_fields_can_be_none(self):
        """Dataclass accepts None for all Optional fields."""
        work = EuropePMCWork(
            pmid=None,
            pmcid=None,
            doi=None,
            title="Test",
            authors=[],
            year=None,
            journal=None,
            volume=None,
            issue=None,
            pages=None,
            abstract=None,
            source="MED",
        )
        assert work.title == "Test"
        assert work.pmid is None
