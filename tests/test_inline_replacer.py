"""
Tests for the Inline Replacer module.
"""

import pytest
from modules.inline_replacer import InlineReplacer


class TestInlineReplacer:
    """Test cases for InlineReplacer."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mapping = {
            1: "[^SmithA-2024-12345678]",
            2: "[^JonesB-2023-87654321]",
            3: "[^WilsonC-2022-11111111]",
            4: "[^BrownD-2021-22222222]",
            5: "[^DavisE-2020-33333333]",
        }
        self.replacer = InlineReplacer(self.mapping)

    def test_replace_single_reference(self):
        """Test replacing single references."""
        content = "This is a statement [1] with a citation."
        result = self.replacer.replace_all(content)

        assert "[^SmithA-2024-12345678]" in result.modified_text
        assert "[1]" not in result.modified_text
        assert result.replacements_made == 1

    def test_replace_multiple_singles(self):
        """Test replacing multiple single references."""
        content = "First [1] second [2] third [3]."
        result = self.replacer.replace_all(content)

        assert "[^SmithA-2024-12345678]" in result.modified_text
        assert "[^JonesB-2023-87654321]" in result.modified_text
        assert "[^WilsonC-2022-11111111]" in result.modified_text
        assert result.replacements_made == 3

    def test_replace_comma_separated(self):
        """Test replacing comma-separated references."""
        content = "Statement with multiple citations [1,2,3]."
        result = self.replacer.replace_all(content)

        # Should become space-separated labels
        assert "[^SmithA-2024-12345678]" in result.modified_text
        assert "[^JonesB-2023-87654321]" in result.modified_text
        assert "[^WilsonC-2022-11111111]" in result.modified_text
        assert "[1,2,3]" not in result.modified_text

    def test_replace_range(self):
        """Test replacing range references."""
        content = "Statement with range [1-3]."
        result = self.replacer.replace_all(content)

        # Should expand range and replace all
        assert "[^SmithA-2024-12345678]" in result.modified_text
        assert "[^JonesB-2023-87654321]" in result.modified_text
        assert "[^WilsonC-2022-11111111]" in result.modified_text
        assert "[1-3]" not in result.modified_text

    def test_unmapped_reference(self):
        """Test handling of unmapped reference numbers."""
        content = "Mapped [1] and unmapped [99]."
        result = self.replacer.replace_all(content)

        assert "[^SmithA-2024-12345678]" in result.modified_text
        assert "[^99]" in result.modified_text  # Kept as footnote format

    def test_extract_inline_numbers(self):
        """Test extracting all reference numbers from content."""
        content = "Text [1] and [2,3] and [4-6] and [10]."
        numbers = InlineReplacer.extract_inline_numbers(content)

        assert 1 in numbers
        assert 2 in numbers
        assert 3 in numbers
        assert 4 in numbers
        assert 5 in numbers
        assert 6 in numbers
        assert 10 in numbers

    def test_preview_replacements(self):
        """Test previewing replacements."""
        content = "Line 1\nText [1] here.\nMore [2] text."
        previews = self.replacer.preview_replacements(content)

        assert len(previews) == 2
        # Each preview is (original, replacement, line_number)
        assert any("[1]" in p[0] for p in previews)
        assert any("[2]" in p[0] for p in previews)


class TestTableEscaping:
    """Test cases for markdown table escaping."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mapping = {
            1: "[^SmithA-2024-12345678]",
            2: "[^JonesB-2023-87654321]",
        }
        self.replacer = InlineReplacer(self.mapping)

    def test_is_table_row(self):
        """Test detection of markdown table rows."""
        assert self.replacer._is_table_row("| Column 1 | Column 2 |")
        assert self.replacer._is_table_row("  | Column 1 | Column 2 |")  # With leading space
        assert not self.replacer._is_table_row("This is normal text")
        assert not self.replacer._is_table_row("Text with | pipe symbol")

    def test_escape_for_table(self):
        """Test bracket escaping for table context."""
        assert self.replacer._escape_for_table("[^SmithA-2024]") == "\\[^SmithA-2024]"
        assert self.replacer._escape_for_table("plain text") == "plain text"

    def test_table_row_reference_escaped(self):
        """Test that references in table rows get escaped brackets."""
        content = "| Data | More data [1] |"
        result = self.replacer.replace_all(content)

        # Should have escaped bracket in table
        assert "\\[^SmithA-2024-12345678]" in result.modified_text
        assert result.replacements_made == 1

    def test_non_table_reference_not_escaped(self):
        """Test that references outside tables are NOT escaped."""
        content = "Normal text with a citation [1]."
        result = self.replacer.replace_all(content)

        # Should NOT have escaped bracket outside table
        assert "[^SmithA-2024-12345678]" in result.modified_text
        assert "\\[^SmithA-2024-12345678]" not in result.modified_text

    def test_mixed_table_and_text(self):
        """Test document with both table and non-table references."""
        content = """Normal paragraph with citation [1].

| Category | Details |
| :--- | :--- |
| Row 1 | Data with citation [2] |

Another paragraph with [1] citation."""
        
        result = self.replacer.replace_all(content)

        # Table row should have escaped bracket
        assert "\\[^JonesB-2023-87654321]" in result.modified_text
        # Non-table rows should have unescaped brackets
        lines = result.modified_text.split('\n')
        paragraph_lines = [l for l in lines if not l.strip().startswith('|') and '[^SmithA' in l]
        for line in paragraph_lines:
            assert "\\[^SmithA" not in line

    def test_table_range_reference_escaped(self):
        """Test that range references in tables get escaped."""
        content = "| Data [1-2] |"
        result = self.replacer.replace_all(content)

        # Both expanded labels should be escaped
        assert "\\[^SmithA-2024-12345678]" in result.modified_text
        assert "\\[^JonesB-2023-87654321]" in result.modified_text

    def test_table_comma_reference_escaped(self):
        """Test that comma-separated references in tables get escaped."""
        content = "| Data [1,2] |"
        result = self.replacer.replace_all(content)

        # Both labels should be escaped
        assert "\\[^SmithA-2024-12345678]" in result.modified_text
        assert "\\[^JonesB-2023-87654321]" in result.modified_text

    def test_footnote_style_in_table(self):
        """Test footnote-style references in tables get escaped."""
        replacer = InlineReplacer({1: "[^SmithA-2024]"}, style="footnote")
        content = "| Data [^1] |"
        result = replacer.replace_all(content)

        assert "\\[^SmithA-2024]" in result.modified_text
