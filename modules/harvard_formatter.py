"""Harvard Referencing Formatter Module."""

import re
from typing import Optional
from loguru import logger

from .base_formatter import BaseFormatter, FormattedCitation
from .pubmed_client import ArticleMetadata, CrossRefMetadata


class HarvardFormatter(BaseFormatter):
    """
    Formats citations in Harvard style.
    
    Key characteristics:
    - Author-date in-text: (Smith, 2024) or Smith (2024)
    - Authors: Last, A.B., Last, C.D. and Last, E.F.
    - Single quotes for article titles (UK) or no quotes (common)
    - Journal names in italics
    - "Available at:" for URLs
    
    Reference format:
    Last, A.B., Last, C.D. and Last, E.F. (Year) 'Article title', Journal Name,
        Volume(Issue), pp. Pages. Available at: https://doi.org/xxx.
    """
    
    STYLE_NAME = "harvard"

    def __init__(self, max_authors: int = 3):
        super().__init__(max_authors)

    def format_journal_article(self, metadata: ArticleMetadata, original_number: int) -> FormattedCitation:
        """Format a journal article in Harvard style."""
        author_label = metadata.get_first_author_label()
        label = self.generate_label(author_label, metadata.year, metadata.pmid)
        
        # Format authors: Last, A.B. and Last, C.D.
        authors_str = self._format_authors_harvard(metadata.authors, self.max_authors)
        
        # Year in parentheses
        year_str = f"({metadata.year})" if metadata.year else "(n.d.)"
        
        # Title in single quotes
        title = metadata.title.strip().rstrip('.')
        title_str = f"'{title}',"
        
        # Journal name (italicized)
        journal = metadata.journal_abbreviation or metadata.journal
        
        # Volume(Issue), pp. Pages
        vol_issue = ""
        if metadata.volume:
            vol_issue = metadata.volume
            if metadata.issue:
                vol_issue += f"({metadata.issue})"
        
        pages_str = f"pp. {metadata.pages}" if metadata.pages else ""
        
        # Build citation
        parts = [f"{authors_str} {year_str}", title_str, f"{journal},"]
        
        if vol_issue:
            parts.append(f"{vol_issue},")
        if pages_str:
            parts.append(f"{pages_str}.")
        else:
            parts[-1] = parts[-1].rstrip(',') + '.'
        
        citation_text = ' '.join(filter(None, parts))
        
        # Add DOI
        if metadata.doi:
            doi_url = self._format_doi_url(metadata.doi)
            citation_text += f" Available at: {doi_url}."
        
        full_citation = f"{label}: {citation_text}"
        logger.debug(f"Formatted Harvard: {label}")
        
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
        Format a book chapter in Harvard style.
        
        Format: Last, A.B. (Year) 'Chapter title', in Last, A.B. (ed.) Book Title.
                Place: Publisher, pp. Pages.
        """
        author_label = metadata.get_first_author_label()
        
        if metadata.pages:
            start_page = metadata.pages.split('-')[0].strip()
            label = self.generate_label(author_label, metadata.year, f"p{start_page}")
        else:
            brief_title = self._generate_brief_title(metadata.title, max_words=2)
            label = self.generate_label(author_label, metadata.year, brief_title)
        
        authors_str = self._format_authors_harvard(metadata.authors, self.max_authors)
        year_str = f"({metadata.year})" if metadata.year else "(n.d.)"
        
        # Chapter title in single quotes
        title = metadata.title.strip().rstrip('.')
        title_str = f"'{title}',"
        
        # Book title (italicized)
        book_title = metadata.book_title or metadata.container_title or ""
        
        # Editors
        editors_str = self._format_editors_harvard(metadata.editors)
        
        # Build citation
        parts = [f"{authors_str} {year_str}", title_str]
        
        if editors_str:
            parts.append(f"in {editors_str}")
        else:
            parts.append("in")
        
        parts.append(f"{book_title}.")
        
        # Publisher info
        pub_parts = []
        if metadata.publisher_location:
            pub_parts.append(metadata.publisher_location)
        if metadata.publisher:
            pub_parts.append(metadata.publisher)
        if pub_parts:
            parts.append(': '.join(pub_parts) + ",")
        
        if metadata.pages:
            parts.append(f"pp. {metadata.pages}.")
        
        citation_text = ' '.join(filter(None, parts))
        
        if metadata.doi:
            doi_url = self._format_doi_url(metadata.doi)
            citation_text += f" Available at: {doi_url}."
        
        full_citation = f"{label}: {citation_text}"
        logger.debug(f"Formatted Harvard book chapter: {label}")
        
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
        Format a book in Harvard style.
        
        Format: Last, A.B. (Year) Book Title. Place: Publisher.
        """
        author_label = metadata.get_first_author_label()
        brief_title = self._generate_brief_title(metadata.title, max_words=2)
        label = self.generate_label(author_label, metadata.year, brief_title)
        
        if metadata.authors:
            authors_str = self._format_authors_harvard(metadata.authors, self.max_authors)
        elif metadata.editors:
            editors = self._format_editors_harvard(metadata.editors)
            authors_str = f"{editors} (eds.)"
        else:
            authors_str = "Unknown"
        
        year_str = f"({metadata.year})" if metadata.year else "(n.d.)"
        
        # Title (italicized)
        title = metadata.title.strip().rstrip('.')
        
        # Build citation
        parts = [f"{authors_str} {year_str}", f"{title}."]
        
        # Publisher info
        pub_parts = []
        if metadata.publisher_location:
            pub_parts.append(metadata.publisher_location)
        if metadata.publisher:
            pub_parts.append(metadata.publisher)
        if pub_parts:
            parts.append(': '.join(pub_parts) + ".")
        
        citation_text = ' '.join(filter(None, parts))
        
        if metadata.doi:
            doi_url = self._format_doi_url(metadata.doi)
            citation_text += f" Available at: {doi_url}."
        
        full_citation = f"{label}: {citation_text}"
        logger.debug(f"Formatted Harvard book: {label}")
        
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
        Format a webpage in Harvard style.
        
        Format: Organization (Year) Title. Available at: URL (Accessed: Day Month Year).
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
        
        year_str = f"({year})" if year else "(n.d.)"
        
        # Title
        title_clean = title.strip().rstrip('.')
        
        access_date = datetime.now().strftime("%d %B %Y")
        
        # Build citation
        parts = [f"{org_name} {year_str}", f"{title_clean}."]
        parts.append(f"Available at: {url}")
        parts.append(f"(Accessed: {access_date}).")
        
        citation_text = ' '.join(filter(None, parts))
        full_citation = f"{label}: {citation_text}"
        
        logger.debug(f"Formatted Harvard webpage: {label}")
        
        return FormattedCitation(
            label=label,
            full_citation=full_citation,
            citation_type="webpage",
            original_number=original_number,
            style=self.STYLE_NAME,
        )

    def _format_editors_harvard(self, editors: list) -> str:
        """Format editors for Harvard: Last, A.B. (ed.) or Last, A.B. and Last, C.D. (eds.)"""
        if not editors:
            return ""
        
        def format_one(editor: str) -> str:
            parts = editor.replace(',', ' ').split()
            if len(parts) >= 2:
                initials = '.'.join([p[0] for p in parts[1:] if p]) + '.'
                return f"{parts[0]}, {initials}"
            return editor
        
        formatted = [format_one(e) for e in editors]
        
        if len(formatted) == 1:
            return f"{formatted[0]} (ed.)"
        elif len(formatted) == 2:
            return f"{formatted[0]} and {formatted[1]} (eds.)"
        else:
            return ', '.join(formatted[:-1]) + ' and ' + formatted[-1] + ' (eds.)'

