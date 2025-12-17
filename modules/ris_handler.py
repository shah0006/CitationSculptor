"""RIS (Research Information Systems) Import/Export Handler Module.

Provides functionality to:
- Export citations to RIS format
- Import and parse RIS files
- Convert between internal metadata and RIS entries
"""

import re
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Iterator
from pathlib import Path
from loguru import logger


# RIS type codes
RIS_TYPES = {
    'journal_article': 'JOUR',
    'article': 'JOUR',
    'book': 'BOOK',
    'book_chapter': 'CHAP',
    'inbook': 'CHAP',
    'conference': 'CONF',
    'thesis': 'THES',
    'report': 'RPRT',
    'webpage': 'ELEC',
    'preprint': 'UNPB',
    'misc': 'GEN',
}

# Reverse mapping
RIS_TYPE_TO_INTERNAL = {v: k for k, v in RIS_TYPES.items()}


@dataclass
class RISEntry:
    """A single RIS entry."""
    entry_type: str  # JOUR, BOOK, CHAP, etc.
    fields: Dict[str, List[str]] = field(default_factory=dict)
    
    @property
    def title(self) -> str:
        titles = self.fields.get('TI', []) or self.fields.get('T1', [])
        return titles[0] if titles else ''
    
    @property
    def authors(self) -> List[str]:
        """Get list of authors (AU fields)."""
        return self.fields.get('AU', []) or self.fields.get('A1', [])
    
    @property
    def year(self) -> str:
        years = self.fields.get('PY', []) or self.fields.get('Y1', [])
        if years:
            # Extract year from date formats like "2023/01/15" or "2023"
            return years[0].split('/')[0][:4]
        return ''
    
    @property
    def doi(self) -> Optional[str]:
        dois = self.fields.get('DO', [])
        return dois[0] if dois else None
    
    @property
    def journal(self) -> Optional[str]:
        journals = self.fields.get('JO', []) or self.fields.get('T2', []) or self.fields.get('JF', [])
        return journals[0] if journals else None
    
    def to_ris(self) -> str:
        """Convert entry to RIS format string."""
        lines = [f"TY  - {self.entry_type}"]
        
        for tag, values in self.fields.items():
            if tag == 'TY':
                continue
            for value in values:
                lines.append(f"{tag}  - {value}")
        
        lines.append("ER  - ")
        return "\n".join(lines)


class RISParser:
    """Parser for RIS files."""
    
    TAG_PATTERN = re.compile(r'^([A-Z][A-Z0-9])\s{2}-\s(.*)$')
    
    def parse_file(self, filepath: str) -> List[RISEntry]:
        """
        Parse a RIS file.
        
        Args:
            filepath: Path to .ris file
        
        Returns:
            List of RISEntry objects
        """
        path = Path(filepath)
        if not path.exists():
            logger.error(f"RIS file not found: {filepath}")
            return []
        
        try:
            content = path.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            content = path.read_text(encoding='latin-1')
        
        return self.parse_string(content)
    
    def parse_string(self, content: str) -> List[RISEntry]:
        """
        Parse RIS content from a string.
        
        Args:
            content: RIS content string
        
        Returns:
            List of RISEntry objects
        """
        entries = []
        current_entry = None
        current_fields: Dict[str, List[str]] = {}
        
        for line in content.split('\n'):
            line = line.strip()
            if not line:
                continue
            
            match = self.TAG_PATTERN.match(line)
            if not match:
                continue
            
            tag = match.group(1)
            value = match.group(2).strip()
            
            if tag == 'TY':
                # Start of new entry
                if current_entry is not None:
                    entries.append(RISEntry(
                        entry_type=current_entry,
                        fields=current_fields
                    ))
                current_entry = value
                current_fields = {}
            
            elif tag == 'ER':
                # End of entry
                if current_entry is not None:
                    entries.append(RISEntry(
                        entry_type=current_entry,
                        fields=current_fields
                    ))
                current_entry = None
                current_fields = {}
            
            else:
                # Regular field
                if tag not in current_fields:
                    current_fields[tag] = []
                current_fields[tag].append(value)
        
        # Handle case where file doesn't end with ER
        if current_entry is not None:
            entries.append(RISEntry(
                entry_type=current_entry,
                fields=current_fields
            ))
        
        return entries


class RISExporter:
    """Exporter for generating RIS from citation metadata."""
    
    def __init__(self):
        self.parser = RISParser()
    
    def from_article_metadata(self, metadata) -> RISEntry:
        """
        Convert ArticleMetadata to RISEntry.
        
        Args:
            metadata: ArticleMetadata object
        
        Returns:
            RISEntry
        """
        fields: Dict[str, List[str]] = {}
        
        # Title
        if hasattr(metadata, 'title') and metadata.title:
            fields['TI'] = [metadata.title]
        
        # Authors (one per AU field)
        if hasattr(metadata, 'authors') and metadata.authors:
            fields['AU'] = list(metadata.authors)
        
        # Year/Date
        if hasattr(metadata, 'year') and metadata.year:
            date_str = str(metadata.year)
            if hasattr(metadata, 'month') and metadata.month:
                date_str += f"/{metadata.month}"
            fields['PY'] = [date_str]
        
        # Journal
        if hasattr(metadata, 'journal') and metadata.journal:
            fields['JO'] = [metadata.journal]
            fields['T2'] = [metadata.journal]
        
        # Volume, Issue, Pages
        if hasattr(metadata, 'volume') and metadata.volume:
            fields['VL'] = [metadata.volume]
        if hasattr(metadata, 'issue') and metadata.issue:
            fields['IS'] = [metadata.issue]
        if hasattr(metadata, 'pages') and metadata.pages:
            # Split page range
            pages = metadata.pages
            if '-' in pages:
                sp, ep = pages.split('-', 1)
                fields['SP'] = [sp.strip()]
                fields['EP'] = [ep.strip()]
            else:
                fields['SP'] = [pages]
        
        # DOI
        if hasattr(metadata, 'doi') and metadata.doi:
            fields['DO'] = [metadata.doi]
        
        # PMID
        if hasattr(metadata, 'pmid') and metadata.pmid:
            fields['AN'] = [f"PMID:{metadata.pmid}"]
        
        # Abstract
        if hasattr(metadata, 'abstract') and metadata.abstract:
            fields['AB'] = [metadata.abstract]
        
        return RISEntry(
            entry_type='JOUR',
            fields=fields
        )
    
    def from_book_metadata(self, metadata) -> RISEntry:
        """
        Convert book metadata to RISEntry.
        """
        fields: Dict[str, List[str]] = {}
        
        # Title
        if hasattr(metadata, 'title') and metadata.title:
            fields['TI'] = [metadata.title]
        
        # Authors
        if hasattr(metadata, 'authors') and metadata.authors:
            if isinstance(metadata.authors, list):
                fields['AU'] = list(metadata.authors)
            else:
                fields['AU'] = [metadata.authors]
        
        # Year
        if hasattr(metadata, 'year') and metadata.year:
            fields['PY'] = [str(metadata.year)]
        elif hasattr(metadata, 'published_date') and metadata.published_date:
            fields['PY'] = [metadata.published_date[:4]]
        
        # Publisher
        if hasattr(metadata, 'publisher') and metadata.publisher:
            fields['PB'] = [metadata.publisher]
        
        # ISBN
        if hasattr(metadata, 'isbn') and metadata.isbn:
            fields['SN'] = [metadata.isbn]
        elif hasattr(metadata, 'display_isbn') and metadata.display_isbn:
            fields['SN'] = [metadata.display_isbn]
        
        # DOI
        if hasattr(metadata, 'doi') and metadata.doi:
            fields['DO'] = [metadata.doi]
        
        # Place
        if hasattr(metadata, 'publisher_location') and metadata.publisher_location:
            fields['CY'] = [metadata.publisher_location]
        
        return RISEntry(
            entry_type='BOOK',
            fields=fields
        )
    
    def from_preprint_metadata(self, metadata) -> RISEntry:
        """
        Convert preprint metadata to RISEntry.
        """
        fields: Dict[str, List[str]] = {}
        
        # Title
        if hasattr(metadata, 'title') and metadata.title:
            fields['TI'] = [metadata.title]
        
        # Authors
        if hasattr(metadata, 'authors') and metadata.authors:
            if isinstance(metadata.authors, list):
                fields['AU'] = list(metadata.authors)
            elif hasattr(metadata, 'authors_list'):
                fields['AU'] = list(metadata.authors_list)
            else:
                fields['AU'] = [str(metadata.authors)]
        
        # Year
        if hasattr(metadata, 'year') and metadata.year:
            fields['PY'] = [str(metadata.year)]
        elif hasattr(metadata, 'published') and metadata.published:
            fields['PY'] = [metadata.published[:4]]
        elif hasattr(metadata, 'date') and metadata.date:
            fields['PY'] = [metadata.date[:4]]
        
        # DOI
        if hasattr(metadata, 'doi') and metadata.doi:
            fields['DO'] = [metadata.doi]
        
        # arXiv
        if hasattr(metadata, 'arxiv_id') and metadata.arxiv_id:
            fields['AN'] = [f"arXiv:{metadata.arxiv_id}"]
            fields['UR'] = [f"https://arxiv.org/abs/{metadata.arxiv_id}"]
        
        # Server (bioRxiv/medRxiv)
        if hasattr(metadata, 'server') and metadata.server:
            fields['PB'] = [metadata.server]
        
        # Abstract
        if hasattr(metadata, 'abstract') and metadata.abstract:
            fields['AB'] = [metadata.abstract]
        
        return RISEntry(
            entry_type='UNPB',
            fields=fields
        )
    
    def export_entries(self, entries: List[RISEntry]) -> str:
        """
        Export list of entries to RIS format string.
        
        Args:
            entries: List of RISEntry objects
        
        Returns:
            RIS formatted string
        """
        return "\n\n".join(entry.to_ris() for entry in entries)
    
    def export_to_file(self, entries: List[RISEntry], filepath: str):
        """
        Export entries to a RIS file.
        
        Args:
            entries: List of RISEntry objects
            filepath: Output file path
        """
        content = self.export_entries(entries)
        Path(filepath).write_text(content, encoding='utf-8')
        logger.info(f"Exported {len(entries)} entries to {filepath}")

