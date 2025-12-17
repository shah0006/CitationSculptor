"""Base Formatter Module - Abstract base class for citation formatters."""

import re
from abc import ABC, abstractmethod
from typing import Optional, List, Union
from dataclasses import dataclass

from .pubmed_client import ArticleMetadata, CrossRefMetadata, WebpageMetadata


@dataclass
class FormattedCitation:
    """A fully formatted citation."""
    label: str  # e.g., "[^SmithJA-2024-12345678]"
    full_citation: str  # Complete formatted citation
    citation_type: str
    original_number: int
    pmid: Optional[str] = None
    doi: Optional[str] = None
    style: str = "vancouver"  # Citation style used


class BaseFormatter(ABC):
    """
    Abstract base class for citation formatters.
    
    All citation style formatters (Vancouver, APA, MLA, etc.) should inherit
    from this class and implement the abstract methods.
    """
    
    STYLE_NAME: str = "base"
    
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
    
    MONTH_FULL = {
        '1': 'January', '01': 'January', 'january': 'January',
        '2': 'February', '02': 'February', 'february': 'February',
        '3': 'March', '03': 'March', 'march': 'March',
        '4': 'April', '04': 'April', 'april': 'April',
        '5': 'May', '05': 'May', 'may': 'May',
        '6': 'June', '06': 'June', 'june': 'June',
        '7': 'July', '07': 'July', 'july': 'July',
        '8': 'August', '08': 'August', 'august': 'August',
        '9': 'September', '09': 'September', 'september': 'September',
        '10': 'October', 'october': 'October',
        '11': 'November', 'november': 'November',
        '12': 'December', 'december': 'December',
    }

    def __init__(self, max_authors: int = 3):
        self.max_authors = max_authors

    # =========================================================================
    # Abstract methods - must be implemented by each style
    # =========================================================================
    
    @abstractmethod
    def format_journal_article(self, metadata: ArticleMetadata, original_number: int) -> FormattedCitation:
        """Format a journal article citation."""
        pass
    
    @abstractmethod
    def format_book_chapter(self, metadata: CrossRefMetadata, original_number: int) -> FormattedCitation:
        """Format a book chapter citation."""
        pass
    
    @abstractmethod
    def format_book(self, metadata: CrossRefMetadata, original_number: int) -> FormattedCitation:
        """Format a book citation."""
        pass
    
    @abstractmethod
    def format_webpage(
        self, 
        title: str, 
        url: str, 
        source_name: Optional[str],
        original_number: int,
        year: Optional[str] = None,
        is_evergreen: bool = False,
    ) -> FormattedCitation:
        """Format a webpage citation."""
        pass
    
    def format_preprint(self, metadata, original_number: int) -> FormattedCitation:
        """
        Format an arXiv preprint citation.
        Default implementation - subclasses can override for style-specific formatting.
        """
        # Import here to avoid circular imports
        from .arxiv_client import ArxivMetadata
        
        if not isinstance(metadata, ArxivMetadata):
            raise TypeError("Expected ArxivMetadata")
        
        author_label = metadata.get_first_author_label()
        label = self.generate_label(author_label, metadata.year, f"arXiv{metadata.arxiv_id.split('.')[-1][:5]}")
        
        # Format authors based on style
        authors_str = self._format_authors_vancouver(metadata.authors, self.max_authors)
        
        title = metadata.title.strip().rstrip('.')
        
        # Build citation
        parts = [f"{authors_str}.", f"{title}."]
        parts.append(f"arXiv:{metadata.arxiv_id} [Preprint].")
        parts.append(f"{metadata.year}.")
        
        if metadata.primary_category:
            parts.append(f"[{metadata.primary_category}]")
        
        citation_text = ' '.join(filter(None, parts))
        
        # Add links
        if metadata.abs_url:
            citation_text += f" Available from: {metadata.abs_url}"
        
        full_citation = f"{label}: {citation_text}"
        
        return FormattedCitation(
            label=label,
            full_citation=full_citation,
            citation_type="preprint",
            original_number=original_number,
            doi=metadata.doi,
            style=self.STYLE_NAME,
        )
    
    def format_biorxiv_preprint(self, metadata, original_number: int) -> FormattedCitation:
        """
        Format a bioRxiv/medRxiv preprint citation.
        Default implementation - subclasses can override for style-specific formatting.
        """
        # Import here to avoid circular imports
        from .preprint_client import PreprintMetadata
        
        if not isinstance(metadata, PreprintMetadata):
            raise TypeError("Expected PreprintMetadata")
        
        author_label = metadata.get_first_author_label()
        doi_suffix = metadata.doi.split('/')[-1][:8] if '/' in metadata.doi else metadata.doi[:8]
        label = self.generate_label(author_label, metadata.year, doi_suffix)
        
        # Format authors
        authors_str = self._format_authors_vancouver(metadata.authors_list, self.max_authors)
        
        title = metadata.title.strip().rstrip('.')
        server_name = "bioRxiv" if metadata.server == "biorxiv" else "medRxiv"
        
        # Build citation
        parts = [f"{authors_str}.", f"{title}."]
        parts.append(f"{server_name} [Preprint].")
        parts.append(f"{metadata.date}.")
        
        citation_text = ' '.join(filter(None, parts))
        
        # Add DOI link
        doi_url = self._format_doi_url(metadata.doi)
        citation_text += f" [DOI]({doi_url})."
        
        # Note if published
        if metadata.published_doi:
            citation_text += f" Published in: {metadata.published_journal or 'journal'}."
        
        full_citation = f"{label}: {citation_text}"
        
        return FormattedCitation(
            label=label,
            full_citation=full_citation,
            citation_type="preprint",
            original_number=original_number,
            doi=metadata.doi,
            style=self.STYLE_NAME,
        )
    
    def format_book_from_isbn(self, metadata, original_number: int) -> FormattedCitation:
        """
        Format a book citation from ISBN lookup.
        Default implementation - subclasses can override for style-specific formatting.
        """
        # Import here to avoid circular imports
        from .book_client import BookMetadata
        
        if not isinstance(metadata, BookMetadata):
            raise TypeError("Expected BookMetadata")
        
        author_label = metadata.get_first_author_label()
        brief_title = self._generate_brief_title(metadata.title, max_words=2)
        label = self.generate_label(author_label, metadata.year, brief_title)
        
        # Format authors
        authors_str = self._format_authors_vancouver(metadata.authors, self.max_authors) if metadata.authors else "Unknown"
        
        title = metadata.title.strip().rstrip('.')
        
        # Build citation
        parts = [f"{authors_str}.", f"{title}."]
        
        if metadata.edition:
            parts.append(f"{metadata.edition}.")
        
        if metadata.publisher:
            parts.append(f"{metadata.publisher};")
        
        if metadata.year:
            parts.append(f"{metadata.year}.")
        
        if metadata.page_count:
            parts.append(f"{metadata.page_count} p.")
        
        citation_text = ' '.join(filter(None, parts))
        
        # Add ISBN
        citation_text += f" ISBN: {metadata.display_isbn}."
        
        full_citation = f"{label}: {citation_text}"
        
        return FormattedCitation(
            label=label,
            full_citation=full_citation,
            citation_type="book",
            original_number=original_number,
            style=self.STYLE_NAME,
        )

    # =========================================================================
    # Common helper methods shared by all formatters
    # =========================================================================
    
    def generate_label(
        self, 
        author_label: str, 
        year: str, 
        identifier: str,
        suffix: Optional[str] = None
    ) -> str:
        """
        Generate the unique citation label/tag.
        
        All styles use the same semantic label format for uniqueness:
        [^AuthorY-Year-Identifier] or [^AuthorY-Year-Suffix]
        """
        year_part = year if year and year != "Null_Date" else "ND"
        if suffix:
            return f"[^{author_label}-{year_part}-{suffix}]"
        return f"[^{author_label}-{year_part}-{identifier}]"
    
    def _format_doi_url(self, doi: str) -> str:
        """Format DOI as URL with markdown escaping."""
        doi_clean = doi
        if doi.startswith('http'):
            doi_clean = re.sub(r'^https?://doi\.org/', '', doi)
        # Escape parentheses for markdown
        doi_escaped = doi_clean.replace('(', r'\(').replace(')', r'\)')
        return f"https://doi.org/{doi_escaped}"
    
    def _generate_author_label(self, author: str) -> str:
        """Generate author label for citation key."""
        if not author:
            return "Unknown"
        parts = author.replace(',', ' ').split()
        if len(parts) >= 2:
            last_name = parts[0]
            initials = ''.join([p[0].upper() for p in parts[1:] if p and p[0].isalpha()])
            return f"{last_name}{initials}"
        return author.replace(' ', '')
    
    def _generate_brief_title(self, title: str, max_words: int = 3) -> str:
        """Generate brief CamelCase title for label."""
        words = re.findall(r'\w+', title)
        stop_words = {'the', 'a', 'an', 'of', 'and', 'or', 'in', 'on', 'at', 'to', 'for', 'with', 'by'}
        significant = [w for w in words if w.lower() not in stop_words]
        selected = significant[:max_words] if significant else words[:max_words]
        return ''.join(w.title() for w in selected)
    
    def _extract_year_from_text(self, text: str) -> Optional[str]:
        """Extract 4-digit year from text, avoiding subject-matter years."""
        subject_year_patterns = [
            r'\b(?:in|for|by|through|until|to)\s+(20\d{2})\b',
            r'\b(20\d{2})\s*[-–—]\s*20\d{2}\b',
        ]
        
        text_clean = text
        for pattern in subject_year_patterns:
            text_clean = re.sub(pattern, '', text_clean, flags=re.IGNORECASE)
        
        match = re.search(r'\b(20\d{2}|19\d{2})\b', text_clean)
        return match.group(1) if match else None
    
    def _extract_year_from_url(self, url: str) -> Optional[str]:
        """Extract year from URL path."""
        match = re.search(r'/(\d{4})/\d{2}/', url)
        if match:
            return match.group(1)
        
        match = re.search(r'/(\d{4})-\d{2}-\d{2}', url)
        if match:
            return match.group(1)
        
        match = re.search(r'\.(\d{4})(\d{2})(\d{2})\.\d+', url)
        if match:
            year = match.group(1)
            month = match.group(2)
            day = match.group(3)
            if 1990 <= int(year) <= 2030 and 1 <= int(month) <= 12 and 1 <= int(day) <= 31:
                return year
        
        match = re.search(r'/(\d{4})/[a-z]', url, re.IGNORECASE)
        if match:
            year = match.group(1)
            if 1990 <= int(year) <= 2030:
                return year
        
        return None
    
    def _extract_organization(self, source_name: Optional[str], url: str) -> str:
        """Extract organization name from source name or URL domain."""
        if source_name:
            org = source_name.strip()
            for suffix in ['.com', '.org', '.gov', '.net', '.io', '.edu']:
                if org.lower().endswith(suffix):
                    org = org[:-len(suffix)]
            return org
        
        import urllib.parse
        try:
            parsed = urllib.parse.urlparse(url)
            domain = parsed.netloc.lower()
            if domain.startswith('www.'):
                domain = domain[4:]
            parts = domain.split('.')
            name = parts[0] if len(parts) >= 2 else domain
            
            if len(name) <= 5 and self._looks_like_acronym(name):
                return name.upper()
            return name.title()
        except (ValueError, AttributeError, IndexError):
            return "Unknown Source"
    
    def _looks_like_acronym(self, name: str) -> bool:
        """Check if a name looks like an acronym."""
        if len(name) > 6:
            return False
        vowels = set('aeiou')
        vowel_count = sum(1 for c in name.lower() if c in vowels)
        return vowel_count <= 1 or len(name) <= 4
    
    def _generate_org_abbreviation(self, org_name: str) -> str:
        """Generate abbreviation for organization name."""
        abbreviations = {
            'american medical association': 'AMA',
            'american hospital association': 'AHA',
            'centers for disease control': 'CDC',
            'centers for medicare': 'CMS',
            'national institutes of health': 'NIH',
            'world health organization': 'WHO',
            'kaiser family foundation': 'KFF',
        }
        
        org_lower = org_name.lower()
        
        if len(org_name) <= 6 and org_name.isupper():
            return org_name
        
        for key, abbrev in abbreviations.items():
            if key in org_lower:
                return abbrev
        
        words = re.findall(r'\w+', org_name)
        stop_words = {'the', 'of', 'and', 'for', 'on', 'in', 'a', 'an'}
        significant_words = [w for w in words if w.lower() not in stop_words]
        
        if len(significant_words) == 0:
            significant_words = words
        
        if len(significant_words) == 1:
            return significant_words[0].title()[:12]
        elif len(significant_words) == 2:
            if all(len(w) > 3 for w in significant_words):
                return ''.join(w[0].upper() for w in significant_words)
            return ''.join(w.title() for w in significant_words)[:12]
        else:
            return ''.join(w[0].upper() for w in significant_words)[:8]

    # =========================================================================
    # Author formatting utilities
    # =========================================================================
    
    def _format_authors_list(
        self, 
        authors: List[str], 
        max_authors: int,
        style: str = "vancouver"
    ) -> str:
        """
        Format author list according to style.
        
        Styles:
        - vancouver: Smith JA, Jones B, Brown C, et al
        - apa: Smith, J. A., Jones, B., & Brown, C.
        - mla: Smith, John A., et al.
        - chicago: John A. Smith, Bob Jones, and Carol Brown
        - harvard: Smith, J.A., Jones, B. and Brown, C.
        - ieee: J. A. Smith, B. Jones, and C. Brown
        """
        if not authors:
            return ""
        
        if style == "apa":
            return self._format_authors_apa(authors, max_authors)
        elif style == "mla":
            return self._format_authors_mla(authors, max_authors)
        elif style == "chicago":
            return self._format_authors_chicago(authors, max_authors)
        elif style == "harvard":
            return self._format_authors_harvard(authors, max_authors)
        elif style == "ieee":
            return self._format_authors_ieee(authors, max_authors)
        else:  # vancouver
            return self._format_authors_vancouver(authors, max_authors)
    
    def _format_authors_vancouver(self, authors: List[str], max_authors: int = 3) -> str:
        """Vancouver: Smith JA, Jones B, et al"""
        if not authors:
            return ""
        if len(authors) <= max_authors:
            return ', '.join(authors)
        return ', '.join(authors[:max_authors]) + ', et al'
    
    def _format_authors_apa(self, authors: List[str], max_authors: int = 20) -> str:
        """APA 7th: Smith, J. A., Jones, B., & Brown, C."""
        if not authors:
            return ""
        
        def format_one(author: str) -> str:
            parts = author.replace(',', ' ').split()
            if len(parts) >= 2:
                last = parts[0]
                initials = ' '.join([f"{p[0]}." for p in parts[1:] if p])
                return f"{last}, {initials}"
            return author
        
        formatted = [format_one(a) for a in authors]
        
        if len(formatted) == 1:
            return formatted[0]
        elif len(formatted) == 2:
            return f"{formatted[0]} & {formatted[1]}"
        elif len(formatted) <= max_authors:
            return ', '.join(formatted[:-1]) + ', & ' + formatted[-1]
        else:
            # APA 7: First 19 authors, ..., last author
            return ', '.join(formatted[:19]) + ', ... ' + formatted[-1]
    
    def _format_authors_mla(self, authors: List[str], max_authors: int = 3) -> str:
        """MLA 9th: Smith, John A., et al."""
        if not authors:
            return ""
        
        def format_first(author: str) -> str:
            # First author: Last, First Middle
            parts = author.replace(',', ' ').split()
            if len(parts) >= 2:
                return f"{parts[0]}, {' '.join(parts[1:])}"
            return author
        
        def format_other(author: str) -> str:
            # Other authors: First Middle Last
            parts = author.replace(',', ' ').split()
            if len(parts) >= 2:
                return f"{' '.join(parts[1:])} {parts[0]}"
            return author
        
        if len(authors) == 1:
            return format_first(authors[0])
        elif len(authors) == 2:
            return f"{format_first(authors[0])}, and {format_other(authors[1])}"
        elif len(authors) <= max_authors:
            middle = ', '.join([format_other(a) for a in authors[1:-1]])
            if middle:
                return f"{format_first(authors[0])}, {middle}, and {format_other(authors[-1])}"
            return f"{format_first(authors[0])}, and {format_other(authors[-1])}"
        else:
            return f"{format_first(authors[0])}, et al."
    
    def _format_authors_chicago(self, authors: List[str], max_authors: int = 10) -> str:
        """Chicago: John A. Smith, Bob Jones, and Carol Brown"""
        if not authors:
            return ""
        
        def format_name(author: str) -> str:
            # Chicago bibliography: First Middle Last
            parts = author.replace(',', ' ').split()
            if len(parts) >= 2:
                return f"{' '.join(parts[1:])} {parts[0]}"
            return author
        
        formatted = [format_name(a) for a in authors]
        
        if len(formatted) == 1:
            return formatted[0]
        elif len(formatted) == 2:
            return f"{formatted[0]} and {formatted[1]}"
        elif len(formatted) <= max_authors:
            return ', '.join(formatted[:-1]) + ', and ' + formatted[-1]
        else:
            return ', '.join(formatted[:7]) + ', et al.'
    
    def _format_authors_harvard(self, authors: List[str], max_authors: int = 3) -> str:
        """Harvard: Smith, J.A., Jones, B. and Brown, C."""
        if not authors:
            return ""
        
        def format_one(author: str) -> str:
            parts = author.replace(',', ' ').split()
            if len(parts) >= 2:
                last = parts[0]
                initials = '.'.join([p[0] for p in parts[1:] if p]) + '.'
                return f"{last}, {initials}"
            return author
        
        formatted = [format_one(a) for a in authors]
        
        if len(formatted) == 1:
            return formatted[0]
        elif len(formatted) == 2:
            return f"{formatted[0]} and {formatted[1]}"
        elif len(formatted) <= max_authors:
            return ', '.join(formatted[:-1]) + ' and ' + formatted[-1]
        else:
            return f"{formatted[0]} et al."
    
    def _format_authors_ieee(self, authors: List[str], max_authors: int = 6) -> str:
        """IEEE: J. A. Smith, B. Jones, and C. Brown"""
        if not authors:
            return ""
        
        def format_one(author: str) -> str:
            parts = author.replace(',', ' ').split()
            if len(parts) >= 2:
                initials = ' '.join([f"{p[0]}." for p in parts[1:] if p])
                return f"{initials} {parts[0]}"
            return author
        
        formatted = [format_one(a) for a in authors]
        
        if len(formatted) == 1:
            return formatted[0]
        elif len(formatted) == 2:
            return f"{formatted[0]} and {formatted[1]}"
        elif len(formatted) <= max_authors:
            return ', '.join(formatted[:-1]) + ', and ' + formatted[-1]
        else:
            return formatted[0] + ' et al.'

