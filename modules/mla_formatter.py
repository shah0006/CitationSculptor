"""MLA 9th Edition Formatter Module."""

import re
from typing import Optional
from loguru import logger

from .base_formatter import BaseFormatter, FormattedCitation
from .pubmed_client import ArticleMetadata, CrossRefMetadata


class MLAFormatter(BaseFormatter):
    """
    Formats citations in MLA 9th Edition style.
    
    Key characteristics:
    - Author-page in-text: (Smith 45) or Smith argues... (45)
    - Authors: Last, First Middle. and First Last.
    - Title in quotes for articles, italics for books/journals
    - Container model: article "in" journal/book
    - Access date for online sources
    
    Reference format:
    Last, First. "Article Title." Journal Name, vol. X, no. X, Year, pp. X-X.
        DOI or URL.
    """
    
    STYLE_NAME = "mla"

    def __init__(self, max_authors: int = 3):
        super().__init__(max_authors)

    def format_journal_article(self, metadata: ArticleMetadata, original_number: int) -> FormattedCitation:
        """Format a journal article in MLA 9th style."""
        author_label = metadata.get_first_author_label()
        label = self.generate_label(author_label, metadata.year, metadata.pmid)
        
        # Format authors: Last, First, and First Last.
        authors_str = self._format_authors_mla(metadata.authors, self.max_authors)
        
        # Title in quotation marks
        title = metadata.title.strip().rstrip('.')
        title = f'"{title}."'
        
        # Journal name (italicized)
        journal = metadata.journal_abbreviation or metadata.journal
        
        # Volume, issue, year, pages
        parts = [authors_str, title, f"{journal},"]
        
        if metadata.volume:
            parts.append(f"vol. {metadata.volume},")
        if metadata.issue:
            parts.append(f"no. {metadata.issue},")
        if metadata.year:
            parts.append(f"{metadata.year},")
        if metadata.pages:
            parts.append(f"pp. {metadata.pages}.")
        else:
            # Remove trailing comma from last part
            parts[-1] = parts[-1].rstrip(',') + '.'
        
        citation_text = ' '.join(filter(None, parts))
        
        # Add DOI
        if metadata.doi:
            doi_url = self._format_doi_url(metadata.doi)
            citation_text += f" {doi_url}."
        
        full_citation = f"{label}: {citation_text}"
        logger.debug(f"Formatted MLA: {label}")
        
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
        Format a book chapter in MLA 9th style.
        
        Format: Last, First. "Chapter Title." Book Title, edited by First Last,
                Publisher, Year, pp. xx-xx.
        """
        author_label = metadata.get_first_author_label()
        
        if metadata.pages:
            start_page = metadata.pages.split('-')[0].strip()
            label = self.generate_label(author_label, metadata.year, f"p{start_page}")
        else:
            brief_title = self._generate_brief_title(metadata.title, max_words=2)
            label = self.generate_label(author_label, metadata.year, brief_title)
        
        # Authors
        authors_str = self._format_authors_mla(metadata.authors, self.max_authors)
        
        # Chapter title in quotes
        title = metadata.title.strip().rstrip('.')
        title = f'"{title}."'
        
        # Book title (italicized)
        book_title = metadata.book_title or metadata.container_title or ""
        
        # Editors
        editors_str = self._format_editors_mla(metadata.editors)
        
        # Build citation
        parts = [authors_str, title, f"{book_title},"]
        
        if editors_str:
            parts.append(f"edited by {editors_str},")
        
        if metadata.publisher:
            parts.append(f"{metadata.publisher},")
        
        if metadata.year:
            parts.append(f"{metadata.year},")
        
        if metadata.pages:
            parts.append(f"pp. {metadata.pages}.")
        else:
            parts[-1] = parts[-1].rstrip(',') + '.'
        
        citation_text = ' '.join(filter(None, parts))
        
        if metadata.doi:
            doi_url = self._format_doi_url(metadata.doi)
            citation_text += f" {doi_url}."
        
        full_citation = f"{label}: {citation_text}"
        logger.debug(f"Formatted MLA book chapter: {label}")
        
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
        Format a book in MLA 9th style.
        
        Format: Last, First. Book Title. Publisher, Year.
        """
        author_label = metadata.get_first_author_label()
        brief_title = self._generate_brief_title(metadata.title, max_words=2)
        label = self.generate_label(author_label, metadata.year, brief_title)
        
        # Authors or Editors
        if metadata.authors:
            authors_str = self._format_authors_mla(metadata.authors, self.max_authors)
        elif metadata.editors:
            authors_str = self._format_editors_mla(metadata.editors) + ", editors."
        else:
            authors_str = "Unknown."
        
        # Title (italicized)
        title = metadata.title.strip().rstrip('.')
        
        # Build citation
        parts = [authors_str, f"{title}."]
        
        if metadata.publisher:
            parts.append(f"{metadata.publisher},")
        
        if metadata.year:
            parts.append(f"{metadata.year}.")
        else:
            parts[-1] = parts[-1].rstrip(',') + '.'
        
        citation_text = ' '.join(filter(None, parts))
        
        if metadata.doi:
            doi_url = self._format_doi_url(metadata.doi)
            citation_text += f" {doi_url}."
        
        full_citation = f"{label}: {citation_text}"
        logger.debug(f"Formatted MLA book: {label}")
        
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
        Format a webpage in MLA 9th style.
        
        Format: "Title." Site Name, Day Month Year, URL. Accessed Day Month Year.
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
        
        # Site name (italicized)
        site_name = source_name or org_name
        
        # Access date
        access_date = datetime.now().strftime("%d %b. %Y")
        
        # Build citation
        parts = [title_str, f"{site_name},"]
        
        if year and year != "n.d.":
            parts.append(f"{year},")
        
        parts.append(f"{url}.")
        parts.append(f"Accessed {access_date}.")
        
        citation_text = ' '.join(filter(None, parts))
        full_citation = f"{label}: {citation_text}"
        
        logger.debug(f"Formatted MLA webpage: {label}")
        
        return FormattedCitation(
            label=label,
            full_citation=full_citation,
            citation_type="webpage",
            original_number=original_number,
            style=self.STYLE_NAME,
        )

    def _format_editors_mla(self, editors: list) -> str:
        """Format editors for MLA: First Last and First Last"""
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

