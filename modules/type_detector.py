"""Citation Type Detector Module - Detects citation types from URLs."""

import re
from enum import Enum
from typing import Optional, List, Dict, Any
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
    
    # DOI patterns - matches doi.org URLs and embedded DOIs in publisher URLs
    # Note: DOIs contain registrant/suffix separated by /. We need to stop before
    # trailing URL paths like /full, /abstract, /pdf, etc.
    DOI_PATTERNS = [
        r'doi\.org/(10\.\d{4,}/[^\s\)\]/\?]+(?:/[^\s\)\]/\?]+)?)',  # doi.org/10.xxxx/yyy or 10.xxxx/yyy/zzz
        r'/doi/(?:abs(?:tract)?/|full/)?(10\.\d{4,}/[^\s\)\]/\?]+(?:/[^\s\)\]/\?]+)?)',  # /doi/10.xxxx or /doi/abs/10.xxxx (AHA, OUP)
        r'/articles?/(10\.\d{4,}/[^\s\)\]/\?]+(?:/[^\s\)\]/\?]+)?)', # /article/10.xxxx/... (BMC, Springer, Frontiers)
        r'/chapter/(10\.\d{4,}/[^\s\)\]/\?]+(?:/[^\s\)\]/\?]+)?)',  # /chapter/10.xxxx/... (Springer book chapters)
        r'/(10\.\d{4,9}/[A-Za-z0-9\.\-_]+)(?:/(?:pdf|full|abstract|html))?(?:\?|$)',  # Generic DOI in path (IMR Press, etc.)
    ]
    
    # URL path suffixes that are NOT part of DOIs - used to strip trailing paths
    DOI_TRAILING_PATHS = ['/full', '/abstract', '/pdf', '/html', '/epdf', '/summary', '/references']

    # Elsevier/ScienceDirect Publisher Item Identifier (PII) patterns.
    # Example: https://www.sciencedirect.com/science/article/pii/S0735109720356412
    # Elsevier serial PIIs are commonly: S + 16 digits (ISSN8 + YY + 6-digit item code)
    PII_PATTERNS = [
        r'/pii/([A-Z]\d{16})(?:[/?]|$)',
        # Fallback: capture any plausible PII-like token after /pii/
        r'/pii/([A-Z0-9]{12,32})(?:[/?]|$)',
    ]

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
        """Extract DOI from URL.
        
        Handles various formats:
        - doi.org/10.xxxx/... 
        - publisher.com/doi/10.xxxx/...
        - publisher.com/articles/10.xxxx/...
        - nature.com/articles/article_id (converts to 10.1038/article_id)
        
        Also cleans up:
        - Query parameters (?key=value)
        - Trailing punctuation
        - OUP-style article IDs (e.g., /7236864 after DOI in academic.oup.com URLs)
        """
        # Special handling for MDPI URLs
        # Format: mdpi.com/1422-0067/26/2/535 → DOI: 10.3390/ijms26020535
        # MDPI uses ISSN in URL, maps to journal abbreviation in DOI
        mdpi_match = re.search(r'mdpi\.com/(\d{4}-\d{4})/(\d+)/(\d+)/(\d+)', url, re.IGNORECASE)
        if mdpi_match:
            issn, volume, issue, article = mdpi_match.groups()
            # Map ISSN to journal abbreviation
            mdpi_journals = {
                '1422-0067': 'ijms',  # Int J Mol Sci
                '2073-4409': 'cells',
                '1999-4923': 'pharmaceutics',
                '2072-6643': 'nu',  # Nutrients
                '2077-0383': 'jcm',  # J Clin Med
                '1424-8220': 'sensors',
                '2076-3417': 'app',  # Applied Sciences
                '1420-3049': 'molecules',
            }
            journal_abbrev = mdpi_journals.get(issn, issn.replace('-', ''))
            # Format: 10.3390/ijms26020535 (volume + padded issue + article)
            doi = f"10.3390/{journal_abbrev}{volume}{issue.zfill(2)}{article.zfill(4)}"
            return doi
        
        # Special handling for Nature.com URLs
        # Format: nature.com/articles/s41591-019-0675-0 → DOI: 10.1038/s41591-019-0675-0
        nature_match = re.search(r'nature\.com/articles/([a-z]\d+[-\w]+)', url, re.IGNORECASE)
        if nature_match:
            article_id = nature_match.group(1)
            return f'10.1038/{article_id}'
        
        for pattern in self.DOI_PATTERNS:
            match = re.search(pattern, url, re.IGNORECASE)
            if match:
                doi = match.group(1)
                
                # Remove query parameters (e.g., ?url_ver=Z39.88-2003&rfr_id=...)
                doi = re.sub(r'\?.*$', '', doi)
                
                # Clean up trailing punctuation/parentheses
                doi = re.sub(r'[\)\]\s]+$', '', doi)
                
                # Remove common URL path suffixes that are NOT part of DOIs
                # e.g., /full, /abstract, /pdf, /html
                for suffix in self.DOI_TRAILING_PATHS:
                    if doi.lower().endswith(suffix.lower().lstrip('/')):
                        doi = doi[:-len(suffix.lstrip('/'))]
                        # Also remove trailing / if present
                        doi = doi.rstrip('/')
                        break
                
                # Only for OUP URLs: remove trailing numeric article ID
                # OUP format: /doi/10.1093/journal/article_id/PAGE_NUMBER
                # The page number is NOT part of the DOI
                if 'academic.oup.com' in url.lower():
                    # Remove trailing /digits if preceded by a non-digit DOI suffix
                    # e.g., "10.1093/jeea/jvad044/7236864" -> "10.1093/jeea/jvad044"
                    doi = re.sub(r'(/[a-zA-Z][^/]*)/\d+$', r'\1', doi)
                
                return doi
        return None

    def extract_pii(self, url: str) -> Optional[str]:
        """Extract a publisher item identifier (PII) from a URL.
        
        This primarily targets Elsevier/ScienceDirect URLs of the form:
            .../pii/S########YY######
        where the captured token is often useful for PubMed lookups when
        DOI extraction/scraping fails.
        """
        if not url:
            return None
        for pattern in self.PII_PATTERNS:
            match = re.search(pattern, url, re.IGNORECASE)
            if match:
                pii = (match.group(1) or '').strip().upper()
                # Basic sanity checks
                if len(pii) >= 12 and re.match(r'^[A-Z0-9]+$', pii):
                    return pii
        return None

    def format_elsevier_pii(self, pii: str) -> Optional[str]:
        """Format an Elsevier *serial* PII to the common hyphen/parentheses form.
        
        Converts:
            S0735109720356412
        to:
            S0735-1097(20)35641-2
        
        Returns None if the PII does not match the serial pattern.
        """
        if not pii:
            return None
        pii = pii.strip().upper()
        m = re.fullmatch(r'S(\d{8})(\d{2})(\d{6})', pii)
        if not m:
            return None
        issn8, yy, rest6 = m.groups()
        return f"S{issn8[:4]}-{issn8[4:]}({yy}){rest6[:5]}-{rest6[5:]}"

    def strip_proxy_url(self, url: Optional[str]) -> str:
        """Remove institutional EZProxy wrapper from a URL, returning the canonical form.

        EZProxy rewrites domains by replacing dots with hyphens and appending
        `.proxy.INSTITUTION.edu`. For example:
            doi.org         -> doi-org.proxy.lib.ohio-state.edu
            www.scopus.com  -> www-scopus-com.proxy.lib.ohio-state.edu

        This method detects the pattern and reverses the transformation.

        Args:
            url: Any URL, possibly proxy-wrapped.

        Returns:
            Canonical URL with proxy wrapper removed, or original URL if not proxied.
            Returns empty string for None/empty input.
        """
        if not url:
            return ""

        # EZProxy pattern: scheme://DOMAIN-WITH-HYPHENS.proxy.INSTITUTION.TLD/path
        # The subdomain before ".proxy." represents the original domain with dots->hyphens
        match = re.match(
            r'^(https?://)([a-zA-Z0-9-]+)\.proxy\.[a-zA-Z0-9.-]+(/.*)?$',
            url
        )
        if not match:
            return url

        scheme = match.group(1)          # "https://"
        hyphenated_domain = match.group(2)  # "doi-org" or "www-sciencedirect-com"
        path = match.group(3) or ""      # "/10.1056/..." or "/science/article/..."

        # Convert hyphens back to dots to reconstruct the original domain.
        # Heuristic: the hyphenated segment is the original domain with dots replaced.
        canonical_domain = hyphenated_domain.replace('-', '.')

        return f"{scheme}{canonical_domain}{path}"

    def parse_scholar_lookup_url(self, url: Optional[str]) -> Optional[Dict[str, Any]]:
        """Parse a Google Scholar scholar_lookup URL, extracting title, year, and authors.

        Scholar lookup URLs embed structured citation metadata as query parameters.
        This method extracts that data for use in PubMed/CrossRef title searches,
        which is significantly more accurate than passing the raw URL as a title.

        Args:
            url: A Google Scholar URL (must contain /scholar_lookup path).

        Returns:
            Dict with keys:
              - "title" (str): URL-decoded article title
              - "year"  (str | None): Publication year, or None if absent
              - "authors" (List[str]): URL-decoded author names (may be empty)
            Returns None if:
              - URL is not a scholar_lookup URL
              - Decoded title has fewer than 4 words (too ambiguous for reliable search)
              - URL is empty or None
        """
        if not url:
            return None

        # Must be a scholar_lookup URL (not a generic Scholar search)
        if 'scholar.google.com/scholar_lookup' not in url:
            return None

        from urllib.parse import urlparse, parse_qs, unquote_plus

        parsed = urlparse(url)
        params = parse_qs(parsed.query, keep_blank_values=False)

        # Extract title (first value if present)
        title_raw = params.get('title', [None])[0]
        if not title_raw:
            return None
        title = unquote_plus(title_raw).strip()

        # Reject titles that are too short to be useful for search
        if len(title.split()) < 3:
            return None

        # Extract year (optional)
        year_raw = params.get('publication_year', [None])[0]
        year = year_raw.strip() if year_raw else None

        # Extract authors (there may be multiple 'author' params)
        authors = [unquote_plus(a).strip() for a in params.get('author', [])]

        return {
            "title": title,
            "year": year,
            "authors": authors,
        }

    def extract_scopus_eid(self, url: Optional[str]) -> Optional[str]:
        """Extract a Scopus Electronic ID (EID) from a Scopus or ScienceDirect URL.

        Scopus EIDs have the format "2-s2.0-{digits}" and appear in:
        - Scopus record URLs: scopus.com/inward/record.url?eid=2-s2.0-85051788505
        - ScienceDirect PDF URLs: /pdfft?pid=1-s2.0-85051788505-main.pdf
          (only when the numeric suffix is all digits -- PII-format pids are excluded)

        EIDs can be resolved to DOI/PMID via the OpenAlex API (free, no key required):
        GET https://api.openalex.org/works?filter=ids.scopus:{eid}

        Args:
            url: Any URL, possibly containing a Scopus EID.

        Returns:
            Normalized EID string (e.g., "2-s2.0-85051788505") or None.
        """
        if not url:
            return None

        from urllib.parse import urlparse, parse_qs

        # Path 1: Scopus record URL -- eid query param
        # Handles both direct and proxy-wrapped Scopus URLs
        if 'scopus' in url.lower():
            parsed = urlparse(url)
            params = parse_qs(parsed.query)
            eid = params.get('eid', [None])[0]
            if eid and re.match(r'^2-s2\.0-\d+$', eid):
                return eid

        # Path 2: ScienceDirect PDF URL -- pid param with numeric Scopus EID
        # Format: pid=1-s2.0-{digits}-main.pdf  (digits only = Scopus EID)
        # Contrast: pid=1-s2.0-{PII}-main.pdf   (PII contains letters = not an EID)
        if 'pdfft' in url or 'pid=' in url:
            pid_match = re.search(r'pid=1-s2\.0-(\d+)-main\.pdf', url)
            if pid_match:
                numeric_id = pid_match.group(1)
                return f"2-s2.0-{numeric_id}"

        return None

    # --- Patterns for extract_identifiers_from_text ---
    # Plain-text DOI: "doi:10.xxx/yyy" or "DOI: 10.xxx/yyy"
    _PLAIN_DOI_RE = re.compile(
        r'(?:doi|DOI|Doi)[\s:]*?(10\.\d{4,}/\S+?)(?:\s|$|[.,;)\]\}>])',
        re.IGNORECASE,
    )
    # Inline doi.org URL: "https://doi.org/10.xxx/yyy"
    _INLINE_DOI_RE = re.compile(
        r'https?://doi\.org/(10\.[^\s)\]]+)',
        re.IGNORECASE,
    )
    # Inline dx.doi.org URL
    _INLINE_DX_DOI_RE = re.compile(
        r'https?://dx\.doi\.org/(10\.[^\s)\]]+)',
        re.IGNORECASE,
    )
    # Plain-text PMID: "PMID: 30110588" or "PubMed PMID: 30110588"
    _PLAIN_PMID_RE = re.compile(
        r'(?:PMID|PubMed\s+ID|PubMed\s+PMID)[\s:._]*(\d{5,8})(?:\s|$|[.,;)\]])',
        re.IGNORECASE,
    )
    # Inline PubMed URL
    _INLINE_PMID_RE = re.compile(
        r'https?://pubmed\.ncbi\.nlm\.nih\.gov/(\d+)/?',
        re.IGNORECASE,
    )
    # Markdown link anchors: [text](url)
    _ANCHOR_RE = re.compile(
        r'\[([^\]]*)\]\((https?://[^\)]+)\)',
    )

    def extract_identifiers_from_text(self, text: str) -> dict:
        """Extract all DOIs, PMIDs, and URLs from free-form reference text.

        Handles plain-text patterns (doi:10.xxx, PMID: 12345), inline URLs
        (https://doi.org/..., https://pubmed.ncbi.nlm.nih.gov/...), and
        multiple markdown link anchors ([text](url)).

        Returns:
            {
                'doi': Optional[str],       # First DOI found (highest confidence)
                'pmid': Optional[str],      # First PMID found
                'all_urls': List[str],      # All URLs found in any [text](url) anchors
                'doi_source': str,          # 'plain_text' | 'inline_url' | 'anchor' | ''
                'pmid_source': str,         # 'plain_text' | 'inline_url' | ''
            }
        """
        result: Dict[str, Any] = {
            'doi': None,
            'pmid': None,
            'all_urls': [],
            'doi_source': '',
            'pmid_source': '',
        }

        if not text:
            return result

        # --- Collect all markdown anchor URLs ---
        anchor_urls: List[str] = []
        for m in self._ANCHOR_RE.finditer(text):
            anchor_urls.append(m.group(2))
        result['all_urls'] = anchor_urls

        # --- DOI extraction (priority order) ---
        doi: Optional[str] = None
        doi_source = ''

        # 1. Plain-text DOI
        m = self._PLAIN_DOI_RE.search(text)
        if m:
            doi = m.group(1)
            doi_source = 'plain_text'

        # 2. Inline doi.org URL
        if not doi:
            m = self._INLINE_DOI_RE.search(text)
            if m:
                doi = m.group(1)
                doi_source = 'inline_url'

        # 3. Inline dx.doi.org URL
        if not doi:
            m = self._INLINE_DX_DOI_RE.search(text)
            if m:
                doi = m.group(1)
                doi_source = 'inline_url'

        # 4. From anchor URLs containing doi.org
        if not doi:
            for url in anchor_urls:
                m = self._INLINE_DOI_RE.search(url)
                if not m:
                    m = self._INLINE_DX_DOI_RE.search(url)
                if m:
                    doi = m.group(1)
                    doi_source = 'anchor'
                    break

        # Post-process DOI: strip trailing punctuation, validate
        if doi:
            doi = re.sub(r'[.,;)\]\}>]+$', '', doi)
            if not doi.startswith('10.'):
                doi = None
                doi_source = ''

        result['doi'] = doi
        result['doi_source'] = doi_source

        # --- PMID extraction (priority order) ---
        pmid: Optional[str] = None
        pmid_source = ''

        # 1. Plain-text PMID
        m = self._PLAIN_PMID_RE.search(text)
        if m:
            candidate = m.group(1)
            if 5 <= len(candidate) <= 8:
                pmid = candidate
                pmid_source = 'plain_text'

        # 2. Inline PubMed URL
        if not pmid:
            m = self._INLINE_PMID_RE.search(text)
            if m:
                candidate = m.group(1)
                if 5 <= len(candidate) <= 8:
                    pmid = candidate
                    pmid_source = 'inline_url'

        # 3. From anchor URLs containing pubmed
        if not pmid:
            for url in anchor_urls:
                m = self._INLINE_PMID_RE.search(url)
                if m:
                    candidate = m.group(1)
                    if 5 <= len(candidate) <= 8:
                        pmid = candidate
                        pmid_source = 'inline_url'
                        break

        result['pmid'] = pmid
        result['pmid_source'] = pmid_source

        return result

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

