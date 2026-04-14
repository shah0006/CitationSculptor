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


class TestStripProxyUrl:
    """Tests for EZProxy URL stripping."""

    def setup_method(self):
        self.detector = CitationTypeDetector()

    def test_doi_proxy_url(self):
        """DOI proxy URL should be converted to canonical doi.org URL."""
        proxied = "https://doi-org.proxy.lib.ohio-state.edu/10.1056/nejmra1710575"
        result = self.detector.strip_proxy_url(proxied)
        assert result == "https://doi.org/10.1056/nejmra1710575"

    def test_sciencedirect_proxy_url(self):
        """ScienceDirect proxy URL should resolve to canonical domain."""
        proxied = "https://www-sciencedirect-com.proxy.lib.ohio-state.edu/science/article/pii/S0735109721082735"
        result = self.detector.strip_proxy_url(proxied)
        assert result == "https://www.sciencedirect.com/science/article/pii/S0735109721082735"

    def test_scopus_proxy_url(self):
        """Scopus proxy URL should resolve to canonical domain."""
        proxied = "https://www-scopus-com.proxy.lib.ohio-state.edu/inward/record.url?eid=2-s2.0-85051788505"
        result = self.detector.strip_proxy_url(proxied)
        assert result == "https://www.scopus.com/inward/record.url?eid=2-s2.0-85051788505"

    def test_non_proxy_url_unchanged(self):
        """Non-proxy URL must be returned unchanged."""
        url = "https://doi.org/10.1056/nejmra1710575"
        result = self.detector.strip_proxy_url(url)
        assert result == url

    def test_pubmed_proxy_url(self):
        """PubMed proxy URL should resolve correctly."""
        proxied = "https://pubmed-ncbi-nlm-nih-gov.proxy.lib.ohio-state.edu/35086660/"
        result = self.detector.strip_proxy_url(proxied)
        assert result == "https://pubmed.ncbi.nlm.nih.gov/35086660/"

    def test_empty_string(self):
        """Empty string should return empty string."""
        assert self.detector.strip_proxy_url("") == ""

    def test_none_input(self):
        """None should return empty string."""
        assert self.detector.strip_proxy_url(None) == ""

    def test_proxy_doi_still_extractable(self):
        """After stripping, extract_doi should find the DOI."""
        proxied = "https://doi-org.proxy.lib.ohio-state.edu/10.1056/nejmra1710575"
        stripped = self.detector.strip_proxy_url(proxied)
        doi = self.detector.extract_doi(stripped)
        assert doi == "10.1056/nejmra1710575"


class TestParseScholarLookupUrl:
    """Tests for Google Scholar scholar_lookup URL parsing."""

    def setup_method(self):
        self.detector = CitationTypeDetector()

    def test_basic_scholar_url(self):
        """Parse title, year, and authors from a typical scholar_lookup URL."""
        url = (
            "https://scholar.google.com/scholar_lookup"
            "?title=Clinical%20course%20and%20management%20of%20hypertrophic%20cardiomyopathy"
            "&publication_year=2018"
            "&author=B.J.%20Maron"
        )
        result = self.detector.parse_scholar_lookup_url(url)
        assert result is not None
        assert result["title"] == "Clinical course and management of hypertrophic cardiomyopathy"
        assert result["year"] == "2018"
        assert result["authors"] == ["B.J. Maron"]

    def test_multiple_authors(self):
        """Multiple author params should be collected into a list."""
        url = (
            "https://scholar.google.com/scholar_lookup"
            "?title=How%20hypertrophic%20cardiomyopathy%20became%20treatable"
            "&publication_year=2016"
            "&author=B.J.%20Maron"
            "&author=E.J.%20Rowin"
            "&author=S.A.%20Casey"
            "&author=M.S.%20Maron"
        )
        result = self.detector.parse_scholar_lookup_url(url)
        assert result is not None
        assert len(result["authors"]) == 4
        assert "B.J. Maron" in result["authors"]
        assert "M.S. Maron" in result["authors"]

    def test_non_scholar_url_returns_none(self):
        """Non-Scholar URL should return None."""
        url = "https://pubmed.ncbi.nlm.nih.gov/35086660/"
        result = self.detector.parse_scholar_lookup_url(url)
        assert result is None

    def test_scholar_search_url_returns_none(self):
        """scholar.google.com/scholar? (search) is NOT a lookup URL -- return None."""
        url = "https://scholar.google.com/scholar?q=hypertrophic+cardiomyopathy"
        result = self.detector.parse_scholar_lookup_url(url)
        assert result is None

    def test_missing_year_still_parses(self):
        """URL without publication_year should still return title and authors."""
        url = (
            "https://scholar.google.com/scholar_lookup"
            "?title=Some%20article%20title"
            "&author=J.%20Smith"
        )
        result = self.detector.parse_scholar_lookup_url(url)
        assert result is not None
        assert result["title"] == "Some article title"
        assert result["year"] is None

    def test_short_title_returns_none(self):
        """Title with fewer than 4 words is too ambiguous -- return None."""
        url = (
            "https://scholar.google.com/scholar_lookup"
            "?title=Short%20title"
            "&publication_year=2020"
            "&author=J.%20Smith"
        )
        result = self.detector.parse_scholar_lookup_url(url)
        assert result is None

    def test_empty_url(self):
        """Empty string returns None."""
        assert self.detector.parse_scholar_lookup_url("") is None

    def test_plus_encoded_spaces(self):
        """Some Scholar URLs use + for spaces -- should decode correctly."""
        url = (
            "https://scholar.google.com/scholar_lookup"
            "?title=A+Guide+to+Hypertrophic+Cardiomyopathy"
            "&publication_year=2022"
            "&author=B.J.+Maron"
        )
        result = self.detector.parse_scholar_lookup_url(url)
        assert result is not None
        assert result["title"] == "A Guide to Hypertrophic Cardiomyopathy"


class TestExtractScopusEid:
    """Tests for Scopus EID extraction."""

    def setup_method(self):
        self.detector = CitationTypeDetector()

    def test_scopus_record_url(self):
        """EID should be extracted from Scopus record URL."""
        url = "https://www.scopus.com/inward/record.url?eid=2-s2.0-85051788505&partnerID=10&rel=R3.0.0"
        result = self.detector.extract_scopus_eid(url)
        assert result == "2-s2.0-85051788505"

    def test_scopus_proxy_url(self):
        """EID should be extracted from proxy-wrapped Scopus URL."""
        url = "https://www-scopus-com.proxy.lib.ohio-state.edu/inward/record.url?eid=2-s2.0-84979547014&partnerID=10"
        result = self.detector.extract_scopus_eid(url)
        assert result == "2-s2.0-84979547014"

    def test_sciencedirect_pdf_pid(self):
        """EID should be extracted from ScienceDirect PDF pid param."""
        url = "https://www-sciencedirect-com.proxy.lib.ohio-state.edu/science/article/pii/S1936878X16303394/pdfft?md5=e346a48bb04e1a3ec14dabaa3250beb8&pid=1-s2.0-S1936878X16303394-main.pdf"
        result = self.detector.extract_scopus_eid(url)
        # Note: the ScienceDirect PDF pid contains the PII not a numeric Scopus EID
        # The numeric portion after "1-s2.0-" here is a PII string, not an EID.
        # extract_scopus_eid should return None for PII-format pids (non-numeric suffix).
        assert result is None

    def test_scopus_numeric_eid_in_pdf(self):
        """EID should be extracted from PDF URL with a numeric Scopus EID in pid."""
        url = "https://example.sciencedirect.com/pdfft?pid=1-s2.0-85051788505-main.pdf"
        result = self.detector.extract_scopus_eid(url)
        assert result == "2-s2.0-85051788505"

    def test_non_scopus_url(self):
        """Non-Scopus URL should return None."""
        url = "https://pubmed.ncbi.nlm.nih.gov/35086660/"
        result = self.detector.extract_scopus_eid(url)
        assert result is None

    def test_empty_url(self):
        """Empty string returns None."""
        assert self.detector.extract_scopus_eid("") is None

    def test_doi_url_returns_none(self):
        """DOI URL is not a Scopus URL -- return None."""
        url = "https://doi.org/10.1056/nejmra1710575"
        assert self.detector.extract_scopus_eid(url) is None

