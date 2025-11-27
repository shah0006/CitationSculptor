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

