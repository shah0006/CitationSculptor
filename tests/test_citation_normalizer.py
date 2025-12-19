"""Tests for the Citation Normalizer module."""

import pytest
from modules.citation_normalizer import (
    CitationNormalizer,
    NormalizationResult,
    normalize_citation_format,
    preview_citation_normalization,
)


class TestCitationNormalizer:
    """Test suite for CitationNormalizer."""
    
    @pytest.fixture
    def normalizer(self):
        return CitationNormalizer()
    
    # ==========================================================================
    # Basic Single Citation Tests
    # ==========================================================================
    
    def test_single_citation(self, normalizer):
        """Test single numeric citation conversion."""
        content = "This is a fact [1]."
        result = normalizer.normalize(content)
        assert result.normalized_content == "This is a fact [^1]."
        assert result.changes_made == 1
    
    def test_single_two_digit(self, normalizer):
        """Test two-digit citation."""
        content = "Another claim [42]."
        result = normalizer.normalize(content)
        assert result.normalized_content == "Another claim [^42]."
    
    def test_single_three_digit(self, normalizer):
        """Test three-digit citation."""
        content = "Large reference [123]."
        result = normalizer.normalize(content)
        assert result.normalized_content == "Large reference [^123]."
    
    def test_multiple_singles_same_line(self, normalizer):
        """Test multiple single citations on same line."""
        content = "Facts [1] and more facts [2]."
        result = normalizer.normalize(content)
        assert result.normalized_content == "Facts [^1] and more facts [^2]."
        assert result.changes_made == 2
    
    # ==========================================================================
    # Comma-Separated List Tests
    # ==========================================================================
    
    def test_comma_two_items(self, normalizer):
        """Test comma-separated list of two."""
        content = "Multiple sources [18, 11]."
        result = normalizer.normalize(content)
        assert result.normalized_content == "Multiple sources [^18] [^11]."
        assert result.changes_made == 1
    
    def test_comma_three_items(self, normalizer):
        """Test comma-separated list of three."""
        content = "See references [1, 2, 3]."
        result = normalizer.normalize(content)
        assert result.normalized_content == "See references [^1] [^2] [^3]."
    
    def test_comma_varying_spaces(self, normalizer):
        """Test comma lists with varying spacing."""
        content = "No spaces [1,2,3] vs spaces [4, 5, 6]."
        result = normalizer.normalize(content)
        assert "[^1] [^2] [^3]" in result.normalized_content
        assert "[^4] [^5] [^6]" in result.normalized_content
    
    # ==========================================================================
    # Range Expansion Tests
    # ==========================================================================
    
    def test_range_hyphen(self, normalizer):
        """Test range with regular hyphen."""
        content = "References [6-10]."
        result = normalizer.normalize(content)
        assert result.normalized_content == "References [^6] [^7] [^8] [^9] [^10]."
    
    def test_range_en_dash(self, normalizer):
        """Test range with en-dash."""
        content = "References [6–10]."
        result = normalizer.normalize(content)
        assert result.normalized_content == "References [^6] [^7] [^8] [^9] [^10]."
    
    def test_range_em_dash(self, normalizer):
        """Test range with em-dash."""
        content = "References [6—10]."
        result = normalizer.normalize(content)
        assert result.normalized_content == "References [^6] [^7] [^8] [^9] [^10]."
    
    def test_range_with_spaces(self, normalizer):
        """Test range with spaces around dash."""
        content = "References [6 - 10]."
        result = normalizer.normalize(content)
        assert result.normalized_content == "References [^6] [^7] [^8] [^9] [^10]."
    
    def test_range_word_to(self, normalizer):
        """Test range with 'to' keyword."""
        content = "References [6 to 10]."
        result = normalizer.normalize(content)
        assert result.normalized_content == "References [^6] [^7] [^8] [^9] [^10]."
    
    def test_range_small(self, normalizer):
        """Test small range."""
        content = "See [1-2]."
        result = normalizer.normalize(content)
        assert result.normalized_content == "See [^1] [^2]."
    
    # ==========================================================================
    # Mixed Format Tests
    # ==========================================================================
    
    def test_mixed_comma_and_range(self, normalizer):
        """Test mixed comma and range format."""
        content = "References [1, 3-5, 8]."
        result = normalizer.normalize(content)
        assert result.normalized_content == "References [^1] [^3] [^4] [^5] [^8]."
    
    def test_mixed_complex(self, normalizer):
        """Test complex mixed format."""
        content = "See [1, 2, 5-7, 10, 12-14]."
        result = normalizer.normalize(content)
        expected_refs = "[^1] [^2] [^5] [^6] [^7] [^10] [^12] [^13] [^14]"
        assert expected_refs in result.normalized_content
    
    # ==========================================================================
    # Table Context Tests
    # ==========================================================================
    
    def test_table_row_escaping(self, normalizer):
        """Test that citations in table rows are escaped."""
        content = "| Cell content [1] | More [2] |"
        result = normalizer.normalize(content)
        assert result.normalized_content == "| Cell content \\[^1\\] | More \\[^2\\] |"
    
    def test_table_row_range_escaping(self, normalizer):
        """Test range expansion in table rows."""
        content = "| References [1-3] |"
        result = normalizer.normalize(content)
        assert "\\[^1\\] \\[^2\\] \\[^3\\]" in result.normalized_content
    
    def test_non_table_no_escaping(self, normalizer):
        """Test that non-table content is not escaped."""
        content = "Regular text [1]."
        result = normalizer.normalize(content)
        assert result.normalized_content == "Regular text [^1]."
        assert "\\" not in result.normalized_content
    
    # ==========================================================================
    # False Positive Prevention Tests
    # ==========================================================================
    
    def test_markdown_link_not_converted(self, normalizer):
        """Test that markdown links are not converted."""
        content = "See [click here](https://example.com) for details [1]."
        result = normalizer.normalize(content)
        assert "[click here](https://example.com)" in result.normalized_content
        assert "[^1]" in result.normalized_content
    
    def test_wikilink_not_converted(self, normalizer):
        """Test that wikilinks are not converted."""
        content = "See [[My Note]] and [1]."
        result = normalizer.normalize(content)
        assert "[[My Note]]" in result.normalized_content
        assert "[^1]" in result.normalized_content
    
    def test_image_not_converted(self, normalizer):
        """Test that images are not converted."""
        content = "![Alt text](image.png) and [1]."
        result = normalizer.normalize(content)
        assert "![Alt text](image.png)" in result.normalized_content
        assert "[^1]" in result.normalized_content
    
    def test_image_wikilink_not_converted(self, normalizer):
        """Test that image wikilinks are not converted."""
        content = "![[image.png]] and [1]."
        result = normalizer.normalize(content)
        assert "![[image.png]]" in result.normalized_content
        assert "[^1]" in result.normalized_content
    
    def test_existing_footnote_not_converted(self, normalizer):
        """Test that existing footnotes are not re-converted."""
        content = "Already formatted [^1] and legacy [2]."
        result = normalizer.normalize(content)
        assert "[^1]" in result.normalized_content  # Original preserved
        assert "[^2]" in result.normalized_content  # Legacy converted
        # Should not create [^^1] or similar
        assert "[^^" not in result.normalized_content
    
    def test_footnote_definition_not_converted(self, normalizer):
        """Test that footnote definitions are not converted."""
        content = "[^1]: This is the footnote definition for [1]."
        result = normalizer.normalize(content)
        assert "[^1]:" in result.normalized_content  # Definition preserved
    
    def test_alphanumeric_not_converted(self, normalizer):
        """Test that alphanumeric brackets are not converted."""
        content = "See [Figure 1] and [1]."
        result = normalizer.normalize(content)
        assert "[Figure 1]" in result.normalized_content
        assert "[^1]" in result.normalized_content
    
    def test_four_digit_not_converted(self, normalizer):
        """Test that 4+ digit numbers are not converted."""
        content = "Year [2024] and citation [1]."
        result = normalizer.normalize(content)
        assert "[2024]" in result.normalized_content
        assert "[^1]" in result.normalized_content
    
    # ==========================================================================
    # Excluded Region Tests
    # ==========================================================================
    
    def test_code_block_excluded(self, normalizer):
        """Test that code blocks are excluded."""
        content = """Regular [1].
```python
array[1] = value
```
More text [2]."""
        result = normalizer.normalize(content)
        assert "[^1]" in result.normalized_content
        assert "[^2]" in result.normalized_content
        assert "array[1]" in result.normalized_content  # Not converted
    
    def test_inline_code_excluded(self, normalizer):
        """Test that inline code is excluded."""
        content = "Use `array[1]` syntax and see [1]."
        result = normalizer.normalize(content)
        assert "`array[1]`" in result.normalized_content
        assert "[^1]" in result.normalized_content
    
    def test_yaml_frontmatter_excluded(self, normalizer):
        """Test that YAML frontmatter is excluded."""
        content = """---
title: Document [1]
tags: [tag1, tag2]
---
Content [1]."""
        result = normalizer.normalize(content)
        # YAML should be preserved exactly
        assert "title: Document [1]" in result.normalized_content
        assert "tags: [tag1, tag2]" in result.normalized_content
        # Content should be converted
        assert "Content [^1]." in result.normalized_content
    
    def test_math_block_excluded(self, normalizer):
        """Test that math blocks are excluded."""
        content = """Text [1].
$$
x[1] + y[2] = z
$$
More [2]."""
        result = normalizer.normalize(content)
        assert "x[1] + y[2]" in result.normalized_content  # Not converted
        assert "[^1]" in result.normalized_content
        assert "[^2]" in result.normalized_content
    
    def test_inline_math_excluded(self, normalizer):
        """Test that inline math is excluded."""
        content = "Formula $a[1] + b[2]$ and citation [1]."
        result = normalizer.normalize(content)
        assert "$a[1] + b[2]$" in result.normalized_content
        assert "[^1]" in result.normalized_content
    
    # ==========================================================================
    # Edge Cases
    # ==========================================================================
    
    def test_empty_content(self, normalizer):
        """Test empty content."""
        result = normalizer.normalize("")
        assert result.normalized_content == ""
        assert result.changes_made == 0
    
    def test_no_citations(self, normalizer):
        """Test content with no citations."""
        content = "Just regular text with no citations."
        result = normalizer.normalize(content)
        assert result.normalized_content == content
        assert result.changes_made == 0
    
    def test_citation_at_start(self, normalizer):
        """Test citation at start of line."""
        content = "[1] starts the sentence."
        result = normalizer.normalize(content)
        assert result.normalized_content == "[^1] starts the sentence."
    
    def test_citation_at_end(self, normalizer):
        """Test citation at end of content."""
        content = "Ends with citation [1]"
        result = normalizer.normalize(content)
        assert result.normalized_content == "Ends with citation [^1]"
    
    def test_consecutive_citations(self, normalizer):
        """Test consecutive citations without space."""
        content = "Multiple[1][2][3]."
        result = normalizer.normalize(content)
        assert "[^1][^2][^3]" in result.normalized_content
    
    def test_preserves_surrounding_text(self, normalizer):
        """Test that surrounding text is preserved."""
        content = "Before [1] middle [2] after."
        result = normalizer.normalize(content)
        assert result.normalized_content == "Before [^1] middle [^2] after."
    
    def test_multiline_document(self, normalizer):
        """Test multi-line document."""
        content = """First paragraph [1].

Second paragraph [2, 3].

Third with range [4-6]."""
        result = normalizer.normalize(content)
        assert "[^1]" in result.normalized_content
        assert "[^2] [^3]" in result.normalized_content
        assert "[^4] [^5] [^6]" in result.normalized_content
        assert result.changes_made == 3
    
    def test_suspicious_large_range_rejected(self, normalizer):
        """Test that suspiciously large ranges are not expanded."""
        content = "Invalid range [1-500]."
        result = normalizer.normalize(content)
        # Should not expand a range > 100
        assert "[1-500]" in result.normalized_content
    
    # ==========================================================================
    # Preview Tests
    # ==========================================================================
    
    def test_dry_run_no_changes(self, normalizer):
        """Test that dry_run doesn't modify content."""
        content = "Citation [1]."
        result = normalizer.normalize(content, dry_run=True)
        assert result.normalized_content == content  # Original returned
        assert result.changes_made == 1  # But changes are logged
    
    def test_preview_output(self, normalizer):
        """Test preview output format."""
        content = "Citations [1] and [2-3]."
        preview = normalizer.preview(content)
        assert "Citation Format Normalization Preview" in preview
        assert "Total changes:" in preview
        assert "[1]" in preview
        assert "[^1]" in preview
    
    def test_preview_table_output(self, normalizer):
        """Test preview table output."""
        content = "Citations [1] and [2, 3]."
        table = normalizer.preview_table(content)
        assert len(table) == 2
        assert table[0]["original"] == "[1]"
        assert table[0]["replacement"] == "[^1]"


class TestConvenienceFunctions:
    """Test convenience functions."""
    
    def test_normalize_citation_format(self):
        """Test normalize_citation_format function."""
        content = "Text [1]."
        result = normalize_citation_format(content)
        assert result.normalized_content == "Text [^1]."
    
    def test_preview_citation_normalization(self):
        """Test preview_citation_normalization function."""
        content = "Text [1]."
        preview = preview_citation_normalization(content)
        assert "Preview" in preview


class TestRealWorldExamples:
    """Test with real-world document patterns."""
    
    @pytest.fixture
    def normalizer(self):
        return CitationNormalizer()
    
    def test_medical_document_pattern(self, normalizer):
        """Test pattern from medical documents with mixed citations."""
        content = """The guidelines recommend [1, 2] that patients undergo 
screening [3]. Previous studies [4-7] have shown efficacy, while 
meta-analyses [8, 10-12] confirmed these findings."""
        
        result = normalizer.normalize(content)
        
        assert "[^1] [^2]" in result.normalized_content
        assert "[^3]" in result.normalized_content
        assert "[^4] [^5] [^6] [^7]" in result.normalized_content
        assert "[^8] [^10] [^11] [^12]" in result.normalized_content
    
    def test_table_with_citations(self, normalizer):
        """Test table containing citations."""
        content = """| Finding | Evidence |
|---------|----------|
| Outcome A | Supported [1, 2] |
| Outcome B | See [3-5] |"""
        
        result = normalizer.normalize(content)
        
        # Table rows should have escaped brackets
        assert "\\[^1\\] \\[^2\\]" in result.normalized_content
        assert "\\[^3\\] \\[^4\\] \\[^5\\]" in result.normalized_content
    
    def test_document_with_existing_footnotes(self, normalizer):
        """Test document mixing legacy and modern footnote styles."""
        content = """This has a legacy citation [1] and a modern one [^Smith2024].

## References

[^Smith2024]: Smith J. Modern Citation. 2024.

The legacy reference [1] needs this definition:
[1] Jones A. Legacy Format. 2020."""
        
        result = normalizer.normalize(content)
        
        # Legacy inline converted
        assert "[^1]" in result.normalized_content
        # Modern preserved
        assert "[^Smith2024]" in result.normalized_content
        # Definitions preserved (lines starting with [^...]:)
        assert "[^Smith2024]:" in result.normalized_content

