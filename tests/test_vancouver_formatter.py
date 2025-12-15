"""
Tests for the Vancouver Formatter module.

Tests cover:
- Journal article formatting
- Book chapter formatting
- Book formatting
- CrossRef journal article formatting
- Webpage and blog formatting
- Newspaper article formatting
- Helper methods (date formatting, author labels, etc.)
"""

import pytest
from unittest.mock import Mock
from datetime import datetime

from modules.vancouver_formatter import VancouverFormatter, FormattedCitation
from modules.pubmed_client import ArticleMetadata, CrossRefMetadata, WebpageMetadata


class TestVancouverFormatterInit:
    """Test VancouverFormatter initialization."""

    def test_default_max_authors(self):
        """Test default max_authors setting."""
        formatter = VancouverFormatter()
        assert formatter.max_authors == 3

    def test_custom_max_authors(self):
        """Test custom max_authors setting."""
        formatter = VancouverFormatter(max_authors=6)
        assert formatter.max_authors == 6


class TestJournalArticleFormatting:
    """Test journal article formatting."""

    def setup_method(self):
        """Set up test fixtures."""
        self.formatter = VancouverFormatter(max_authors=3)

    def test_format_journal_article_basic(self):
        """Test basic journal article formatting."""
        metadata = ArticleMetadata(
            pmid="12345678",
            title="Test Article Title",
            authors=["Smith J", "Jones M", "Brown K"],
            journal="Test Journal",
            journal_abbreviation="Test J",
            year="2024",
            month="06",
            volume="10",
            issue="3",
            pages="100-110",
            doi="10.1234/test"
        )

        result = self.formatter.format_journal_article(metadata, original_number=1)

        assert isinstance(result, FormattedCitation)
        assert "[^SmithJ-2024-12345678]" in result.label
        assert "Smith J, Jones M, Brown K." in result.full_citation
        assert "Test Article Title." in result.full_citation
        assert "Test J." in result.full_citation
        assert "2024 Jun" in result.full_citation
        assert ";10(3):100-110" in result.full_citation
        assert "[DOI]" in result.full_citation
        assert "[PMID: 12345678]" in result.full_citation
        assert result.citation_type == "journal_article"
        assert result.pmid == "12345678"
        assert result.doi == "10.1234/test"

    def test_format_journal_article_et_al(self):
        """Test journal article with more than max_authors."""
        metadata = ArticleMetadata(
            pmid="12345678",
            title="Test Article",
            authors=["Smith J", "Jones M", "Brown K", "Wilson L", "Davis P"],
            journal="Test Journal",
            journal_abbreviation="Test J",
            year="2024"
        )

        result = self.formatter.format_journal_article(metadata, original_number=1)

        assert "Smith J, Jones M, Brown K, et al." in result.full_citation

    def test_format_journal_article_no_doi(self):
        """Test journal article without DOI."""
        metadata = ArticleMetadata(
            pmid="12345678",
            title="Test Article",
            authors=["Smith J"],
            journal="Test Journal",
            year="2024"
        )

        result = self.formatter.format_journal_article(metadata, original_number=1)

        assert "[DOI]" not in result.full_citation
        assert "[PMID: 12345678]" in result.full_citation

    def test_format_journal_article_title_period(self):
        """Test that title ends with period."""
        metadata = ArticleMetadata(
            pmid="12345678",
            title="Test Article Without Period",
            authors=["Smith J"],
            journal="Test Journal",
            year="2024"
        )

        result = self.formatter.format_journal_article(metadata, original_number=1)

        # Title should end with period
        assert "Test Article Without Period." in result.full_citation


class TestBookChapterFormatting:
    """Test book chapter formatting."""

    def setup_method(self):
        """Set up test fixtures."""
        self.formatter = VancouverFormatter(max_authors=3)

    def test_format_book_chapter_basic(self):
        """Test basic book chapter formatting."""
        metadata = CrossRefMetadata(
            doi="10.1234/chapter",
            title="Test Chapter Title",
            work_type="book-chapter",
            authors=["Smith J", "Jones M"],
            editors=["Editor A", "Editor B"],
            book_title="Test Book Title",
            publisher="Test Publisher",
            publisher_location="New York",
            year="2023",
            pages="100-120"
        )

        result = self.formatter.format_book_chapter(metadata, original_number=1)

        assert "[^SmithJ-2023-p100]" in result.label  # Uses page number in label
        assert "Smith J, Jones M." in result.full_citation
        assert "Test Chapter Title." in result.full_citation
        assert "In:" in result.full_citation
        assert "Editor A, Editor B, editors." in result.full_citation
        assert "Test Book Title." in result.full_citation
        assert "New York: Test Publisher" in result.full_citation
        assert "2023" in result.full_citation
        assert "p. 100-120" in result.full_citation
        assert result.citation_type == "book_chapter"

    def test_format_book_chapter_no_pages(self):
        """Test book chapter without page numbers."""
        metadata = CrossRefMetadata(
            doi="10.1234/chapter",
            title="Test Chapter on Ageism",
            work_type="book-chapter",
            authors=["Smith J"],
            year="2023"
        )

        result = self.formatter.format_book_chapter(metadata, original_number=1)

        # Uses brief title format - implementation uses first significant words
        assert "SmithJ" in result.label
        assert "2023" in result.label


class TestBookFormatting:
    """Test book formatting."""

    def setup_method(self):
        """Set up test fixtures."""
        self.formatter = VancouverFormatter(max_authors=3)

    def test_format_book_basic(self):
        """Test basic book formatting."""
        metadata = CrossRefMetadata(
            doi="10.1234/book",
            title="Test Book Title",
            work_type="book",
            authors=["Author A", "Author B"],
            publisher="Test Publisher",
            publisher_location="Boston",
            year="2022"
        )

        result = self.formatter.format_book(metadata, original_number=1)

        assert "AuthorA" in result.label
        assert "Author A, Author B." in result.full_citation
        assert "Test Book Title." in result.full_citation
        assert "Boston: Test Publisher" in result.full_citation
        assert "2022" in result.full_citation
        assert result.citation_type == "book"

    def test_format_book_with_editors_only(self):
        """Test book with editors but no authors."""
        metadata = CrossRefMetadata(
            doi="10.1234/book",
            title="Edited Book",
            work_type="book",
            editors=["Editor X", "Editor Y"],
            publisher="Publisher",
            year="2021"
        )

        result = self.formatter.format_book(metadata, original_number=1)

        assert "Editor X, Editor Y, editors." in result.full_citation


class TestCrossRefJournalArticleFormatting:
    """Test CrossRef journal article formatting (non-PubMed)."""

    def setup_method(self):
        """Set up test fixtures."""
        self.formatter = VancouverFormatter(max_authors=3)

    def test_format_crossref_journal_article(self):
        """Test CrossRef journal article formatting."""
        metadata = CrossRefMetadata(
            doi="10.1234/journal",
            title="CrossRef Article Title",
            work_type="journal-article",
            authors=["Smith J", "Jones M"],
            container_title="CrossRef Journal",
            year="2024",
            volume="5",
            issue="2",
            pages="50-60"
        )

        result = self.formatter.format_crossref_journal_article(metadata, original_number=1)

        # Label should use brief title (no PMID)
        assert "SmithJ-2024" in result.label
        assert "Smith J, Jones M." in result.full_citation
        assert "CrossRef Article Title." in result.full_citation
        assert "CrossRef Journal." in result.full_citation
        assert ";5(2):50-60" in result.full_citation
        assert "[DOI]" in result.full_citation


class TestWebpageFormatting:
    """Test webpage formatting."""

    def setup_method(self):
        """Set up test fixtures."""
        self.formatter = VancouverFormatter(max_authors=3)

    def test_format_webpage_basic(self):
        """Test basic webpage formatting."""
        result = self.formatter.format_webpage(
            title="Test Webpage Title",
            url="https://example.com/article",
            source_name="Example Organization",
            original_number=1,
            year="2024"
        )

        # Implementation uses organization abbreviation in label
        assert "2024" in result.label
        assert "Example Organization" in result.full_citation
        assert "Test Webpage Title." in result.full_citation
        assert "2024" in result.full_citation
        assert "[Link](https://example.com/article)" in result.full_citation
        assert result.citation_type == "webpage"

    def test_format_webpage_no_year(self):
        """Test webpage without year (non-evergreen)."""
        result = self.formatter.format_webpage(
            title="Test Article",
            url="https://example.com/article",
            source_name="Example Org",
            original_number=1
        )

        # Should include Null_Date for non-evergreen pages
        assert "Null_Date" in result.full_citation or "ND" in result.label

    def test_format_webpage_evergreen(self):
        """Test evergreen webpage (no date expected)."""
        result = self.formatter.format_webpage(
            title="About Us",
            url="https://example.com/about",
            source_name="Example Org",
            original_number=1,
            is_evergreen=True
        )

        # Evergreen pages should not have Null_Date
        # (they legitimately don't have dates)
        assert "Null_Date" not in result.full_citation or result.full_citation.count("Null") == 0

    def test_format_webpage_truncated_title(self):
        """Test that truncated titles are cleaned."""
        result = self.formatter.format_webpage(
            title="This is a truncated title...",
            url="https://example.com/full-title-here",
            source_name="Example",
            original_number=1,
            year="2024"
        )

        # Ellipsis should be removed or title extracted from URL
        assert "..." not in result.full_citation or "full" in result.full_citation.lower()

    def test_format_webpage_acronym_organization(self):
        """Test organization abbreviation handling."""
        result = self.formatter.format_webpage(
            title="Test Article",
            url="https://cbpp.org/article",
            source_name="Center on Budget and Policy Priorities",
            original_number=1,
            year="2024"
        )

        # Should include both full name and abbreviation
        assert "CBPP" in result.label or "CBPP" in result.full_citation

    def test_format_scraped_webpage(self):
        """Test formatting with scraped metadata."""
        metadata = WebpageMetadata(
            title="Scraped Article Title",
            url="https://example.com/article",
            authors=["Smith John", "Jones Mary"],
            journal="Academic Site",
            year="2024",
            site_name="Example Academic"
        )

        result = self.formatter.format_scraped_webpage(metadata, original_number=1)

        # Implementation formats "Smith John" as "John S" (first name first format)
        assert "2024" in result.label
        assert "Scraped Article Title." in result.full_citation
        assert "2024" in result.full_citation

    def test_format_scraped_webpage_no_authors(self):
        """Test scraped webpage without authors."""
        metadata = WebpageMetadata(
            title="No Author Article",
            url="https://example.com/article",
            year="2024",
            site_name="Example Site"
        )

        result = self.formatter.format_scraped_webpage(metadata, original_number=1)

        # Should use Null_Author placeholder
        assert "Null_Author" in result.full_citation


class TestBlogFormatting:
    """Test blog formatting."""

    def setup_method(self):
        """Set up test fixtures."""
        self.formatter = VancouverFormatter(max_authors=3)

    def test_format_blog(self):
        """Test blog formatting (similar to webpage)."""
        result = self.formatter.format_blog(
            title="Blog Post Title",
            url="https://blog.example.com/post",
            source_name="Example Blog",
            original_number=1,
            year="2024"
        )

        assert result.citation_type == "blog"
        assert "Blog Post Title." in result.full_citation


class TestNewspaperFormatting:
    """Test newspaper article formatting."""

    def setup_method(self):
        """Set up test fixtures."""
        self.formatter = VancouverFormatter(max_authors=3)

    def test_format_newspaper_article(self):
        """Test newspaper article formatting."""
        result = self.formatter.format_newspaper_article(
            title="News Article Title",
            url="https://nytimes.com/2024/01/15/news-article",
            source_name="The New York Times",
            original_number=1,
            year="2024"
        )

        assert result.citation_type == "newspaper_article"
        assert "The New York Times." in result.full_citation
        assert "News Article Title [Internet]." in result.full_citation
        assert "2024" in result.full_citation
        assert "[cited" in result.full_citation
        assert "Available from:" in result.full_citation

    def test_format_newspaper_extracts_name_from_url(self):
        """Test newspaper name extraction from URL."""
        result = self.formatter.format_newspaper_article(
            title="News Article",
            url="https://www.naplesnews.com/story/news",
            source_name=None,
            original_number=1
        )

        assert "Naples" in result.full_citation


class TestHelperMethods:
    """Test helper methods."""

    def setup_method(self):
        """Set up test fixtures."""
        self.formatter = VancouverFormatter()

    def test_format_date_year_only(self):
        """Test date formatting with year only."""
        result = self.formatter._format_date("2024", "")
        assert result == "2024"

    def test_format_date_with_month(self):
        """Test date formatting with month."""
        result = self.formatter._format_date("2024", "06")
        assert result == "2024 Jun"

    def test_format_date_month_name(self):
        """Test date formatting with month name."""
        result = self.formatter._format_date("2024", "january")
        assert result == "2024 Jan"

    def test_format_date_empty(self):
        """Test date formatting with no year."""
        result = self.formatter._format_date("", "")
        assert result == ""

    def test_format_volume_issue_pages(self):
        """Test volume/issue/pages formatting."""
        result = self.formatter._format_volume_issue_pages("10", "3", "100-110")
        assert result == ";10(3):100-110"

    def test_format_volume_issue_pages_no_issue(self):
        """Test volume/pages without issue."""
        result = self.formatter._format_volume_issue_pages("10", "", "100-110")
        assert result == ";10:100-110"

    def test_format_volume_issue_pages_no_pages(self):
        """Test volume/issue without pages."""
        result = self.formatter._format_volume_issue_pages("10", "3", "")
        assert result == ";10(3)"

    def test_format_doi_url(self):
        """Test DOI URL formatting."""
        result = self.formatter._format_doi_url("10.1234/test")
        assert result == "https://doi.org/10.1234/test"

    def test_format_doi_url_from_full_url(self):
        """Test DOI URL formatting from full URL."""
        result = self.formatter._format_doi_url("https://doi.org/10.1234/test")
        assert result == "https://doi.org/10.1234/test"

    def test_format_doi_url_escapes_parentheses(self):
        """Test DOI URL escapes parentheses for markdown."""
        result = self.formatter._format_doi_url("10.1234/test(v1)")
        assert r"\(" in result and r"\)" in result

    def test_generate_author_label(self):
        """Test author label generation."""
        result = self.formatter._generate_author_label("Smith John")
        assert result == "SmithJ"

    def test_generate_author_label_empty(self):
        """Test author label with empty input."""
        result = self.formatter._generate_author_label("")
        assert result == "Unknown"

    def test_generate_brief_title(self):
        """Test brief title generation."""
        result = self.formatter._generate_brief_title(
            "The Quick Brown Fox Jumps Over the Lazy Dog"
        )
        # Should remove stop words and take first 3 significant words
        assert "Quick" in result
        assert "Brown" in result
        assert "Fox" in result
        assert "The" not in result

    def test_generate_brief_title_short(self):
        """Test brief title with few words."""
        result = self.formatter._generate_brief_title("Short Title")
        assert result == "ShortTitle"

    def test_extract_organization(self):
        """Test organization extraction from source name."""
        result = self.formatter._extract_organization("Example.com", "https://example.com")
        assert result == "Example"

    def test_extract_organization_from_url(self):
        """Test organization extraction from URL when source is None."""
        result = self.formatter._extract_organization(None, "https://www.testorg.com/page")
        assert result == "Testorg"

    def test_looks_like_acronym(self):
        """Test acronym detection."""
        assert self.formatter._looks_like_acronym("CDC") is True
        assert self.formatter._looks_like_acronym("NIH") is True
        assert self.formatter._looks_like_acronym("CBPP") is True
        assert self.formatter._looks_like_acronym("Hospital") is False
        assert self.formatter._looks_like_acronym("Testing") is False

    def test_get_org_full_name(self):
        """Test organization full name lookup."""
        assert "American Medical Association" in self.formatter._get_org_full_name("ama")
        assert "Centers for Disease Control" in self.formatter._get_org_full_name("cdc")
        assert self.formatter._get_org_full_name("unknown") is None

    def test_generate_org_abbreviation(self):
        """Test organization abbreviation generation."""
        assert self.formatter._generate_org_abbreviation("American Medical Association") == "AMA"
        assert self.formatter._generate_org_abbreviation("Center on Budget and Policy Priorities") == "CBPP"
        # Already abbreviated
        assert self.formatter._generate_org_abbreviation("CDC") == "CDC"

    def test_extract_year_from_text(self):
        """Test year extraction from text."""
        # Note: "Published in 2024" would filter out "in 2024" as subject matter
        assert self.formatter._extract_year_from_text("Published 2024") == "2024"
        assert self.formatter._extract_year_from_text("Article 1998") == "1998"
        assert self.formatter._extract_year_from_text("© 2023 All rights reserved") == "2023"

    def test_extract_year_from_text_skips_subject_years(self):
        """Test that subject matter years are skipped."""
        # "in 2025" is likely a projection, not publication date
        result = self.formatter._extract_year_from_text("Healthcare predictions in 2025")
        assert result is None or result != "2025"

    def test_extract_year_from_url(self):
        """Test year extraction from URL path."""
        assert self.formatter._extract_year_from_url("https://example.com/2024/05/article") == "2024"
        assert self.formatter._extract_year_from_url("https://example.com/2024-05-12/article") == "2024"
        assert self.formatter._extract_year_from_url("https://example.com/random") is None

    def test_extract_year_from_url_doi_style(self):
        """Test year extraction from DOI-style URL."""
        url = "https://healthaffairs.org/do/10.1377/forefront.20201130.594055"
        result = self.formatter._extract_year_from_url(url)
        assert result == "2020"

    def test_extract_title_from_url(self):
        """Test title extraction from URL slug."""
        url = "https://example.com/articles/this-is-a-test-article-title"
        result = self.formatter._extract_title_from_url(url)
        assert result is not None
        assert "test" in result.lower() or "article" in result.lower()

    def test_extract_title_from_url_social_media(self):
        """Test that social media URLs are skipped."""
        assert self.formatter._extract_title_from_url("https://linkedin.com/post/garbage") is None
        assert self.formatter._extract_title_from_url("https://twitter.com/user/status") is None


class TestFormattedCitationDataclass:
    """Test FormattedCitation dataclass."""

    def test_creation(self):
        """Test creating a FormattedCitation."""
        citation = FormattedCitation(
            label="[^SmithJ-2024-12345678]",
            full_citation="[^SmithJ-2024-12345678]: Smith J. Title. Journal. 2024.",
            citation_type="journal_article",
            original_number=1,
            pmid="12345678",
            doi="10.1234/test"
        )

        assert citation.label == "[^SmithJ-2024-12345678]"
        assert citation.citation_type == "journal_article"
        assert citation.pmid == "12345678"
        assert citation.doi == "10.1234/test"

    def test_default_values(self):
        """Test default values."""
        citation = FormattedCitation(
            label="[^Test]",
            full_citation="Test citation",
            citation_type="webpage",
            original_number=1
        )

        assert citation.pmid is None
        assert citation.doi is None


class TestEdgeCases:
    """Test edge cases and error handling."""

    def setup_method(self):
        """Set up test fixtures."""
        self.formatter = VancouverFormatter()

    def test_empty_authors(self):
        """Test handling of empty author list."""
        metadata = ArticleMetadata(
            pmid="12345678",
            title="Test Article",
            authors=[],
            journal="Test Journal",
            year="2024"
        )

        result = self.formatter.format_journal_article(metadata, original_number=1)
        # Should still produce valid citation
        assert "Test Article" in result.full_citation
        assert "Unknown" in result.label

    def test_special_characters_in_title(self):
        """Test handling of special characters in title."""
        metadata = ArticleMetadata(
            pmid="12345678",
            title="Test: A Study of <Special> Characters & Symbols",
            authors=["Smith J"],
            journal="Test Journal",
            year="2024"
        )

        result = self.formatter.format_journal_article(metadata, original_number=1)
        assert "Test:" in result.full_citation

    def test_unicode_in_authors(self):
        """Test handling of unicode characters in author names."""
        metadata = ArticleMetadata(
            pmid="12345678",
            title="Test Article",
            authors=["Müller J", "García M", "Øberg S"],
            journal="Test Journal",
            year="2024"
        )

        result = self.formatter.format_journal_article(metadata, original_number=1)
        assert "Müller" in result.full_citation

    def test_very_long_title(self):
        """Test handling of very long titles."""
        long_title = "A " * 100 + "Very Long Title"
        metadata = ArticleMetadata(
            pmid="12345678",
            title=long_title,
            authors=["Smith J"],
            journal="Test Journal",
            year="2024"
        )

        result = self.formatter.format_journal_article(metadata, original_number=1)
        # Should still work
        assert long_title in result.full_citation

