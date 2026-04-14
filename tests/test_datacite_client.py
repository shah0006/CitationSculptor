"""Tests for the DataCite API Client Module.

Tests cover:
- DOI lookup with correct field extraction
- Author name construction (givenName+familyName vs name fallback)
- Abstract extraction from descriptions list
- Related DOI extraction from relatedIdentifiers
- 404 / not found returns None
- Network error returns None (never raises)
- Search returns list of results
- Empty search results returns empty list
- None / empty DOI returns None without HTTP call
- DOI URL-encoding in path

All tests mock session.get -- never hit the real API.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from requests.exceptions import ConnectionError, Timeout

from modules.datacite_client import DataCiteClient, DataCiteWork


def _make_datacite_response(doi="10.5061/dryad.1g2nt40", **overrides):
    """Build a realistic DataCite API response for a single DOI lookup."""
    attrs = {
        "doi": doi,
        "titles": [{"title": "Data from: Cardiac Biomarker Study"}],
        "creators": [
            {"name": "Smith, John", "givenName": "John", "familyName": "Smith"},
            {"name": "Doe, Jane", "givenName": "Jane", "familyName": "Doe"},
        ],
        "publicationYear": 2019,
        "publisher": "Dryad",
        "container": {"title": "Dryad Digital Repository"},
        "descriptions": [
            {"description": "This dataset contains cardiac biomarker measurements.", "descriptionType": "Abstract"},
            {"description": "Methods section text here.", "descriptionType": "Methods"},
        ],
        "types": {"resourceTypeGeneral": "Dataset"},
        "relatedIdentifiers": [
            {
                "relatedIdentifier": "10.1234/journal.1234",
                "relatedIdentifierType": "DOI",
                "relationType": "IsSupplementTo",
            },
            {
                "relatedIdentifier": "10.9999/other",
                "relatedIdentifierType": "DOI",
                "relationType": "References",
            },
        ],
        "url": "https://datadryad.org/stash/dataset/doi:10.5061/dryad.1g2nt40",
    }
    attrs.update(overrides)
    return {
        "data": {
            "id": doi,
            "type": "dois",
            "attributes": attrs,
        }
    }


def _make_search_response(items=None):
    """Build a DataCite search response with a data array."""
    if items is None:
        items = [
            {
                "id": "10.5061/dryad.1g2nt40",
                "type": "dois",
                "attributes": {
                    "doi": "10.5061/dryad.1g2nt40",
                    "titles": [{"title": "Dataset Alpha"}],
                    "creators": [{"name": "Alpha, A.", "givenName": "A.", "familyName": "Alpha"}],
                    "publicationYear": 2020,
                    "publisher": "Zenodo",
                    "container": {},
                    "descriptions": [],
                    "types": {"resourceTypeGeneral": "Software"},
                    "relatedIdentifiers": [],
                    "url": "https://zenodo.org/record/123",
                },
            },
            {
                "id": "10.5281/zenodo.456",
                "type": "dois",
                "attributes": {
                    "doi": "10.5281/zenodo.456",
                    "titles": [{"title": "Dataset Beta"}],
                    "creators": [{"name": "Beta, B."}],
                    "publicationYear": 2021,
                    "publisher": "Figshare",
                    "container": {},
                    "descriptions": [
                        {"description": "Beta abstract.", "descriptionType": "Abstract"}
                    ],
                    "types": {"resourceTypeGeneral": "Dataset"},
                    "relatedIdentifiers": [],
                    "url": None,
                },
            },
        ]
    return {"data": items}


class TestDataCiteWork:
    """Test the DataCiteWork dataclass."""

    def test_dataclass_fields(self):
        """DataCiteWork holds all expected fields."""
        work = DataCiteWork(
            doi="10.5061/dryad.1g2nt40",
            title="Test Dataset",
            authors=["Smith, John"],
            year=2019,
            publisher="Dryad",
            resource_type="Dataset",
            abstract="Abstract text.",
            url="https://example.com",
            related_doi="10.1234/journal.1234",
        )
        assert work.doi == "10.5061/dryad.1g2nt40"
        assert work.title == "Test Dataset"
        assert work.authors == ["Smith, John"]
        assert work.year == 2019
        assert work.publisher == "Dryad"
        assert work.resource_type == "Dataset"
        assert work.abstract == "Abstract text."
        assert work.url == "https://example.com"
        assert work.related_doi == "10.1234/journal.1234"


class TestFetchByDoi:
    """Tests for DataCiteClient.fetch_by_doi()."""

    def test_successful_lookup(self):
        """Successful DOI lookup returns DataCiteWork with correct fields."""
        client = DataCiteClient(request_delay=0)
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = _make_datacite_response()
        mock_resp.raise_for_status = Mock()
        client.session.get = Mock(return_value=mock_resp)

        result = client.fetch_by_doi("10.5061/dryad.1g2nt40")

        assert result is not None
        assert result.doi == "10.5061/dryad.1g2nt40"
        assert result.title == "Data from: Cardiac Biomarker Study"
        assert result.year == 2019
        assert result.publisher == "Dryad"
        assert result.resource_type == "Dataset"
        assert result.url == "https://datadryad.org/stash/dataset/doi:10.5061/dryad.1g2nt40"

    def test_authors_from_given_family_name(self):
        """Authors built from familyName, givenName when both present."""
        client = DataCiteClient(request_delay=0)
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = _make_datacite_response()
        mock_resp.raise_for_status = Mock()
        client.session.get = Mock(return_value=mock_resp)

        result = client.fetch_by_doi("10.5061/dryad.1g2nt40")

        assert result.authors == ["Smith, John", "Doe, Jane"]

    def test_authors_name_fallback(self):
        """When givenName/familyName missing, fall back to 'name' field."""
        client = DataCiteClient(request_delay=0)
        response_data = _make_datacite_response(
            creators=[
                {"name": "National Institutes of Health"},
                {"name": "World Health Organization"},
            ]
        )
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = response_data
        mock_resp.raise_for_status = Mock()
        client.session.get = Mock(return_value=mock_resp)

        result = client.fetch_by_doi("10.5061/dryad.1g2nt40")

        assert result.authors == ["National Institutes of Health", "World Health Organization"]

    def test_abstract_extracted_from_descriptions(self):
        """Abstract is extracted only from descriptions with descriptionType 'Abstract'."""
        client = DataCiteClient(request_delay=0)
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = _make_datacite_response()
        mock_resp.raise_for_status = Mock()
        client.session.get = Mock(return_value=mock_resp)

        result = client.fetch_by_doi("10.5061/dryad.1g2nt40")

        assert result.abstract == "This dataset contains cardiac biomarker measurements."

    def test_no_abstract_when_no_abstract_type(self):
        """Abstract is None when no description has descriptionType 'Abstract'."""
        client = DataCiteClient(request_delay=0)
        response_data = _make_datacite_response(
            descriptions=[
                {"description": "Methods only.", "descriptionType": "Methods"}
            ]
        )
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = response_data
        mock_resp.raise_for_status = Mock()
        client.session.get = Mock(return_value=mock_resp)

        result = client.fetch_by_doi("10.5061/dryad.1g2nt40")

        assert result.abstract is None

    def test_related_doi_from_is_supplement_to(self):
        """related_doi populated from first IsSupplementTo relatedIdentifier."""
        client = DataCiteClient(request_delay=0)
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = _make_datacite_response()
        mock_resp.raise_for_status = Mock()
        client.session.get = Mock(return_value=mock_resp)

        result = client.fetch_by_doi("10.5061/dryad.1g2nt40")

        assert result.related_doi == "10.1234/journal.1234"

    def test_related_doi_from_is_part_of(self):
        """related_doi falls back to IsPartOf when no IsSupplementTo."""
        client = DataCiteClient(request_delay=0)
        response_data = _make_datacite_response(
            relatedIdentifiers=[
                {
                    "relatedIdentifier": "10.9999/parent",
                    "relatedIdentifierType": "DOI",
                    "relationType": "IsPartOf",
                }
            ]
        )
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = response_data
        mock_resp.raise_for_status = Mock()
        client.session.get = Mock(return_value=mock_resp)

        result = client.fetch_by_doi("10.5061/dryad.1g2nt40")

        assert result.related_doi == "10.9999/parent"

    def test_related_doi_none_when_no_matching_relation(self):
        """related_doi is None when no IsSupplementTo or IsPartOf relations exist."""
        client = DataCiteClient(request_delay=0)
        response_data = _make_datacite_response(
            relatedIdentifiers=[
                {
                    "relatedIdentifier": "10.9999/other",
                    "relatedIdentifierType": "DOI",
                    "relationType": "References",
                }
            ]
        )
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = response_data
        mock_resp.raise_for_status = Mock()
        client.session.get = Mock(return_value=mock_resp)

        result = client.fetch_by_doi("10.5061/dryad.1g2nt40")

        assert result.related_doi is None

    def test_404_returns_none(self):
        """404 response returns None, not an exception."""
        client = DataCiteClient(request_delay=0)
        mock_resp = Mock()
        mock_resp.status_code = 404
        client.session.get = Mock(return_value=mock_resp)

        result = client.fetch_by_doi("10.9999/nonexistent")

        assert result is None

    def test_network_error_returns_none(self):
        """Network errors return None, never raise."""
        client = DataCiteClient(request_delay=0)
        client.session.get = Mock(side_effect=ConnectionError("DNS failure"))

        result = client.fetch_by_doi("10.5061/dryad.1g2nt40")

        assert result is None

    def test_timeout_returns_none(self):
        """Timeout returns None, never raises."""
        client = DataCiteClient(request_delay=0)
        client.session.get = Mock(side_effect=Timeout("Request timed out"))

        result = client.fetch_by_doi("10.5061/dryad.1g2nt40")

        assert result is None

    def test_none_doi_returns_none_without_http(self):
        """None DOI returns None without making an HTTP call."""
        client = DataCiteClient(request_delay=0)
        client.session.get = Mock()

        result = client.fetch_by_doi(None)

        assert result is None
        client.session.get.assert_not_called()

    def test_empty_doi_returns_none_without_http(self):
        """Empty string DOI returns None without making an HTTP call."""
        client = DataCiteClient(request_delay=0)
        client.session.get = Mock()

        result = client.fetch_by_doi("")

        assert result is None
        client.session.get.assert_not_called()

    def test_whitespace_doi_returns_none_without_http(self):
        """Whitespace-only DOI returns None without making an HTTP call."""
        client = DataCiteClient(request_delay=0)
        client.session.get = Mock()

        result = client.fetch_by_doi("   ")

        assert result is None
        client.session.get.assert_not_called()

    def test_doi_url_encoded_in_path(self):
        """DOI with slash is URL-encoded in the request path."""
        client = DataCiteClient(request_delay=0)
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = _make_datacite_response()
        mock_resp.raise_for_status = Mock()
        client.session.get = Mock(return_value=mock_resp)

        client.fetch_by_doi("10.5061/dryad.1g2nt40")

        call_args = client.session.get.call_args
        url = call_args[0][0] if call_args[0] else call_args[1].get("url", "")
        # The DOI must be URL-encoded: slash becomes %2F
        assert "10.5061%2Fdryad.1g2nt40" in url

    def test_doi_prefix_stripped(self):
        """DOI URL prefixes (https://doi.org/) are stripped before lookup."""
        client = DataCiteClient(request_delay=0)
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = _make_datacite_response()
        mock_resp.raise_for_status = Mock()
        client.session.get = Mock(return_value=mock_resp)

        client.fetch_by_doi("https://doi.org/10.5061/dryad.1g2nt40")

        call_args = client.session.get.call_args
        url = call_args[0][0] if call_args[0] else call_args[1].get("url", "")
        # Should NOT contain double doi.org
        assert "doi.org" not in url
        assert "10.5061%2Fdryad.1g2nt40" in url


class TestSearch:
    """Tests for DataCiteClient.search()."""

    def test_search_returns_list(self):
        """Search returns a list of DataCiteWork objects."""
        client = DataCiteClient(request_delay=0)
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = _make_search_response()
        mock_resp.raise_for_status = Mock()
        client.session.get = Mock(return_value=mock_resp)

        results = client.search("cardiac biomarkers")

        assert isinstance(results, list)
        assert len(results) == 2
        assert results[0].title == "Dataset Alpha"
        assert results[1].title == "Dataset Beta"

    def test_search_populates_fields(self):
        """Search results have correct fields populated."""
        client = DataCiteClient(request_delay=0)
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = _make_search_response()
        mock_resp.raise_for_status = Mock()
        client.session.get = Mock(return_value=mock_resp)

        results = client.search("cardiac")

        assert results[0].doi == "10.5061/dryad.1g2nt40"
        assert results[0].publisher == "Zenodo"
        assert results[0].resource_type == "Software"
        assert results[1].abstract == "Beta abstract."

    def test_search_empty_data_returns_empty_list(self):
        """Empty data array returns empty list."""
        client = DataCiteClient(request_delay=0)
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"data": []}
        mock_resp.raise_for_status = Mock()
        client.session.get = Mock(return_value=mock_resp)

        results = client.search("nonexistent query")

        assert results == []

    def test_search_network_error_returns_empty_list(self):
        """Network errors during search return empty list, never raise."""
        client = DataCiteClient(request_delay=0)
        client.session.get = Mock(side_effect=ConnectionError("Network down"))

        results = client.search("test query")

        assert results == []

    def test_search_passes_max_results(self):
        """Search passes max_results as page[size] parameter."""
        client = DataCiteClient(request_delay=0)
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = _make_search_response(items=[])
        mock_resp.raise_for_status = Mock()
        client.session.get = Mock(return_value=mock_resp)

        client.search("test", max_results=3)

        call_args = client.session.get.call_args
        params = call_args[1].get("params", {}) if call_args[1] else {}
        assert params.get("page[size]") == 3

    def test_search_passes_query_parameter(self):
        """Search passes query string as 'query' parameter."""
        client = DataCiteClient(request_delay=0)
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = _make_search_response(items=[])
        mock_resp.raise_for_status = Mock()
        client.session.get = Mock(return_value=mock_resp)

        client.search("cardiac biomarkers dataset")

        call_args = client.session.get.call_args
        params = call_args[1].get("params", {}) if call_args[1] else {}
        assert params.get("query") == "cardiac biomarkers dataset"


class TestRateLimiting:
    """Tests for rate limiting behavior."""

    def test_rate_limit_enforced(self):
        """Requests respect rate limiting delay."""
        client = DataCiteClient(request_delay=0.05)
        mock_resp = Mock()
        mock_resp.status_code = 404
        client.session.get = Mock(return_value=mock_resp)

        import time
        start = time.time()
        client.fetch_by_doi("10.5061/a")
        client.fetch_by_doi("10.5061/b")
        elapsed = time.time() - start

        # Second call should have waited at least request_delay
        assert elapsed >= 0.04  # Small tolerance
