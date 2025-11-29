"""Vancouver Formatter Module - Formats citations in Vancouver style."""

import re
from typing import Optional
from dataclasses import dataclass
from loguru import logger

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
        if metadata.pmid:
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

    def format_book_chapter(self, metadata: CrossRefMetadata, original_number: int) -> FormattedCitation:
        """
        Format a book chapter in Vancouver style.
        
        Format: Author(s). Chapter title. In: Editor(s), editor(s). Book Title. 
                Place: Publisher; Year. p. Pages. [DOI](url).
        
        Label format priority:
        1. Starting page number: [^AuthorA-2018-p193]
        2. Brief title (fallback): [^AuthorA-2018-Ageism]
        """
        # Generate label
        author_label = metadata.get_first_author_label()
        
        # Determine label suffix: prefer starting page, fallback to brief title
        if metadata.pages:
            # Extract starting page number (e.g., "193-212" -> "193")
            start_page = metadata.pages.split('-')[0].strip()
            label_suffix = f"p{start_page}"
        else:
            # Fallback: use brief title
            label_suffix = self._generate_brief_title(metadata.title, max_words=2)
        
        label = f"[^{author_label}-{metadata.year}-{label_suffix}]"
        
        # Format authors
        authors_str = metadata.format_authors_vancouver(self.max_authors)
        
        # Format title
        title = metadata.title.strip()
        if not title.endswith('.'):
            title += '.'
        
        # Format editors
        editors_str = metadata.format_editors_vancouver(self.max_authors)
        
        # Book title
        book_title = metadata.book_title or metadata.container_title or ""
        
        # Publisher info
        publisher_info = ""
        if metadata.publisher_location and metadata.publisher:
            publisher_info = f"{metadata.publisher_location}: {metadata.publisher}"
        elif metadata.publisher:
            publisher_info = metadata.publisher
        
        # Build citation parts
        citation_parts = [authors_str + '.', title]
        
        # Add "In:" section
        if editors_str:
            citation_parts.append(f"In: {editors_str}.")
        else:
            citation_parts.append("In:")
        
        # Add book title
        if book_title:
            citation_parts.append(book_title + '.')
        
        # Add publisher and year
        if publisher_info and metadata.year:
            citation_parts.append(f"{publisher_info}; {metadata.year}.")
        elif metadata.year:
            citation_parts.append(f"{metadata.year}.")
        
        # Add pages
        if metadata.pages:
            citation_parts.append(f"p. {metadata.pages}.")
        
        citation_text = ' '.join(filter(None, citation_parts))
        
        # Add DOI link
        if metadata.doi:
            doi_url = self._format_doi_url(metadata.doi)
            citation_text += f" [DOI]({doi_url})"
        
        full_citation = f"{label}: {citation_text}"
        logger.debug(f"Formatted book chapter: {label}")
        
        return FormattedCitation(
            label=label,
            full_citation=full_citation,
            citation_type="book_chapter",
            original_number=original_number,
            doi=metadata.doi,
        )

    def format_crossref_journal_article(self, metadata: CrossRefMetadata, original_number: int) -> FormattedCitation:
        """
        Format a journal article from CrossRef (not in PubMed) in Vancouver style.
        
        Format: Author(s). Title. Journal. Year;Volume(Issue):Pages. [DOI](url).
        
        Label format: [^AuthorA-2024-BriefTitle] (uses title since no PMID)
        """
        # Generate label with brief title (no PMID available)
        author_label = metadata.get_first_author_label()
        brief_title = self._generate_brief_title(metadata.title, max_words=2)
        label = f"[^{author_label}-{metadata.year}-{brief_title}]"
        
        # Format authors
        authors_str = metadata.format_authors_vancouver(self.max_authors)
        
        # Format title
        title = metadata.title.strip()
        if not title.endswith('.'):
            title += '.'
        
        # Journal name
        journal = metadata.container_title or ""
        
        # Date
        date_str = self._format_date(metadata.year, metadata.month)
        
        # Volume/issue/pages
        vol_issue_pages = self._format_volume_issue_pages(metadata.volume, metadata.issue, metadata.pages)
        
        # Build citation
        citation_parts = [authors_str + '.', title]
        if journal:
            citation_parts.append(journal + '.')
        if date_str or vol_issue_pages:
            citation_parts.append(date_str + vol_issue_pages + '.')
        
        citation_text = ' '.join(filter(None, citation_parts))
        
        # Add DOI link
        if metadata.doi:
            doi_url = self._format_doi_url(metadata.doi)
            citation_text += f" [DOI]({doi_url})"
        
        full_citation = f"{label}: {citation_text}"
        logger.debug(f"Formatted CrossRef journal article: {label}")
        
        return FormattedCitation(
            label=label,
            full_citation=full_citation,
            citation_type="journal_article",
            original_number=original_number,
            doi=metadata.doi,
        )

    def format_book(self, metadata: CrossRefMetadata, original_number: int) -> FormattedCitation:
        """
        Format a book in Vancouver style.
        
        Format: Author(s). Book Title. Place: Publisher; Year.
        
        Label format: [^AuthorA-2018-BriefTitle]
        """
        # Generate label with brief title for uniqueness
        author_label = metadata.get_first_author_label()
        brief_title = self._generate_brief_title(metadata.title, max_words=2)
        label = f"[^{author_label}-{metadata.year}-{brief_title}]"
        
        # Format authors (or editors for edited books)
        if metadata.authors:
            authors_str = metadata.format_authors_vancouver(self.max_authors)
        elif metadata.editors:
            authors_str = metadata.format_editors_vancouver(self.max_authors)
        else:
            authors_str = "Unknown"
        
        # Title
        title = metadata.title.strip()
        if not title.endswith('.'):
            title += '.'
        
        # Publisher info
        publisher_info = ""
        if metadata.publisher_location and metadata.publisher:
            publisher_info = f"{metadata.publisher_location}: {metadata.publisher}"
        elif metadata.publisher:
            publisher_info = metadata.publisher
        
        # Build citation
        citation_parts = [authors_str + '.', title]
        
        if publisher_info and metadata.year:
            citation_parts.append(f"{publisher_info}; {metadata.year}.")
        elif metadata.year:
            citation_parts.append(f"{metadata.year}.")
        
        citation_text = ' '.join(filter(None, citation_parts))
        
        # Add DOI link
        if metadata.doi:
            doi_url = self._format_doi_url(metadata.doi)
            citation_text += f" [DOI]({doi_url})"
        
        full_citation = f"{label}: {citation_text}"
        logger.debug(f"Formatted book: {label}")
        
        return FormattedCitation(
            label=label,
            full_citation=full_citation,
            citation_type="book",
            original_number=original_number,
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
        label_year = year if year != "Null_Date" else "ND"
        label = f"[^{author_label}-{brief_title}-{label_year}]"

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

    def format_webpage(
        self, 
        title: str, 
        url: str, 
        source_name: Optional[str],
        original_number: int,
        year: Optional[str] = None,
    ) -> FormattedCitation:
        """
        Format a webpage citation in Vancouver style (Obsidian-friendly compact format).
        
        Full Vancouver format for websites:
        Author/Organization. Title [Internet]. Place: Publisher; Year [cited YYYY Mon DD]. 
        Available from: URL
        
        Obsidian-friendly compact format (what we produce):
        Organization. Title. Year. [Link](URL)
        """
        # If title is truncated (contains ... or …), try to get full title from URL
        if '...' in title or '…' in title:
            url_title = self._extract_title_from_url(url)
            if url_title and len(url_title) > len(title.replace('...', '').replace('…', '')):
                title = url_title
            else:
                # No better title found - remove ellipses anyway (incomplete is better than ellipses)
                title = title.replace('...', '').replace('…', '').rstrip(' -:').strip()
        
        # Extract organization/source from source_name or URL
        org_name = self._extract_organization(source_name, url)
        org_abbrev = self._generate_org_abbreviation(org_name)
        
        # Get full organization name (if we have abbreviation, expand it)
        full_org_name = self._get_org_full_name(org_name) or org_name
        
        # Format organization name: "Full Name (ABBREV)" if abbreviation is different
        if org_abbrev.upper() != full_org_name.upper() and len(org_abbrev) <= 6:
            org_display = f"{full_org_name} ({org_abbrev})"
        else:
            org_display = full_org_name
        
        # Extract year from title or URL if not provided
        if not year:
            year = self._extract_year_from_text(title) or self._extract_year_from_url(url) or "Null_Date"
        
        # Generate brief title for label
        brief_title = self._generate_brief_title(title, max_words=2)
        
        # Create label (ensure abbreviation is uppercase)
        # Use "ND" in label for missing dates, but keep Null_Date in citation text
        org_abbrev_upper = org_abbrev.upper() if len(org_abbrev) <= 6 else org_abbrev
        label_year = year if year != "Null_Date" else "ND"
        label = f"[^{org_abbrev_upper}-{brief_title}-{label_year}]"
        
        # Clean title - ensure it ends with period
        title_clean = title.strip()
        if not title_clean.endswith('.'):
            title_clean += '.'
        
        # Build Obsidian-friendly compact citation
        # Format: Organization (Abbrev). Title. Year. [Link](URL)
        citation_parts = []
        citation_parts.append(f"{org_display}.")
        citation_parts.append(title_clean)
        
        # Always include year (Null_Date for missing dates, for searchability)
        if year:
            citation_parts.append(f"{year}.")
        
        citation_parts.append(f"[Link]({url})")
        
        citation_text = ' '.join(filter(None, citation_parts))
        full_citation = f"{label}: {citation_text}"
        
        logger.debug(f"Formatted webpage: {label}")
        
        return FormattedCitation(
            label=label,
            full_citation=full_citation,
            citation_type="webpage",
            original_number=original_number,
        )

    def format_scraped_webpage(
        self,
        metadata: WebpageMetadata,
        original_number: int,
    ) -> FormattedCitation:
        """
        Format a webpage citation using scraped metadata in Vancouver style.
        
        This produces a proper citation when the webpage has author/organization info.
        
        Format: Authors. Title. Organization/Site. Year. [Link](URL)
        """
        
        # Generate author label
        author_label = metadata.get_first_author_label()
        
        # Create label with year
        year = metadata.year or "Null_Date"
        label_year = year if year != "Null_Date" else "ND"
        label = f"[^{author_label}-{label_year}]"
        
        # Format authors
        authors_str = metadata.format_authors_vancouver(self.max_authors)
        
        # Format title
        title = metadata.title.strip()
        if not title.endswith('.'):
            title += '.'
        
        # Build citation parts
        citation_parts = []
        
        if authors_str:
            citation_parts.append(authors_str + '.')
        else:
            # Use Null_Author placeholder when author is missing
            citation_parts.append('Null_Author.')
        
        citation_parts.append(title)
        
        # Add journal if available (academic sources)
        if metadata.journal:
            journal_text = metadata.journal.strip().rstrip('.')
            citation_parts.append(journal_text + '.')
        # Otherwise add site_name/organization
        elif hasattr(metadata, 'site_name') and metadata.site_name:
            # Get full organization name and abbreviation
            site_name = metadata.site_name.strip()
            full_org_name = self._get_org_full_name(site_name) or site_name
            org_abbrev = self._generate_org_abbreviation(site_name)
            
            # Format: "Full Name (ABBREV)" if abbreviation is different and short
            if org_abbrev.upper() != full_org_name.upper() and len(org_abbrev) <= 6:
                org_display = f"{full_org_name} ({org_abbrev.upper()})"
            else:
                org_display = full_org_name
            
            # Always include organization (even if we have authors)
            citation_parts.append(org_display + '.')
        
        # Date and volume/issue/pages
        date_vol_parts = []
        if metadata.year:
            date_vol_parts.append(metadata.year)
        if metadata.volume:
            date_vol_parts.append(f";{metadata.volume}")
            if metadata.issue:
                date_vol_parts.append(f"({metadata.issue})")
        if metadata.pages:
            date_vol_parts.append(f":{metadata.pages}")
        
        if date_vol_parts:
            citation_parts.append(''.join(date_vol_parts) + '.')
        
        citation_text = ' '.join(filter(None, citation_parts))
        
        # Add DOI if available
        if metadata.doi:
            doi_url = self._format_doi_url(metadata.doi)
            citation_text += f" [DOI]({doi_url})."
        
        # Add link to original page
        citation_text += f" [Link]({metadata.url})"
        
        full_citation = f"{label}: {citation_text}"
        
        logger.debug(f"Formatted scraped webpage: {label}")
        
        return FormattedCitation(
            label=label,
            full_citation=full_citation,
            citation_type="webpage",
            original_number=original_number,
            doi=metadata.doi if metadata.doi else None,
        )

    def format_blog(
        self, 
        title: str, 
        url: str, 
        source_name: Optional[str],
        original_number: int,
        year: Optional[str] = None,
    ) -> FormattedCitation:
        """Format a blog post citation - similar to webpage."""
        # Blogs use same format as webpages
        citation = self.format_webpage(title, url, source_name, original_number, year)
        citation.citation_type = "blog"
        return citation

    def format_newspaper_article(
        self, 
        title: str, 
        url: str, 
        source_name: Optional[str],
        original_number: int,
        year: Optional[str] = None,
    ) -> FormattedCitation:
        """
        Format a newspaper article citation in Vancouver style.
        
        Vancouver format for online newspapers:
        Newspaper Name. Title [Internet]. Year [cited YYYY Mon DD]. 
        Available from: URL
        """
        from datetime import datetime
        
        # Extract newspaper name from source or URL
        newspaper_name = self._extract_newspaper_name(source_name, url)
        newspaper_abbrev = self._generate_newspaper_abbreviation(newspaper_name)
        
        # Extract year from title, URL, or default to Null_Date
        if not year:
            year = self._extract_year_from_text(title) or self._extract_year_from_url(url) or "Null_Date"
        
        # Generate brief title for label
        brief_title = self._generate_brief_title(title, max_words=2)
        
        # Create label (use ND for missing dates in label)
        label_year = year if year != "Null_Date" else "ND"
        label = f"[^{newspaper_abbrev}-{brief_title}-{label_year}]"
        
        # Clean title - remove trailing period for [Internet] addition
        title_clean = title.strip().rstrip('.')
        
        # Get current date for "cited" field
        access_date = datetime.now().strftime("%Y %b %d")
        
        # Build Vancouver-style newspaper citation
        citation_parts = []
        citation_parts.append(f"{newspaper_name}.")
        citation_parts.append(f"{title_clean} [Internet].")
        
        # Always include year (Null_Date for missing dates, for searchability)
        if year:
            citation_parts.append(f"{year}")
        
        citation_parts.append(f"[cited {access_date}].")
        citation_parts.append(f"Available from: {url}")
        
        citation_text = ' '.join(filter(None, citation_parts))
        full_citation = f"{label}: {citation_text}"
        
        logger.debug(f"Formatted newspaper article: {label}")
        
        return FormattedCitation(
            label=label,
            full_citation=full_citation,
            citation_type="newspaper_article",
            original_number=original_number,
        )

    def _extract_newspaper_name(self, source_name: Optional[str], url: str) -> str:
        """Extract newspaper name from source or URL."""
        # Known newspaper mappings
        newspaper_map = {
            'naplesnews': 'Naples Daily News',
            'naples daily news': 'Naples Daily News',
            'floridaweekly': 'Florida Weekly',
            'naples.floridaweekly': 'Naples Florida Weekly',
            'nytimes': 'The New York Times',
            'washingtonpost': 'The Washington Post',
            'wsj': 'The Wall Street Journal',
        }
        
        # Check source name first
        if source_name:
            source_lower = source_name.lower()
            for key, name in newspaper_map.items():
                if key in source_lower:
                    return name
            return source_name
        
        # Fall back to URL parsing
        url_lower = url.lower()
        for key, name in newspaper_map.items():
            if key in url_lower:
                return name
        
        # Extract from domain
        return self._extract_organization(source_name, url)

    def _generate_newspaper_abbreviation(self, newspaper_name: str) -> str:
        """Generate abbreviation for newspaper name."""
        abbreviations = {
            'naples daily news': 'NDN',
            'naples florida weekly': 'NFW',
            'florida weekly': 'FW',
            'the new york times': 'NYT',
            'the washington post': 'WaPo',
            'the wall street journal': 'WSJ',
        }
        
        name_lower = newspaper_name.lower()
        if name_lower in abbreviations:
            return abbreviations[name_lower]
        
        # Generate from words
        words = re.findall(r'\w+', newspaper_name)
        if len(words) <= 2:
            return ''.join(w.title() for w in words)[:10]
        else:
            return ''.join(w[0].upper() for w in words if w.lower() not in {'the', 'of'})[:6]

    def _extract_organization(self, source_name: Optional[str], url: str) -> str:
        """Extract organization name from source name or URL domain."""
        if source_name:
            # Clean up common suffixes
            org = source_name.strip()
            for suffix in ['.com', '.org', '.gov', '.net', '.io', '.edu']:
                if org.lower().endswith(suffix):
                    org = org[:-len(suffix)]
            return org
        
        # Fall back to domain extraction
        import urllib.parse
        try:
            parsed = urllib.parse.urlparse(url)
            domain = parsed.netloc.lower()
            # Remove www. prefix
            if domain.startswith('www.'):
                domain = domain[4:]
            # Get first part of domain
            parts = domain.split('.')
            name = parts[0] if len(parts) >= 2 else domain
            
            # If it looks like an acronym (short, mostly consonants), uppercase it
            # Examples: cbpp, nih, cdc, ama, kff
            if len(name) <= 5 and self._looks_like_acronym(name):
                return name.upper()
            return name.title()
        except:
            return "Unknown Source"
    
    def _looks_like_acronym(self, name: str) -> bool:
        """Check if a name looks like an acronym (few vowels, short)."""
        if len(name) > 6:
            return False
        vowels = set('aeiou')
        vowel_count = sum(1 for c in name.lower() if c in vowels)
        # Acronyms typically have 0-1 vowels (CDC, NIH, CBPP, AMA, KFF)
        # or are very short (CDC = 3 chars with 0 vowels)
        return vowel_count <= 1 or len(name) <= 4

    def _get_org_full_name(self, org_name: str) -> Optional[str]:
        """Get full organization name from abbreviation or partial name."""
        # Reverse mapping: acronym -> full name
        org_mappings = {
            'ama': 'American Medical Association',
            'aamc': 'Association of American Medical Colleges',
            'aha': 'American Hospital Association',
            'cbpp': 'Center on Budget and Policy Priorities',
            'cdc': 'Centers for Disease Control and Prevention',
            'cms': 'Centers for Medicare & Medicaid Services',
            'fda': 'U.S. Food and Drug Administration',
            'nih': 'National Institutes of Health',
            'who': 'World Health Organization',
            'kff': 'Kaiser Family Foundation',
            'actuary.org': 'American Academy of Actuaries',
            'actuary': 'American Academy of Actuaries',
        }
        
        org_lower = org_name.lower().strip()
        
        # Check exact match first
        if org_lower in org_mappings:
            return org_mappings[org_lower]
        
        # Check if it's already a full name (contains common words)
        if any(word in org_lower for word in ['association', 'academy', 'center', 'centers', 'institute', 'foundation']):
            return org_name  # Already full name
        
        # Check partial matches
        for abbrev, full_name in org_mappings.items():
            if abbrev in org_lower or org_lower in abbrev:
                return full_name
        
        return None
    
    def _generate_org_abbreviation(self, org_name: str) -> str:
        """Generate abbreviation for organization name (always uppercase for known acronyms)."""
        # Common abbreviations - these are well-known acronyms
        abbreviations = {
            'american medical association': 'AMA',
            'american hospital association': 'AHA',
            'association of american medical colleges': 'AAMC',
            'center on budget and policy priorities': 'CBPP',
            'centers for disease control': 'CDC',
            'centers for medicare': 'CMS',
            'florida department of health': 'FLDOH',
            'food and drug administration': 'FDA',
            'national institutes of health': 'NIH',
            'world health organization': 'WHO',
            'kaiser family foundation': 'KFF',
            'commonwealth fund': 'CWF',
            'u.s. news': 'USNews',
            'america\'s health rankings': 'AHR',
            'blue zones': 'BlueZones',
            'american academy of actuaries': 'AAA',
        }
        
        org_lower = org_name.lower()
        
        # Check if it's already an acronym (short, uppercase-like)
        if len(org_name) <= 6 and org_name.isupper():
            return org_name  # Already uppercase acronym
        
        # Check known abbreviations
        for key, abbrev in abbreviations.items():
            if key in org_lower:
                return abbrev
        
        # Check reverse mapping (if it's already abbreviated)
        full_name = self._get_org_full_name(org_name)
        if full_name:
            # Find the abbreviation for the full name
            for key, abbrev in abbreviations.items():
                if key in full_name.lower():
                    return abbrev
        
        # Generate abbreviation from words
        words = re.findall(r'\w+', org_name)
        # Filter out common words that don't contribute to acronyms
        stop_words = {'the', 'of', 'and', 'for', 'on', 'in', 'a', 'an', 'inc', 'llc', 'corp'}
        significant_words = [w for w in words if w.lower() not in stop_words]
        
        if len(significant_words) == 0:
            significant_words = words  # Fall back to all words
        
        if len(significant_words) == 1:
            # Single word - use as-is (capitalized, max 12 chars)
            return significant_words[0].title()[:12]
        elif len(significant_words) == 2:
            # 2 words - use initials if both are long, otherwise concatenate
            if all(len(w) > 3 for w in significant_words):
                return ''.join(w[0].upper() for w in significant_words)
            return ''.join(w.title() for w in significant_words)[:12]
        else:
            # 3+ words - use initials (uppercase acronym)
            return ''.join(w[0].upper() for w in significant_words)[:8]

    def _extract_year_from_text(self, text: str) -> Optional[str]:
        """Extract 4-digit year from text, avoiding subject-matter years.
        
        Skips years that appear to be about subject matter rather than publication:
        - "in 2025" (projections)
        - "for 2025" (forecasts)  
        - "by 2025" (deadlines)
        - "through 2025" (time ranges)
        """
        # Skip years that are clearly subject matter, not publication dates
        subject_year_patterns = [
            r'\b(?:in|for|by|through|until|to)\s+(20\d{2})\b',
            r'\b(20\d{2})\s*[-–—]\s*20\d{2}\b',  # Year ranges like "2025-2035"
        ]
        
        text_clean = text
        for pattern in subject_year_patterns:
            # Remove subject-matter years from consideration
            text_clean = re.sub(pattern, '', text_clean, flags=re.IGNORECASE)
        
        # Now look for remaining years
        match = re.search(r'\b(20\d{2}|19\d{2})\b', text_clean)
        return match.group(1) if match else None

    def _extract_year_from_url(self, url: str) -> Optional[str]:
        """Extract year from URL path - only from date-like patterns.
        
        Only matches paths that look like publication dates:
        - /2024/05/12/ (full date paths)
        - /2024/05/ (year-month paths)
        - /2024/ (year-only paths at start of content path)
        - /2024-05-12/ (date in filename)
        
        Skips years embedded in article slugs (likely subject matter).
        """
        # Match date-like patterns: /2024/05/ or /2024-05-12
        match = re.search(r'/(\d{4})/\d{2}/', url)
        if match:
            return match.group(1)
        
        match = re.search(r'/(\d{4})-\d{2}-\d{2}', url)
        if match:
            return match.group(1)
        
        # Match year-only at start of content path (e.g., /2019/external-reference...)
        # This pattern requires the year to be followed by a content slug (not just numbers)
        # Match patterns like: domain.com/2019/title or domain.com/news/2019/title
        match = re.search(r'/(\d{4})/[a-z]', url, re.IGNORECASE)
        if match:
            year = match.group(1)
            if 1990 <= int(year) <= 2030:  # Reasonable year range
                return year
        
        return None
    
    def _extract_title_from_url(self, url: str) -> Optional[str]:
        """Extract title from URL slug (last path segment)."""
        import urllib.parse
        try:
            parsed = urllib.parse.urlparse(url)
            domain = parsed.netloc.lower()
            
            # Skip certain domains where URL slugs produce garbage
            skip_domains = ['linkedin.com', 'twitter.com', 'x.com', 'facebook.com']
            if any(d in domain for d in skip_domains):
                return None
            
            path = parsed.path.strip('/')
            if not path:
                return None
            
            # Get last path segment
            slug = path.split('/')[-1]
            
            # Skip if slug contains obvious IDs (long numbers, UUIDs)
            if re.search(r'\d{10,}|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}', slug, re.IGNORECASE):
                return None
            
            # Remove file extension if present
            slug = re.sub(r'\.\w+$', '', slug)
            
            # Convert slug to title (replace hyphens/underscores with spaces)
            title = slug.replace('-', ' ').replace('_', ' ')
            
            # Title case, but keep short words lowercase
            words = title.split()
            if not words:
                return None
            
            stop_words = {'a', 'an', 'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'}
            titled_words = []
            for i, word in enumerate(words):
                if i == 0 or word.lower() not in stop_words:
                    titled_words.append(word.capitalize())
                else:
                    titled_words.append(word.lower())
            
            result = ' '.join(titled_words)
            
            # Only return if it's a reasonable title (more than 3 words)
            if len(words) >= 3:
                return result
            return None
        except:
            return None

