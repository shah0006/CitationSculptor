"""Auto-Bibliography Generator Module.

Generates formatted bibliographies from:
- Document text (extracting citations)
- Citation database
- Lists of identifiers
"""

import re
from dataclasses import dataclass
from typing import Optional, List, Dict, Any, Tuple, Set
from pathlib import Path
from loguru import logger


@dataclass
class ExtractedReference:
    """A reference extracted from document text."""
    inline_mark: str
    position: int
    line_number: int
    context: str  # Surrounding text


@dataclass
class Bibliography:
    """A generated bibliography."""
    entries: List[str]  # Formatted citation strings
    format_style: str
    sort_order: str  # 'alphabetical', 'appearance', 'year'
    header: str
    footer: str


class BibliographyGenerator:
    """
    Generates bibliographies from documents or citation lists.
    """
    
    # Patterns for inline citations
    CITATION_PATTERNS = [
        # Footnote style: [^AuthorY-2024-12345678]
        re.compile(r'\[\^([^\]]+)\]'),
        # Numeric: [1], [1,2,3], [1-5]
        re.compile(r'\[(\d+(?:[-,]\d+)*)\]'),
        # Author-year: (Smith, 2024), (Smith et al., 2024)
        re.compile(r'\(([A-Z][a-z]+(?:\s+et\s+al\.?)?,?\s*\d{4}[a-z]?)\)'),
        # Superscript numbers (in some markdown): ^1^, ^1,2^
        re.compile(r'\^(\d+(?:,\d+)*)\^'),
    ]
    
    def __init__(self):
        self.citation_lookup = None  # Will be set if available
    
    def extract_citations(self, text: str) -> List[ExtractedReference]:
        """
        Extract all citation references from document text.
        
        Args:
            text: Document text
        
        Returns:
            List of ExtractedReference objects
        """
        references = []
        lines = text.split('\n')
        
        for line_num, line in enumerate(lines, 1):
            for pattern in self.CITATION_PATTERNS:
                for match in pattern.finditer(line):
                    # Get context (surrounding text)
                    start = max(0, match.start() - 30)
                    end = min(len(line), match.end() + 30)
                    context = line[start:end]
                    
                    references.append(ExtractedReference(
                        inline_mark=match.group(0),
                        position=match.start(),
                        line_number=line_num,
                        context=context
                    ))
        
        return references
    
    def extract_unique_citations(self, text: str) -> List[str]:
        """
        Extract unique citation marks from text.
        
        Returns:
            List of unique citation marks in order of first appearance
        """
        refs = self.extract_citations(text)
        seen = set()
        unique = []
        
        for ref in refs:
            if ref.inline_mark not in seen:
                seen.add(ref.inline_mark)
                unique.append(ref.inline_mark)
        
        return unique
    
    def generate_from_document(
        self, 
        document_path: str,
        style: str = "vancouver",
        sort: str = "appearance"
    ) -> Bibliography:
        """
        Generate bibliography from a document file.
        
        Args:
            document_path: Path to document (markdown, txt)
            style: Citation style
            sort: Sort order ('appearance', 'alphabetical', 'year')
        
        Returns:
            Bibliography object
        """
        path = Path(document_path)
        if not path.exists():
            raise FileNotFoundError(f"Document not found: {document_path}")
        
        text = path.read_text(encoding='utf-8')
        return self.generate_from_text(text, style, sort)
    
    def generate_from_text(
        self, 
        text: str,
        style: str = "vancouver",
        sort: str = "appearance"
    ) -> Bibliography:
        """
        Generate bibliography from document text.
        
        Args:
            text: Document text
            style: Citation style
            sort: Sort order
        
        Returns:
            Bibliography object
        """
        # Extract citations
        unique_marks = self.extract_unique_citations(text)
        
        # Check if there's an existing references section
        existing_refs = self._extract_existing_references(text)
        
        # Build bibliography entries
        entries = []
        for mark in unique_marks:
            # Check if we have an existing definition
            if mark in existing_refs:
                entries.append(existing_refs[mark])
            else:
                # Mark as needing lookup
                entries.append(f"{mark}: [Citation needed - lookup required]")
        
        # Sort entries
        if sort == "alphabetical":
            entries = sorted(entries, key=lambda x: x.lower())
        elif sort == "year":
            entries = sorted(entries, key=self._extract_year_for_sort, reverse=True)
        # 'appearance' keeps original order
        
        return Bibliography(
            entries=entries,
            format_style=style,
            sort_order=sort,
            header="## References\n",
            footer=""
        )
    
    def generate_from_identifiers(
        self, 
        identifiers: List[str],
        style: str = "vancouver",
        sort: str = "alphabetical"
    ) -> Bibliography:
        """
        Generate bibliography from a list of identifiers.
        
        Args:
            identifiers: List of PMIDs, DOIs, etc.
            style: Citation style
            sort: Sort order
        
        Returns:
            Bibliography object
        """
        entries = []
        
        for identifier in identifiers:
            # Would need citation lookup integration
            entries.append(f"[{identifier}]: [Lookup required]")
        
        if sort == "alphabetical":
            entries = sorted(entries, key=lambda x: x.lower())
        
        return Bibliography(
            entries=entries,
            format_style=style,
            sort_order=sort,
            header="## References\n",
            footer=""
        )
    
    def format_bibliography(
        self, 
        bibliography: Bibliography,
        include_header: bool = True,
        number_entries: bool = False
    ) -> str:
        """
        Format a bibliography as a string.
        
        Args:
            bibliography: Bibliography object
            include_header: Whether to include section header
            number_entries: Whether to number each entry
        
        Returns:
            Formatted bibliography string
        """
        lines = []
        
        if include_header:
            lines.append(bibliography.header)
        
        for i, entry in enumerate(bibliography.entries, 1):
            if number_entries:
                lines.append(f"{i}. {entry}")
            else:
                lines.append(entry)
        
        if bibliography.footer:
            lines.append(bibliography.footer)
        
        return '\n'.join(lines)
    
    def update_document_bibliography(
        self, 
        text: str,
        bibliography: Bibliography,
        replace_existing: bool = True
    ) -> str:
        """
        Update or add a bibliography section to document text.
        
        Args:
            text: Original document text
            bibliography: Bibliography to insert
            replace_existing: Whether to replace existing references section
        
        Returns:
            Updated document text
        """
        formatted = self.format_bibliography(bibliography)
        
        # Look for existing references section
        ref_pattern = re.compile(
            r'^#{1,3}\s*(?:References|Bibliography|Sources|Works Cited)\s*\n',
            re.MULTILINE | re.IGNORECASE
        )
        
        match = ref_pattern.search(text)
        
        if match and replace_existing:
            # Find where the next section starts or end of document
            next_section = re.search(r'^#{1,3}\s+\w', text[match.end():], re.MULTILINE)
            if next_section:
                end_pos = match.end() + next_section.start()
            else:
                end_pos = len(text)
            
            # Replace
            return text[:match.start()] + formatted + '\n\n' + text[end_pos:]
        else:
            # Append
            return text.rstrip() + '\n\n' + formatted
    
    def _extract_existing_references(self, text: str) -> Dict[str, str]:
        """
        Extract existing reference definitions from text.
        
        Returns:
            Dict mapping inline marks to their definitions
        """
        refs = {}
        
        # Look for footnote definitions: [^mark]: definition
        footnote_pattern = re.compile(r'^\[\^([^\]]+)\]:\s*(.+)$', re.MULTILINE)
        
        for match in footnote_pattern.finditer(text):
            mark = f"[^{match.group(1)}]"
            definition = match.group(2).strip()
            refs[mark] = f"{mark}: {definition}"
        
        return refs
    
    def _extract_year_for_sort(self, entry: str) -> str:
        """Extract year from entry for sorting."""
        # Try to find a 4-digit year
        match = re.search(r'\b(19|20)\d{2}\b', entry)
        return match.group(0) if match else "0000"
    
    def count_citations(self, text: str) -> Dict[str, int]:
        """
        Count how many times each citation is used in text.
        
        Returns:
            Dict mapping inline marks to usage counts
        """
        refs = self.extract_citations(text)
        counts: Dict[str, int] = {}
        
        for ref in refs:
            counts[ref.inline_mark] = counts.get(ref.inline_mark, 0) + 1
        
        return counts
    
    def find_undefined_citations(self, text: str) -> List[str]:
        """
        Find citations used in text but not defined.
        
        Returns:
            List of undefined citation marks
        """
        used = set(self.extract_unique_citations(text))
        defined = set(self._extract_existing_references(text).keys())
        
        return list(used - defined)
    
    def find_unused_citations(self, text: str) -> List[str]:
        """
        Find citations defined but not used in text.
        
        Returns:
            List of unused citation marks
        """
        used = set(self.extract_unique_citations(text))
        defined = set(self._extract_existing_references(text).keys())
        
        return list(defined - used)

