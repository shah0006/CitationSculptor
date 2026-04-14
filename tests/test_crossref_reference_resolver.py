"""
Tests for CrossRefReferenceResolver.

Verifies that the resolver correctly fetches reference DOIs from CrossRef's
API for a citing article, parsing various publisher key formats (Elsevier,
Springer, Wiley, fallback sequential).
"""

import pytest
from unittest.mock import MagicMock, patch
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from modules.pdf_extractor import CrossRefReferenceResolver


def _mock_crossref_response(refs: list) -> MagicMock:
    """Build a mock requests.Response for a CrossRef works/{doi} response."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "status": "ok",
        "message": {
            "DOI": "10.1016/j.jacc.2021.12.002",
            "reference": refs
        }
    }
    return mock_resp


class TestParseRefNum:
    """Unit tests for _parse_ref_num key parsing."""

    def setup_method(self):
        self.resolver = CrossRefReferenceResolver()

    def test_elsevier_bib_key(self):
        assert self.resolver._parse_ref_num("10.1016/j.jacc.2021.12.002_bib42", 0) == 42

    def test_elsevier_bib_key_bib1(self):
        assert self.resolver._parse_ref_num("10.1016/j.jacc.2021.12.002_bib1", 99) == 1

    def test_springer_cr_key(self):
        assert self.resolver._parse_ref_num("10.1007/s00432-021_CR15_2021", 0) == 15

    def test_wiley_dash_bib_key(self):
        assert self.resolver._parse_ref_num("10.1002/hep.30000-bib7", 0) == 7

    def test_empty_key_uses_fallback(self):
        assert self.resolver._parse_ref_num("", 5) == 5

    def test_unrecognized_key_uses_fallback(self):
        assert self.resolver._parse_ref_num("some-random-key-format", 12) == 12


class TestFetchReferenceDois:
    """Tests for CrossRefReferenceResolver.fetch_reference_dois()."""

    def setup_method(self):
        self.resolver = CrossRefReferenceResolver(email="test@example.com")

    def test_returns_doi_map_for_known_article(self):
        mock_refs = [
            {
                "key": "10.1016/j.jacc.2021.12.002_bib1",
                "DOI": "10.1056/NEJMra1710575",
                "doi-asserted-by": "crossref"
            },
            {
                "key": "10.1016/j.jacc.2021.12.002_bib2",
                "DOI": "10.1001/jamacardio.2015.0354",
                "doi-asserted-by": "crossref"
            },
        ]
        mock_resp = _mock_crossref_response(mock_refs)

        with patch.object(self.resolver.session, 'get', return_value=mock_resp):
            result = self.resolver.fetch_reference_dois("10.1016/j.jacc.2021.12.002")

        assert result[1] == "10.1056/NEJMra1710575"
        assert result[2] == "10.1001/jamacardio.2015.0354"
        assert len(result) == 2

    def test_skips_refs_without_doi(self):
        mock_refs = [
            {"key": "10.1016/j.jacc.2021.12.002_bib1", "DOI": "10.1056/NEJMra1710575"},
            {"key": "10.1016/j.jacc.2021.12.002_bib2"},  # No DOI field
            {"key": "10.1016/j.jacc.2021.12.002_bib3", "DOI": ""},  # Empty DOI
        ]
        mock_resp = _mock_crossref_response(mock_refs)

        with patch.object(self.resolver.session, 'get', return_value=mock_resp):
            result = self.resolver.fetch_reference_dois("10.1016/j.jacc.2021.12.002")

        assert len(result) == 1
        assert 2 not in result
        assert 3 not in result

    def test_returns_empty_on_404(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 404

        with patch.object(self.resolver.session, 'get', return_value=mock_resp):
            result = self.resolver.fetch_reference_dois("10.9999/nonexistent")

        assert result == {}

    def test_returns_empty_on_no_reference_list(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"status": "ok", "message": {"DOI": "10.1016/x"}}

        with patch.object(self.resolver.session, 'get', return_value=mock_resp):
            result = self.resolver.fetch_reference_dois("10.1016/x")

        assert result == {}

    def test_strips_doi_prefix(self):
        """Should strip https://doi.org/ prefix before API call."""
        mock_resp = _mock_crossref_response([])
        mock_resp.status_code = 200

        with patch.object(self.resolver.session, 'get', return_value=mock_resp) as mock_get:
            self.resolver.fetch_reference_dois("https://doi.org/10.1016/j.jacc.2021.12.002")

        call_args = mock_get.call_args
        assert "10.1016/j.jacc.2021.12.002" in call_args[0][0]
        assert "https://doi.org/" not in call_args[0][0]

    def test_returns_empty_on_network_error(self):
        import requests as req
        with patch.object(self.resolver.session, 'get', side_effect=req.RequestException("timeout")):
            result = self.resolver.fetch_reference_dois("10.1016/j.jacc.2021.12.002")
        assert result == {}

    def test_fallback_sequential_numbering(self):
        """When keys have no parseable number, uses sequential position."""
        mock_refs = [
            {"key": "alpha", "DOI": "10.1056/NEJM1"},
            {"key": "beta", "DOI": "10.1056/NEJM2"},
            {"key": "gamma", "DOI": "10.1056/NEJM3"},
        ]
        mock_resp = _mock_crossref_response(mock_refs)

        with patch.object(self.resolver.session, 'get', return_value=mock_resp):
            result = self.resolver.fetch_reference_dois("10.1016/j.jacc.2021.12.002")

        assert result[1] == "10.1056/NEJM1"
        assert result[2] == "10.1056/NEJM2"
        assert result[3] == "10.1056/NEJM3"


class TestResolveMarcaMaronPDF:
    """Verify the complete pipeline: PDF DOI extraction → CrossRef reference lookup."""

    def setup_method(self):
        self.resolver = CrossRefReferenceResolver(email="test@example.com")

    def test_resolve_from_pdf_uses_page1_doi(self, tmp_path):
        """resolve_from_pdf() should find article DOI from page 1 annotation."""
        pdf = tmp_path / "maron.pdf"
        pdf.write_bytes(b"%PDF-1.4")

        from modules.pdf_extractor import PDFReferenceLink, PDFExtractor

        mock_links = [
            PDFReferenceLink(link_type='doi', url='https://doi.org/10.1016/j.jacc.2021.12.002',
                             doi='10.1016/j.jacc.2021.12.002', page_num=1),
            PDFReferenceLink(link_type='refhub', url='http://refhub.elsevier.com/S/sref1',
                             ref_num=1, page_num=16),
        ]

        mock_crossref_resp = _mock_crossref_response([
            {"key": "10.1016/j.jacc.2021.12.002_bib1", "DOI": "10.1056/NEJMra1710575"},
            {"key": "10.1016/j.jacc.2021.12.002_bib5", "DOI": "10.1161/CIRCULATIONAHA.116.022240"},
        ])

        with patch.object(PDFExtractor, 'extract_reference_links', return_value=mock_links), \
             patch.object(PDFExtractor, 'extract_metadata', return_value=None), \
             patch.object(self.resolver.session, 'get', return_value=mock_crossref_resp):
            result = self.resolver.resolve_from_pdf(str(pdf))

        assert result[1] == "10.1056/NEJMra1710575"
        assert result[5] == "10.1161/CIRCULATIONAHA.116.022240"

    def test_resolve_from_pdf_returns_empty_when_no_article_doi(self, tmp_path):
        """Returns empty dict when article DOI cannot be found."""
        pdf = tmp_path / "nodoi.pdf"
        pdf.write_bytes(b"%PDF-1.4")

        from modules.pdf_extractor import PDFExtractor

        with patch.object(PDFExtractor, 'extract_reference_links', return_value=[]), \
             patch.object(PDFExtractor, 'extract_metadata', return_value=None):
            result = self.resolver.resolve_from_pdf(str(pdf))

        assert result == {}
