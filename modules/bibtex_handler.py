"""BibTeX Import/Export Handler Module.

Provides functionality to:
- Export citations to BibTeX format
- Import and parse BibTeX files
- Convert between internal metadata and BibTeX entries
"""

import re
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Iterator
from pathlib import Path
from loguru import logger


@dataclass
class BibTeXEntry:
    """A single BibTeX entry."""
    entry_type: str  # article, book, inproceedings, etc.
    cite_key: str
    fields: Dict[str, str] = field(default_factory=dict)
    
    @property
    def title(self) -> str:
        return self.fields.get('title', '')
    
    @property
    def authors(self) -> List[str]:
        """Parse author field into list of names."""
        author_str = self.fields.get('author', '')
        if not author_str:
            return []
        # BibTeX uses "and" to separate authors
        return [a.strip() for a in author_str.split(' and ') if a.strip()]
    
    @property
    def year(self) -> str:
        return self.fields.get('year', '')
    
    @property
    def doi(self) -> Optional[str]:
        return self.fields.get('doi')
    
    def to_bibtex(self, indent: str = "  ") -> str:
        """Convert entry back to BibTeX format."""
        lines = [f"@{self.entry_type}{{{self.cite_key},"]
        
        for key, value in self.fields.items():
            # Escape special characters and wrap in braces
            escaped = value.replace('{', '\\{').replace('}', '\\}')
            lines.append(f"{indent}{key} = {{{escaped}}},")
        
        lines.append("}")
        return "\n".join(lines)


class BibTeXParser:
    """Parser for BibTeX files."""
    
    # Pattern to match entry start
    ENTRY_PATTERN = re.compile(r'@(\w+)\s*\{\s*([^,]+)\s*,', re.IGNORECASE)
    
    # Pattern to match field
    FIELD_PATTERN = re.compile(r'(\w+)\s*=\s*(?:\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}|"([^"]*)"|\d+)')
    
    def parse_file(self, filepath: str) -> List[BibTeXEntry]:
        """
        Parse a BibTeX file.
        
        Args:
            filepath: Path to .bib file
        
        Returns:
            List of BibTeXEntry objects
        """
        path = Path(filepath)
        if not path.exists():
            logger.error(f"BibTeX file not found: {filepath}")
            return []
        
        try:
            content = path.read_text(encoding='utf-8')
            return self.parse_string(content)
        except UnicodeDecodeError:
            # Try latin-1 encoding
            content = path.read_text(encoding='latin-1')
            return self.parse_string(content)
    
    def parse_string(self, content: str) -> List[BibTeXEntry]:
        """
        Parse BibTeX content from a string.
        
        Args:
            content: BibTeX content string
        
        Returns:
            List of BibTeXEntry objects
        """
        entries = []
        
        # Find all entries
        entry_starts = list(self.ENTRY_PATTERN.finditer(content))
        
        for i, match in enumerate(entry_starts):
            entry_type = match.group(1).lower()
            cite_key = match.group(2).strip()
            
            # Find entry content (between this match and next, or end)
            start = match.end()
            if i + 1 < len(entry_starts):
                end = entry_starts[i + 1].start()
            else:
                end = len(content)
            
            entry_content = content[start:end]
            
            # Find closing brace (accounting for nested braces)
            brace_count = 1
            actual_end = 0
            for j, char in enumerate(entry_content):
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        actual_end = j
                        break
            
            entry_content = entry_content[:actual_end]
            
            # Parse fields
            fields = self._parse_fields(entry_content)
            
            entries.append(BibTeXEntry(
                entry_type=entry_type,
                cite_key=cite_key,
                fields=fields
            ))
        
        return entries
    
    def _parse_fields(self, content: str) -> Dict[str, str]:
        """Parse fields from entry content."""
        fields = {}
        
        # Find all field matches
        for match in self.FIELD_PATTERN.finditer(content):
            key = match.group(1).lower()
            # Value can be in braces (group 2) or quotes (group 3)
            value = match.group(2) or match.group(3) or ""
            
            # Clean up value
            value = self._clean_value(value)
            
            if value:
                fields[key] = value
        
        return fields
    
    def _clean_value(self, value: str) -> str:
        """Clean up a BibTeX field value."""
        # Remove surrounding whitespace
        value = value.strip()
        
        # Remove LaTeX commands for special chars
        value = re.sub(r'\\[\'"`^~=.uvHtcdb]\{?(\w)\}?', r'\1', value)
        
        # Remove remaining braces used for case protection
        value = re.sub(r'\{([^{}]*)\}', r'\1', value)
        
        # Clean up whitespace
        value = ' '.join(value.split())
        
        return value


class BibTeXExporter:
    """Exporter for generating BibTeX from citation metadata."""
    
    def __init__(self):
        self.parser = BibTeXParser()
    
    def from_article_metadata(self, metadata, cite_key: str = None) -> BibTeXEntry:
        """
        Convert ArticleMetadata to BibTeXEntry.
        
        Args:
            metadata: ArticleMetadata object
            cite_key: Optional cite key (auto-generated if not provided)
        
        Returns:
            BibTeXEntry
        """
        if not cite_key:
            cite_key = self._generate_cite_key(metadata)
        
        fields = {
            'title': metadata.title,
            'author': ' and '.join(metadata.authors) if hasattr(metadata, 'authors') else '',
            'year': str(metadata.year) if hasattr(metadata, 'year') else '',
            'journal': metadata.journal if hasattr(metadata, 'journal') else '',
        }
        
        # Optional fields
        if hasattr(metadata, 'volume') and metadata.volume:
            fields['volume'] = metadata.volume
        if hasattr(metadata, 'issue') and metadata.issue:
            fields['number'] = metadata.issue
        if hasattr(metadata, 'pages') and metadata.pages:
            fields['pages'] = metadata.pages
        if hasattr(metadata, 'doi') and metadata.doi:
            fields['doi'] = metadata.doi
        if hasattr(metadata, 'pmid') and metadata.pmid:
            fields['pmid'] = metadata.pmid
        if hasattr(metadata, 'abstract') and metadata.abstract:
            fields['abstract'] = metadata.abstract
        if hasattr(metadata, 'month') and metadata.month:
            fields['month'] = metadata.month
        
        return BibTeXEntry(
            entry_type='article',
            cite_key=cite_key,
            fields={k: v for k, v in fields.items() if v}
        )
    
    def from_book_metadata(self, metadata, cite_key: str = None) -> BibTeXEntry:
        """
        Convert book metadata to BibTeXEntry.
        
        Args:
            metadata: BookMetadata or CrossRefMetadata object
            cite_key: Optional cite key
        
        Returns:
            BibTeXEntry
        """
        if not cite_key:
            cite_key = self._generate_cite_key(metadata)
        
        fields = {
            'title': metadata.title if hasattr(metadata, 'title') else '',
            'author': ' and '.join(metadata.authors) if hasattr(metadata, 'authors') and metadata.authors else '',
            'year': str(metadata.year) if hasattr(metadata, 'year') and metadata.year else '',
        }
        
        # Publisher
        if hasattr(metadata, 'publisher') and metadata.publisher:
            fields['publisher'] = metadata.publisher
        
        # ISBN
        if hasattr(metadata, 'isbn') and metadata.isbn:
            fields['isbn'] = metadata.isbn
        elif hasattr(metadata, 'display_isbn') and metadata.display_isbn:
            fields['isbn'] = metadata.display_isbn
        
        # DOI
        if hasattr(metadata, 'doi') and metadata.doi:
            fields['doi'] = metadata.doi
        
        # Edition
        if hasattr(metadata, 'edition') and metadata.edition:
            fields['edition'] = metadata.edition
        
        # Address/location
        if hasattr(metadata, 'publisher_location') and metadata.publisher_location:
            fields['address'] = metadata.publisher_location
        
        return BibTeXEntry(
            entry_type='book',
            cite_key=cite_key,
            fields={k: v for k, v in fields.items() if v}
        )
    
    def from_preprint_metadata(self, metadata, cite_key: str = None) -> BibTeXEntry:
        """
        Convert preprint metadata (arXiv, bioRxiv) to BibTeXEntry.
        
        Uses @misc or @unpublished type for preprints.
        """
        if not cite_key:
            cite_key = self._generate_cite_key(metadata)
        
        fields = {
            'title': metadata.title if hasattr(metadata, 'title') else '',
            'year': str(metadata.year) if hasattr(metadata, 'year') and metadata.year else '',
        }
        
        # Authors
        if hasattr(metadata, 'authors'):
            if isinstance(metadata.authors, list):
                fields['author'] = ' and '.join(metadata.authors)
            else:
                fields['author'] = metadata.authors
        
        # arXiv specific
        if hasattr(metadata, 'arxiv_id') and metadata.arxiv_id:
            fields['eprint'] = metadata.arxiv_id
            fields['archiveprefix'] = 'arXiv'
            if hasattr(metadata, 'primary_category') and metadata.primary_category:
                fields['primaryclass'] = metadata.primary_category
        
        # bioRxiv/medRxiv
        if hasattr(metadata, 'server') and metadata.server:
            fields['howpublished'] = f"{metadata.server} preprint"
        
        # DOI
        if hasattr(metadata, 'doi') and metadata.doi:
            fields['doi'] = metadata.doi
        
        # Abstract
        if hasattr(metadata, 'abstract') and metadata.abstract:
            fields['abstract'] = metadata.abstract
        
        return BibTeXEntry(
            entry_type='misc',
            cite_key=cite_key,
            fields={k: v for k, v in fields.items() if v}
        )
    
    def export_entries(self, entries: List[BibTeXEntry]) -> str:
        """
        Export list of entries to BibTeX format string.
        
        Args:
            entries: List of BibTeXEntry objects
        
        Returns:
            BibTeX formatted string
        """
        return "\n\n".join(entry.to_bibtex() for entry in entries)
    
    def export_to_file(self, entries: List[BibTeXEntry], filepath: str):
        """
        Export entries to a BibTeX file.
        
        Args:
            entries: List of BibTeXEntry objects
            filepath: Output file path
        """
        content = self.export_entries(entries)
        Path(filepath).write_text(content, encoding='utf-8')
        logger.info(f"Exported {len(entries)} entries to {filepath}")
    
    def _generate_cite_key(self, metadata) -> str:
        """Generate a cite key from metadata."""
        # Get first author surname
        author = "Unknown"
        if hasattr(metadata, 'get_first_author_label'):
            author = metadata.get_first_author_label()
        elif hasattr(metadata, 'authors') and metadata.authors:
            first = metadata.authors[0] if isinstance(metadata.authors, list) else metadata.authors.split(',')[0]
            parts = first.split()
            author = parts[-1] if parts else "Unknown"
        
        # Clean author name
        author = re.sub(r'[^a-zA-Z]', '', author)[:15]
        
        # Get year
        year = ""
        if hasattr(metadata, 'year'):
            year = str(metadata.year)[:4] if metadata.year else ""
        
        # Get first word of title
        title_word = ""
        if hasattr(metadata, 'title') and metadata.title:
            words = re.findall(r'\b[A-Za-z]+\b', metadata.title)
            # Skip common words
            skip = {'the', 'a', 'an', 'of', 'in', 'on', 'for', 'and', 'to'}
            for word in words:
                if word.lower() not in skip:
                    title_word = word.capitalize()[:10]
                    break
        
        return f"{author}{year}{title_word}"

