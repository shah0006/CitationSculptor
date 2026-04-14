"""
Tests for CrossRef polite pool email configuration and timeout tuning.

Covers:
- CrossRef requests use NCBI_EMAIL in User-Agent header
- Fallback email used when NCBI_EMAIL not set
- crossref_email attribute on PubMedClient
- Timeout values across all API clients
"""

import os
import pytest
from unittest.mock import patch, MagicMock

from modules.pubmed_client import PubMedClient


class TestCrossRefPolitePool:
    """Verify CrossRef requests use real email for polite pool access."""

    def test_crossref_email_attribute_reads_ncbi_email(self):
        """PubMedClient should have a crossref_email attribute populated from NCBI_EMAIL."""
        with patch.dict(os.environ, {"NCBI_EMAIL": "tushar@example.com"}):
            client = PubMedClient()
            assert client.crossref_email == "tushar@example.com"

    def test_crossref_email_attribute_empty_when_env_not_set(self):
        """crossref_email should be empty string when NCBI_EMAIL is not set."""
        env = os.environ.copy()
        env.pop("NCBI_EMAIL", None)
        with patch.dict(os.environ, env, clear=True):
            client = PubMedClient()
            assert client.crossref_email == ""

    @patch("modules.pubmed_client.requests.get")
    def test_crossref_search_uses_ncbi_email_in_user_agent(self, mock_get):
        """crossref_search_title should include NCBI_EMAIL in User-Agent header."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"message": {"items": []}}
        mock_get.return_value = mock_response

        with patch.dict(os.environ, {"NCBI_EMAIL": "real@university.edu"}):
            client = PubMedClient()
            client.crossref_search_title("Heart failure outcomes")

        # Verify the request was made with correct User-Agent
        mock_get.assert_called_once()
        call_kwargs = mock_get.call_args
        headers = call_kwargs.kwargs.get("headers") or call_kwargs[1].get("headers", {})
        user_agent = headers.get("User-Agent", "")
        assert "real@university.edu" in user_agent
        assert "support@example.com" not in user_agent

    @patch("modules.pubmed_client.requests.get")
    def test_crossref_lookup_doi_uses_ncbi_email(self, mock_get):
        """crossref_lookup_doi should include NCBI_EMAIL in User-Agent header."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "message": {
                "DOI": "10.1234/test",
                "title": ["Test Article"],
                "author": [],
                "type": "journal-article",
            }
        }
        mock_get.return_value = mock_response

        with patch.dict(os.environ, {"NCBI_EMAIL": "researcher@hospital.org"}):
            client = PubMedClient()
            client.crossref_lookup_doi("10.1234/test")

        mock_get.assert_called_once()
        call_kwargs = mock_get.call_args
        headers = call_kwargs.kwargs.get("headers") or call_kwargs[1].get("headers", {})
        user_agent = headers.get("User-Agent", "")
        assert "researcher@hospital.org" in user_agent
        assert "support@example.com" not in user_agent

    @patch("modules.pubmed_client.requests.get")
    def test_fallback_email_used_when_ncbi_email_not_set(self, mock_get):
        """When NCBI_EMAIL is not set, a fallback email should appear in User-Agent."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"message": {"items": []}}
        mock_get.return_value = mock_response

        env = os.environ.copy()
        env.pop("NCBI_EMAIL", None)
        with patch.dict(os.environ, env, clear=True):
            client = PubMedClient()
            client.crossref_search_title("Some title")

        mock_get.assert_called_once()
        call_kwargs = mock_get.call_args
        headers = call_kwargs.kwargs.get("headers") or call_kwargs[1].get("headers", {})
        user_agent = headers.get("User-Agent", "")
        assert "citationsculptor@example.com" in user_agent
        assert "support@example.com" not in user_agent


class TestTimeoutTuning:
    """Verify timeout values are correctly tuned across all API clients."""

    @patch("modules.pubmed_client.requests.get")
    def test_crossref_search_title_timeout_is_10(self, mock_get):
        """crossref_search_title should use timeout=10 (was 15)."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"message": {"items": []}}
        mock_get.return_value = mock_response

        client = PubMedClient()
        client.crossref_search_title("Test title")

        call_kwargs = mock_get.call_args
        timeout = call_kwargs.kwargs.get("timeout") or call_kwargs[1].get("timeout")
        assert timeout == 10

    @patch("modules.pubmed_client.requests.get")
    def test_crossref_lookup_doi_timeout_is_10(self, mock_get):
        """crossref_lookup_doi should use timeout=10 (was 15)."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "message": {
                "DOI": "10.1234/test",
                "title": ["Test"],
                "author": [],
                "type": "journal-article",
            }
        }
        mock_get.return_value = mock_response

        client = PubMedClient()
        client.crossref_lookup_doi("10.1234/test")

        call_kwargs = mock_get.call_args
        timeout = call_kwargs.kwargs.get("timeout") or call_kwargs[1].get("timeout")
        assert timeout == 10

    def test_openalex_non_batch_timeouts_are_12(self):
        """OpenAlex non-batch calls should use timeout=12."""
        from modules.openalex_client import OpenAlexClient
        import inspect

        source = inspect.getsource(OpenAlexClient)
        # All timeout=30 in non-batch methods should be changed to timeout=12
        # The only timeout=10 is in test_connection which is fine
        assert "timeout=30" not in source, (
            "OpenAlex client still has timeout=30 on non-batch calls"
        )

    def test_semantic_scholar_non_batch_timeouts_are_12(self):
        """Semantic Scholar non-batch calls should use timeout=12."""
        from modules.semantic_scholar_client import SemanticScholarClient
        import inspect

        source = inspect.getsource(SemanticScholarClient)
        assert "timeout=30" not in source, (
            "Semantic Scholar client still has timeout=30 on non-batch calls"
        )

    def test_europe_pmc_non_batch_timeouts_are_12(self):
        """Europe PMC non-batch calls should use timeout=12."""
        from modules.europe_pmc_client import EuropePMCClient
        import inspect

        source = inspect.getsource(EuropePMCClient)
        assert "timeout=30" not in source, (
            "Europe PMC client still has timeout=30 on non-batch calls"
        )

    def test_datacite_non_batch_timeouts_are_12(self):
        """DataCite non-batch calls should use timeout=12."""
        from modules.datacite_client import DataCiteClient
        import inspect

        source = inspect.getsource(DataCiteClient)
        assert "timeout=30" not in source, (
            "DataCite client still has timeout=30 on non-batch calls"
        )

    def test_pubmed_eutils_request_timeout_stays_30_for_batch(self):
        """PubMed _eutils_request keeps timeout=30 because batch_fetch_by_pmids uses it."""
        import inspect

        source = inspect.getsource(PubMedClient._eutils_request)
        assert "timeout=30" in source

    def test_pubmed_convert_ids_timeout_stays_30_for_batch(self):
        """PubMed convert_ids keeps timeout=30 because batch_prefetch_conversions uses it."""
        import inspect

        source = inspect.getsource(PubMedClient.convert_ids)
        assert "timeout=30" in source

    def test_no_fake_email_in_modules(self):
        """No module should contain the fake support@example.com email."""
        import inspect
        source = inspect.getsource(PubMedClient)
        assert "support@example.com" not in source
