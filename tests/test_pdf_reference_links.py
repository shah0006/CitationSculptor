"""
Tests for PDFExtractor.extract_reference_links() and helpers.

These tests verify the link-annotation extraction pipeline that captures
embedded hyperlinks from journal PDFs (doi.org, PubMed, Elsevier refhub, etc.)
without requiring any network calls.
"""

import pytest
from unittest.mock import MagicMock, patch, PropertyMock
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from modules.pdf_extractor import PDFExtractor, PDFReferenceLink


class TestClassifyLink:
    """Unit tests for PDFExtractor._classify_link()."""

    def setup_method(self):
        self.extractor = PDFExtractor()

    def test_doi_org_link(self):
        result = self.extractor._classify_link(
            "https://doi.org/10.1056/NEJMoa1710000", page_num=5
        )
        assert result is not None
        assert result.link_type == 'doi'
        assert result.doi == '10.1056/NEJMoa1710000'
        assert result.page_num == 5

    def test_dx_doi_org_link(self):
        result = self.extractor._classify_link(
            "https://dx.doi.org/10.1016/j.jacc.2021.12.002", page_num=3
        )
        assert result is not None
        assert result.link_type == 'doi'
        assert result.doi == '10.1016/j.jacc.2021.12.002'

    def test_doi_trailing_punctuation_stripped(self):
        result = self.extractor._classify_link(
            "https://doi.org/10.1056/NEJMoa1710000.,", page_num=1
        )
        assert result is not None
        assert result.doi == '10.1056/NEJMoa1710000'

    def test_pubmed_url(self):
        result = self.extractor._classify_link(
            "https://pubmed.ncbi.nlm.nih.gov/30110588/", page_num=2
        )
        assert result is not None
        assert result.link_type == 'pmid'
        assert result.pmid == '30110588'

    def test_pubmed_url_no_trailing_slash(self):
        result = self.extractor._classify_link(
            "https://pubmed.ncbi.nlm.nih.gov/12345678", page_num=2
        )
        assert result is not None
        assert result.link_type == 'pmid'
        assert result.pmid == '12345678'

    def test_elsevier_refhub_link(self):
        result = self.extractor._classify_link(
            "http://refhub.elsevier.com/S0735-1097(21)08273-5/sref42", page_num=16
        )
        assert result is not None
        assert result.link_type == 'refhub'
        assert result.ref_num == 42
        assert result.doi is None

    def test_elsevier_refhub_sciencedirect_variant(self):
        result = self.extractor._classify_link(
            "https://www.sciencedirect.com/science/refhub/S0735-1097(21)08273-5/sref1",
            page_num=16
        )
        assert result is not None
        assert result.link_type == 'refhub'
        assert result.ref_num == 1

    def test_mailto_skipped(self):
        result = self.extractor._classify_link("mailto:author@example.com", page_num=1)
        assert result is None

    def test_fragment_skipped(self):
        result = self.extractor._classify_link("#section1", page_num=1)
        assert result is None

    def test_javascript_skipped(self):
        result = self.extractor._classify_link("javascript:void(0)", page_num=1)
        assert result is None

    def test_other_http_url(self):
        result = self.extractor._classify_link(
            "https://hearthealthbydesign.com/", page_num=18
        )
        assert result is not None
        assert result.link_type == 'other'
        assert result.doi is None
        assert result.pmid is None

    def test_bare_doi_uri(self):
        result = self.extractor._classify_link("10.1056/NEJMoa1710000", page_num=1)
        assert result is not None
        assert result.link_type == 'doi'
        assert result.doi == '10.1056/NEJMoa1710000'


class TestExtractReferenceLinks:
    """Integration tests using a mock PyMuPDF document."""

    def setup_method(self):
        self.extractor = PDFExtractor()

    def _make_mock_doc(self, pages_links: list):
        """Build a mock fitz document with specified links per page."""
        import modules.pdf_extractor as mod
        doc = MagicMock()
        doc.__len__ = MagicMock(return_value=len(pages_links))

        pages = []
        for links in pages_links:
            page = MagicMock()
            page.get_links.return_value = [{'uri': u} for u in links]
            pages.append(page)

        doc.__getitem__ = MagicMock(side_effect=lambda i: pages[i])
        doc.close = MagicMock()
        return doc

    def test_extracts_doi_links(self, tmp_path):
        pdf = tmp_path / "test.pdf"
        pdf.write_bytes(b"%PDF-1.4")

        mock_doc = self._make_mock_doc([
            ["https://doi.org/10.1056/NEJMoa1710000",
             "https://doi.org/10.1016/j.jacc.2021.12.002"]
        ])

        with patch('modules.pdf_extractor.fitz') as mock_fitz:
            mock_fitz.open.return_value = mock_doc
            results = self.extractor.extract_reference_links(str(pdf))

        doi_links = [r for r in results if r.link_type == 'doi']
        assert len(doi_links) == 2
        dois = {r.doi for r in doi_links}
        assert '10.1056/NEJMoa1710000' in dois
        assert '10.1016/j.jacc.2021.12.002' in dois

    def test_deduplicates_refhub_links(self, tmp_path):
        """Elsevier PDFs have 3-5 links per reference -- all same sref; deduplicate."""
        pdf = tmp_path / "test.pdf"
        pdf.write_bytes(b"%PDF-1.4")

        refhub = "http://refhub.elsevier.com/S0735-1097(21)08273-5/sref1"
        mock_doc = self._make_mock_doc([
            [refhub, refhub, refhub]  # Same link 3x for one reference
        ])

        with patch('modules.pdf_extractor.fitz') as mock_fitz:
            mock_fitz.open.return_value = mock_doc
            results = self.extractor.extract_reference_links(str(pdf))

        refhub_links = [r for r in results if r.link_type == 'refhub']
        assert len(refhub_links) == 1
        assert refhub_links[0].ref_num == 1

    def test_extracts_pmid_links(self, tmp_path):
        pdf = tmp_path / "test.pdf"
        pdf.write_bytes(b"%PDF-1.4")

        mock_doc = self._make_mock_doc([
            ["https://pubmed.ncbi.nlm.nih.gov/30110588/"]
        ])

        with patch('modules.pdf_extractor.fitz') as mock_fitz:
            mock_fitz.open.return_value = mock_doc
            results = self.extractor.extract_reference_links(str(pdf))

        pmid_links = [r for r in results if r.link_type == 'pmid']
        assert len(pmid_links) == 1
        assert pmid_links[0].pmid == '30110588'

    def test_returns_empty_for_missing_file(self):
        results = self.extractor.extract_reference_links("/nonexistent/path.pdf")
        assert results == []

    def test_get_all_doi_links(self, tmp_path):
        pdf = tmp_path / "test.pdf"
        pdf.write_bytes(b"%PDF-1.4")

        mock_doc = self._make_mock_doc([
            ["https://doi.org/10.1056/NEJMoa0001",
             "https://doi.org/10.1016/j.jacc.2021.12.002",
             "https://pubmed.ncbi.nlm.nih.gov/12345/"]
        ])

        with patch('modules.pdf_extractor.fitz') as mock_fitz:
            mock_fitz.open.return_value = mock_doc
            dois = self.extractor.get_all_doi_links(str(pdf))

        assert len(dois) == 2
        assert '10.1056/NEJMoa0001' in dois

    def test_build_ref_doi_map_empty_for_refhub(self, tmp_path):
        """Elsevier refhub links have no direct DOI -- map should be empty."""
        pdf = tmp_path / "test.pdf"
        pdf.write_bytes(b"%PDF-1.4")

        mock_doc = self._make_mock_doc([
            ["http://refhub.elsevier.com/S0735-1097(21)08273-5/sref1",
             "http://refhub.elsevier.com/S0735-1097(21)08273-5/sref2"]
        ])

        with patch('modules.pdf_extractor.fitz') as mock_fitz:
            mock_fitz.open.return_value = mock_doc
            ref_map = self.extractor.build_ref_doi_map(str(pdf))

        assert ref_map == {}

    def test_maron_pdf_has_refhub_links_not_dois(self, tmp_path):
        """Simulate the Maron JACC 2022 HCM PDF -- all reference links are refhub."""
        pdf = tmp_path / "maron.pdf"
        pdf.write_bytes(b"%PDF-1.4")

        # Simulate 79 references each with 3 refhub annotations (typical for Elsevier)
        links = []
        for ref_n in range(1, 80):
            url = f"http://refhub.elsevier.com/S0735-1097(21)08273-5/sref{ref_n}"
            links.extend([url, url, url])
        # Plus ref 79 has a website URL
        links.append("https://hearthealthbydesign.com/")

        mock_doc = self._make_mock_doc([links])

        with patch('modules.pdf_extractor.fitz') as mock_fitz:
            mock_fitz.open.return_value = mock_doc
            results = self.extractor.extract_reference_links(str(pdf))

        refhub = [r for r in results if r.link_type == 'refhub']
        doi_links = [r for r in results if r.link_type == 'doi']
        other = [r for r in results if r.link_type == 'other']

        assert len(refhub) == 79          # One per reference (deduplicated)
        assert len(doi_links) == 0         # No direct DOIs in Elsevier refhub PDFs
        assert len(other) == 1             # The hearthealthbydesign.com URL (ref 79)
        assert other[0].url == "https://hearthealthbydesign.com/"
