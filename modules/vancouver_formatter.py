"""Vancouver Formatter Module - Formats citations in Vancouver style."""

import re
from typing import Optional
from dataclasses import dataclass
from loguru import logger

from .pubmed_client import ArticleMetadata


@dataclass
class FormattedCitation:
    """A fully formatted citation."""
    label: str  # e.g., "[^SmithJA-2024-12345678]"
    full_citation: str  # Complete formatted citation
    citation_type: str
    original_number: int
    pmid: Optional[str] = None
    doi: Optional[str] = None


class VancouverFormatter:
    """Formats citations in Vancouver style."""

    MONTH_ABBREV = {
        '1': 'Jan', '01': 'Jan', 'january': 'Jan',
        '2': 'Feb', '02': 'Feb', 'february': 'Feb',
        '3': 'Mar', '03': 'Mar', 'march': 'Mar',
        '4': 'Apr', '04': 'Apr', 'april': 'Apr',
        '5': 'May', '05': 'May', 'may': 'May',
        '6': 'Jun', '06': 'Jun', 'june': 'Jun',
        '7': 'Jul', '07': 'Jul', 'july': 'Jul',
        '8': 'Aug', '08': 'Aug', 'august': 'Aug',
        '9': 'Sep', '09': 'Sep', 'september': 'Sep',
        '10': 'Oct', 'october': 'Oct',
        '11': 'Nov', 'november': 'Nov',
        '12': 'Dec', 'december': 'Dec',
    }

    def __init__(self, max_authors: int = 3):
        self.max_authors = max_authors

    def format_journal_article(self, metadata: ArticleMetadata, original_number: int) -> FormattedCitation:
        """Format a journal article in Vancouver style."""
        # Generate label
        author_label = metadata.get_first_author_label()
        label = f"[^{author_label}-{metadata.year}-{metadata.pmid}]"

        # Format authors
        authors_str = metadata.format_authors_vancouver(self.max_authors)

        # Format title
        title = metadata.title.strip()
        if not title.endswith('.'):
            title += '.'

        # Journal abbreviation
        journal = metadata.journal_abbreviation or metadata.journal

        # Date
        date_str = self._format_date(metadata.year, metadata.month)

        # Volume/issue/pages
        vol_issue_pages = self._format_volume_issue_pages(metadata.volume, metadata.issue, metadata.pages)

        # Build citation
        citation_parts = [
            authors_str + '.',
            title,
            journal + '.',
            date_str + vol_issue_pages + '.',
        ]
        citation_text = ' '.join(filter(None, citation_parts))

        # Add DOI link
        if metadata.doi:
            doi_url = self._format_doi_url(metadata.doi)
            citation_text += f" [DOI]({doi_url})."

        # Add PMID link
        pmid_url = f"https://pubmed.ncbi.nlm.nih.gov/{metadata.pmid}/"
        citation_text += f" [PMID: {metadata.pmid}]({pmid_url})"

        full_citation = f"{label}: {citation_text}"
        logger.debug(f"Formatted: {label}")

        return FormattedCitation(
            label=label,
            full_citation=full_citation,
            citation_type="journal_article",
            original_number=original_number,
            pmid=metadata.pmid,
            doi=metadata.doi,
        )

    def _format_date(self, year: str, month: str = "") -> str:
        """Format publication date."""
        if not year:
            return ""
        if month:
            month_abbrev = self.MONTH_ABBREV.get(month.lower(), month[:3].title())
            return f"{year} {month_abbrev}"
        return year

    def _format_volume_issue_pages(self, volume: str, issue: str, pages: str) -> str:
        """Format volume, issue, pages."""
        parts = []
        if volume:
            parts.append(f";{volume}")
            if issue:
                parts.append(f"({issue})")
        if pages:
            parts.append(f":{pages}")
        return ''.join(parts)

    def _format_doi_url(self, doi: str) -> str:
        """Format DOI as URL with markdown escaping."""
        doi_clean = doi
        if doi.startswith('http'):
            doi_clean = re.sub(r'^https?://doi\.org/', '', doi)
        # Escape parentheses for markdown
        doi_escaped = doi_clean.replace('(', r'\(').replace(')', r'\)')
        return f"https://doi.org/{doi_escaped}"

    def format_web_article(self, author: str, title: str, source: str, year: str,
                          url: str, original_number: int) -> FormattedCitation:
        """Format a web article citation."""
        author_label = self._generate_author_label(author)
        brief_title = self._generate_brief_title(title)
        label = f"[^{author_label}-{brief_title}-{year}]"

        title_clean = title.strip()
        if not title_clean.endswith('.'):
            title_clean += '.'

        parts = [author + '.', title_clean]
        if source:
            parts.append(source + '.')
        parts.extend([year + '.', f"[Link]({url})"])

        citation_text = ' '.join(filter(None, parts))
        full_citation = f"{label}: {citation_text}"

        return FormattedCitation(
            label=label,
            full_citation=full_citation,
            citation_type="web_article",
            original_number=original_number,
        )

    def _generate_author_label(self, author: str) -> str:
        """Generate author label."""
        if not author:
            return "Unknown"
        parts = author.replace(',', ' ').split()
        if len(parts) >= 2:
            last_name = parts[0]
            initials = ''.join([p[0].upper() for p in parts[1:] if p and p[0].isalpha()])
            return f"{last_name}{initials}"
        return author.replace(' ', '')

    def _generate_brief_title(self, title: str, max_words: int = 3) -> str:
        """Generate brief CamelCase title."""
        words = re.findall(r'\w+', title)
        stop_words = {'the', 'a', 'an', 'of', 'and', 'or', 'in', 'on', 'at', 'to', 'for', 'with', 'by'}
        significant = [w for w in words if w.lower() not in stop_words]
        selected = significant[:max_words] if significant else words[:max_words]
        return ''.join(w.title() for w in selected)

