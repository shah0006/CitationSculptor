"""Inline Replacer Module - Replaces inline reference marks."""

import re
from typing import Dict, List, Tuple
from dataclasses import dataclass
from loguru import logger


@dataclass
class ReplacementResult:
    """Result of inline reference replacement."""
    original_text: str
    modified_text: str
    replacements_made: int
    replacement_log: List[Tuple[str, str]]


class InlineReplacer:
    r"""Replaces inline reference marks with mnemonic labels.
    
    Note: In Obsidian markdown tables, square brackets must be escaped with
    a single backslash (e.g., \[^ref]) to render correctly. This class 
    automatically detects table rows and applies the necessary escaping.
    """

    # Numeric style: [1], [1,2,3], [1-5]
    SINGLE_REF_PATTERN = r'\[(\d+)\]'
    COMMA_REF_PATTERN = r'\[([\d,\s]+)\]'
    RANGE_REF_PATTERN = r'\[(\d+)\s*[-–—]\s*(\d+)\]'
    
    # Footnote style: [^1], [^2]
    FOOTNOTE_REF_PATTERN = r'\[\^(\d+)\]'
    
    # Pattern to detect markdown table rows (lines starting with |)
    TABLE_ROW_PATTERN = r'^\s*\|'

    def __init__(self, number_to_label_map: Dict[int, str], style: str = "numeric"):
        """
        Initialize with mapping: {1: "[^SmithJA-2024-12345]", ...}
        
        Args:
            number_to_label_map: Mapping from original number to new label
            style: "numeric" for [N] or "footnote" for [^N] input style
        """
        self.mapping = number_to_label_map
        self.style = style
        self.replacement_log: List[Tuple[str, str]] = []

    def _is_table_row(self, line: str) -> bool:
        """Check if a line is part of a markdown table."""
        return bool(re.match(self.TABLE_ROW_PATTERN, line))
    
    def _escape_for_table(self, label: str) -> str:
        r"""Escape square brackets for use in markdown tables.
        
        In Obsidian tables, [^ref] must be written as \[^ref] to render correctly.
        A single backslash before the opening bracket is required.
        """
        if label.startswith('[^'):
            return '\\' + label
        return label

    def replace_all(self, content: str) -> ReplacementResult:
        """Replace all inline references.
        
        Automatically escapes brackets for references within markdown tables.
        """
        self.replacement_log = []
        
        # Process line by line to handle table escaping
        lines = content.split('\n')
        modified_lines = []
        
        for line in lines:
            is_table = self._is_table_row(line)
            modified_line = line
            
            if self.style == "footnote":
                modified_line = self._replace_footnotes_in_line(modified_line, is_table)
            else:
                modified_line = self._replace_ranges_in_line(modified_line, is_table)
                modified_line = self._replace_comma_separated_in_line(modified_line, is_table)
                modified_line = self._replace_singles_in_line(modified_line, is_table)
            
            modified_lines.append(modified_line)
        
        modified = '\n'.join(modified_lines)

        return ReplacementResult(
            original_text=content,
            modified_text=modified,
            replacements_made=len(self.replacement_log),
            replacement_log=self.replacement_log,
        )
    
    def _replace_footnotes_in_line(self, line: str, is_table: bool) -> str:
        """Replace [^1] with [^label] in a single line."""
        def replacer(match: re.Match) -> str:
            num = int(match.group(1))
            original = match.group(0)

            if num in self.mapping:
                replacement = self.mapping[num]
                if is_table:
                    replacement = self._escape_for_table(replacement)
                self.replacement_log.append((original, replacement))
                logger.debug(f"Footnote: {original} -> {replacement}")
                return replacement
            return original  # Keep original if not mapped

        return re.sub(self.FOOTNOTE_REF_PATTERN, replacer, line)

    def _replace_ranges_in_line(self, line: str, is_table: bool) -> str:
        """Replace [1-5] with [^label1] [^label2] ... in a single line."""
        def replacer(match: re.Match) -> str:
            start = int(match.group(1))
            end = int(match.group(2))
            original = match.group(0)

            labels = []
            for num in range(start, end + 1):
                label = self.mapping.get(num, f"[^{num}]")
                if is_table:
                    label = self._escape_for_table(label)
                labels.append(label)

            replacement = ' '.join(labels)
            self.replacement_log.append((original, replacement))
            logger.debug(f"Range: {original} -> {replacement}")
            return replacement

        return re.sub(self.RANGE_REF_PATTERN, replacer, line)

    def _replace_comma_separated_in_line(self, line: str, is_table: bool) -> str:
        """Replace [1,2,3] with [^label1] [^label2] [^label3] in a single line."""
        def replacer(match: re.Match) -> str:
            numbers_str = match.group(1)
            original = match.group(0)

            if ',' not in numbers_str:
                return original

            numbers = [int(n.strip()) for n in numbers_str.split(',') if n.strip().isdigit()]
            if not numbers:
                return original

            labels = []
            for num in numbers:
                label = self.mapping.get(num, f"[^{num}]")
                if is_table:
                    label = self._escape_for_table(label)
                labels.append(label)
            
            replacement = ' '.join(labels)
            self.replacement_log.append((original, replacement))
            logger.debug(f"Comma: {original} -> {replacement}")
            return replacement

        return re.sub(self.COMMA_REF_PATTERN, replacer, line)

    def _replace_singles_in_line(self, line: str, is_table: bool) -> str:
        """Replace [1] with [^label] in a single line."""
        def replacer(match: re.Match) -> str:
            num = int(match.group(1))
            original = match.group(0)

            if num in self.mapping:
                replacement = self.mapping[num]
                if is_table:
                    replacement = self._escape_for_table(replacement)
                self.replacement_log.append((original, replacement))
                logger.debug(f"Single: {original} -> {replacement}")
                return replacement
            fallback = f"[^{num}]"
            if is_table:
                fallback = self._escape_for_table(fallback)
            return fallback

        return re.sub(self.SINGLE_REF_PATTERN, replacer, line)
    
    # Legacy methods for backwards compatibility
    def _replace_footnotes(self, content: str) -> str:
        """Replace [^1] with [^label]. Legacy method - use replace_all instead."""
        return self._replace_footnotes_in_line(content, is_table=False)

    def _replace_ranges(self, content: str) -> str:
        """Replace [1-5] with [^label1] [^label2] .... Legacy method."""
        return self._replace_ranges_in_line(content, is_table=False)

    def _replace_comma_separated(self, content: str) -> str:
        """Replace [1,2,3] with [^label1] [^label2] [^label3]. Legacy method."""
        return self._replace_comma_separated_in_line(content, is_table=False)

    def _replace_singles(self, content: str) -> str:
        """Replace [1] with [^label]. Legacy method."""
        return self._replace_singles_in_line(content, is_table=False)

    def preview_replacements(self, content: str) -> List[Tuple[str, str, int]]:
        """Preview replacements without modifying."""
        previews = []
        lines = content.split('\n')

        for line_num, line in enumerate(lines, 1):
            for match in re.finditer(self.SINGLE_REF_PATTERN, line):
                num = int(match.group(1))
                if num in self.mapping:
                    previews.append((match.group(0), self.mapping[num], line_num))

        return previews

    @staticmethod
    def extract_inline_numbers(content: str, style: str = "auto") -> List[int]:
        """
        Extract all reference numbers from content.
        
        Args:
            content: Text to search
            style: "numeric" for [N], "footnote" for [^N], "auto" for both
        """
        numbers = set()

        # Numeric style: [1], [1-3], [1,2,3]
        if style in ("numeric", "auto"):
            for match in re.finditer(r'\[(\d+)\]', content):
                numbers.add(int(match.group(1)))

            for match in re.finditer(r'\[(\d+)\s*[-–—]\s*(\d+)\]', content):
                start, end = int(match.group(1)), int(match.group(2))
                numbers.update(range(start, end + 1))

            for match in re.finditer(r'\[([\d,\s]+)\]', content):
                for num_str in match.group(1).split(','):
                    if num_str.strip().isdigit():
                        numbers.add(int(num_str.strip()))
        
        # Footnote style: [^1]
        if style in ("footnote", "auto"):
            for match in re.finditer(r'\[\^(\d+)\]', content):
                numbers.add(int(match.group(1)))

        return sorted(numbers)

