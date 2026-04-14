"""
Tests for PubMed batch fetch capability.

Tests cover:
- PubMedClient.batch_fetch_by_pmids() - batched efetch API calls
- CitationLookup.batch_lookup_pmids() - cache-aware batch lookup with formatting
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, call
import xml.etree.ElementTree as ET
from dataclasses import asdict

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from modules.pubmed_client import PubMedClient, ArticleMetadata
from citation_lookup import CitationLookup, LookupResult


def _make_pubmed_article_xml(pmid: str, title: str = "Test Article",
                              authors: list = None, journal: str = "Test J",
                              year: str = "2023", volume: str = "1",
                              issue: str = "1", pages: str = "1-10",
                              doi: str = None) -> str:
    """Build a PubmedArticle XML string for testing."""
    if authors is None:
        authors = [("Smith", "AB")]

    author_xml = ""
    for last, initials in authors:
        author_xml += f"<Author><LastName>{last}</LastName><Initials>{initials}</Initials></Author>"

    doi_xml = ""
    if doi:
        doi_xml = f'<ELocationID EIdType="doi">{doi}</ELocationID>'

    return f"""<PubmedArticle>
  <MedlineCitation>
    <PMID>{pmid}</PMID>
    <Article>
      <ArticleTitle>{title}</ArticleTitle>
      <AuthorList>{author_xml}</AuthorList>
      <Journal>
        <Title>{journal}</Title>
        <ISOAbbreviation>{journal}</ISOAbbreviation>
        <JournalIssue>
          <Volume>{volume}</Volume>
          <Issue>{issue}</Issue>
          <PubDate><Year>{year}</Year></PubDate>
        </JournalIssue>
      </Journal>
      {doi_xml}
      <Pagination><MedlinePgn>{pages}</MedlinePgn></Pagination>
    </Article>
  </MedlineCitation>
  <PubmedData><ArticleIdList></ArticleIdList></PubmedData>
</PubmedArticle>"""


def _make_article_set_xml(*article_xmls: str) -> ET.Element:
    """Wrap PubmedArticle XMLs into a PubmedArticleSet element."""
    xml_str = f"<PubmedArticleSet>{''.join(article_xmls)}</PubmedArticleSet>"
    return ET.fromstring(xml_str)


class TestBatchFetchByPmids:
    """Tests for PubMedClient.batch_fetch_by_pmids()."""

    def test_single_pmid_in_batch(self):
        """A batch of one PMID should return a dict with that PMID's metadata."""
        client = PubMedClient()
        article_xml = _make_pubmed_article_xml("30110588", title="Single Article")
        mock_response = _make_article_set_xml(article_xml)

        with patch.object(client, '_eutils_request', return_value=mock_response) as mock_req:
            results = client.batch_fetch_by_pmids(["30110588"])

        assert len(results) == 1
        assert "30110588" in results
        assert results["30110588"] is not None
        assert results["30110588"].pmid == "30110588"
        assert results["30110588"].title == "Single Article"
        mock_req.assert_called_once()

    def test_multiple_pmids_in_batch(self):
        """Batch with multiple PMIDs returns metadata for each."""
        client = PubMedClient()
        art1 = _make_pubmed_article_xml("30110588", title="Article One")
        art2 = _make_pubmed_article_xml("32755608", title="Article Two")
        art3 = _make_pubmed_article_xml("28886413", title="Article Three")
        mock_response = _make_article_set_xml(art1, art2, art3)

        with patch.object(client, '_eutils_request', return_value=mock_response):
            results = client.batch_fetch_by_pmids(["30110588", "32755608", "28886413"])

        assert len(results) == 3
        assert results["30110588"].title == "Article One"
        assert results["32755608"].title == "Article Two"
        assert results["28886413"].title == "Article Three"

    def test_missing_pmid_maps_to_none(self):
        """If a requested PMID is not in the API response, map it to None."""
        client = PubMedClient()
        # Request 3 PMIDs but response only contains 2
        art1 = _make_pubmed_article_xml("30110588", title="Found One")
        art2 = _make_pubmed_article_xml("32755608", title="Found Two")
        mock_response = _make_article_set_xml(art1, art2)

        with patch.object(client, '_eutils_request', return_value=mock_response):
            results = client.batch_fetch_by_pmids(["30110588", "32755608", "99999999"])

        assert len(results) == 3
        assert results["30110588"] is not None
        assert results["32755608"] is not None
        assert results["99999999"] is None

    def test_chunk_splitting(self):
        """201 PMIDs should result in 2 API calls (chunk_size=200)."""
        client = PubMedClient()
        pmids = [str(10000000 + i) for i in range(201)]

        # First chunk: 200 PMIDs, second chunk: 1 PMID
        art_chunk1 = [_make_pubmed_article_xml(p, title=f"Art {p}") for p in pmids[:200]]
        art_chunk2 = [_make_pubmed_article_xml(pmids[200], title=f"Art {pmids[200]}")]

        response1 = _make_article_set_xml(*art_chunk1)
        response2 = _make_article_set_xml(*art_chunk2)

        with patch.object(client, '_eutils_request', side_effect=[response1, response2]) as mock_req:
            results = client.batch_fetch_by_pmids(pmids, chunk_size=200)

        assert mock_req.call_count == 2
        assert len(results) == 201
        # Verify all PMIDs have results
        for p in pmids:
            assert p in results
            assert results[p] is not None

    def test_empty_list_returns_empty_dict(self):
        """Empty PMID list should return empty dict without API calls."""
        client = PubMedClient()

        with patch.object(client, '_eutils_request') as mock_req:
            results = client.batch_fetch_by_pmids([])

        assert results == {}
        mock_req.assert_not_called()

    def test_api_error_returns_nones_for_chunk(self):
        """If API call fails for a chunk, all PMIDs in that chunk get None."""
        client = PubMedClient()

        with patch.object(client, '_eutils_request', return_value=None):
            results = client.batch_fetch_by_pmids(["30110588", "32755608"])

        assert len(results) == 2
        assert results["30110588"] is None
        assert results["32755608"] is None

    def test_rate_limiter_called_once_per_chunk_not_per_pmid(self):
        """Rate limiter should be called once per chunk, not once per PMID."""
        client = PubMedClient()
        pmids = [str(10000000 + i) for i in range(5)]

        art_xmls = [_make_pubmed_article_xml(p) for p in pmids]
        mock_response = _make_article_set_xml(*art_xmls)

        # _eutils_request already calls rate limiter internally, so we mock
        # at the level above: patch _eutils_request and check call count
        with patch.object(client, '_eutils_request', return_value=mock_response) as mock_req:
            results = client.batch_fetch_by_pmids(pmids, chunk_size=200)

        # 5 PMIDs with chunk_size=200 -> 1 chunk -> 1 API call
        mock_req.assert_called_once()
        assert len(results) == 5

    def test_custom_chunk_size(self):
        """Custom chunk_size of 2 with 5 PMIDs should make 3 API calls."""
        client = PubMedClient()
        pmids = ["111", "222", "333", "444", "555"]

        def make_response(chunk):
            arts = [_make_pubmed_article_xml(p) for p in chunk]
            return _make_article_set_xml(*arts)

        responses = [
            make_response(["111", "222"]),
            make_response(["333", "444"]),
            make_response(["555"]),
        ]

        with patch.object(client, '_eutils_request', side_effect=responses) as mock_req:
            results = client.batch_fetch_by_pmids(pmids, chunk_size=2)

        assert mock_req.call_count == 3
        assert len(results) == 5

    def test_partial_chunk_error(self):
        """If second chunk fails, first chunk results preserved, second gets None."""
        client = PubMedClient()
        pmids = ["111", "222", "333"]

        art1 = _make_pubmed_article_xml("111", title="Good")
        response1 = _make_article_set_xml(art1, _make_pubmed_article_xml("222"))

        with patch.object(client, '_eutils_request', side_effect=[response1, None]) as mock_req:
            results = client.batch_fetch_by_pmids(pmids, chunk_size=2)

        assert results["111"] is not None
        assert results["222"] is not None
        assert results["333"] is None


class TestBatchLookupPmids:
    """Tests for CitationLookup.batch_lookup_pmids()."""

    def _make_mock_metadata(self, pmid: str, title: str = "Test") -> ArticleMetadata:
        return ArticleMetadata(
            pmid=pmid, title=title, authors=["Smith AB"],
            journal="Test Journal", journal_abbreviation="Test J",
            year="2023", month="Jan", volume="1", issue="1",
            pages="1-10", doi=f"10.1234/{pmid}", abstract="Abstract",
            pub_date="2023 Jan",
        )

    def test_batch_returns_results_in_order(self):
        """Results should be in the same order as input PMIDs."""
        lookup = CitationLookup(use_cache=False)
        pmids = ["111", "222", "333"]

        meta_map = {
            "111": self._make_mock_metadata("111", "First"),
            "222": self._make_mock_metadata("222", "Second"),
            "333": self._make_mock_metadata("333", "Third"),
        }

        with patch.object(lookup.pubmed_client, 'batch_fetch_by_pmids', return_value=meta_map):
            results = lookup.batch_lookup_pmids(pmids)

        assert len(results) == 3
        assert results[0].identifier == "111"
        assert results[1].identifier == "222"
        assert results[2].identifier == "333"
        assert all(r.success for r in results)

    def test_batch_uses_cache_for_known_pmids(self):
        """Cached PMIDs should not be fetched from API."""
        lookup = CitationLookup(use_cache=True)

        # Pre-populate cache
        cached_result = LookupResult(
            success=True, identifier="111", identifier_type="pmid",
            inline_mark="[^cached]", endnote_citation="Cached citation",
            full_citation="Cached citation", metadata={"pmid": "111"},
        )
        with patch.object(lookup, '_check_cache', side_effect=lambda t, i: cached_result if i == "111" else None):
            meta_222 = self._make_mock_metadata("222", "Fetched")
            with patch.object(lookup.pubmed_client, 'batch_fetch_by_pmids', return_value={"222": meta_222}) as mock_batch:
                results = lookup.batch_lookup_pmids(["111", "222"])

        assert len(results) == 2
        # First result from cache
        assert results[0].full_citation == "Cached citation"
        # batch_fetch_by_pmids called only with uncached PMIDs
        mock_batch.assert_called_once_with(["222"])

    def test_batch_caches_new_results(self):
        """Newly fetched results should be cached."""
        lookup = CitationLookup(use_cache=True)

        meta = self._make_mock_metadata("111", "New Article")

        with patch.object(lookup, '_check_cache', return_value=None):
            with patch.object(lookup.pubmed_client, 'batch_fetch_by_pmids', return_value={"111": meta}):
                with patch.object(lookup, '_cache_result') as mock_cache:
                    results = lookup.batch_lookup_pmids(["111"])

        assert len(results) == 1
        assert results[0].success is True
        mock_cache.assert_called_once()

    def test_batch_failed_pmid(self):
        """PMIDs that return None from batch fetch should produce failed LookupResults."""
        lookup = CitationLookup(use_cache=False)

        with patch.object(lookup.pubmed_client, 'batch_fetch_by_pmids', return_value={"999": None}):
            results = lookup.batch_lookup_pmids(["999"])

        assert len(results) == 1
        assert results[0].success is False
        assert results[0].identifier == "999"

    def test_batch_empty_list(self):
        """Empty input should return empty list."""
        lookup = CitationLookup(use_cache=False)
        results = lookup.batch_lookup_pmids([])
        assert results == []
