"""Chicago/Turabian Formatter Module (Notes-Bibliography style)."""

import re
from typing import Optional
from loguru import logger

from .base_formatter import BaseFormatter, FormattedCitation
from .pubmed_client import ArticleMetadata, CrossRefMetadata


class ChicagoFormatter(BaseFormatter):
    """
    Formats citations in Chicago Manual of Style (Notes-Bibliography).
    
    Key characteristics:
    - Full names: First Middle Last
    - Titles in quotation marks or italics
    - Publication info in parentheses
    - DOI or URL at end
    
    Reference format:
    Last, First M. "Article Title." Journal Name Volume, no. Issue (Year): Pages.
        https://doi.org/xxx.
    """
    
    STYLE_NAME = "chicago"

    def __init__(self, max_authors: int = 10):
        super().__init__(max_authors)

    def format_journal_article(self, metadata: ArticleMetadata, original_number: int) -> FormattedCitation:
        """Format a journal article in Chicago style."""
        author_label = metadata.get_first_author_label()
        label = self.generate_label(author_label, metadata.year, metadata.pmid)
        
        # Format authors: Last, First M., and First M. Last
        authors_str = self._format_authors_chicago(metadata.authors, self.max_authors)
        
        # Title in quotation marks
        title = metadata.title.strip().rstrip('.')
        title_str = f'"{title}."'
        
        # Journal name (italicized)
        journal = metadata.journal_abbreviation or metadata.journal
        
        # Volume, issue, year, pages
        vol_str = ""
        if metadata.volume:
            vol_str = metadata.volume
            if metadata.issue:
                vol_str += f", no. {metadata.issue}"
        
        year_str = f"({metadata.year})" if metadata.year else ""
        
        pages_str = f": {metadata.pages}" if metadata.pages else ""
        
        # Build citation
        parts = [f"{authors_str}.", title_str, journal]
        
        if vol_str:
            parts.append(vol_str)
        if year_str:
            parts.append(year_str + pages_str + ".")
        
        citation_text = ' '.join(filter(None, parts))
        
        # Add DOI
        if metadata.doi:
            doi_url = self._format_doi_url(metadata.doi)
            citation_text += f" {doi_url}."
        
        full_citation = f"{label}: {citation_text}"
        logger.debug(f"Formatted Chicago: {label}")
        
        return FormattedCitation(
            label=label,
            full_citation=full_citation,
            citation_type="journal_article",
            original_number=original_number,
            pmid=metadata.pmid,
            doi=metadata.doi,
            style=self.STYLE_NAME,
        )

    def format_book_chapter(self, metadata: CrossRefMetadata, original_number: int) -> FormattedCitation:
        """
        Format a book chapter in Chicago style.
        
        Format: Last, First M. "Chapter Title." In Book Title, edited by First Last,
                Pages. Place: Publisher, Year.
        """
        author_label = metadata.get_first_author_label()
        
        if metadata.pages:
            start_page = metadata.pages.split('-')[0].strip()
            label = self.generate_label(author_label, metadata.year, f"p{start_page}")
        else:
            brief_title = self._generate_brief_title(metadata.title, max_words=2)
            label = self.generate_label(author_label, metadata.year, brief_title)
        
        authors_str = self._format_authors_chicago(metadata.authors, self.max_authors)
        
        # Chapter title in quotes
        title = metadata.title.strip().rstrip('.')
        title_str = f'"{title}."'
        
        # Book title (italicized)
        book_title = metadata.book_title or metadata.container_title or ""
        
        # Editors
        editors_str = self._format_editors_chicago(metadata.editors)
        
        # Build citation
        parts = [f"{authors_str}.", title_str, f"In {book_title},"]
        
        if editors_str:
            parts.append(f"edited by {editors_str},")
        
        if metadata.pages:
            parts.append(f"{metadata.pages}.")
        
        # Publisher info
        pub_parts = []
        if metadata.publisher_location:
            pub_parts.append(metadata.publisher_location)
        if metadata.publisher:
            pub_parts.append(metadata.publisher)
        if pub_parts:
            parts.append(': '.join(pub_parts) + ",")
        
        if metadata.year:
            parts.append(f"{metadata.year}.")
        
        citation_text = ' '.join(filter(None, parts))
        
        if metadata.doi:
            doi_url = self._format_doi_url(metadata.doi)
            citation_text += f" {doi_url}."
        
        full_citation = f"{label}: {citation_text}"
        logger.debug(f"Formatted Chicago book chapter: {label}")
        
        return FormattedCitation(
            label=label,
            full_citation=full_citation,
            citation_type="book_chapter",
            original_number=original_number,
            doi=metadata.doi,
            style=self.STYLE_NAME,
        )

    def format_book(self, metadata: CrossRefMetadata, original_number: int) -> FormattedCitation:
        """
        Format a book in Chicago style.
        
        Format: Last, First M. Book Title. Place: Publisher, Year.
        """
        author_label = metadata.get_first_author_label()
        brief_title = self._generate_brief_title(metadata.title, max_words=2)
        label = self.generate_label(author_label, metadata.year, brief_title)
        
        if metadata.authors:
            authors_str = self._format_authors_chicago(metadata.authors, self.max_authors)
        elif metadata.editors:
            editors = self._format_editors_chicago(metadata.editors)
            authors_str = f"{editors}, eds."
        else:
            authors_str = "Unknown"
        
        # Title (italicized)
        title = metadata.title.strip().rstrip('.')
        
        # Build citation
        parts = [f"{authors_str}.", f"{title}."]
        
        # Publisher info
        pub_parts = []
        if metadata.publisher_location:
            pub_parts.append(metadata.publisher_location)
        if metadata.publisher:
            pub_parts.append(metadata.publisher)
        if pub_parts:
            parts.append(': '.join(pub_parts) + ",")
        
        if metadata.year:
            parts.append(f"{metadata.year}.")
        
        citation_text = ' '.join(filter(None, parts))
        
        if metadata.doi:
            doi_url = self._format_doi_url(metadata.doi)
            citation_text += f" {doi_url}."
        
        full_citation = f"{label}: {citation_text}"
        logger.debug(f"Formatted Chicago book: {label}")
        
        return FormattedCitation(
            label=label,
            full_citation=full_citation,
            citation_type="book",
            original_number=original_number,
            doi=metadata.doi,
            style=self.STYLE_NAME,
        )

    def format_webpage(
        self, 
        title: str, 
        url: str, 
        source_name: Optional[str],
        original_number: int,
        year: Optional[str] = None,
        is_evergreen: bool = False,
    ) -> FormattedCitation:
        """
        Format a webpage in Chicago style.
        
        Format: Author/Organization. "Title." Site Name. Last modified/Accessed Date. URL.
        """
        from datetime import datetime
        
        org_name = self._extract_organization(source_name, url)
        org_abbrev = self._generate_org_abbreviation(org_name)
        
        if not year:
            year = self._extract_year_from_text(title) or self._extract_year_from_url(url)
            if not year and not is_evergreen:
                year = "n.d."
        
        brief_title = self._generate_brief_title(title, max_words=2)
        label_year = year if year and year not in ("Null_Date", "n.d.") else "ND"
        label = f"[^{org_abbrev.upper()}-{brief_title}-{label_year}]"
        
        # Title in quotes
        title_clean = title.strip().rstrip('.')
        title_str = f'"{title_clean}."'
        
        site_name = source_name or org_name
        access_date = datetime.now().strftime("%B %d, %Y")
        
        # Build citation
        parts = [f"{org_name}.", title_str, f"{site_name}."]
        
        if year and year != "n.d.":
            parts.append(f"Last modified {year}.")
        
        parts.append(f"Accessed {access_date}.")
        parts.append(url + ".")
        
        citation_text = ' '.join(filter(None, parts))
        full_citation = f"{label}: {citation_text}"
        
        logger.debug(f"Formatted Chicago webpage: {label}")
        
        return FormattedCitation(
            label=label,
            full_citation=full_citation,
            citation_type="webpage",
            original_number=original_number,
            style=self.STYLE_NAME,
        )

    def _format_editors_chicago(self, editors: list) -> str:
        """Format editors for Chicago: First Last and First Last"""
        if not editors:
            return ""
        
        def format_name(editor: str) -> str:
            parts = editor.replace(',', ' ').split()
            if len(parts) >= 2:
                return f"{' '.join(parts[1:])} {parts[0]}"
            return editor
        
        formatted = [format_name(e) for e in editors]
        
        if len(formatted) == 1:
            return formatted[0]
        elif len(formatted) == 2:
            return f"{formatted[0]} and {formatted[1]}"
        else:
            return ', '.join(formatted[:-1]) + ', and ' + formatted[-1]

