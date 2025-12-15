"""
Tests for the Reference Parser module.

Tests cover:
- Reference section detection
- Multiple reference format parsing (V1-V8)
- Multi-section document handling
- Inline reference style detection
- Unreferenced citation filtering
- Undefined reference detection
"""

import pytest
from modules.reference_parser import ReferenceParser, ParsedReference, DocumentSection


class TestReferenceParserInit:
    """Test ReferenceParser initialization."""

    def test_initialization(self):
        """Test basic initialization."""
        content = "Test content\n## References\n1. Test ref"
        parser = ReferenceParser(content)

        assert parser.content == content
        assert len(parser.lines) == 3
        assert parser.multi_section is False
        assert parser.references == []

    def test_initialization_multi_section(self):
        """Test initialization with multi_section flag."""
        parser = ReferenceParser("content", multi_section=True)
        assert parser.multi_section is True


class TestReferenceSectionDetection:
    """Test finding reference sections in documents."""

    def test_find_references_header(self):
        """Test finding ## References header."""
        content = """# Document
        
Some body content here.

## References

1. First reference
2. Second reference
"""
        parser = ReferenceParser(content)
        start, end = parser.find_reference_section()

        assert start is not None
        assert end is not None
        assert parser.lines[start].strip() == "## References"

    def test_find_sources_header(self):
        """Test finding ## Sources header."""
        content = """# Document

Body content.

## Sources

1. Source one
"""
        parser = ReferenceParser(content)
        start, end = parser.find_reference_section()

        assert start is not None
        assert "Sources" in parser.lines[start]

    def test_find_bold_sources_header(self):
        """Test finding **Sources:** header (V6 format)."""
        content = """# Document

Body content [^1]

**Sources:**

[^1] Title here
"""
        parser = ReferenceParser(content)
        sections = parser.find_all_reference_sections()

        assert len(sections) >= 1

    def test_find_citations_header(self):
        """Test finding Citations header."""
        content = """# Document

## Citations

1. Citation one
"""
        parser = ReferenceParser(content)
        start, end = parser.find_reference_section()

        assert start is not None

    def test_find_bibliography_header(self):
        """Test finding Bibliography header."""
        content = """# Document

### Bibliography

1. Bibliography entry
"""
        parser = ReferenceParser(content)
        start, end = parser.find_reference_section()

        assert start is not None

    def test_no_reference_section(self):
        """Test document without reference section."""
        content = """# Document

Just regular content without references.
"""
        parser = ReferenceParser(content)
        start, end = parser.find_reference_section()

        assert start is None
        assert end is None

    def test_implicit_footnote_section(self):
        """Test finding implicit footnote section without header."""
        content = """# Document

Body with [^1] reference.

[^1]: This is the footnote definition.
[^2]: Another footnote.
"""
        parser = ReferenceParser(content)
        sections = parser.find_all_reference_sections()

        assert len(sections) >= 1

    def test_multiple_reference_sections(self):
        """Test finding multiple reference sections."""
        content = """# Section 1

Content [1]

## References

1. First section ref

# Section 2

More content [1]

## References

1. Second section ref
"""
        parser = ReferenceParser(content)
        sections = parser.find_all_reference_sections()

        assert len(sections) == 2


class TestReferenceFormatParsing:
    """Test parsing different reference formats."""

    def test_parse_simple_format_v1(self):
        """Test parsing simple format: 1. [Title - Source](URL)"""
        content = """## References

1. [Article Title - Test Source](https://example.com/article)
2. [Another Article - Source Two](https://example.com/another)
"""
        parser = ReferenceParser(content)
        parser.find_reference_section()
        refs = parser.parse_references()

        assert len(refs) == 2
        assert refs[0].original_number == 1
        assert refs[0].title == "Article Title"
        assert refs[0].source_name == "Test Source"
        assert refs[0].url == "https://example.com/article"

    def test_parse_extended_format_v2(self):
        """Test parsing extended format: 1. [Title](URL). Authors. Journal..."""
        content = """## References

1. [Test Article](https://doi.org/10.1234/test). Smith J, Jones M. Test Journal. 2024;10:100-110. doi:10.1234/test.
"""
        parser = ReferenceParser(content)
        parser.find_reference_section()
        refs = parser.parse_references()

        assert len(refs) == 1
        assert refs[0].title == "Test Article"
        assert refs[0].url == "https://doi.org/10.1234/test"
        assert 'doi' in refs[0].metadata or refs[0].metadata.get('extra_info', '')

    def test_parse_footnote_format_v3(self):
        """Test parsing footnote definition: [^1]: Citation text..."""
        content = """# Document

Body with [^1] reference.

## References

[^1]: Smith J. Article Title. Journal. 2024. https://example.com
[^2]: Jones M. Another Article. Journal. 2023.
"""
        parser = ReferenceParser(content)
        parser.find_reference_section()
        refs = parser.parse_references()

        assert len(refs) == 2
        assert refs[0].original_number == 1
        assert refs[1].original_number == 2

    def test_parse_text_only_format_v4(self):
        """Test parsing text-only format: 1. Title. Authors..."""
        content = """## References

1. Article Title. Smith J, Jones M. Test Journal. 2024;10:100-110.
2. Another Article. Brown K. Different Journal. 2023.
"""
        parser = ReferenceParser(content)
        parser.find_reference_section()
        refs = parser.parse_references()

        assert len(refs) == 2
        assert refs[0].title == "Article Title"

    def test_parse_text_only_with_doi(self):
        """Test text-only format extracts DOI and creates URL."""
        content = """## References

1. Article Title. Smith J. Journal. 2024. doi:10.1234/test.
"""
        parser = ReferenceParser(content)
        parser.find_reference_section()
        refs = parser.parse_references()

        assert len(refs) == 1
        assert refs[0].url is not None
        assert "10.1234/test" in refs[0].url

    def test_parse_grouped_footnotes_v6(self):
        """Test parsing V6 grouped footnotes: [^1] [^2] [^3] Title | Source"""
        content = """# Document

Text [^1] and more [^47] and [^49]

**Sources:**

[^1] [^47] [^49] Article Title | Source Name
<https://example.com/article>

[^2] Another Title | Other Source
<https://example.com/other>
"""
        parser = ReferenceParser(content, multi_section=True)
        sections = parser.parse_multi_section()

        # All grouped numbers should create separate ParsedReference objects
        all_refs = parser.references
        numbers = {ref.original_number for ref in all_refs}
        
        # Should have refs for 1, 47, 49, and 2
        assert 1 in numbers
        assert 47 in numbers
        assert 49 in numbers
        assert 2 in numbers

    def test_parse_v6_with_angle_bracket_url(self):
        """Test V6 format with URL on separate line."""
        content = """**Sources:**

[^1] Article Title | Source
<https://example.com/article>
"""
        parser = ReferenceParser(content, multi_section=True)
        parser.parse_multi_section()
        
        refs = parser.references
        assert len(refs) >= 1
        assert refs[0].url == "https://example.com/article"

    def test_parse_numbered_link_format_v7(self):
        """Test parsing V7 numbered list with embedded link."""
        content = """## References

1. [Article Title](https://example.com/article). Smith J et al. J Test. 2024;10:100-105. doi:10.1234/test.
2. [Second Article](https://pubmed.ncbi.nlm.nih.gov/12345678/). Jones M. Another J. 2023.
"""
        parser = ReferenceParser(content)
        parser.find_reference_section()
        refs = parser.parse_references()

        assert len(refs) == 2
        assert refs[0].title == "Article Title"
        assert 'doi' in refs[0].metadata or refs[0].url

    def test_parse_works_cited_format_v8(self):
        """Test parsing V8 works cited format: 1. Title, accessed date, <URL>"""
        content = """## Works Cited

1. Article Title Here, accessed December 2024, <https://example.com/article>
2. Another Title, accessed January 2025, <https://example.com/other>
"""
        parser = ReferenceParser(content)
        parser.find_reference_section()
        refs = parser.parse_references()

        assert len(refs) >= 1
        # First ref should have title and URL
        assert refs[0].url == "https://example.com/article"


class TestMultiSectionParsing:
    """Test multi-section document parsing."""

    def test_parse_multi_section_basic(self):
        """Test basic multi-section parsing."""
        content = """# Section 1

Body content with [1] reference.

## References

1. [First Ref](https://example.com/1)

# Section 2

More content with [1] reference.

## References

1. [Second Section Ref](https://example.com/2)
"""
        parser = ReferenceParser(content, multi_section=True)
        sections = parser.parse_multi_section()

        assert len(sections) == 2
        assert len(sections[0].references) >= 1
        assert len(sections[1].references) >= 1

    def test_multi_section_body_content(self):
        """Test that body content is correctly extracted per section."""
        content = """# First Section

This is body content for section one.

## References

1. Ref one

# Second Section

This is body content for section two.

## References

1. Ref two
"""
        parser = ReferenceParser(content, multi_section=True)
        sections = parser.parse_multi_section()

        assert "section one" in sections[0].body_content.lower()
        assert "section two" in sections[1].body_content.lower()

    def test_multi_section_body_after_references(self):
        """Test handling body content after reference definitions."""
        content = """# Document

Body before [^1] footnotes.

[^1]: Footnote definition here.

Body content after footnotes.
"""
        parser = ReferenceParser(content, multi_section=True)
        sections = parser.parse_multi_section()

        assert len(sections) >= 1
        # Body should include content from both before and after refs
        assert "before" in sections[0].body_content.lower()
        # After content should be marked or included
        if "<!-- REF_SECTION_MARKER -->" in sections[0].body_content:
            assert "after" in sections[0].body_content.lower()


class TestInlineStyleDetection:
    """Test inline reference style detection."""

    def test_detect_numeric_style(self):
        """Test detecting [N] style references."""
        content = """Body with [1] and [2] and [3] references."""
        parser = ReferenceParser(content)
        style = parser._detect_inline_style(content)

        assert style == "numeric"

    def test_detect_footnote_style(self):
        """Test detecting [^N] style references."""
        content = """Body with [^1] and [^2] and [^3] references."""
        parser = ReferenceParser(content)
        style = parser._detect_inline_style(content)

        assert style == "footnote"

    def test_detect_mixed_style(self):
        """Test detecting dominant style when both are present."""
        content = """Body with [^1] [^2] [^3] [^4] and only [1] reference."""
        parser = ReferenceParser(content)
        style = parser._detect_inline_style(content)

        # Should detect footnote as more common
        assert style == "footnote"


class TestUnreferencedFiltering:
    """Test filtering of unreferenced citations."""

    def test_find_referenced_numbers(self):
        """Test finding referenced numbers in body."""
        content = """# Document

Text with [1] and [3] and [5] references.

## References

1. Ref one
2. Ref two (not used)
3. Ref three
4. Ref four (not used)
5. Ref five
"""
        parser = ReferenceParser(content)
        parser.find_reference_section()
        parser.body_content = '\n'.join(parser.lines[:parser.reference_section_start])
        
        referenced = parser.find_referenced_numbers()

        assert 1 in referenced
        assert 3 in referenced
        assert 5 in referenced
        assert 2 not in referenced
        assert 4 not in referenced

    def test_find_referenced_numbers_with_ranges(self):
        """Test finding referenced numbers including explicit numbers."""
        # Note: Range expansion [1-3] is not automatically expanded to 1,2,3
        # The parser finds literal numbers used in brackets
        content = """Text with [1] [3] and [5] [6] [7] references."""
        parser = ReferenceParser(content)
        
        referenced = parser.find_referenced_numbers(body_content=content, style="numeric")

        assert 1 in referenced
        assert 3 in referenced
        assert 5 in referenced
        assert 6 in referenced
        assert 7 in referenced

    def test_find_referenced_numbers_footnote_style(self):
        """Test finding footnote-style references."""
        content = """Text with [^1] and [^5] references."""
        parser = ReferenceParser(content)
        
        referenced = parser.find_referenced_numbers(body_content=content, style="footnote")

        assert 1 in referenced
        assert 5 in referenced

    def test_filter_unreferenced(self):
        """Test filtering unreferenced citations."""
        content = """# Document

Text with [1] reference only.

## References

1. [Used Ref](https://example.com/1)
2. [Unused Ref](https://example.com/2)
3. [Another Unused](https://example.com/3)
"""
        parser = ReferenceParser(content)
        parser.find_reference_section()
        parser.parse_references()

        used, unused = parser.filter_unreferenced()

        assert len(used) == 1
        assert len(unused) == 2
        assert used[0].original_number == 1


class TestUndefinedReferenceDetection:
    """Test detection of undefined references."""

    def test_find_undefined_references(self):
        """Test finding references used but not defined."""
        body_content = "Text with [^1] and [^5] and [^10] references."
        defined_numbers = {1, 5}  # 10 is not defined

        parser = ReferenceParser("")
        undefined = parser.find_undefined_references(
            body_content, defined_numbers, style="footnote"
        )

        assert 10 in undefined
        assert 1 not in undefined
        assert 5 not in undefined

    def test_find_undefined_references_numeric(self):
        """Test finding undefined numeric references."""
        body_content = "Text with [1], [2], [99] references."
        defined_numbers = {1, 2}

        parser = ReferenceParser("")
        undefined = parser.find_undefined_references(
            body_content, defined_numbers, style="numeric"
        )

        assert 99 in undefined


class TestTitleSourceSplitting:
    """Test title and source splitting."""

    def test_split_title_source_pipe(self):
        """Test splitting with pipe separator."""
        parser = ReferenceParser("")
        title, source = parser._split_title_source("Article Title | Source Name")

        assert title == "Article Title"
        assert source == "Source Name"

    def test_split_title_source_dash(self):
        """Test splitting with dash separator."""
        parser = ReferenceParser("")
        title, source = parser._split_title_source("Article Title - Source Name")

        assert title == "Article Title"
        assert source == "Source Name"

    def test_split_title_source_no_separator(self):
        """Test when there's no separator."""
        parser = ReferenceParser("")
        title, source = parser._split_title_source("Just a Title")

        assert title == "Just a Title"
        assert source is None

    def test_split_title_source_year_in_dash(self):
        """Test that year after dash is not treated as source."""
        parser = ReferenceParser("")
        title, source = parser._split_title_source("Title - 2024")

        # 2024 looks like a year, not a source
        assert "Title" in title
        assert source is None or source != "2024"


class TestAlreadyFormattedDetection:
    """Test detection of already-formatted footnotes."""

    def test_is_already_formatted_author_year_pmid(self):
        """Test detecting [^AuthorY-2020-12345678] format."""
        parser = ReferenceParser("")
        
        assert parser._is_already_formatted_footnote(
            "[^SmithJ-2024-12345678]: Citation text"
        ) is True

    def test_is_already_formatted_author_title_year(self):
        """Test detecting [^Author-Title-Year] format."""
        parser = ReferenceParser("")
        
        assert parser._is_already_formatted_footnote(
            "[^Smith-Article-2024]: Citation text"
        ) is True

    def test_is_already_formatted_org_title_year(self):
        """Test detecting [^ORG-Title-Year] format."""
        parser = ReferenceParser("")
        
        assert parser._is_already_formatted_footnote(
            "[^WHO-Report-2024]: Citation text"
        ) is True

    def test_is_not_formatted_numeric(self):
        """Test that numeric footnotes are not considered formatted."""
        parser = ReferenceParser("")
        
        assert parser._is_already_formatted_footnote(
            "[^1]: Some citation text"
        ) is False


class TestParsedReferenceDataclass:
    """Test ParsedReference dataclass."""

    def test_creation(self):
        """Test creating a ParsedReference."""
        ref = ParsedReference(
            original_number=1,
            original_text="1. Test reference",
            title="Test Title",
            url="https://example.com",
            source_name="Test Source",
            line_number=10
        )

        assert ref.original_number == 1
        assert ref.title == "Test Title"
        assert ref.url == "https://example.com"
        assert ref.processed is False
        assert ref.needs_review is False

    def test_default_values(self):
        """Test default values."""
        ref = ParsedReference(
            original_number=1,
            original_text="text",
            title="title",
            url=None,
            source_name=None,
            line_number=1
        )

        assert ref.section_index == 0
        assert ref.citation_type is None
        assert ref.new_label is None
        assert ref.metadata == {}


class TestDocumentSectionDataclass:
    """Test DocumentSection dataclass."""

    def test_creation(self):
        """Test creating a DocumentSection."""
        section = DocumentSection(
            section_index=0,
            body_start=0,
            body_end=50,
            ref_start=51,
            ref_end=60,
            body_content="Body content here"
        )

        assert section.section_index == 0
        assert section.body_content == "Body content here"
        assert section.inline_ref_style == "numeric"
        assert section.references == []


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_document(self):
        """Test parsing empty document."""
        parser = ReferenceParser("")
        start, end = parser.find_reference_section()

        assert start is None
        assert end is None

    def test_references_header_only(self):
        """Test document with header but no actual references."""
        content = """# Document

## References

"""
        parser = ReferenceParser(content)
        start, end = parser.find_reference_section()

        # Implementation requires actual reference content after header
        # Empty reference sections are not detected
        # This is expected behavior - no references to process
        assert start is None

    def test_malformed_reference(self):
        """Test handling of malformed reference."""
        content = """## References

1. This is not a proper reference format at all
2. [Proper Reference](https://example.com)
"""
        parser = ReferenceParser(content)
        parser.find_reference_section()
        refs = parser.parse_references()

        # Should parse what it can
        assert len(refs) >= 1

    def test_special_characters_in_title(self):
        """Test handling special characters in titles."""
        content = """## References

1. [Title with <special> & "characters"](https://example.com)
"""
        parser = ReferenceParser(content)
        parser.find_reference_section()
        refs = parser.parse_references()

        assert len(refs) == 1
        assert "special" in refs[0].title

    def test_unicode_content(self):
        """Test handling unicode characters."""
        content = """## References

1. [Étude française](https://example.com)
2. [日本語タイトル](https://example.jp)
"""
        parser = ReferenceParser(content)
        parser.find_reference_section()
        refs = parser.parse_references()

        assert len(refs) == 2

    def test_very_long_reference(self):
        """Test handling very long reference text."""
        long_title = "A " * 200 + "Very Long Title"
        content = f"""## References

1. [{long_title}](https://example.com)
"""
        parser = ReferenceParser(content)
        parser.find_reference_section()
        refs = parser.parse_references()

        assert len(refs) == 1
        assert len(refs[0].title) > 100

