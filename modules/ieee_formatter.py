"""IEEE Citation Formatter Module."""

import re
from typing import Optional
from loguru import logger

from .base_formatter import BaseFormatter, FormattedCitation
from .pubmed_client import ArticleMetadata, CrossRefMetadata


class IEEEFormatter(BaseFormatter):
    """
    Formats citations in IEEE style.
    
    Key characteristics:
    - Numbered in-text citations: [1], [2], [3]
    - Authors: F. M. Last, F. M. Last, and F. M. Last
    - Title in quotation marks for articles
    - Journal names in italics, abbreviated
    - "vol.", "no.", "pp."
    - Month abbreviated
    
    Reference format:
    [1] F. M. Last, F. M. Last, and F. M. Last, "Article title," Journal Name,
        vol. X, no. X, pp. X-X, Mon. Year, doi: xxx.
    """
    
    STYLE_NAME = "ieee"

    def __init__(self, max_authors: int = 6):
        super().__init__(max_authors)

    def format_journal_article(self, metadata: ArticleMetadata, original_number: int) -> FormattedCitation:
        """Format a journal article in IEEE style."""
        author_label = metadata.get_first_author_label()
        label = self.generate_label(author_label, metadata.year, metadata.pmid)
        
        # Format authors: F. M. Last, F. M. Last, and F. M. Last
        authors_str = self._format_authors_ieee(metadata.authors, self.max_authors)
        
        # Title in quotation marks
        title = metadata.title.strip().rstrip('.')
        title_str = f'"{title},"'
        
        # Journal name (italicized, abbreviated)
        journal = metadata.journal_abbreviation or metadata.journal
        
        # Volume, issue, pages, date
        parts = [authors_str + ",", title_str, f"{journal},"]
        
        if metadata.volume:
            parts.append(f"vol. {metadata.volume},")
        if metadata.issue:
            parts.append(f"no. {metadata.issue},")
        if metadata.pages:
            parts.append(f"pp. {metadata.pages},")
        
        # Date: Mon. Year
        date_str = self._format_date_ieee(metadata.year, metadata.month)
        if date_str:
            parts.append(f"{date_str},")
        
        # Clean up trailing comma
        parts[-1] = parts[-1].rstrip(',')
        
        citation_text = ' '.join(filter(None, parts))
        
        # Add DOI
        if metadata.doi:
            citation_text += f", doi: {metadata.doi}."
        else:
            citation_text += "."
        
        full_citation = f"{label}: {citation_text}"
        logger.debug(f"Formatted IEEE: {label}")
        
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
        Format a book chapter in IEEE style.
        
        Format: F. M. Last, "Chapter title," in Book Title, Ed. Name, Ed.
                Place: Publisher, Year, pp. Pages.
        """
        author_label = metadata.get_first_author_label()
        
        if metadata.pages:
            start_page = metadata.pages.split('-')[0].strip()
            label = self.generate_label(author_label, metadata.year, f"p{start_page}")
        else:
            brief_title = self._generate_brief_title(metadata.title, max_words=2)
            label = self.generate_label(author_label, metadata.year, brief_title)
        
        authors_str = self._format_authors_ieee(metadata.authors, self.max_authors)
        
        # Chapter title in quotes
        title = metadata.title.strip().rstrip('.')
        title_str = f'"{title},"'
        
        # Book title (italicized)
        book_title = metadata.book_title or metadata.container_title or ""
        
        # Editors
        editors_str = self._format_editors_ieee(metadata.editors)
        
        # Build citation
        parts = [authors_str + ",", title_str, f"in {book_title},"]
        
        if editors_str:
            parts.append(f"{editors_str},")
        
        # Publisher info
        pub_parts = []
        if metadata.publisher_location:
            pub_parts.append(metadata.publisher_location)
        if metadata.publisher:
            pub_parts.append(metadata.publisher)
        if pub_parts:
            parts.append(': '.join(pub_parts) + ",")
        
        if metadata.year:
            parts.append(f"{metadata.year},")
        
        if metadata.pages:
            parts.append(f"pp. {metadata.pages}.")
        else:
            parts[-1] = parts[-1].rstrip(',') + '.'
        
        citation_text = ' '.join(filter(None, parts))
        
        if metadata.doi:
            citation_text = citation_text.rstrip('.') + f", doi: {metadata.doi}."
        
        full_citation = f"{label}: {citation_text}"
        logger.debug(f"Formatted IEEE book chapter: {label}")
        
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
        Format a book in IEEE style.
        
        Format: F. M. Last, Book Title. Place: Publisher, Year.
        """
        author_label = metadata.get_first_author_label()
        brief_title = self._generate_brief_title(metadata.title, max_words=2)
        label = self.generate_label(author_label, metadata.year, brief_title)
        
        if metadata.authors:
            authors_str = self._format_authors_ieee(metadata.authors, self.max_authors)
        elif metadata.editors:
            editors = self._format_editors_ieee(metadata.editors)
            authors_str = editors
        else:
            authors_str = "Unknown"
        
        # Title (italicized)
        title = metadata.title.strip().rstrip('.')
        
        # Build citation
        parts = [authors_str + ",", f"{title}."]
        
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
            citation_text = citation_text.rstrip('.') + f", doi: {metadata.doi}."
        
        full_citation = f"{label}: {citation_text}"
        logger.debug(f"Formatted IEEE book: {label}")
        
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
        Format a webpage in IEEE style.
        
        Format: Organization. "Title." Site Name. URL (accessed Mon. Day, Year).
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
        access_date = datetime.now().strftime("%b. %d, %Y")
        
        # Build citation
        parts = [f"{org_name}.", title_str, f"{site_name}."]
        parts.append(f"{url} (accessed {access_date}).")
        
        citation_text = ' '.join(filter(None, parts))
        full_citation = f"{label}: {citation_text}"
        
        logger.debug(f"Formatted IEEE webpage: {label}")
        
        return FormattedCitation(
            label=label,
            full_citation=full_citation,
            citation_type="webpage",
            original_number=original_number,
            style=self.STYLE_NAME,
        )

    def _format_date_ieee(self, year: str, month: str = "") -> str:
        """Format date for IEEE: Mon. Year"""
        if not year:
            return ""
        if month:
            month_abbrev = self.MONTH_ABBREV.get(month.lower(), month[:3].title())
            return f"{month_abbrev}. {year}"
        return year

    def _format_editors_ieee(self, editors: list) -> str:
        """Format editors for IEEE: F. M. Last, Ed. or F. M. Last and F. M. Last, Eds."""
        if not editors:
            return ""
        
        def format_one(editor: str) -> str:
            parts = editor.replace(',', ' ').split()
            if len(parts) >= 2:
                initials = ' '.join([f"{p[0]}." for p in parts[1:] if p])
                return f"{initials} {parts[0]}"
            return editor
        
        formatted = [format_one(e) for e in editors]
        
        if len(formatted) == 1:
            return f"{formatted[0]}, Ed."
        elif len(formatted) == 2:
            return f"{formatted[0]} and {formatted[1]}, Eds."
        else:
            return ', '.join(formatted[:-1]) + ', and ' + formatted[-1] + ', Eds.'

