"""Tests for SemanticScholarClient.batch_fetch method.

[Using: TDD] RED phase -- all tests written before implementation.
Tests cover: batch fetching, null handling, chunking, empty input,
network errors, rate limiting, mixed ID types, and API key headers.
"""

import pytest
from unittest.mock import MagicMock, patch, call
import requests

from modules.semantic_scholar_client import SemanticScholarClient, SemanticScholarWork


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_paper_response(paper_id: str, doi: str = None, pmid: str = None) -> dict:
    """Build a minimal S2 paper response dict."""
    return {
        "paperId": paper_id,
        "externalIds": {"DOI": doi, "PubMed": pmid},
        "title": f"Paper {paper_id}",
        "authors": [{"name": "Test Author"}],
        "year": 2024,
        "venue": "Test Journal",
        "publicationDate": "2024-01-01",
        "abstract": f"Abstract for {paper_id}",
        "citationCount": 42,
        "openAccessPdf": None,
    }


PAPER_A = _make_paper_response("s2_aaa", doi="10.1000/aaa", pmid="11111")
PAPER_B = _make_paper_response("s2_bbb", doi="10.1000/bbb", pmid="22222")
PAPER_C = _make_paper_response("s2_ccc", doi="10.1000/ccc")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestBatchFetch:
    """Tests for SemanticScholarClient.batch_fetch."""

    def _make_client(self) -> SemanticScholarClient:
        """Create a client with zero delay for fast tests."""
        return SemanticScholarClient(request_delay=0.0)

    # -- Core behavior -------------------------------------------------------

    def test_batch_returns_dict_keyed_by_input_id(self):
        """batch_fetch returns a dict mapping each input ID to a SemanticScholarWork."""
        client = self._make_client()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = [PAPER_A, PAPER_B]

        with patch.object(client.session, "post", return_value=mock_resp):
            result = client.batch_fetch(["DOI:10.1000/aaa", "PMID:22222"])

        assert isinstance(result, dict)
        assert len(result) == 2
        assert "DOI:10.1000/aaa" in result
        assert "PMID:22222" in result
        assert isinstance(result["DOI:10.1000/aaa"], SemanticScholarWork)
        assert result["DOI:10.1000/aaa"].doi == "10.1000/aaa"
        assert result["PMID:22222"].pmid == "22222"

    def test_batch_maps_nulls_to_none(self):
        """Null entries in S2 response map to None in the output dict."""
        client = self._make_client()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = [PAPER_A, None, PAPER_C]

        with patch.object(client.session, "post", return_value=mock_resp):
            result = client.batch_fetch(
                ["DOI:10.1000/aaa", "PMID:99999", "DOI:10.1000/ccc"]
            )

        assert result["DOI:10.1000/aaa"] is not None
        assert result["PMID:99999"] is None
        assert result["DOI:10.1000/ccc"] is not None

    def test_batch_splits_into_chunks(self):
        """501 IDs should produce exactly 2 POST calls (chunk_size=500)."""
        client = self._make_client()

        ids = [f"DOI:10.1000/paper{i}" for i in range(501)]

        # First chunk: 500 papers, second chunk: 1 paper
        chunk1_response = MagicMock()
        chunk1_response.status_code = 200
        chunk1_response.raise_for_status = MagicMock()
        chunk1_response.json.return_value = [
            _make_paper_response(f"s2_{i}") for i in range(500)
        ]

        chunk2_response = MagicMock()
        chunk2_response.status_code = 200
        chunk2_response.raise_for_status = MagicMock()
        chunk2_response.json.return_value = [_make_paper_response("s2_500")]

        with patch.object(
            client.session, "post", side_effect=[chunk1_response, chunk2_response]
        ) as mock_post:
            result = client.batch_fetch(ids)

        assert mock_post.call_count == 2
        assert len(result) == 501

        # Verify first call has 500 IDs, second has 1
        first_call_body = mock_post.call_args_list[0]
        second_call_body = mock_post.call_args_list[1]
        assert len(first_call_body.kwargs.get("json", {}).get("ids", [])) == 500
        assert len(second_call_body.kwargs.get("json", {}).get("ids", [])) == 1

    def test_batch_empty_list_returns_empty_dict(self):
        """Empty input list returns empty dict without any HTTP calls."""
        client = self._make_client()

        with patch.object(client.session, "post") as mock_post:
            result = client.batch_fetch([])

        assert result == {}
        mock_post.assert_not_called()

    def test_batch_network_error_returns_nones(self):
        """Network error during a chunk returns None for all IDs in that chunk."""
        client = self._make_client()

        with patch.object(
            client.session, "post", side_effect=requests.ConnectionError("timeout")
        ):
            result = client.batch_fetch(["DOI:10.1000/aaa", "PMID:22222"])

        assert len(result) == 2
        assert result["DOI:10.1000/aaa"] is None
        assert result["PMID:22222"] is None

    def test_rate_limiter_called_once_per_chunk(self):
        """_rate_limit is called exactly once per chunk, not once per ID."""
        client = self._make_client()

        ids = [f"DOI:10.1000/paper{i}" for i in range(3)]

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = [
            _make_paper_response(f"s2_{i}") for i in range(3)
        ]

        with patch.object(client.session, "post", return_value=mock_resp), \
             patch.object(client, "_rate_limit") as mock_rl:
            client.batch_fetch(ids, chunk_size=500)

        # 3 IDs, chunk_size=500 -> 1 chunk -> 1 rate_limit call
        mock_rl.assert_called_once()

    def test_mixed_id_types_in_one_call(self):
        """DOI: and PMID: IDs can be mixed in a single batch call."""
        client = self._make_client()

        mixed_ids = ["DOI:10.1000/aaa", "PMID:22222", "ARXIV:2301.04104"]

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = [PAPER_A, PAPER_B, PAPER_C]

        with patch.object(client.session, "post", return_value=mock_resp) as mock_post:
            result = client.batch_fetch(mixed_ids)

        # Verify all three mixed types were sent in one call
        posted_ids = mock_post.call_args.kwargs.get("json", {}).get("ids", [])
        assert posted_ids == mixed_ids
        assert len(result) == 3

    def test_api_key_in_header_when_env_set(self):
        """When SEMANTIC_SCHOLAR_API_KEY is set, x-api-key header is present."""
        with patch.dict("os.environ", {"SEMANTIC_SCHOLAR_API_KEY": "test-key-123"}):
            client = SemanticScholarClient(request_delay=0.0)

        assert client.session.headers.get("x-api-key") == "test-key-123"

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = [PAPER_A]

        with patch.object(client.session, "post", return_value=mock_resp) as mock_post:
            client.batch_fetch(["DOI:10.1000/aaa"])

        # Session headers carry the key into the POST call
        assert client.session.headers["x-api-key"] == "test-key-123"
