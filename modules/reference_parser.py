"""Reference Parser Module - Parses reference sections from markdown documents."""

import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple
from loguru import logger


@dataclass
class ParsedReference:
    """Represents a single parsed reference."""
    original_number: int
    original_text: str
    title: str
    url: Optional[str]
    source_name: Optional[str]
    line_number: int
    citation_type: Optional[str] = None
    processed: bool = False
    new_label: Optional[str] = None
    formatted_citation: Optional[str] = None
    needs_review: bool = False
    review_reason: Optional[str] = None
    metadata: dict = field(default_factory=dict)


class ReferenceParser:
    """Parses reference sections from markdown documents."""

    REFERENCE_HEADER_PATTERNS = [
        r'^#{1,2}\s*References\s*$',
        r'^#{1,2}\s*Sources\s*$',
        r'^#{1,2}\s*Citations\s*$',
    ]
    
    # Pattern 1: Simple format - "1. [Title - Source](URL)"
    SIMPLE_REF_PATTERN = r'^(\d+)\.\s*\[([^\]]+)\]\(([^)]+)\)\s*$'
    
    # Pattern 2: Extended format - "1. [Title](URL). Authors. Journal. Year;Vol:Pages. doi:xxx"
    EXTENDED_REF_PATTERN = r'^(\d+)\.\s*\[([^\]]+)\]\(([^)]+)\)\.?\s*(.*)$'
    
    # Pattern 3: Text-only format - "1. Title. Authors. Journal. Year;Vol:Pages."
    TEXT_ONLY_REF_PATTERN = r'^(\d+)\.\s+([^[\]]+)$'

    def __init__(self, content: str):
        self.content = content
        self.lines = content.split('\n')
        self.reference_section_start: Optional[int] = None
        self.reference_section_end: Optional[int] = None
        self.body_content: str = ""
        self.references: List[ParsedReference] = []

    def find_reference_section(self) -> Tuple[Optional[int], Optional[int]]:
        """
        Find the start and end of the reference section.
        
        Uses the LAST reference header found to handle documents with
        multiple sections that might be titled "References".
        """
        logger.info("Searching for reference section...")

        # Find ALL reference headers, then use the last one
        ref_header_positions = []
        for i, line in enumerate(self.lines):
            for pattern in self.REFERENCE_HEADER_PATTERNS:
                if re.match(pattern, line.strip(), re.IGNORECASE):
                    ref_header_positions.append(i)
                    break

        if not ref_header_positions:
            logger.warning("No reference section found")
            return None, None
        
        # Use the last reference header (most likely the actual references)
        self.reference_section_start = ref_header_positions[-1]
        logger.info(f"Found reference section at line {self.reference_section_start + 1}")
        
        if len(ref_header_positions) > 1:
            logger.info(f"Note: Found {len(ref_header_positions)} 'References' headers, using last one")

        self.reference_section_end = len(self.lines)
        for i in range(self.reference_section_start + 1, len(self.lines)):
            line = self.lines[i].strip()
            if re.match(r'^#{1,2}\s+(?!References|Sources|Citations)', line, re.IGNORECASE):
                self.reference_section_end = i
                break

        return self.reference_section_start, self.reference_section_end

    def parse_references(self) -> List[ParsedReference]:
        """Parse all references from the reference section."""
        if self.reference_section_start is None:
            self.find_reference_section()

        if self.reference_section_start is None:
            return []

        self.body_content = '\n'.join(self.lines[:self.reference_section_start])
        logger.info(f"Parsing references from lines {self.reference_section_start + 1} to {self.reference_section_end}")

        for i in range(self.reference_section_start + 1, self.reference_section_end):
            line = self.lines[i].strip()
            if not line:
                continue

            parsed = self._parse_single_reference(line, i + 1)
            if parsed:
                self.references.append(parsed)

        logger.info(f"Parsed {len(self.references)} references")
        return self.references

    def _parse_single_reference(self, line: str, line_number: int) -> Optional[ParsedReference]:
        """Parse a single reference line supporting multiple formats."""
        
        # Try Pattern 1: Simple format "1. [Title - Source](URL)"
        match = re.match(self.SIMPLE_REF_PATTERN, line)
        if match:
            number = int(match.group(1))
            full_title = match.group(2)
            url = match.group(3)
            title, source = self._split_title_source(full_title)
            return ParsedReference(
                original_number=number,
                original_text=line,
                title=title,
                url=url,
                source_name=source,
                line_number=line_number,
            )
        
        # Try Pattern 2: Extended format "1. [Title](URL). Authors. Journal..."
        match = re.match(self.EXTENDED_REF_PATTERN, line)
        if match:
            number = int(match.group(1))
            title = match.group(2)
            url = match.group(3)
            extra_info = match.group(4).strip() if match.group(4) else ""
            
            # Extract source/journal from extra info if present
            source = None
            if extra_info:
                # Try to extract journal name (usually after authors, before year)
                # Format: "Authors. Journal Name. Year;Vol..."
                parts = extra_info.split('.')
                if len(parts) >= 2:
                    # Second part is often the journal
                    source = parts[1].strip() if parts[1].strip() else None
            
            return ParsedReference(
                original_number=number,
                original_text=line,
                title=title,
                url=url,
                source_name=source,
                line_number=line_number,
                metadata={'extra_info': extra_info} if extra_info else {},
            )

        # Try Pattern 3: Text-only numbered reference "1. Title. Authors..."
        if re.match(r'^\d+\.', line):
            number_match = re.match(r'^(\d+)\.\s*(.+)$', line)
            if number_match:
                number = int(number_match.group(1))
                content = number_match.group(2).strip()
                
                # Check if it has a URL hidden in brackets
                url_match = re.search(r'\(([^)]*https?://[^)]+)\)', content)
                url = url_match.group(1) if url_match else None
                
                # Extract title (first sentence or up to first period)
                title_parts = content.split('.')
                title = title_parts[0].strip() if title_parts else content
                
                return ParsedReference(
                    original_number=number,
                    original_text=line,
                    title=title,
                    url=url,
                    source_name=None,
                    line_number=line_number,
                    needs_review=url is None,  # Flag for review if no URL
                    review_reason="No URL found" if url is None else None,
                )
        
        return None

    def _split_title_source(self, full_title: str) -> Tuple[str, Optional[str]]:
        """Split 'Title - Source' string."""
        for sep in [' - ', ' | ', ' – ', ' — ']:
            if sep in full_title:
                parts = full_title.rsplit(sep, 1)
                if len(parts) == 2:
                    return parts[0].strip(), parts[1].strip()
        return full_title, None

    def get_body_content(self) -> str:
        """Get document body (before references)."""
        return self.body_content

    def get_number_to_label_mapping(self) -> dict:
        """Get mapping of original numbers to new labels."""
        return {ref.original_number: ref.new_label for ref in self.references if ref.processed and ref.new_label}

    def find_referenced_numbers(self) -> set:
        """Find all citation numbers actually used in the body text."""
        if not self.body_content:
            self.body_content = '\n'.join(self.lines[:self.reference_section_start or len(self.lines)])
        
        # Pattern matches [1], [2], [1, 2], [1-3], etc.
        pattern = r'\[(\d+(?:\s*[-,]\s*\d+)*)\]'
        matches = re.findall(pattern, self.body_content)
        
        referenced = set()
        for match in matches:
            # Handle ranges like "1-3" and lists like "1, 2"
            parts = re.split(r'[-,]', match)
            for part in parts:
                part = part.strip()
                if part.isdigit():
                    referenced.add(int(part))
        
        return referenced

    def filter_unreferenced(self) -> Tuple[List[ParsedReference], List[ParsedReference]]:
        """
        Separate references into used and unused.
        
        Returns:
            Tuple of (used_references, unused_references)
        """
        referenced_numbers = self.find_referenced_numbers()
        
        used = []
        unused = []
        
        for ref in self.references:
            if ref.original_number in referenced_numbers:
                used.append(ref)
            else:
                unused.append(ref)
                logger.info(f"Reference #{ref.original_number} not used in body text")
        
        if unused:
            logger.info(f"Found {len(unused)} unreferenced citations (will be skipped)")
        
        return used, unused

