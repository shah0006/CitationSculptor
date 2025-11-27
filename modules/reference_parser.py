"""Reference Parser Module - Parses reference sections from markdown documents."""

import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict
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
    section_index: int = 0  # Which reference section this belongs to
    citation_type: Optional[str] = None
    processed: bool = False
    new_label: Optional[str] = None
    formatted_citation: Optional[str] = None
    needs_review: bool = False
    review_reason: Optional[str] = None
    metadata: dict = field(default_factory=dict)


@dataclass
class DocumentSection:
    """Represents a section of the document with its own reference list."""
    section_index: int
    body_start: int  # Line number where body starts
    body_end: int    # Line number where body ends (before references)
    ref_start: int   # Line number where references header is
    ref_end: int     # Line number where references end
    body_content: str
    references: List[ParsedReference] = field(default_factory=list)
    inline_ref_style: str = "numeric"  # "numeric" [1] or "footnote" [^1]


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
    
    # Patterns for bullet-point references
    BULLET_REF_PATTERN = r'^[-*]\s+(?:[^:]+:\s*)?\[([^\]]+)\]\(([^)]+)\)\s*$'

    def __init__(self, content: str, multi_section: bool = False):
        self.content = content
        self.lines = content.split('\n')
        self.multi_section = multi_section
        self.reference_section_start: Optional[int] = None
        self.reference_section_end: Optional[int] = None
        self.body_content: str = ""
        self.references: List[ParsedReference] = []
        self.sections: List[DocumentSection] = []

    def find_all_reference_sections(self) -> List[Tuple[int, int]]:
        """
        Find ALL reference sections in the document.
        
        Returns list of (start_line, end_line) tuples for each reference section.
        """
        logger.info("Searching for all reference sections...")
        
        ref_header_positions = []
        for i, line in enumerate(self.lines):
            for pattern in self.REFERENCE_HEADER_PATTERNS:
                if re.match(pattern, line.strip(), re.IGNORECASE):
                    # Verify this is a real reference section (has numbered items after it)
                    has_refs = False
                    for j in range(i + 1, min(i + 20, len(self.lines))):
                        check_line = self.lines[j].strip()
                        if re.match(r'^\d+\.', check_line) or re.match(r'^[-*]\s+.*\[', check_line):
                            has_refs = True
                            break
                        if re.match(r'^#{1,2}\s+', check_line):
                            break  # Hit another header, no refs found
                    if has_refs:
                        ref_header_positions.append(i)
                    break
        
        if not ref_header_positions:
            logger.warning("No reference sections found")
            return []
        
        logger.info(f"Found {len(ref_header_positions)} reference section(s)")
        
        # Calculate end positions for each section
        sections = []
        for idx, start in enumerate(ref_header_positions):
            # End is either the next reference section or end of document
            if idx + 1 < len(ref_header_positions):
                end = ref_header_positions[idx + 1]
            else:
                end = len(self.lines)
            
            # But also check for other headers that might end the section
            for i in range(start + 1, end):
                line = self.lines[i].strip()
                # Stop at major headers that aren't reference-related
                if re.match(r'^#{1,2}\s+(?!References|Sources|Citations)', line, re.IGNORECASE):
                    # Check if this header starts another content section
                    end = i
                    break
            
            sections.append((start, end))
        
        return sections

    def find_reference_section(self) -> Tuple[Optional[int], Optional[int]]:
        """
        Find the start and end of the reference section.
        
        Uses the LAST reference header found to handle documents with
        multiple sections that might be titled "References".
        """
        logger.info("Searching for reference section...")

        all_sections = self.find_all_reference_sections()
        
        if not all_sections:
            logger.warning("No reference section found")
            return None, None
        
        # Use the last reference section by default
        self.reference_section_start, self.reference_section_end = all_sections[-1]
        logger.info(f"Found reference section at line {self.reference_section_start + 1}")
        
        if len(all_sections) > 1:
            logger.info(f"Note: Found {len(all_sections)} 'References' headers, using last one")

        return self.reference_section_start, self.reference_section_end
    
    def parse_multi_section(self) -> List[DocumentSection]:
        """
        Parse document with multiple reference sections.
        
        Each section is processed independently with its own body content
        and reference list.
        """
        all_ref_sections = self.find_all_reference_sections()
        
        if not all_ref_sections:
            logger.warning("No reference sections found for multi-section parsing")
            return []
        
        logger.info(f"Parsing {len(all_ref_sections)} document section(s)...")
        
        for idx, (ref_start, ref_end) in enumerate(all_ref_sections):
            # Determine body start (end of previous section or start of document)
            if idx == 0:
                body_start = 0
            else:
                body_start = all_ref_sections[idx - 1][1]
            
            body_end = ref_start
            body_content = '\n'.join(self.lines[body_start:body_end])
            
            # Detect inline reference style
            inline_style = self._detect_inline_style(body_content)
            
            section = DocumentSection(
                section_index=idx,
                body_start=body_start,
                body_end=body_end,
                ref_start=ref_start,
                ref_end=ref_end,
                body_content=body_content,
                inline_ref_style=inline_style,
            )
            
            # Parse references for this section
            section.references = self._parse_section_references(ref_start, ref_end, idx)
            
            self.sections.append(section)
            logger.info(f"Section {idx + 1}: {len(section.references)} references, style={inline_style}")
        
        # Aggregate all references for compatibility
        for section in self.sections:
            self.references.extend(section.references)
        
        return self.sections
    
    def _detect_inline_style(self, body_content: str) -> str:
        """Detect whether body uses [N] or [^N] style references."""
        footnote_count = len(re.findall(r'\[\^(\d+)\]', body_content))
        numeric_count = len(re.findall(r'\[(\d+)\]', body_content))
        
        if footnote_count > numeric_count:
            return "footnote"
        return "numeric"
    
    def _parse_section_references(self, start: int, end: int, section_idx: int) -> List[ParsedReference]:
        """Parse references from a specific section."""
        refs = []
        
        for i in range(start + 1, end):
            line = self.lines[i].strip()
            if not line:
                continue
            
            parsed = self._parse_single_reference(line, i + 1)
            if parsed:
                parsed.section_index = section_idx
                refs.append(parsed)
        
        return refs

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
                
                # Clean up title if it contains author separators like dashes
                for sep in [' - ', ' – ', ' — ', ' | ']:
                    if sep in title:
                        title = title.split(sep)[0].strip()
                        break
                
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

    def find_referenced_numbers(self, body_content: Optional[str] = None, style: str = "auto") -> set:
        """
        Find all citation numbers actually used in the body text.
        
        Args:
            body_content: Optional body text to search (uses self.body_content if not provided)
            style: "numeric" for [N], "footnote" for [^N], "auto" to detect both
        """
        if body_content is None:
            if not self.body_content:
                self.body_content = '\n'.join(self.lines[:self.reference_section_start or len(self.lines)])
            body_content = self.body_content
        
        referenced = set()
        
        # Numeric style: [1], [2], [1, 2], [1-3], etc.
        if style in ("numeric", "auto"):
            pattern = r'\[(\d+(?:\s*[-,]\s*\d+)*)\]'
            matches = re.findall(pattern, body_content)
            for match in matches:
                parts = re.split(r'[-,]', match)
                for part in parts:
                    part = part.strip()
                    if part.isdigit():
                        referenced.add(int(part))
        
        # Footnote style: [^1], [^2], etc.
        if style in ("footnote", "auto"):
            pattern = r'\[\^(\d+)\]'
            matches = re.findall(pattern, body_content)
            for match in matches:
                referenced.add(int(match))
        
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
    
    def filter_unreferenced_by_section(self) -> Dict[int, Tuple[List[ParsedReference], List[ParsedReference]]]:
        """
        Separate references into used and unused, by section.
        
        Returns:
            Dict mapping section_index -> (used_references, unused_references)
        """
        results = {}
        
        for section in self.sections:
            referenced_numbers = self.find_referenced_numbers(
                body_content=section.body_content,
                style=section.inline_ref_style
            )
            
            used = []
            unused = []
            
            for ref in section.references:
                if ref.original_number in referenced_numbers:
                    used.append(ref)
                else:
                    unused.append(ref)
                    logger.debug(f"Section {section.section_index + 1}: Reference #{ref.original_number} not used")
            
            if unused:
                logger.info(f"Section {section.section_index + 1}: Found {len(unused)} unreferenced citations")
            
            results[section.section_index] = (used, unused)
        
        return results

