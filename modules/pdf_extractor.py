"""PDF Metadata and DOI Extractor Module.

Extracts citation-relevant metadata from PDF files including:
- Document metadata (title, authors, date)
- DOIs embedded in text
- arXiv IDs
- PubMed IDs
- Hyperlink annotations (embedded DOI/PMID/refhub links in reference sections)
"""

import re
import os
import time
from dataclasses import dataclass, field
from typing import Optional, List, Tuple, Dict
from pathlib import Path
from loguru import logger

import requests

try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False
    logger.warning("PyMuPDF not installed. PDF extraction will be limited.")


@dataclass
class PDFReferenceLink:
    """A hyperlink annotation found in a PDF reference section."""
    link_type: str          # 'doi', 'pmid', 'refhub', 'pubmed_url', 'other'
    url: str                # Raw URL from annotation
    doi: Optional[str] = None    # Extracted DOI (10.xxx/yyy) if link_type == 'doi'
    pmid: Optional[str] = None   # Extracted PMID if link_type == 'pmid'
    ref_num: Optional[int] = None  # Reference number (from Elsevier srefN or similar)
    page_num: int = 0       # 1-indexed page number where found


@dataclass
class PDFMetadata:
    """Extracted metadata from a PDF file."""
    title: Optional[str]
    authors: List[str]
    doi: Optional[str]
    arxiv_id: Optional[str]
    pmid: Optional[str]
    creation_date: Optional[str]
    subject: Optional[str]
    keywords: List[str]
    page_count: int
    file_path: str
    file_size: int
    
    @property
    def has_identifier(self) -> bool:
        """Check if any usable identifier was found."""
        return bool(self.doi or self.arxiv_id or self.pmid)
    
    @property
    def best_identifier(self) -> Tuple[str, str]:
        """Return the best available identifier (type, value)."""
        if self.doi:
            return ('doi', self.doi)
        if self.pmid:
            return ('pmid', self.pmid)
        if self.arxiv_id:
            return ('arxiv', self.arxiv_id)
        if self.title:
            return ('title', self.title)
        return ('none', '')


class PDFExtractor:
    """
    Extracts citation metadata from PDF files.
    
    Requires PyMuPDF (fitz) for full functionality.
    Install with: pip install PyMuPDF
    """
    
    # DOI patterns
    DOI_PATTERNS = [
        # Standard DOI format
        re.compile(r'(?:doi[:\s]*)?10\.\d{4,9}/[^\s\]>"\']+', re.IGNORECASE),
        # DOI URL format
        re.compile(r'(?:https?://)?(?:dx\.)?doi\.org/(10\.\d{4,9}/[^\s\]>"\']+)', re.IGNORECASE),
    ]
    
    # arXiv patterns
    ARXIV_PATTERNS = [
        re.compile(r'arXiv[:\s]*(\d{4}\.\d{4,5}(?:v\d+)?)', re.IGNORECASE),
        re.compile(r'arXiv[:\s]*([a-z-]+/\d{7}(?:v\d+)?)', re.IGNORECASE),
    ]
    
    # PubMed patterns
    PMID_PATTERNS = [
        re.compile(r'PMID[:\s]*(\d{7,8})', re.IGNORECASE),
        re.compile(r'PubMed[:\s]*(?:ID[:\s]*)?(\d{7,8})', re.IGNORECASE),
        re.compile(r'pubmed\.ncbi\.nlm\.nih\.gov/(\d{7,8})', re.IGNORECASE),
    ]
    
    def __init__(self, max_pages_to_scan: int = 5):
        """
        Initialize the PDF extractor.
        
        Args:
            max_pages_to_scan: Maximum pages to scan for identifiers (default 5)
        """
        self.max_pages_to_scan = max_pages_to_scan
        
        if not PYMUPDF_AVAILABLE:
            logger.warning("PyMuPDF not available. Install with: pip install PyMuPDF")
    
    def extract_metadata(self, pdf_path: str) -> Optional[PDFMetadata]:
        """
        Extract metadata from a PDF file.
        
        Args:
            pdf_path: Path to the PDF file
        
        Returns:
            PDFMetadata object or None if extraction fails
        """
        path = Path(pdf_path)
        
        if not path.exists():
            logger.error(f"PDF file not found: {pdf_path}")
            return None
        
        if not path.suffix.lower() == '.pdf':
            logger.warning(f"File may not be a PDF: {pdf_path}")
        
        if not PYMUPDF_AVAILABLE:
            # Return basic metadata without content extraction
            return PDFMetadata(
                title=path.stem,
                authors=[],
                doi=None,
                arxiv_id=None,
                pmid=None,
                creation_date=None,
                subject=None,
                keywords=[],
                page_count=0,
                file_path=str(path),
                file_size=path.stat().st_size
            )
        
        try:
            doc = fitz.open(pdf_path)
            
            # Extract document metadata
            metadata = doc.metadata
            
            title = metadata.get('title', '').strip() or None
            author_str = metadata.get('author', '')
            creation_date = metadata.get('creationDate', '')
            subject = metadata.get('subject', '').strip() or None
            keywords_str = metadata.get('keywords', '')
            
            # Parse authors (usually comma or semicolon separated)
            authors = []
            if author_str:
                # Split by common separators
                for sep in [';', ',', ' and ', '&']:
                    if sep in author_str:
                        authors = [a.strip() for a in author_str.split(sep) if a.strip()]
                        break
                if not authors:
                    authors = [author_str.strip()]
            
            # Parse keywords
            keywords = []
            if keywords_str:
                keywords = [k.strip() for k in re.split(r'[;,]', keywords_str) if k.strip()]
            
            # Extract text from first few pages for identifier detection
            text = ""
            pages_to_scan = min(self.max_pages_to_scan, len(doc))
            for page_num in range(pages_to_scan):
                page = doc[page_num]
                text += page.get_text() + "\n"
            
            # Extract identifiers from text
            doi = self._extract_doi(text)
            arxiv_id = self._extract_arxiv(text)
            pmid = self._extract_pmid(text)
            
            # If no title from metadata, try first page
            if not title:
                title = self._extract_title_from_first_page(doc)
            
            doc.close()
            
            return PDFMetadata(
                title=title,
                authors=authors,
                doi=doi,
                arxiv_id=arxiv_id,
                pmid=pmid,
                creation_date=self._parse_pdf_date(creation_date),
                subject=subject,
                keywords=keywords,
                page_count=len(doc),
                file_path=str(path),
                file_size=path.stat().st_size
            )
            
        except Exception as e:
            logger.error(f"Failed to extract PDF metadata: {e}")
            return None
    
    def extract_doi(self, pdf_path: str) -> Optional[str]:
        """
        Extract DOI from a PDF file.
        
        Convenience method that returns just the DOI.
        """
        metadata = self.extract_metadata(pdf_path)
        return metadata.doi if metadata else None
    
    def _extract_doi(self, text: str) -> Optional[str]:
        """Extract DOI from text."""
        for pattern in self.DOI_PATTERNS:
            match = pattern.search(text)
            if match:
                doi = match.group(1) if match.lastindex else match.group(0)
                # Clean up DOI
                doi = doi.strip().rstrip('.,;)')
                doi = re.sub(r'^doi[:\s]*', '', doi, flags=re.IGNORECASE)
                # Validate it looks like a DOI
                if doi.startswith('10.') and '/' in doi:
                    return doi
        return None
    
    def _extract_arxiv(self, text: str) -> Optional[str]:
        """Extract arXiv ID from text."""
        for pattern in self.ARXIV_PATTERNS:
            match = pattern.search(text)
            if match:
                return match.group(1)
        return None
    
    def _extract_pmid(self, text: str) -> Optional[str]:
        """Extract PubMed ID from text."""
        for pattern in self.PMID_PATTERNS:
            match = pattern.search(text)
            if match:
                return match.group(1)
        return None
    
    def _extract_title_from_first_page(self, doc) -> Optional[str]:
        """
        Attempt to extract title from first page of PDF.
        
        Heuristic: Look for largest text in top portion of first page.
        """
        try:
            page = doc[0]
            blocks = page.get_text("dict")["blocks"]
            
            candidates = []
            
            for block in blocks:
                if "lines" not in block:
                    continue
                
                # Only consider top third of page
                if block.get("bbox", [0, 0, 0, 0])[1] > page.rect.height / 3:
                    continue
                
                for line in block["lines"]:
                    text = ""
                    max_size = 0
                    
                    for span in line["spans"]:
                        text += span["text"]
                        max_size = max(max_size, span["size"])
                    
                    text = text.strip()
                    if text and len(text) > 10:
                        candidates.append((text, max_size))
            
            if candidates:
                # Return the text with largest font size
                candidates.sort(key=lambda x: x[1], reverse=True)
                return candidates[0][0]
            
            return None
            
        except Exception:
            return None
    
    def _parse_pdf_date(self, date_str: str) -> Optional[str]:
        """Parse PDF date format (D:YYYYMMDDHHmmSS) to YYYY-MM-DD."""
        if not date_str:
            return None
        
        # Remove D: prefix
        date_str = date_str.replace('D:', '')
        
        try:
            if len(date_str) >= 8:
                year = date_str[0:4]
                month = date_str[4:6]
                day = date_str[6:8]
                return f"{year}-{month}-{day}"
        except (ValueError, IndexError):
            pass
        
        return None
    
    # Patterns for classifying link URLs
    _DOI_URL_RE = re.compile(
        r'https?://(?:dx\.)?doi\.org/(10\.\d{4,}/\S+)', re.IGNORECASE
    )
    _PUBMED_URL_RE = re.compile(
        r'https?://pubmed\.ncbi\.nlm\.nih\.gov/(\d{5,8})/?', re.IGNORECASE
    )
    _REFHUB_RE = re.compile(
        r'(?:refhub\.elsevier\.com|sciencedirect\.com/science/refhub)/[^/]+/sref(\d+)',
        re.IGNORECASE
    )
    _DOI_BARE_RE = re.compile(
        r'^(10\.\d{4,}/\S+)$'
    )

    def extract_reference_links(self, pdf_path: str) -> List[PDFReferenceLink]:
        """
        Extract hyperlink annotations from all pages of a PDF.

        Captures embedded DOI, PubMed, and publisher refhub links that are
        invisible as plain text but present as clickable annotations. Many
        journal PDFs (Elsevier, NEJM, JAMA, etc.) embed these links directly
        on reference entries even when no DOI text is visible in the body.

        Args:
            pdf_path: Path to the PDF file.

        Returns:
            List of PDFReferenceLink objects, deduplicated by (link_type, doi/pmid/ref_num).
            Empty list if PyMuPDF is unavailable or extraction fails.
        """
        if not PYMUPDF_AVAILABLE:
            return []

        path = Path(pdf_path)
        if not path.exists():
            logger.warning(f"PDF not found for link extraction: {pdf_path}")
            return []

        try:
            doc = fitz.open(str(path))
            seen: set = set()
            results: List[PDFReferenceLink] = []

            for page_idx in range(len(doc)):
                page = doc[page_idx]
                for link in page.get_links():
                    uri = link.get('uri', '') or ''
                    if not uri:
                        continue

                    parsed = self._classify_link(uri, page_idx + 1)
                    if parsed is None:
                        continue

                    # Deduplicate
                    key = (parsed.link_type, parsed.doi, parsed.pmid, parsed.ref_num)
                    if key in seen:
                        continue
                    seen.add(key)
                    results.append(parsed)

            doc.close()
            logger.debug(
                f"Extracted {len(results)} unique reference links from {path.name}"
            )
            return results

        except Exception as e:
            logger.debug(f"PDF link extraction failed for {pdf_path}: {e}")
            return []

    def _classify_link(self, uri: str, page_num: int) -> Optional[PDFReferenceLink]:
        """Classify a URI and return a PDFReferenceLink or None if not citation-relevant."""
        # Skip mailto: and javascript: and empty fragments
        if uri.startswith(('mailto:', 'javascript:', '#')):
            return None

        # Direct doi.org link
        m = self._DOI_URL_RE.match(uri)
        if m:
            doi = m.group(1).rstrip('.,;)')
            if doi.startswith('10.') and '/' in doi:
                return PDFReferenceLink(
                    link_type='doi', url=uri, doi=doi, page_num=page_num
                )

        # PubMed URL
        m = self._PUBMED_URL_RE.search(uri)
        if m:
            return PDFReferenceLink(
                link_type='pmid', url=uri, pmid=m.group(1), page_num=page_num
            )

        # Elsevier refhub link (srefN → reference number N)
        m = self._REFHUB_RE.search(uri)
        if m:
            return PDFReferenceLink(
                link_type='refhub', url=uri, ref_num=int(m.group(1)),
                page_num=page_num
            )

        # Bare DOI as URI (some PDFs use doi: scheme or raw 10.xxx/yyy)
        bare = uri.replace('doi:', '').strip()
        m = self._DOI_BARE_RE.match(bare)
        if m:
            doi = m.group(1).rstrip('.,;)')
            return PDFReferenceLink(
                link_type='doi', url=uri, doi=doi, page_num=page_num
            )

        # Any other http URL (web references, etc.)
        if uri.startswith('http'):
            return PDFReferenceLink(
                link_type='other', url=uri, page_num=page_num
            )

        return None

    def build_ref_doi_map(self, pdf_path: str) -> Dict[int, str]:
        """
        Build a mapping of reference number → DOI from PDF link annotations.

        Works best for PDFs that embed direct doi.org hyperlinks on reference
        entries (common in NEJM, JAMA, BMJ, Lancet, AHA journals, etc.).

        For Elsevier PDFs, refhub links are present but do not directly expose
        DOIs; the map will be empty in that case.

        Args:
            pdf_path: Path to PDF.

        Returns:
            Dict mapping ref_num (int) → doi (str). May be empty.
        """
        links = self.extract_reference_links(pdf_path)
        result: Dict[int, str] = {}
        for link in links:
            if link.link_type == 'doi' and link.ref_num is not None and link.doi:
                result[link.ref_num] = link.doi
        return result

    def get_all_doi_links(self, pdf_path: str) -> List[str]:
        """Return all unique DOIs found in hyperlink annotations (no ref number required)."""
        links = self.extract_reference_links(pdf_path)
        return [link.doi for link in links if link.link_type == 'doi' and link.doi]

    def batch_extract(self, pdf_paths: List[str]) -> List[PDFMetadata]:
        """
        Extract metadata from multiple PDFs.
        
        Args:
            pdf_paths: List of paths to PDF files
        
        Returns:
            List of PDFMetadata objects (None entries filtered out)
        """
        results = []
        for path in pdf_paths:
            metadata = self.extract_metadata(path)
            if metadata:
                results.append(metadata)
        return results
    
    def find_pdfs_in_directory(self, directory: str, recursive: bool = True) -> List[str]:
        """
        Find all PDF files in a directory.
        
        Args:
            directory: Directory to search
            recursive: Whether to search subdirectories
        
        Returns:
            List of PDF file paths
        """
        path = Path(directory)
        if not path.exists():
            return []
        
        pattern = "**/*.pdf" if recursive else "*.pdf"
        return [str(p) for p in path.glob(pattern)]


class CrossRefReferenceResolver:
    """
    Resolve the complete reference list of a published article via CrossRef.

    Many publisher PDFs (Elsevier, Springer, Wiley, etc.) embed only their
    internal resolver links (refhub, etc.) rather than direct DOIs.  However,
    CrossRef stores the reference list -- including each reference's DOI -- for
    most journal articles.  Given the *citing article's* DOI we can fetch all
    reference DOIs in a single API call, then feed them directly into the
    PubMed/OpenAlex lookup pipeline instead of doing slow title searches.

    This is the preferred resolution path for publisher PDFs where:
    1. The PDF annotations contain only refhub/internal links (not direct DOIs).
    2. The article DOI is known (it appears on page 1 of virtually every PDF).

    Usage:
        resolver = CrossRefReferenceResolver()
        doi_map = resolver.fetch_reference_dois("10.1016/j.jacc.2021.12.002")
        # {1: "10.1056/NEJMra1710575", 2: "10.1001/jamacardio.2015.0354", ...}
    """

    BASE_URL = "https://api.crossref.org/works"
    _BIB_NUM_RE = re.compile(r'bib(\d+)$', re.IGNORECASE)

    def __init__(self, email: str = None, request_delay: float = 0.5):
        self.email = email or os.environ.get('NCBI_EMAIL', '')
        self.request_delay = request_delay
        self._last_request = 0.0
        self.session = requests.Session()
        ua = 'CitationSculptor/1.8.0 (https://github.com/yourusername/CitationSculptor)'
        if self.email:
            ua += f'; mailto:{self.email}'
        self.session.headers['User-Agent'] = ua

    def _throttle(self):
        elapsed = time.time() - self._last_request
        if elapsed < self.request_delay:
            time.sleep(self.request_delay - elapsed)
        self._last_request = time.time()

    def fetch_reference_dois(self, article_doi: str) -> Dict[int, str]:
        """
        Return a mapping of {reference_number: doi} for a published article.

        CrossRef stores the citing article's reference list and, where known,
        each reference's DOI.  The key format varies by publisher; we parse:
          - Elsevier:  "{article_doi}_bib{N}"     → ref N
          - Springer:  "{article_doi}_CR{N}_..."  → ref N
          - Wiley:     "{article_doi}-bib{N}"     → ref N
          - Fallback:  sequential position (1-indexed)

        Args:
            article_doi: DOI of the citing article (with or without prefix).

        Returns:
            Dict mapping reference number (int) → reference DOI (str).
            Empty dict if CrossRef has no reference data or request fails.
        """
        doi = article_doi.replace('https://doi.org/', '').replace('http://doi.org/', '').strip()
        self._throttle()

        try:
            url = f"{self.BASE_URL}/{doi}"
            params = {}
            if self.email:
                params['mailto'] = self.email

            resp = self.session.get(url, params=params, timeout=12)
            if resp.status_code == 404:
                logger.debug(f"CrossRef: article DOI not found: {doi}")
                return {}
            resp.raise_for_status()

            data = resp.json()
            refs = data.get('message', {}).get('reference', [])
            if not refs:
                logger.debug(f"CrossRef: no reference list for {doi}")
                return {}

            result: Dict[int, str] = {}
            for pos, ref in enumerate(refs, start=1):
                ref_doi = ref.get('DOI', '').strip()
                if not ref_doi:
                    continue

                # Try to extract reference number from the key field
                key = ref.get('key', '')
                ref_num = self._parse_ref_num(key, pos)
                result[ref_num] = ref_doi

            logger.debug(
                f"CrossRef reference list: {len(result)}/{len(refs)} refs have DOIs for {doi}"
            )
            return result

        except requests.RequestException as e:
            logger.debug(f"CrossRef reference fetch failed for {doi}: {e}")
            return {}

    def _parse_ref_num(self, key: str, fallback_pos: int) -> int:
        """Parse reference number from CrossRef key field."""
        if not key:
            return fallback_pos

        # Elsevier: "10.1016/j.jacc.2021.12.002_bib42" → 42
        m = self._BIB_NUM_RE.search(key)
        if m:
            return int(m.group(1))

        # Springer: "..._CR42_..." → 42
        cr_m = re.search(r'_CR(\d+)', key)
        if cr_m:
            return int(cr_m.group(1))

        # Wiley: "...-bib42" → 42
        w_m = re.search(r'-bib(\d+)', key)
        if w_m:
            return int(w_m.group(1))

        return fallback_pos

    def resolve_from_pdf(self, pdf_path: str) -> Dict[int, str]:
        """
        Extract the article DOI from a PDF and fetch its reference DOIs via CrossRef.

        Convenience method combining PDFExtractor (article DOI from annotation) +
        CrossRef reference list lookup.

        Args:
            pdf_path: Path to the source PDF.

        Returns:
            Dict mapping reference number → DOI. Empty if article DOI not found.
        """
        extractor = PDFExtractor()
        links = extractor.extract_reference_links(pdf_path)

        # Article DOI is usually a doi.org link on page 1
        article_doi = None
        for link in links:
            if link.link_type == 'doi' and link.page_num == 1 and link.doi:
                article_doi = link.doi
                break

        # Fallback: check PDF text metadata
        if not article_doi:
            metadata = extractor.extract_metadata(pdf_path)
            if metadata and metadata.doi:
                article_doi = metadata.doi

        if not article_doi:
            logger.debug(f"Cannot resolve references: no article DOI found in {pdf_path}")
            return {}

        logger.info(f"Resolving references for article DOI {article_doi} via CrossRef")
        return self.fetch_reference_dois(article_doi)

