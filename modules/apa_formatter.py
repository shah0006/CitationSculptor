"""APA 7th Edition Formatter Module."""

import re
from typing import Optional
from loguru import logger

from .base_formatter import BaseFormatter, FormattedCitation
from .pubmed_client import ArticleMetadata, CrossRefMetadata, WebpageMetadata


class APAFormatter(BaseFormatter):
    """
    Formats citations in APA 7th Edition style.
    
    Key characteristics:
    - Author-date in-text: (Smith, 2024) or Smith (2024)
    - Authors: Last, F. M., & Last, F. M.
    - Up to 20 authors before using "..."
    - Title case for article titles (only first word + proper nouns capitalized)
    - Italicized journal names and volume numbers
    - DOI as URL: https://doi.org/xxx
    
    Reference format:
    Author, A. A., & Author, B. B. (Year). Title of article. Journal Name, 
        Volume(Issue), Pages. https://doi.org/xxx
    """
    
    STYLE_NAME = "apa"

    def __init__(self, max_authors: int = 20):
        super().__init__(max_authors)

    def format_journal_article(self, metadata: ArticleMetadata, original_number: int) -> FormattedCitation:
        """Format a journal article in APA 7th style."""
        # Generate label (same unique format for all styles)
        author_label = metadata.get_first_author_label()
        label = self.generate_label(author_label, metadata.year, metadata.pmid)
        
        # Format authors: Last, F. M., & Last, F. M.
        authors_str = self._format_authors_apa(metadata.authors, self.max_authors)
        
        # Year in parentheses
        year_str = f"({metadata.year})" if metadata.year else "(n.d.)"
        
        # Title: sentence case (only first word capitalized)
        title = self._to_sentence_case(metadata.title)
        if not title.endswith('.'):
            title += '.'
        
        # Journal name (would be italicized in rich text)
        journal = metadata.journal_abbreviation or metadata.journal
        
        # Volume(Issue), Pages
        vol_issue = ""
        if metadata.volume:
            vol_issue = metadata.volume
            if metadata.issue:
                vol_issue += f"({metadata.issue})"
        
        pages = metadata.pages if metadata.pages else ""
        
        # Build citation
        parts = [f"{authors_str} {year_str}.", title, f"{journal},"]
        
        if vol_issue and pages:
            parts.append(f"{vol_issue}, {pages}.")
        elif vol_issue:
            parts.append(f"{vol_issue}.")
        elif pages:
            parts.append(f"{pages}.")
        
        citation_text = ' '.join(filter(None, parts))
        
        # Add DOI as URL
        if metadata.doi:
            doi_url = self._format_doi_url(metadata.doi)
            citation_text += f" {doi_url}"
        
        full_citation = f"{label}: {citation_text}"
        logger.debug(f"Formatted APA: {label}")
        
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
        Format a book chapter in APA 7th style.
        
        Format: Author, A. A. (Year). Title of chapter. In E. E. Editor (Ed.), 
                Title of book (pp. xx-xx). Publisher. https://doi.org/xxx
        """
        author_label = metadata.get_first_author_label()
        
        if metadata.pages:
            start_page = metadata.pages.split('-')[0].strip()
            label = self.generate_label(author_label, metadata.year, f"p{start_page}")
        else:
            brief_title = self._generate_brief_title(metadata.title, max_words=2)
            label = self.generate_label(author_label, metadata.year, brief_title)
        
        # Authors
        authors_str = self._format_authors_apa(metadata.authors, self.max_authors)
        year_str = f"({metadata.year})" if metadata.year else "(n.d.)"
        
        # Chapter title (sentence case)
        title = self._to_sentence_case(metadata.title)
        if not title.endswith('.'):
            title += '.'
        
        # Editors
        editors_str = self._format_editors_apa(metadata.editors)
        
        # Book title
        book_title = metadata.book_title or metadata.container_title or ""
        
        # Pages
        pages = f"(pp. {metadata.pages})" if metadata.pages else ""
        
        # Publisher
        publisher = metadata.publisher or ""
        
        # Build citation
        parts = [f"{authors_str} {year_str}.", title]
        
        if editors_str:
            parts.append(f"In {editors_str},")
        else:
            parts.append("In")
        
        if book_title:
            parts.append(f"{book_title}")
        
        if pages:
            parts.append(pages + ".")
        else:
            parts[-1] = parts[-1].rstrip(',') + '.'
        
        if publisher:
            parts.append(publisher + ".")
        
        citation_text = ' '.join(filter(None, parts))
        
        if metadata.doi:
            doi_url = self._format_doi_url(metadata.doi)
            citation_text += f" {doi_url}"
        
        full_citation = f"{label}: {citation_text}"
        logger.debug(f"Formatted APA book chapter: {label}")
        
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
        Format a book in APA 7th style.
        
        Format: Author, A. A. (Year). Title of book. Publisher. https://doi.org/xxx
        """
        author_label = metadata.get_first_author_label()
        brief_title = self._generate_brief_title(metadata.title, max_words=2)
        label = self.generate_label(author_label, metadata.year, brief_title)
        
        # Authors or Editors
        if metadata.authors:
            authors_str = self._format_authors_apa(metadata.authors, self.max_authors)
        elif metadata.editors:
            authors_str = self._format_editors_apa(metadata.editors) + " (Eds.)"
        else:
            authors_str = "Unknown"
        
        year_str = f"({metadata.year})" if metadata.year else "(n.d.)"
        
        # Title (italicized in rich text)
        title = metadata.title.strip()
        if not title.endswith('.'):
            title += '.'
        
        # Publisher
        publisher = metadata.publisher or ""
        
        # Build citation
        parts = [f"{authors_str} {year_str}.", title]
        
        if publisher:
            parts.append(publisher + ".")
        
        citation_text = ' '.join(filter(None, parts))
        
        if metadata.doi:
            doi_url = self._format_doi_url(metadata.doi)
            citation_text += f" {doi_url}"
        
        full_citation = f"{label}: {citation_text}"
        logger.debug(f"Formatted APA book: {label}")
        
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
        Format a webpage in APA 7th style.
        
        Format: Author/Organization. (Year, Month Day). Title. Site Name. URL
        """
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
        
        # Title (sentence case)
        title_clean = self._to_sentence_case(title)
        if not title_clean.endswith('.'):
            title_clean += '.'
        
        # Build citation
        parts = [f"{org_name}. {year_str}.", title_clean]
        
        if source_name and source_name != org_name:
            parts.append(f"{source_name}.")
        
        parts.append(url)
        
        citation_text = ' '.join(filter(None, parts))
        full_citation = f"{label}: {citation_text}"
        
        logger.debug(f"Formatted APA webpage: {label}")
        
        return FormattedCitation(
            label=label,
            full_citation=full_citation,
            citation_type="webpage",
            original_number=original_number,
            style=self.STYLE_NAME,
        )

    def format_crossref_journal_article(self, metadata: CrossRefMetadata, original_number: int) -> FormattedCitation:
        """Format a journal article from CrossRef in APA style."""
        author_label = metadata.get_first_author_label()
        brief_title = self._generate_brief_title(metadata.title, max_words=2)
        label = self.generate_label(author_label, metadata.year, brief_title)
        
        authors_str = self._format_authors_apa(metadata.authors, self.max_authors)
        year_str = f"({metadata.year})" if metadata.year else "(n.d.)"
        
        title = self._to_sentence_case(metadata.title)
        if not title.endswith('.'):
            title += '.'
        
        journal = metadata.container_title or ""
        
        vol_issue = ""
        if metadata.volume:
            vol_issue = metadata.volume
            if metadata.issue:
                vol_issue += f"({metadata.issue})"
        
        pages = metadata.pages if metadata.pages else ""
        
        parts = [f"{authors_str} {year_str}.", title]
        
        if journal:
            parts.append(f"{journal},")
        
        if vol_issue and pages:
            parts.append(f"{vol_issue}, {pages}.")
        elif vol_issue:
            parts.append(f"{vol_issue}.")
        elif pages:
            parts.append(f"{pages}.")
        
        citation_text = ' '.join(filter(None, parts))
        
        if metadata.doi:
            doi_url = self._format_doi_url(metadata.doi)
            citation_text += f" {doi_url}"
        
        full_citation = f"{label}: {citation_text}"
        logger.debug(f"Formatted APA CrossRef article: {label}")
        
        return FormattedCitation(
            label=label,
            full_citation=full_citation,
            citation_type="journal_article",
            original_number=original_number,
            doi=metadata.doi,
            style=self.STYLE_NAME,
        )

    # =========================================================================
    # Helper methods specific to APA
    # =========================================================================
    
    def _to_sentence_case(self, title: str) -> str:
        """Convert title to sentence case (first word + proper nouns capitalized)."""
        if not title:
            return ""
        
        # Split into words
        words = title.split()
        if not words:
            return ""
        
        result = []
        for i, word in enumerate(words):
            if i == 0:
                # First word always capitalized
                result.append(word.capitalize())
            elif ':' in words[i-1]:
                # Word after colon capitalized
                result.append(word.capitalize())
            elif word.isupper() and len(word) > 1:
                # Preserve acronyms
                result.append(word)
            elif word[0].isupper() and not word.isupper():
                # Likely a proper noun, preserve
                result.append(word)
            else:
                result.append(word.lower())
        
        return ' '.join(result)
    
    def _format_editors_apa(self, editors: list) -> str:
        """Format editors for APA: E. E. Editor (Ed.) or E. E. Editor & F. F. Editor (Eds.)"""
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
            return f"{formatted[0]} (Ed.)"
        elif len(formatted) == 2:
            return f"{formatted[0]} & {formatted[1]} (Eds.)"
        else:
            return ', '.join(formatted[:-1]) + ', & ' + formatted[-1] + ' (Eds.)'

