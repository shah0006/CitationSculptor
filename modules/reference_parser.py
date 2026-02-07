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
        r'^#{1,4}\s*References\s*$',  # Include #### level
        r'^#{1,4}\s*Sources\s*$',
        r'^#{1,4}\s*Citations\s*$',
        r'^#{1,4}\s*Works\s+[Cc]ited\s*$',  # "Works cited" or "Works Cited"
        r'^#{1,4}\s*Bibliography\s*$',
        r'^\*\*Sources:\*\*\s*$',  # Bold **Sources:** header (V6 format)
        r'^\*\*References:\*\*\s*$',
        r'^\*\*Works\s+[Cc]ited:\*\*\s*$',
    ]
    
    # Pattern V8: Works cited format - "1. Title, accessed date, <URL>"
    WORKS_CITED_PATTERN = r'^(\d+)\.\s*(.+?),\s*accessed\s+.+?,\s*<(https?://[^>]+)>$'
    
    # Pattern V7: Numbered list with embedded link - "1. [Title](URL). Authors. Journal..."
    # This is a more detailed pattern that extracts all components
    NUMBERED_LINK_REF_PATTERN = r'^(\d+)\.\s*\[([^\]]+)\]\(([^)]+)\)\.?\s*(.*)$'
    
    # Pattern 1: Simple format - "1. [Title - Source](URL)"
    SIMPLE_REF_PATTERN = r'^(\d+)\.\s*\[([^\]]+)\]\(([^)]+)\)\s*$'
    
    # Pattern 2: Extended format - "1. [Title](URL). Authors. Journal. Year;Vol:Pages. doi:xxx"
    EXTENDED_REF_PATTERN = r'^(\d+)\.\s*\[([^\]]+)\]\(([^)]+)\)\.?\s*(.*)$'
    
    # Pattern 3: Text-only format - "1. Title. Authors. Journal. Year;Vol:Pages."
    TEXT_ONLY_REF_PATTERN = r'^(\d+)\.\s+([^[\]]+)$'
    
    # Pattern 4: Footnote definition - "[^1]: Citation text..."
    FOOTNOTE_DEF_PATTERN = r'^\[\^(\d+)\]:\s*(.+)$'
    
    # Pattern 5: Grouped footnotes without colon - "[^1] [^2] [^3] Title text"
    # This captures ALL [^N] groups and the remaining title
    FOOTNOTE_NO_COLON_PATTERN = r'^(\[\^\d+\](?:\s*\[\^\d+\])*)\s+(.+)$'
    
    # Pattern for angle-bracket URL on separate line - "<https://...>"
    ANGLE_BRACKET_URL_PATTERN = r'^<(https?://[^>]+)>$'
    
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
        
        Also detects V7 numbered list format:
            1. [Title](URL). Authors. Journal. Year. doi:XXX.
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
                        # Check for V7 numbered refs with embedded links
                        if re.match(self.NUMBERED_LINK_REF_PATTERN, check_line):
                            has_refs = True
                            break
                        # Other reference formats
                        if re.match(r'^\d+\.', check_line) or \
                           re.match(r'^[-*]\s+.*\[', check_line) or \
                           re.match(r'^\[\^(\d+)\]:', check_line) or \
                           re.match(self.FOOTNOTE_NO_COLON_PATTERN, check_line):  # V6 format
                            has_refs = True
                            break
                        if re.match(r'^#{1,3}\s+', check_line):
                            break  # Hit another header, no refs found
                    if has_refs:
                        ref_header_positions.append(i)
                    break
        
        if not ref_header_positions:
            # Fallback: Look for implicit footnote section (lines starting with [^1]: or [^1] without colon)
            logger.info("No reference headers found. Looking for implicit footnote section...")
            implicit_start = -1
            for i, line in enumerate(self.lines):
                stripped = line.strip()
                # Check for [^N]: format (with colon)
                if re.match(r'^\[\^(\d+)\]:', stripped):
                    implicit_start = i
                    break
                # Check for [^N] format without colon (V6 format)
                # Must have [^N] followed by space and text (not just [^N] alone)
                if re.match(self.FOOTNOTE_NO_COLON_PATTERN, stripped):
                    implicit_start = i
                    break
            
            if implicit_start != -1:
                logger.info(f"Found implicit reference section starting at line {implicit_start + 1}")
                # Return range. Start is implicit_start - 1 so that the loop 
                # (start + 1 to end) begins at implicit_start.
                return [(implicit_start - 1, len(self.lines))]

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
        
        Handles documents where body text continues AFTER the reference definitions
        (e.g., footnotes defined mid-document).
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
            
            # Body content BEFORE references
            body_before = '\n'.join(self.lines[body_start:ref_start])
            
            # Check for body content AFTER references (but before next section or EOF)
            # This handles documents where footnotes are defined mid-document
            if idx + 1 < len(all_ref_sections):
                next_section_start = all_ref_sections[idx + 1][0]
            else:
                next_section_start = len(self.lines)
            
            body_after = '\n'.join(self.lines[ref_end:next_section_start])
            
            # Combine body content (before + after references)
            # Use a marker so we can reconstruct the document later
            if body_after.strip():
                body_content = body_before + '\n<!-- REF_SECTION_MARKER -->\n' + body_after
                body_end_effective = next_section_start
                logger.info(f"Section {idx + 1}: Found body content after references (lines {ref_end + 1}-{next_section_start})")
            else:
                body_content = body_before
                body_end_effective = ref_start
            
            # Detect inline reference style from combined body
            inline_style = self._detect_inline_style(body_content)
            
            section = DocumentSection(
                section_index=idx,
                body_start=body_start,
                body_end=body_end_effective,
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
    
    def _is_already_formatted_footnote(self, line: str) -> bool:
        """
        Check if a footnote definition is already in Vancouver format.
        
        Already formatted: [^AuthorY-2020-12345678]: Author Name. Title...
        Not formatted: [^1]: Some text...
        """
        # Check for [^Author-Year-PMID] pattern (already processed)
        if re.match(r'^\[\^[A-Za-z]+-\d{4}-\d+\]:', line):
            return True
        # Check for [^Author-Title-Year] pattern
        if re.match(r'^\[\^[A-Za-z]+-[A-Za-z]+-\d{4}\]:', line):
            return True
        # Check for [^Org-Title-Year] pattern  
        if re.match(r'^\[\^[A-Z]+-[A-Za-z]+-\d{4}\]:', line):
            return True
        return False
    
    def find_numbered_list_references(self) -> List[ParsedReference]:
        """
        Find and parse V7 format numbered list references.
        
        Format: "1. [Title](URL). Authors et al. Journal. Year. doi:XXX."
        
        These correspond to inline [^N] references that don't have 
        footnote definitions but match numbered list items.
        """
        refs = []
        in_numbered_section = False
        
        for i, line in enumerate(self.lines):
            stripped = line.strip()
            
            # Check for a References header (could start numbered section)
            if re.match(r'^#{1,3}\s*(References|Sources)\s*$', stripped, re.IGNORECASE):
                in_numbered_section = True
                continue
            
            # Skip already-formatted footnotes
            if self._is_already_formatted_footnote(stripped):
                continue
            
            # Parse V7 numbered format
            if in_numbered_section:
                match = re.match(self.NUMBERED_LINK_REF_PATTERN, stripped)
                if match:
                    parsed = self._parse_single_reference(stripped, i + 1)
                    if parsed:
                        refs.append(parsed)
                elif stripped and not stripped.startswith('#'):
                    # Still in section, but line doesn't match pattern
                    pass
                elif stripped.startswith('#'):
                    # Hit another header, end of section
                    in_numbered_section = False
        
        if refs:
            logger.info(f"Found {len(refs)} V7 numbered list references")
        
        return refs
    
    def find_undefined_references(self, body_content: str, defined_numbers: set, style: str = "footnote") -> set:
        """
        Find reference numbers used in body but not defined in reference list.
        
        Args:
            body_content: The body text to scan
            defined_numbers: Set of reference numbers that have definitions
            style: "footnote" for [^N] or "numeric" for [N]
            
        Returns:
            Set of undefined reference numbers
        """
        if style == "footnote":
            used_numbers = set(int(m) for m in re.findall(r'\[\^(\d+)\]', body_content))
        else:
            used_numbers = set(int(m) for m in re.findall(r'\[(\d+)\]', body_content))
        
        undefined = used_numbers - defined_numbers
        
        if undefined:
            logger.warning(f"Found {len(undefined)} undefined references: {sorted(undefined)}")
        
        return undefined
    
    def _parse_section_references(self, start: int, end: int, section_idx: int) -> List[ParsedReference]:
        """Parse references from a specific section.
        
        Handles multiple formats:
        - V6: [^1] [^2] [^3] Title text here <URL>
        - V7: 1. [Title](URL). Authors. Journal. Year. doi:XXX.
        - Standard footnotes: [^1]: Citation text...
        
        Skips already-formatted Vancouver citations.
        """
        refs = []
        i = start + 1
        
        while i < end:
            line = self.lines[i].strip()
            if not line:
                i += 1
                continue
            
            # Skip already-formatted footnotes (don't reprocess them)
            if self._is_already_formatted_footnote(line):
                logger.debug(f"Skipping already-formatted footnote: {line[:50]}...")
                i += 1
                continue
            
            # Check for V7 format: numbered list with embedded link
            v7_match = re.match(self.NUMBERED_LINK_REF_PATTERN, line)
            if v7_match:
                parsed = self._parse_single_reference(line, i + 1)
                if parsed:
                    parsed.section_index = section_idx
                    refs.append(parsed)
                    logger.debug(f"V7 format: #{parsed.original_number} -> '{parsed.title[:40]}...'")
                i += 1
                continue
            
            # Check for V6 format: grouped footnotes without colon
            v6_match = re.match(self.FOOTNOTE_NO_COLON_PATTERN, line)
            if v6_match:
                # Extract all [^N] numbers from the grouped line
                footnote_ids_str = v6_match.group(1)  # e.g., "[^1] [^47] [^49]"
                title = v6_match.group(2).strip()  # e.g., "How Much More..."
                
                # Parse individual numbers from the grouped footnotes
                numbers = [int(m) for m in re.findall(r'\[\^(\d+)\]', footnote_ids_str)]
                
                # Look ahead for URL on next non-empty line (may be angle-bracket format)
                url = None
                j = i + 1
                while j < end:
                    next_line = self.lines[j].strip()
                    if not next_line:
                        j += 1
                        continue
                    # Check for angle-bracket URL: <https://...>
                    url_match = re.match(self.ANGLE_BRACKET_URL_PATTERN, next_line)
                    if url_match:
                        url = url_match.group(1)
                        i = j  # Skip past the URL line
                    break
                
                # Extract source name from title if present (e.g., "Title | Source")
                title_clean, source_name = self._split_title_source(title)
                
                # Create a ParsedReference for EACH footnote number
                # They all share the same title/URL/source but have different numbers
                for num in numbers:
                    refs.append(ParsedReference(
                        original_number=num,
                        original_text=line,
                        title=title_clean,
                        url=url,
                        source_name=source_name,
                        line_number=i + 1,
                        section_index=section_idx,
                        metadata={'grouped_numbers': numbers, 'raw_title': title}
                    ))
                
                if numbers:
                    logger.debug(f"V6 format: {len(numbers)} refs ({numbers}) -> '{title_clean[:40]}...'")
                
                i += 1
                continue
            
            # Try other patterns via _parse_single_reference
            parsed = self._parse_single_reference(line, i + 1)
            if parsed:
                parsed.section_index = section_idx
                refs.append(parsed)
            
            i += 1
        
        return refs

    def parse_references(self) -> List[ParsedReference]:
        """Parse all references from the reference section."""
        if self.reference_section_start is None:
            self.find_reference_section()

        if self.reference_section_start is None:
            return []

        self.body_content = '\n'.join(self.lines[:self.reference_section_start])
        logger.info(f"Parsing references from lines {self.reference_section_start + 1} to {self.reference_section_end}")

        # Use the enhanced section parser which handles V6 multi-line format
        self.references = self._parse_section_references(
            self.reference_section_start, 
            self.reference_section_end, 
            section_idx=0
        )

        logger.info(f"Parsed {len(self.references)} references")
        return self.references

    def _parse_single_reference(self, line: str, line_number: int) -> Optional[ParsedReference]:
        """Parse a single reference line supporting multiple formats."""
        
        # Try V8 Works Cited format: "1. Title, accessed date, <URL>"
        match = re.match(self.WORKS_CITED_PATTERN, line)
        if match:
            number = int(match.group(1))
            title = match.group(2).strip()
            url = match.group(3)
            
            # Clean up title - remove trailing comma if present
            title = title.rstrip(',').strip()
            
            logger.debug(f"Parsed Works Cited format #{number}: {title[:50]}...")
            return ParsedReference(
                original_number=number,
                original_text=line,
                title=title,
                url=url,
                source_name=None,
                line_number=line_number,
                metadata={'format': 'works_cited'},
            )
        
        # Try Pattern 1: Simple format "1. [Title - Source](URL)"
        match = re.match(self.SIMPLE_REF_PATTERN, line)
        if match:
            number = int(match.group(1))
            full_title = match.group(2)
            url = self._clean_url(match.group(3))
            title, source = self._split_title_source(full_title)
            return ParsedReference(
                original_number=number,
                original_text=line,
                title=title,
                url=url,
                source_name=source,
                line_number=line_number,
            )
        
        # Try Pattern 2/V7: Extended format "1. [Title](URL). Authors. Journal..."
        # V7 format: "1. [Title](URL). Authors et al. Journal. Year;Vol:Pages. doi:XXX."
        match = re.match(self.EXTENDED_REF_PATTERN, line)
        if match:
            number = int(match.group(1))
            title = match.group(2)
            url = self._clean_url(match.group(3))
            extra_info = match.group(4).strip() if match.group(4) else ""
            
            # Parse V7 format metadata from extra_info
            metadata = {'extra_info': extra_info, 'format': 'v7_numbered'}
            source = None
            authors = None
            year = None
            doi = None
            
            if extra_info:
                # Extract DOI if present - DOIs can contain dots (e.g., 10.3389/fcvm.2018.00062)
                # Exclude ? from DOI capture to avoid query parameters
                doi_match = re.search(r'doi[:\s]*(10\.\d{4,}/[^\s\)\]<>\?]+)', extra_info, re.IGNORECASE)
                if doi_match:
                    doi = doi_match.group(1).rstrip('.,;')
                    metadata['doi'] = doi
                
                # Extract year (4-digit number)
                year_match = re.search(r'\b(19|20)\d{2}\b', extra_info)
                if year_match:
                    year = year_match.group(0)
                    metadata['year'] = year
                
                # Parse "Authors et al. Journal. Year;Vol:Pages."
                # Split by periods but be careful with "et al."
                # Replace "et al." temporarily to avoid splitting
                temp_info = extra_info.replace('et al.', 'ET_AL_MARKER')
                parts = [p.strip() for p in temp_info.split('.') if p.strip()]
                parts = [p.replace('ET_AL_MARKER', 'et al.') for p in parts]
                
                if len(parts) >= 1:
                    # First part is usually authors
                    authors = parts[0]
                    metadata['authors'] = authors
                    
                if len(parts) >= 2:
                    # Second part is often the journal (might include year/vol)
                    journal_part = parts[1]
                    # Extract just journal name (before year or volume info)
                    journal_match = re.match(r'^([A-Za-z][A-Za-z\s&]+)', journal_part)
                    if journal_match:
                        source = journal_match.group(1).strip()
                    else:
                        source = journal_part.split(';')[0].strip()
            
            return ParsedReference(
                original_number=number,
                original_text=line,
                title=title,
                url=url,
                source_name=source,
                line_number=line_number,
                metadata=metadata,
            )

        # Try Pattern 4: Footnote definition "[^1]: ..."
        match = re.match(self.FOOTNOTE_DEF_PATTERN, line)
        if match:
            number = int(match.group(1))
            content = match.group(2).strip()
            
            # Initialize metadata
            metadata = {'raw_content': content}
            
            # Try to extract URL/DOI from content
            url = None
            # Check for markdown link [DOI](url) or just link
            md_link_match = re.search(r'\[([^\]]*)\]\(([^)]+)\)', content)
            if md_link_match:
                url = self._clean_url(md_link_match.group(2))
            else:
                # Raw URL
                url_match = re.search(r'https?://[^\s\)]+', content)
                if url_match:
                    url = self._clean_url(url_match.group(0))
            
            # ALWAYS try to extract DOI and PMID from text and store in metadata
            # DOI extraction
            doi = self._extract_doi_from_text(content)
            if doi:
                metadata['doi'] = doi
                logger.debug(f"Extracted DOI from footnote text: {doi}")
                # If no URL, construct one from DOI
                if not url:
                    url = f"https://doi.org/{doi}"

            # PMID extraction
            pmid = self._extract_pmid_from_text(content)
            if pmid:
                metadata['pmid'] = pmid
                logger.debug(f"Extracted PMID from footnote text: {pmid}")
                # If no URL, construct one from PMID
                if not url:
                    url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}"

            # Extract title using multi-strategy approach
            title = self._extract_title_from_citation(content)

            return ParsedReference(
                original_number=number,
                original_text=line,
                title=title,
                url=url,
                source_name=None,
                line_number=line_number,
                metadata=metadata,
            )

        # Try Pattern 3: Text-only numbered reference "1. Title. Authors..."
        if re.match(r'^\d+\.', line):
            number_match = re.match(r'^(\d+)\.\s*(.+)$', line)
            if number_match:
                number = int(number_match.group(1))
                content = number_match.group(2).strip()
                
                # Check if it has a URL - try multiple patterns:
                # 1. Markdown link with closing paren: [text](url)
                # 2. Markdown link without closing paren: [text](url  (malformed)
                # 3. URL in parentheses: (url)
                # 4. Raw URL: https://...
                url = None
                # Try markdown link first (handles both complete and incomplete)
                md_link_match = re.search(r'\]\((https?://[^\s\)]+)', content)
                if md_link_match:
                    url = self._clean_url(md_link_match.group(1))
                else:
                    # Try URL in parentheses
                    url_match = re.search(r'\((https?://[^\s\)]+)\)', content)
                    if url_match:
                        url = self._clean_url(url_match.group(1))
                    else:
                        # Try raw URL
                        raw_url_match = re.search(r'https?://[^\s]+', content)
                        if raw_url_match:
                            url = self._clean_url(raw_url_match.group(0))
                
                # ALWAYS try to extract DOI and PMID from text and store in metadata
                # This helps even when URL is present but doesn't contain the identifiers
                metadata = {}

                # DOI extraction
                doi = self._extract_doi_from_text(content)
                if doi:
                    metadata['doi'] = doi
                    logger.debug(f"Extracted DOI from text: {doi}")
                    # If no URL, construct one from DOI
                    if not url:
                        url = f"https://doi.org/{doi}"

                # PMID extraction
                pmid = self._extract_pmid_from_text(content)
                if pmid:
                    metadata['pmid'] = pmid
                    logger.debug(f"Extracted PMID from text: {pmid}")
                    # If no URL, construct one from PMID
                    if not url:
                        url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}"

                # Extract title using multi-strategy approach
                title = self._extract_title_from_citation(content)
                
                return ParsedReference(
                    original_number=number,
                    original_text=line,
                    title=title,
                    url=url,
                    source_name=None,
                    line_number=line_number,
                    needs_review=url is None,  # Flag for review if no URL
                    review_reason="No URL found" if url is None else None,
                    metadata=metadata,
                )
        
        return None
    
    def _extract_pmid_from_text(self, text: str) -> Optional[str]:
        """
        Extract PMID from citation text if present.

        Handles multiple formats:
        - PMID: 12345678
        - PMID 12345678
        - pubmed.ncbi.nlm.nih.gov/12345678
        - ncbi.nlm.nih.gov/pubmed/12345678

        Returns:
            PMID string (8 digits) or None if not found
        """
        # Pattern 1: Explicit PMID label
        match = re.search(r'PMID:?\s*(\d{8})', text, re.IGNORECASE)
        if match:
            return match.group(1)

        # Pattern 2: PubMed URL
        match = re.search(r'pubmed\.ncbi\.nlm\.nih\.gov/(\d{8})', text, re.IGNORECASE)
        if match:
            return match.group(1)

        match = re.search(r'ncbi\.nlm\.nih\.gov/pubmed/(\d{8})', text, re.IGNORECASE)
        if match:
            return match.group(1)

        return None

    def _extract_doi_from_text(self, text: str) -> Optional[str]:
        """
        Extract DOI from citation text if present.

        Handles multiple formats:
        - DOI: 10.1234/abc
        - DOI 10.1234/abc
        - doi.org/10.1234/abc
        - https://doi.org/10.1234/abc
        - DOI: 10.1016/S0140-6736(18)31133-4  (with parentheses)

        Returns:
            DOI string or None if not found
        """
        # Pattern 1: Explicit DOI label
        # DOIs can contain parentheses, so we need to be careful with the pattern
        # Match until whitespace, closing bracket ], or angle bracket <
        # But allow parentheses within the DOI
        match = re.search(r'doi[:\s]+\s*(10\.\d{4,}/[^\s\]<>]+)', text, re.IGNORECASE)
        if match:
            # Clean trailing punctuation, but preserve internal parentheses
            doi = match.group(1).rstrip('.,;?')
            # Remove trailing closing paren only if it's at the very end and not part of DOI structure
            # DOIs with parens are like 10.1016/S0140-6736(18)31133-4
            # We want to keep the complete DOI
            return doi

        # Pattern 2: DOI URL
        match = re.search(r'doi\.org/(10\.\d{4,}/[^\s\]<>]+)', text, re.IGNORECASE)
        if match:
            doi = match.group(1).rstrip('.,;?')
            return doi

        return None

    def _extract_title_from_citation(self, content: str) -> str:
        """
        Extract article title from citation text using multiple strategies.

        Handles multiple citation formats:
        1. Vancouver (period-delimited): Authors. Title. Journal. Year;Vol(Issue):Pages.
        2. Dash-delimited: Authors Year - Title - Journal - Metadata
        3. Parenthetical year: Authors (Year). Title. Journal, Vol(Issue), Pages.

        Returns the best candidate title, validated to not be a year string,
        volume number, or other non-title fragment.
        """
        # NEW: Detect dash-delimited format first
        # Pattern: "Authors Year - Title - Journal - ..."
        # Indicators: multiple " - " delimiters and few/no periods
        dash_count = content.count(' - ')
        period_count = content.count('.')

        if dash_count >= 2 and period_count < 3:
            # Likely dash-delimited format
            logger.debug(f"Detected dash-delimited format ({dash_count} dashes, {period_count} periods)")
            parts = content.split(' - ')

            if len(parts) >= 3:
                # Check if first segment looks like authors + year
                first = parts[0].strip()
                has_initials = bool(re.findall(r'\b[A-Z]{1,3}\b', first))
                has_commas = first.count(',') >= 1
                has_year = bool(re.search(r'\b(19|20)\d{2}\b', first))

                if has_initials and has_commas and has_year:
                    # Authors + year in first segment, title is second segment
                    title_candidate = parts[1].strip()
                    # Remove markdown italic markers (*Title*)
                    title_candidate = re.sub(r'^\*+|\*+$', '', title_candidate).strip()

                    if self._is_valid_title(title_candidate):
                        logger.debug(f"Extracted title from dash format: {title_candidate[:60]}...")
                        return title_candidate

        # Strip any year in parentheses from the start (common LLM format)
        # e.g., "Xu S, et al. (2021). Title..." → work with text after "(2021)."
        content_stripped = re.sub(r'\(\d{4}\)\.\s*', '', content, count=1)

        # Strategy 1: Look for Vancouver author pattern at start
        # Pattern: "LastName Initials, LastName Initials, et al."
        # Matches: "Xu S, Ilyas I, Little PJ, et al."
        author_pattern = r'^((?:[A-Z][a-zÀ-ÿ\-\']+\s+[A-Z]{1,3},?\s*)+(?:et\s+al\.?)?\s*)'

        # Try with year stripped first, then original
        for text in [content_stripped, content]:
            parts = text.split('.')
            if len(parts) >= 3:
                # Check if first segment looks like an author list (has commas + short uppercase tokens)
                first = parts[0].strip()
                # Author indicators: multiple commas, short uppercase tokens (initials)
                has_initials = bool(re.findall(r'\b[A-Z]{1,3}\b', first))
                has_commas = first.count(',') >= 1

                if has_initials and has_commas:
                    # Authors are first segment. Title is the next meaningful segment.
                    # Skip segments that are just year strings like "(2021)"
                    for i in range(1, len(parts)):
                        candidate = parts[i].strip()
                        # Skip parenthetical years and empty segments
                        candidate_clean = re.sub(r'^\(\d{4}\)\s*', '', candidate).strip()
                        if candidate_clean and self._is_valid_title(candidate_clean):
                            return candidate_clean

        # Strategy 2: Find the longest meaningful segment between periods
        parts = content.split('.')
        candidates = []
        for part in parts:
            part = part.strip()
            # Remove leading parenthetical years
            part = re.sub(r'^\(\d{4}\)\s*', '', part).strip()
            if self._is_valid_title(part) and len(part) > 15:
                candidates.append(part)

        if candidates:
            # Return the longest candidate (article titles are typically the longest segment)
            return max(candidates, key=len)

        # Strategy 3: Return everything before first year;volume pattern
        year_vol_match = re.search(r'\b(19|20)\d{2}\s*[;:]', content)
        if year_vol_match:
            before = content[:year_vol_match.start()].rstrip('. ')
            if before and self._is_valid_title(before):
                return before

        # Fallback: return full content (cross-verify will catch bad matches)
        logger.warning(f"Title extraction fallback: using full content for: {content[:60]}...")
        return content

    def _is_valid_title(self, text: str) -> bool:
        """
        Check if extracted text is a plausible article title.

        Rejects:
        - Pure year strings like "(2021)" or "2021"
        - Journal abbreviation fragments
        - Volume/issue patterns like "26(15)"
        - Very short strings
        """
        if not text or len(text) < 5:
            return False
        # Reject pure year strings (with or without parens)
        if re.match(r'^\(?\d{4}\)?$', text.strip()):
            return False
        # Reject volume/issue patterns
        if re.match(r'^\d+\s*\(\d+', text.strip()):
            return False
        # Reject page range patterns
        if re.match(r'^\d+[\-–]\d+$', text.strip()):
            return False
        # Reject very short text with many periods (journal abbreviations)
        if len(text) < 15 and text.count('.') > 1:
            return False
        # Must contain at least 2 alphabetic words with 3+ characters
        alpha_words = [w for w in text.split() if re.match(r'^[a-zA-ZÀ-ÿ]{3,}', w)]
        return len(alpha_words) >= 2

    def _clean_url(self, url: str) -> str:
        """
        Clean extracted URLs that may have malformed markdown syntax.
        
        Handles cases like:
        - [https://url](https://url)  -> https://url
        - [URL](https://url)          -> https://url  
        - https://url                 -> https://url (unchanged)
        """
        if not url:
            return url
        
        # Strip whitespace
        url = url.strip()
        
        # If URL starts with '[', it's likely a nested markdown link like [url](url)
        if url.startswith('['):
            # Try to extract URL from markdown link format
            # Pattern: [text](actual_url) -> actual_url
            md_link_match = re.search(r'\]\((https?://[^)]+)', url)
            if md_link_match:
                url = md_link_match.group(1)
            else:
                # Just strip the leading bracket and extract URL
                url_match = re.search(r'https?://[^\]\)\s]+', url)
                if url_match:
                    url = url_match.group(0)
        
        # Clean trailing characters
        url = url.rstrip('.,;)]')
        
        return url

    def _split_title_source(self, full_title: str) -> Tuple[str, Optional[str]]:
        """Split 'Title - Source' string.
        
        Priority: ' | ' (or escaped ' \\| ') is the preferred separator since it's less ambiguous.
        Dashes may appear within titles (e.g., "Challenges & Threats - 2025").
        """
        # Check for pipe separators first (both escaped and unescaped)
        for pipe_sep in [' \\| ', ' | ']:
            if pipe_sep in full_title:
                parts = full_title.rsplit(pipe_sep, 1)
                if len(parts) == 2:
                    return parts[0].strip(), parts[1].strip()
        
        # Then check other dash variants (prefer rightmost)
        for sep in [' – ', ' — ', ' - ']:
            if sep in full_title:
                parts = full_title.rsplit(sep, 1)
                if len(parts) == 2:
                    # Only split if the right part looks like a source name
                    # (not a year or continuation of title)
                    right_part = parts[1].strip()
                    # If it's just a year, don't split here
                    if re.match(r'^\d{4}$', right_part):
                        continue
                    return parts[0].strip(), right_part
        
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

