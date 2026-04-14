"""
Tests for OpenAlexClient.fetch_by_scopus_eid().

All network calls are mocked -- these tests never hit the real OpenAlex API.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from modules.openalex_client import OpenAlexClient, OpenAlexWork


MOCK_OPENALEX_WORK = {
    "id": "https://openalex.org/W2741809809",
    "doi": "https://doi.org/10.1056/nejmra1710575",
    "title": "Clinical Course and Management of Hypertrophic Cardiomyopathy",
    "publication_year": 2018,
    "publication_date": "2018-08-16",
    "type": "journal-article",
    "cited_by_count": 1250,
    "open_access": {"is_oa": False, "oa_url": None},
    "authorships": [
        {"author": {"display_name": "Barry J. Maron"}}
    ],
    "primary_location": {
        "source": {
            "display_name": "New England Journal of Medicine",
            "issn": ["0028-4793"]
        }
    },
    "biblio": {
        "volume": "379",
        "issue": "7",
        "first_page": "655",
        "last_page": "668"
    },
    "ids": {
        "pmid": "https://pubmed.ncbi.nlm.nih.gov/30110588/",
        "pmcid": None
    },
    "concepts": [],
    "referenced_works": []
}


class TestFetchByScopusEid:
    """Tests for OpenAlexClient.fetch_by_scopus_eid."""

    def setup_method(self):
        self.client = OpenAlexClient(email="test@example.com")

    def test_successful_eid_lookup(self):
        """Valid EID should return an OpenAlexWork with DOI and PMID populated."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [MOCK_OPENALEX_WORK],
            "meta": {"count": 1}
        }

        with patch.object(self.client.session, 'get', return_value=mock_response):
            result = self.client.fetch_by_scopus_eid("2-s2.0-85051788505")

        assert result is not None
        assert isinstance(result, OpenAlexWork)
        assert result.doi == "10.1056/nejmra1710575"
        assert result.pmid == "30110588"
        assert result.title == "Clinical Course and Management of Hypertrophic Cardiomyopathy"

    def test_eid_not_found_returns_none(self):
        """EID with no OpenAlex match should return None."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [],
            "meta": {"count": 0}
        }

        with patch.object(self.client.session, 'get', return_value=mock_response):
            result = self.client.fetch_by_scopus_eid("2-s2.0-99999999999")

        assert result is None

    def test_api_error_returns_none(self):
        """Network error should return None without raising."""
        import requests
        with patch.object(self.client.session, 'get', side_effect=requests.RequestException("timeout")):
            result = self.client.fetch_by_scopus_eid("2-s2.0-85051788505")

        assert result is None

    def test_correct_api_url_called(self):
        """Verify the correct OpenAlex filter URL is constructed."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"results": [], "meta": {"count": 0}}

        with patch.object(self.client.session, 'get', return_value=mock_response) as mock_get:
            self.client.fetch_by_scopus_eid("2-s2.0-85051788505")

        call_args = mock_get.call_args
        url = call_args[0][0]
        assert "api.openalex.org/works" in url
        # The EID filter should be in params, not the URL path
        params = call_args[1].get('params', {}) or call_args[0][1] if len(call_args[0]) > 1 else {}
        # Accept either inline or params-dict form
        assert "2-s2.0-85051788505" in str(call_args)

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

    def test_eid_prefix_normalized(self):
        """EID without '2-s2.0-' prefix should still work."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [MOCK_OPENALEX_WORK],
            "meta": {"count": 1}
        }

        with patch.object(self.client.session, 'get', return_value=mock_response):
            # Some callers may pass just the numeric part
            result = self.client.fetch_by_scopus_eid("85051788505")

        # Should still succeed (method normalizes the prefix)
        assert result is not None
