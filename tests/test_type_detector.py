"""
Tests for the Citation Type Detector module.
"""

import pytest
from modules.type_detector import CitationTypeDetector, CitationType


class TestCitationTypeDetector:
    """Test cases for CitationTypeDetector."""

    def setup_method(self):
        """Set up test fixtures."""
        self.detector = CitationTypeDetector()

    def test_detect_pubmed_url(self):
        """Test detection of PubMed URLs."""
        urls = [
            "https://pubmed.ncbi.nlm.nih.gov/12345678/",
            "https://www.ncbi.nlm.nih.gov/pubmed/12345678",
            "https://pmc.ncbi.nlm.nih.gov/articles/PMC1234567/",
        ]

        for url in urls:
            result = self.detector.detect_type(url)
            assert result == CitationType.JOURNAL_ARTICLE, f"Failed for {url}"

    def test_detect_doi_url(self):
        """Test detection of DOI URLs."""
        url = "https://doi.org/10.1234/journal.123456"
        result = self.detector.detect_type(url)
        assert result == CitationType.JOURNAL_ARTICLE

    def test_detect_journal_domains(self):
        """Test detection of known journal domains."""
        urls = [
            ("https://www.nature.com/articles/s41586", CitationType.JOURNAL_ARTICLE),
            ("https://jamanetwork.com/journals/jama/article", CitationType.JOURNAL_ARTICLE),
            ("https://www.nejm.org/doi/full/10.1056", CitationType.JOURNAL_ARTICLE),
        ]

        for url, expected in urls:
            result = self.detector.detect_type(url)
            assert result == expected, f"Failed for {url}"

    def test_detect_newspaper(self):
        """Test detection of newspaper domains."""
        urls = [
            ("https://www.nytimes.com/article", CitationType.NEWSPAPER_ARTICLE),
            ("https://www.washingtonpost.com/news", CitationType.NEWSPAPER_ARTICLE),
            ("https://www.naplesnews.com/story", CitationType.NEWSPAPER_ARTICLE),
        ]

        for url, expected in urls:
            result = self.detector.detect_type(url)
            assert result == expected, f"Failed for {url}"

    def test_detect_pdf(self):
        """Test detection of PDF URLs."""
        urls = [
            "https://example.com/document.pdf",
            "https://example.com/files/report.PDF",
        ]

        for url in urls:
            result = self.detector.detect_type(url)
            assert result == CitationType.PDF_DOCUMENT, f"Failed for {url}"

    def test_detect_blog(self):
        """Test detection of blog URLs."""
        urls = [
            ("https://medium.com/article", CitationType.BLOG),
            ("https://example.com/blog/post", CitationType.BLOG),
        ]

        for url, expected in urls:
            result = self.detector.detect_type(url)
            assert result == expected, f"Failed for {url}"

    def test_extract_pmid(self):
        """Test PMID extraction."""
        url = "https://pubmed.ncbi.nlm.nih.gov/12345678/"
        pmid = self.detector.extract_pmid(url)
        assert pmid == "12345678"

    def test_extract_doi(self):
        """Test DOI extraction."""
        url = "https://doi.org/10.1234/journal.abc123"
        doi = self.detector.extract_doi(url)
        assert doi == "10.1234/journal.abc123"

    def test_default_to_webpage(self):
        """Test default fallback to webpage."""
        url = "https://www.example.com/page"
        result = self.detector.detect_type(url)
        assert result == CitationType.WEBPAGE

    def test_none_url(self):
        """Test handling of None URL."""
        result = self.detector.detect_type(None)
        assert result == CitationType.UNKNOWN

