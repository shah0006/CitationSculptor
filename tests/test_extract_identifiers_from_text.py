"""
Tests for CitationTypeDetector.extract_identifiers_from_text().

Covers extraction of DOIs, PMIDs, and URLs from free-form reference text,
including plain-text identifiers, inline URLs, and markdown link anchors.
"""

import pytest
from modules.type_detector import CitationTypeDetector


class TestExtractIdentifiersFromText:
    """Test cases for extract_identifiers_from_text."""

    def setup_method(self):
        self.detector = CitationTypeDetector()

    def test_plain_text_doi_extracted(self):
        """Plain-text doi:10.xxx pattern is extracted."""
        text = "Maron BJ, et al. N Engl J Med. 2018;379:655-668. doi:10.1056/NEJMra1710575. PMID: 30110588."
        result = self.detector.extract_identifiers_from_text(text)
        assert result['doi'] == "10.1056/NEJMra1710575"
        assert result['doi_source'] == 'plain_text'

    def test_plain_text_pmid_extracted(self):
        """Plain-text PMID: nnnnn pattern is extracted."""
        text = "Maron BJ, et al. N Engl J Med. 2018;379:655-668. doi:10.1056/NEJMra1710575. PMID: 30110588."
        result = self.detector.extract_identifiers_from_text(text)
        assert result['pmid'] == "30110588"
        assert result['pmid_source'] == 'plain_text'

    def test_doi_url_extracted_from_text(self):
        """Inline https://doi.org/10.xxx URL is extracted as DOI."""
        text = "See https://doi.org/10.1056/NEJMra1710575 for the full article."
        result = self.detector.extract_identifiers_from_text(text)
        assert result['doi'] == "10.1056/NEJMra1710575"
        assert result['doi_source'] == 'inline_url'

    def test_pubmed_url_pmid_extracted(self):
        """PubMed URL in markdown anchor extracts PMID."""
        text = "Available at [PubMed](https://pubmed.ncbi.nlm.nih.gov/30110588/)."
        result = self.detector.extract_identifiers_from_text(text)
        assert result['pmid'] == "30110588"
        assert result['pmid_source'] == 'inline_url'

    def test_multiple_anchors_all_urls_returned(self):
        """Multiple [text](url) anchors are all collected in all_urls."""
        text = (
            "[Scholar](https://scholar.google.com/scholar_lookup?title=foo) "
            "[DOI](https://doi.org/10.1056/NEJMra1710575) "
            "[PubMed](https://pubmed.ncbi.nlm.nih.gov/30110588/)"
        )
        result = self.detector.extract_identifiers_from_text(text)
        assert len(result['all_urls']) == 3
        assert "https://scholar.google.com/scholar_lookup?title=foo" in result['all_urls']
        assert "https://doi.org/10.1056/NEJMra1710575" in result['all_urls']
        assert "https://pubmed.ncbi.nlm.nih.gov/30110588/" in result['all_urls']

    def test_doi_trailing_punctuation_stripped(self):
        """Trailing period after DOI is stripped."""
        text = "doi:10.1056/NEJMra1710575."
        result = self.detector.extract_identifiers_from_text(text)
        assert result['doi'] == "10.1056/NEJMra1710575"

    def test_plain_text_doi_case_insensitive(self):
        """Both 'DOI:' and 'doi:' variants work."""
        for prefix in ["DOI: 10.1056/NEJMra1710575", "doi: 10.1056/NEJMra1710575", "Doi:10.1056/NEJMra1710575"]:
            result = self.detector.extract_identifiers_from_text(prefix)
            assert result['doi'] == "10.1056/NEJMra1710575", f"Failed for: {prefix}"

    def test_empty_text_returns_empty_dict(self):
        """Empty string returns structure with all Nones and empty list."""
        result = self.detector.extract_identifiers_from_text("")
        assert result['doi'] is None
        assert result['pmid'] is None
        assert result['all_urls'] == []

    def test_no_identifiers_returns_nones(self):
        """Random text without identifiers returns Nones."""
        text = "This is a random string with no identifiers whatsoever."
        result = self.detector.extract_identifiers_from_text(text)
        assert result['doi'] is None
        assert result['pmid'] is None
        assert result['all_urls'] == []

    def test_dx_doi_url_extracted(self):
        """dx.doi.org variant extracts DOI."""
        text = "Available at https://dx.doi.org/10.1016/j.jacc.2020.11.010 for details."
        result = self.detector.extract_identifiers_from_text(text)
        assert result['doi'] == "10.1016/j.jacc.2020.11.010"
        assert result['doi_source'] == 'inline_url'

    def test_pmid_with_colon_and_space(self):
        """'PMID: 30110588' with space is extracted."""
        text = "PMID: 30110588"
        result = self.detector.extract_identifiers_from_text(text)
        assert result['pmid'] == "30110588"

    def test_pmid_without_space(self):
        """'PMID:30110588' without space is extracted."""
        text = "PMID:30110588"
        result = self.detector.extract_identifiers_from_text(text)
        assert result['pmid'] == "30110588"

    def test_pubmed_pmid_variant(self):
        """'PubMed PMID: 30110588' is extracted."""
        text = "PubMed PMID: 30110588"
        result = self.detector.extract_identifiers_from_text(text)
        assert result['pmid'] == "30110588"

    def test_doi_from_anchor_url(self):
        """DOI extracted from [text](doi.org/...) anchor when no plain-text DOI."""
        text = "See [Full Text](https://doi.org/10.1093/eurheartj/ehaa798) for details."
        result = self.detector.extract_identifiers_from_text(text)
        assert result['doi'] == "10.1093/eurheartj/ehaa798"
        # Could be inline_url or anchor -- either is acceptable
        assert result['doi_source'] in ('inline_url', 'anchor')

    def test_pmid_from_anchor_url(self):
        """PMID extracted from [text](pubmed.../12345678/) anchor."""
        text = "See [PubMed](https://pubmed.ncbi.nlm.nih.gov/12345678/) for details."
        result = self.detector.extract_identifiers_from_text(text)
        assert result['pmid'] == "12345678"

    def test_full_reference_line(self):
        """Full reference line with DOI, PMID, and Scholar link extracts all."""
        text = (
            "Maron BJ. N Engl J Med. 2018;379:655. doi:10.1056/NEJMra1710575. "
            "PMID: 30110588. [Link](https://scholar.google.com/scholar_lookup?title=Clinical+Course)"
        )
        result = self.detector.extract_identifiers_from_text(text)
        assert result['doi'] == "10.1056/NEJMra1710575"
        assert result['pmid'] == "30110588"
        assert len(result['all_urls']) == 1
        assert "scholar.google.com" in result['all_urls'][0]

    def test_doi_with_trailing_semicolon_stripped(self):
        """Trailing semicolons are stripped from DOI."""
        text = "doi:10.1056/NEJMra1710575;"
        result = self.detector.extract_identifiers_from_text(text)
        assert result['doi'] == "10.1056/NEJMra1710575"

    def test_doi_with_trailing_bracket_stripped(self):
        """Trailing bracket is stripped from DOI."""
        text = "doi:10.1056/NEJMra1710575]"
        result = self.detector.extract_identifiers_from_text(text)
        assert result['doi'] == "10.1056/NEJMra1710575"

    def test_pmid_5_digit(self):
        """5-digit PMID is valid."""
        text = "PMID: 12345"
        result = self.detector.extract_identifiers_from_text(text)
        assert result['pmid'] == "12345"

    def test_pmid_8_digit(self):
        """8-digit PMID is valid."""
        text = "PMID: 12345678"
        result = self.detector.extract_identifiers_from_text(text)
        assert result['pmid'] == "12345678"

    def test_pmid_4_digit_rejected(self):
        """4-digit number after PMID: is too short to be a PMID."""
        text = "PMID: 1234"
        result = self.detector.extract_identifiers_from_text(text)
        assert result['pmid'] is None

    def test_pmid_9_digit_rejected(self):
        """9-digit number after PMID: is too long to be a PMID."""
        text = "PMID: 123456789"
        result = self.detector.extract_identifiers_from_text(text)
        assert result['pmid'] is None
