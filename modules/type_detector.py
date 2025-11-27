"""Citation Type Detector Module - Detects citation types from URLs."""

import re
from enum import Enum
from typing import Optional, List
from loguru import logger


class CitationType(Enum):
    """Supported citation types."""
    JOURNAL_ARTICLE = "journal_article"
    BOOK = "book"
    BOOK_CHAPTER = "book_chapter"
    NEWSPAPER_ARTICLE = "newspaper_article"
    WEBPAGE = "webpage"
    WEB_ARTICLE = "web_article"
    BLOG = "blog"
    PDF_DOCUMENT = "pdf_document"
    UNKNOWN = "unknown"


class CitationTypeDetector:
    """Detects citation types based on URL patterns."""

    PUBMED_PATTERNS = [
        r'pubmed\.ncbi\.nlm\.nih\.gov/(\d+)',
        r'ncbi\.nlm\.nih\.gov/pubmed/(\d+)',
        r'pmc\.ncbi\.nlm\.nih\.gov/articles/(PMC\d+)',
        r'ncbi\.nlm\.nih\.gov/pmc/articles/(PMC\d+)',
    ]
    DOI_PATTERN = r'doi\.org/(10\.\d{4,}/[^\s]+)'

    JOURNAL_DOMAINS = [
        'biomedcentral.com', 'springer.com', 'link.springer.com', 'sciencedirect.com',
        'nature.com', 'cell.com', 'jamanetwork.com', 'nejm.org', 'thelancet.com',
        'bmj.com', 'ahajournals.org', 'wiley.com', 'onlinelibrary.wiley.com',
        'academic.oup.com', 'frontiersin.org', 'mdpi.com', 'plos.org', 'jci.org',
        'jacc.org', 'acc.org', 'arxiv.org', 'medrxiv.org', 'biorxiv.org',
    ]

    NEWSPAPER_DOMAINS = [
        'nytimes.com', 'washingtonpost.com', 'wsj.com', 'usatoday.com',
        'naplesnews.com', 'floridaweekly.com', 'sfchronicle.com', 'latimes.com',
        'chicagotribune.com', 'bostonglobe.com', 'reuters.com', 'apnews.com',
    ]

    def detect_type(self, url: Optional[str], title: Optional[str] = None) -> CitationType:
        """Detect citation type from URL."""
        if not url:
            return CitationType.UNKNOWN

        url_lower = url.lower()

        if self.is_pubmed_url(url):
            return CitationType.JOURNAL_ARTICLE
        if self.extract_doi(url):
            return CitationType.JOURNAL_ARTICLE
        if url_lower.endswith('.pdf') or '/pdf/' in url_lower:
            return CitationType.PDF_DOCUMENT

        for domain in self.JOURNAL_DOMAINS:
            if domain in url_lower:
                return CitationType.JOURNAL_ARTICLE

        for domain in self.NEWSPAPER_DOMAINS:
            if domain in url_lower:
                return CitationType.NEWSPAPER_ARTICLE

        if '/blog/' in url_lower or '/blogs/' in url_lower or 'medium.com' in url_lower:
            return CitationType.BLOG

        return CitationType.WEBPAGE

    def is_pubmed_url(self, url: str) -> bool:
        """Check if URL is PubMed/PMC."""
        for pattern in self.PUBMED_PATTERNS:
            if re.search(pattern, url, re.IGNORECASE):
                return True
        return False

    def extract_pmid(self, url: str) -> Optional[str]:
        """Extract PMID from PubMed URL."""
        for pattern in self.PUBMED_PATTERNS[:2]:
            match = re.search(pattern, url, re.IGNORECASE)
            if match:
                return match.group(1)
        return None

    def extract_pmcid(self, url: str) -> Optional[str]:
        """Extract PMC ID from PMC URL."""
        for pattern in self.PUBMED_PATTERNS[2:]:
            match = re.search(pattern, url, re.IGNORECASE)
            if match:
                return match.group(1)
        return None

    def extract_doi(self, url: str) -> Optional[str]:
        """Extract DOI from URL."""
        match = re.search(self.DOI_PATTERN, url, re.IGNORECASE)
        return match.group(1) if match else None

    def categorize_references(self, references: List) -> dict:
        """Categorize references by type."""
        categorized = {ct: [] for ct in CitationType}
        for ref in references:
            ct = self.detect_type(ref.url, ref.title)
            ref.citation_type = ct.value
            categorized[ct].append(ref)

        for ct, refs in categorized.items():
            if refs:
                logger.info(f"Found {len(refs)} {ct.value} citations")
        return categorized

