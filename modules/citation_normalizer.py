"""
Citation Normalizer Module - Preprocesses legacy citation formats to Obsidian footnote style.

Converts legacy LLM-generated citation formats to proper Obsidian footnotes:
    [1]         →  [^1]
    [1, 2]      →  [^1] [^2]
    [6-10]      →  [^6] [^7] [^8] [^9] [^10]
    [1, 3-5, 8] →  [^1] [^3] [^4] [^5] [^8]

Uses a hybrid protection strategy to avoid false positives:
- Placeholder protection for markdown links, wikilinks, images, existing footnotes
- Context validation for edge cases
- Exclusion of code blocks, YAML frontmatter, and math blocks
"""

import re
import uuid
from typing import Dict, List, Tuple, Optional, Set
from dataclasses import dataclass, field
from enum import Enum
from loguru import logger


class NormalizationChange(Enum):
    """Types of normalization changes."""
    SINGLE = "single"           # [1] → [^1]
    COMMA_LIST = "comma_list"   # [1, 2] → [^1] [^2]
    RANGE = "range"             # [1-5] → [^1] [^2] ...
    MIXED = "mixed"             # [1, 3-5] → [^1] [^3] [^4] [^5]


@dataclass
class NormalizationResult:
    """Result of citation normalization."""
    original_content: str
    normalized_content: str
    changes_made: int
    change_log: List[Tuple[str, str, int, str]]  # (original, replacement, line_num, change_type)
    skipped_regions: List[Tuple[int, int, str]]  # (start, end, reason)
    
    @property
    def has_changes(self) -> bool:
        return self.changes_made > 0


@dataclass
class ProtectedRegion:
    """A region of text that should not be processed."""
    start: int
    end: int
    reason: str
    placeholder: str
    original_text: str


class CitationNormalizer:
    """
    Normalizes legacy numeric citation formats to Obsidian footnote style.
    
    Uses a hybrid protection strategy:
    1. Placeholder protection for non-citation brackets
    2. Context validation for ambiguous cases
    3. State tracking for excluded regions (code, YAML, math)
    """
    
    # Patterns for citation detection (1-3 digit integers)
    # Matches: [1], [12], [123], [1,2], [1, 2, 3], [1-5], [1–10], [1—20], [1 to 5]
    LEGACY_CITATION_PATTERN = re.compile(
        r'\[(\d{1,3}(?:\s*(?:[,]|[-–—]|\s+to\s+)\s*\d{1,3})*)\]',
        re.IGNORECASE
    )
    
    # Patterns for protected content (non-citations)
    MARKDOWN_LINK_PATTERN = re.compile(r'\[([^\]]*)\]\([^)]+\)')  # [text](url)
    WIKILINK_PATTERN = re.compile(r'\[\[([^\]]+)\]\]')            # [[note]]
    IMAGE_PATTERN = re.compile(r'!\[([^\]]*)\]\([^)]*\)')         # ![alt](url)
    IMAGE_WIKILINK_PATTERN = re.compile(r'!\[\[([^\]]+)\]\]')     # ![[image]]
    EXISTING_FOOTNOTE_PATTERN = re.compile(r'\[\^[^\]]+\]')       # [^existing]
    FOOTNOTE_DEF_PATTERN = re.compile(r'^\[\^[^\]]+\]:')          # [^ref]: definition
    
    # Patterns for excluded regions
    CODE_BLOCK_PATTERN = re.compile(r'```[\s\S]*?```', re.MULTILINE)
    INLINE_CODE_PATTERN = re.compile(r'`[^`]+`')
    YAML_FRONTMATTER_PATTERN = re.compile(r'^---\n[\s\S]*?\n---\n', re.MULTILINE)
    MATH_BLOCK_PATTERN = re.compile(r'\$\$[\s\S]*?\$\$')
    INLINE_MATH_PATTERN = re.compile(r'\$[^$\n]+\$')
    
    # Table row detection
    TABLE_ROW_PATTERN = re.compile(r'^\s*\|', re.MULTILINE)
    
    def __init__(self):
        """Initialize the normalizer."""
        self._placeholders: Dict[str, ProtectedRegion] = {}
        self._excluded_ranges: List[Tuple[int, int, str]] = []
    
    def normalize(self, content: str, dry_run: bool = False) -> NormalizationResult:
        """
        Normalize all legacy citation formats in the content.
        
        Args:
            content: The markdown content to process
            dry_run: If True, only preview changes without modifying
            
        Returns:
            NormalizationResult with the normalized content and change log
        """
        self._placeholders.clear()
        self._excluded_ranges.clear()
        
        change_log: List[Tuple[str, str, int, str]] = []
        
        # Step 1: Identify excluded regions (code, YAML, math)
        self._identify_excluded_regions(content)
        
        # Step 2: Protect non-citation brackets with placeholders
        protected_content = self._protect_non_citations(content)
        
        # Step 3: Process citations line by line (for accurate line numbers)
        lines = protected_content.split('\n')
        normalized_lines = []
        
        # Calculate line start positions for excluded region checking
        line_starts = []
        pos = 0
        for line in lines:
            line_starts.append(pos)
            pos += len(line) + 1  # +1 for newline
        
        for line_num, line in enumerate(lines, 1):
            line_start = line_starts[line_num - 1]
            
            # Check if this is a footnote definition line (skip these)
            if self.FOOTNOTE_DEF_PATTERN.match(line.strip()):
                normalized_lines.append(line)
                continue
            
            # Process citations in this line, passing the line_start for offset calculations
            is_table_row = bool(self.TABLE_ROW_PATTERN.match(line))
            normalized_line, line_changes = self._normalize_line(
                line, line_num, is_table_row, line_start
            )
            normalized_lines.append(normalized_line)
            change_log.extend(line_changes)
        
        normalized_content = '\n'.join(normalized_lines)
        
        # Step 4: Restore protected content from placeholders
        normalized_content = self._restore_placeholders(normalized_content)
        
        # Build result
        result = NormalizationResult(
            original_content=content,
            normalized_content=normalized_content if not dry_run else content,
            changes_made=len(change_log),
            change_log=change_log,
            skipped_regions=[(r[0], r[1], r[2]) for r in self._excluded_ranges],
        )
        
        return result
    
    def _identify_excluded_regions(self, content: str) -> None:
        """Identify regions that should be excluded from processing."""
        # YAML frontmatter
        for match in self.YAML_FRONTMATTER_PATTERN.finditer(content):
            self._excluded_ranges.append((match.start(), match.end(), "yaml_frontmatter"))
        
        # Code blocks
        for match in self.CODE_BLOCK_PATTERN.finditer(content):
            self._excluded_ranges.append((match.start(), match.end(), "code_block"))
        
        # Inline code
        for match in self.INLINE_CODE_PATTERN.finditer(content):
            self._excluded_ranges.append((match.start(), match.end(), "inline_code"))
        
        # Math blocks
        for match in self.MATH_BLOCK_PATTERN.finditer(content):
            self._excluded_ranges.append((match.start(), match.end(), "math_block"))
        
        # Inline math
        for match in self.INLINE_MATH_PATTERN.finditer(content):
            self._excluded_ranges.append((match.start(), match.end(), "inline_math"))
        
        # Sort by start position
        self._excluded_ranges.sort(key=lambda x: x[0])
    
    def _is_in_excluded_region(self, start: int, end: int) -> bool:
        """Check if a position range overlaps with any excluded region."""
        for region_start, region_end, _ in self._excluded_ranges:
            if start < region_end and end > region_start:
                return True
        return False
    
    def _protect_non_citations(self, content: str) -> str:
        """Replace non-citation brackets with placeholders."""
        protected = content
        
        # Order matters: protect more specific patterns first
        patterns = [
            (self.IMAGE_WIKILINK_PATTERN, "image_wikilink"),
            (self.IMAGE_PATTERN, "image"),
            (self.WIKILINK_PATTERN, "wikilink"),
            (self.MARKDOWN_LINK_PATTERN, "markdown_link"),
            (self.EXISTING_FOOTNOTE_PATTERN, "existing_footnote"),
        ]
        
        for pattern, reason in patterns:
            protected = self._protect_pattern(protected, pattern, reason)
        
        return protected
    
    def _protect_pattern(self, content: str, pattern: re.Pattern, reason: str) -> str:
        """Replace matches of a pattern with unique placeholders."""
        def replacer(match: re.Match) -> str:
            placeholder_id = f"__PROTECTED_{uuid.uuid4().hex[:12]}__"
            region = ProtectedRegion(
                start=match.start(),
                end=match.end(),
                reason=reason,
                placeholder=placeholder_id,
                original_text=match.group(0),
            )
            self._placeholders[placeholder_id] = region
            return placeholder_id
        
        return pattern.sub(replacer, content)
    
    def _restore_placeholders(self, content: str) -> str:
        """Restore all placeholders with their original content."""
        restored = content
        for placeholder_id, region in self._placeholders.items():
            restored = restored.replace(placeholder_id, region.original_text)
        return restored
    
    def _normalize_line(
        self, 
        line: str, 
        line_num: int, 
        is_table_row: bool,
        line_start: int = 0
    ) -> Tuple[str, List[Tuple[str, str, int, str]]]:
        """
        Normalize citations in a single line.
        
        Returns:
            Tuple of (normalized_line, list of changes)
        """
        changes: List[Tuple[str, str, int, str]] = []
        
        def normalize_match(match: re.Match) -> str:
            original = match.group(0)
            inner = match.group(1)
            
            # Context validation: check characters before/after
            start_pos = match.start()
            end_pos = match.end()
            
            # Check if this match is in an excluded region (code, math, etc.)
            abs_start = line_start + start_pos
            abs_end = line_start + end_pos
            if self._is_in_excluded_region(abs_start, abs_end):
                return original
            
            # Skip if preceded by ! (image)
            if start_pos > 0 and line[start_pos - 1] == '!':
                return original
            
            # Skip if preceded by [ (wikilink start like [[)
            if start_pos > 0 and line[start_pos - 1] == '[':
                return original
            
            # Skip if followed by ( (markdown link)
            if end_pos < len(line) and line[end_pos] == '(':
                return original
            
            # Skip if followed by [ and then NOT a digit or ^ (wikilink, not another citation)
            if end_pos < len(line) and line[end_pos] == '[':
                # Check if it's another citation [N] or [^N]
                remaining = line[end_pos:]
                if not re.match(r'\[\^?\d', remaining):
                    return original  # It's a wikilink like [[
            
            # Skip if it looks like a placeholder (contains letters other than "to")
            # Allow "to" as a range separator (e.g., [6 to 10])
            inner_without_to = re.sub(r'\bto\b', '', inner, flags=re.IGNORECASE)
            if re.search(r'[a-zA-Z]', inner_without_to):
                return original
            
            # Parse and expand the citation
            expanded = self._expand_citation(inner)
            if not expanded:
                return original
            
            # Format as footnotes
            if is_table_row:
                # Escape brackets for table context
                formatted = ' '.join(f'\\[^{n}\\]' for n in expanded)
            else:
                formatted = ' '.join(f'[^{n}]' for n in expanded)
            
            # Determine change type
            if len(expanded) == 1 and ',' not in inner and not any(c in inner for c in '-–—') and ' to ' not in inner.lower():
                change_type = NormalizationChange.SINGLE.value
            elif ',' in inner and not any(c in inner for c in '-–—') and ' to ' not in inner.lower():
                change_type = NormalizationChange.COMMA_LIST.value
            elif ',' not in inner:
                change_type = NormalizationChange.RANGE.value
            else:
                change_type = NormalizationChange.MIXED.value
            
            changes.append((original, formatted, line_num, change_type))
            logger.debug(f"Normalized: {original} → {formatted} (line {line_num})")
            
            return formatted
        
        normalized_line = self.LEGACY_CITATION_PATTERN.sub(normalize_match, line)
        return normalized_line, changes
    
    def _expand_citation(self, inner: str) -> Optional[List[int]]:
        """
        Expand citation content to a list of integers.
        
        Examples:
            "1" → [1]
            "1, 2, 3" → [1, 2, 3]
            "6-10" → [6, 7, 8, 9, 10]
            "1, 3-5, 8" → [1, 3, 4, 5, 8]
        """
        # Normalize separators
        normalized = inner.strip()
        normalized = normalized.replace('–', '-')  # en-dash
        normalized = normalized.replace('—', '-')  # em-dash
        normalized = re.sub(r'\s+to\s+', '-', normalized, flags=re.IGNORECASE)  # "to"
        
        # Split by comma
        parts = [p.strip() for p in normalized.split(',')]
        
        result: List[int] = []
        
        for part in parts:
            if not part:
                continue
            
            if '-' in part:
                # Range: "6-10"
                range_parts = part.split('-')
                if len(range_parts) != 2:
                    return None  # Invalid range
                
                try:
                    start = int(range_parts[0].strip())
                    end = int(range_parts[1].strip())
                except ValueError:
                    return None  # Non-integer
                
                if start > end:
                    return None  # Invalid range direction
                
                if end - start > 100:
                    return None  # Suspiciously large range, probably not a citation
                
                result.extend(range(start, end + 1))
            else:
                # Single number
                try:
                    num = int(part)
                    if num < 1 or num > 999:
                        return None  # Outside 1-3 digit range
                    result.append(num)
                except ValueError:
                    return None  # Non-integer
        
        return result if result else None
    
    def preview(self, content: str) -> str:
        """
        Generate a preview of changes in diff-style format.
        
        Args:
            content: The markdown content to analyze
            
        Returns:
            A formatted string showing what would change
        """
        result = self.normalize(content, dry_run=True)
        
        if not result.has_changes:
            return "No citation format changes needed."
        
        lines = []
        lines.append(f"Citation Format Normalization Preview")
        lines.append(f"=" * 50)
        lines.append(f"Total changes: {result.changes_made}")
        lines.append("")
        
        # Group by change type
        by_type: Dict[str, List[Tuple[str, str, int]]] = {}
        for original, replacement, line_num, change_type in result.change_log:
            if change_type not in by_type:
                by_type[change_type] = []
            by_type[change_type].append((original, replacement, line_num))
        
        type_names = {
            "single": "Single Citations",
            "comma_list": "Comma-Separated Lists",
            "range": "Range Expansions",
            "mixed": "Mixed Formats",
        }
        
        for change_type, changes in by_type.items():
            lines.append(f"\n### {type_names.get(change_type, change_type)} ({len(changes)})")
            lines.append("-" * 40)
            
            for original, replacement, line_num in changes:
                lines.append(f"  Line {line_num:4d}: {original}")
                lines.append(f"           → {replacement}")
        
        if result.skipped_regions:
            lines.append(f"\n### Skipped Regions ({len(result.skipped_regions)})")
            lines.append("-" * 40)
            region_counts: Dict[str, int] = {}
            for _, _, reason in result.skipped_regions:
                region_counts[reason] = region_counts.get(reason, 0) + 1
            for reason, count in region_counts.items():
                lines.append(f"  {reason}: {count}")
        
        return '\n'.join(lines)
    
    def preview_table(self, content: str) -> List[Dict[str, str]]:
        """
        Generate a preview as a list of dictionaries (for structured output).
        
        Args:
            content: The markdown content to analyze
            
        Returns:
            List of dicts with keys: line, original, replacement, type
        """
        result = self.normalize(content, dry_run=True)
        
        return [
            {
                "line": str(line_num),
                "original": original,
                "replacement": replacement,
                "type": change_type,
            }
            for original, replacement, line_num, change_type in result.change_log
        ]


def normalize_citation_format(content: str, dry_run: bool = False) -> NormalizationResult:
    """
    Convenience function to normalize citation formats.
    
    Args:
        content: Markdown content to process
        dry_run: If True, only preview changes
        
    Returns:
        NormalizationResult
    """
    normalizer = CitationNormalizer()
    return normalizer.normalize(content, dry_run=dry_run)


def preview_citation_normalization(content: str) -> str:
    """
    Convenience function to preview citation normalization.
    
    Args:
        content: Markdown content to analyze
        
    Returns:
        Formatted preview string
    """
    normalizer = CitationNormalizer()
    return normalizer.preview(content)

