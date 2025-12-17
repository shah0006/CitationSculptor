"""PDF Metadata and DOI Extractor Module.

Extracts citation-relevant metadata from PDF files including:
- Document metadata (title, authors, date)
- DOIs embedded in text
- arXiv IDs
- PubMed IDs
"""

import re
import os
from dataclasses import dataclass
from typing import Optional, List, Tuple
from pathlib import Path
from loguru import logger

try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False
    logger.warning("PyMuPDF not installed. PDF extraction will be limited.")


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

