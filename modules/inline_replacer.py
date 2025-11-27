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
    """Replaces inline reference marks with mnemonic labels."""

    # Numeric style: [1], [1,2,3], [1-5]
    SINGLE_REF_PATTERN = r'\[(\d+)\]'
    COMMA_REF_PATTERN = r'\[([\d,\s]+)\]'
    RANGE_REF_PATTERN = r'\[(\d+)\s*[-–—]\s*(\d+)\]'
    
    # Footnote style: [^1], [^2]
    FOOTNOTE_REF_PATTERN = r'\[\^(\d+)\]'

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

    def replace_all(self, content: str) -> ReplacementResult:
        """Replace all inline references."""
        self.replacement_log = []
        modified = content

        if self.style == "footnote":
            # Footnote style: only single refs [^1]
            modified = self._replace_footnotes(modified)
        else:
            # Numeric style: Process in order: ranges, comma-separated, singles
            modified = self._replace_ranges(modified)
            modified = self._replace_comma_separated(modified)
            modified = self._replace_singles(modified)

        return ReplacementResult(
            original_text=content,
            modified_text=modified,
            replacements_made=len(self.replacement_log),
            replacement_log=self.replacement_log,
        )
    
    def _replace_footnotes(self, content: str) -> str:
        """Replace [^1] with [^label]."""
        def replacer(match: re.Match) -> str:
            num = int(match.group(1))
            original = match.group(0)

            if num in self.mapping:
                replacement = self.mapping[num]
                self.replacement_log.append((original, replacement))
                logger.debug(f"Footnote: {original} -> {replacement}")
                return replacement
            return original  # Keep original if not mapped

        return re.sub(self.FOOTNOTE_REF_PATTERN, replacer, content)

    def _replace_ranges(self, content: str) -> str:
        """Replace [1-5] with [^label1] [^label2] ..."""
        def replacer(match: re.Match) -> str:
            start = int(match.group(1))
            end = int(match.group(2))
            original = match.group(0)

            labels = []
            for num in range(start, end + 1):
                labels.append(self.mapping.get(num, f"[^{num}]"))

            replacement = ' '.join(labels)
            self.replacement_log.append((original, replacement))
            logger.debug(f"Range: {original} -> {replacement}")
            return replacement

        return re.sub(self.RANGE_REF_PATTERN, replacer, content)

    def _replace_comma_separated(self, content: str) -> str:
        """Replace [1,2,3] with [^label1] [^label2] [^label3]."""
        def replacer(match: re.Match) -> str:
            numbers_str = match.group(1)
            original = match.group(0)

            if ',' not in numbers_str:
                return original

            numbers = [int(n.strip()) for n in numbers_str.split(',') if n.strip().isdigit()]
            if not numbers:
                return original

            labels = [self.mapping.get(num, f"[^{num}]") for num in numbers]
            replacement = ' '.join(labels)
            self.replacement_log.append((original, replacement))
            logger.debug(f"Comma: {original} -> {replacement}")
            return replacement

        return re.sub(self.COMMA_REF_PATTERN, replacer, content)

    def _replace_singles(self, content: str) -> str:
        """Replace [1] with [^label]."""
        def replacer(match: re.Match) -> str:
            num = int(match.group(1))
            original = match.group(0)

            if num in self.mapping:
                replacement = self.mapping[num]
                self.replacement_log.append((original, replacement))
                logger.debug(f"Single: {original} -> {replacement}")
                return replacement
            return f"[^{num}]"

        return re.sub(self.SINGLE_REF_PATTERN, replacer, content)

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

