"""arXiv API Client Module.

Provides integration with the arXiv API for fetching preprint metadata.
Supports arXiv IDs (e.g., 2301.12345, cond-mat/0601234) and search queries.
"""

import re
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Optional, List
from loguru import logger

import requests


@dataclass
class ArxivMetadata:
    """Metadata for an arXiv preprint."""
    arxiv_id: str
    title: str
    authors: List[str]
    abstract: str
    primary_category: str
    categories: List[str]
    published: str  # ISO date format
    updated: str    # ISO date format
    doi: Optional[str] = None
    journal_ref: Optional[str] = None
    comment: Optional[str] = None
    pdf_url: Optional[str] = None
    abs_url: Optional[str] = None
    
    def get_first_author_label(self) -> str:
        """Get label from first author's surname + first initial."""
        if not self.authors:
            return "Unknown"
        first = self.authors[0]
        parts = first.split()
        if len(parts) >= 2:
            surname = parts[-1]
            initial = parts[0][0] if parts[0] else ""
            return f"{surname}{initial}"
        return first[:10] if first else "Unknown"
    
    @property
    def year(self) -> str:
        """Extract year from published date."""
        if self.published and len(self.published) >= 4:
            return self.published[:4]
        return ""
    
    @property
    def month(self) -> str:
        """Extract month from published date."""
        if self.published and len(self.published) >= 7:
            return self.published[5:7]
        return ""


class ArxivClient:
    """
    Client for the arXiv API.
    
    API docs: https://info.arxiv.org/help/api/basics.html
    """
    
    BASE_URL = "http://export.arxiv.org/api/query"
    ATOM_NS = "{http://www.w3.org/2005/Atom}"
    ARXIV_NS = "{http://arxiv.org/schemas/atom}"
    
    # Pattern to match arXiv IDs (both old and new format)
    ARXIV_ID_PATTERN = re.compile(
        r'^(?:arXiv:)?'  # Optional prefix
        r'(?:'
        r'(\d{4}\.\d{4,5}(?:v\d+)?)'  # New format: 2301.12345 or 2301.12345v2
        r'|'
        r'([a-z-]+/\d{7}(?:v\d+)?)'   # Old format: cond-mat/0601234
        r')$',
        re.IGNORECASE
    )
    
    def __init__(self, request_delay: float = 3.0):
        """
        Initialize the arXiv client.
        
        Args:
            request_delay: Minimum seconds between requests (arXiv asks for 3s)
        """
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'CitationSculptor/1.6.0 (https://github.com/yourusername/CitationSculptor)'
        })
        self.request_delay = request_delay
        self.last_request_time = 0.0
    
    def _rate_limit(self):
        """Enforce rate limiting between requests."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.request_delay:
            time.sleep(self.request_delay - elapsed)
        self.last_request_time = time.time()
    
    def is_arxiv_id(self, identifier: str) -> bool:
        """Check if a string looks like an arXiv ID."""
        return bool(self.ARXIV_ID_PATTERN.match(identifier.strip()))
    
    def normalize_arxiv_id(self, identifier: str) -> str:
        """
        Normalize an arXiv ID to canonical form.
        
        Removes 'arXiv:' prefix and version suffix for consistent querying.
        """
        identifier = identifier.strip()
        if identifier.lower().startswith('arxiv:'):
            identifier = identifier[6:]
        # Remove version suffix for lookup
        identifier = re.sub(r'v\d+$', '', identifier, flags=re.IGNORECASE)
        return identifier
    
    def fetch_by_id(self, arxiv_id: str) -> Optional[ArxivMetadata]:
        """
        Fetch metadata for a single arXiv article by ID.
        
        Args:
            arxiv_id: arXiv ID (e.g., "2301.12345" or "cond-mat/0601234")
        
        Returns:
            ArxivMetadata object or None if not found
        """
        normalized_id = self.normalize_arxiv_id(arxiv_id)
        
        self._rate_limit()
        
        try:
            response = self.session.get(
                self.BASE_URL,
                params={'id_list': normalized_id, 'max_results': 1},
                timeout=30
            )
            response.raise_for_status()
            
            return self._parse_single_entry(response.text, normalized_id)
            
        except requests.RequestException as e:
            logger.error(f"arXiv API request failed: {e}")
            return None
    
    def search(self, query: str, max_results: int = 10) -> List[ArxivMetadata]:
        """
        Search arXiv for articles matching a query.
        
        Args:
            query: Search query (supports arXiv search syntax)
            max_results: Maximum number of results to return (default 10)
        
        Returns:
            List of ArxivMetadata objects
        """
        self._rate_limit()
        
        try:
            response = self.session.get(
                self.BASE_URL,
                params={
                    'search_query': f'all:{query}',
                    'start': 0,
                    'max_results': min(max_results, 100),
                    'sortBy': 'relevance',
                    'sortOrder': 'descending'
                },
                timeout=30
            )
            response.raise_for_status()
            
            return self._parse_feed(response.text)
            
        except requests.RequestException as e:
            logger.error(f"arXiv search failed: {e}")
            return []
    
    def _parse_single_entry(self, xml_text: str, expected_id: str) -> Optional[ArxivMetadata]:
        """Parse a single entry from arXiv API response."""
        try:
            root = ET.fromstring(xml_text)
            
            # Check for error
            entries = root.findall(f'{self.ATOM_NS}entry')
            if not entries:
                logger.warning(f"No entry found for arXiv ID: {expected_id}")
                return None
            
            entry = entries[0]
            
            # Check if this is an error response (no id element or error message)
            entry_id = entry.find(f'{self.ATOM_NS}id')
            if entry_id is None or 'api/errors' in (entry_id.text or ''):
                summary = entry.find(f'{self.ATOM_NS}summary')
                if summary is not None:
                    logger.warning(f"arXiv API error: {summary.text}")
                return None
            
            return self._parse_entry(entry)
            
        except ET.ParseError as e:
            logger.error(f"Failed to parse arXiv XML: {e}")
            return None
    
    def _parse_feed(self, xml_text: str) -> List[ArxivMetadata]:
        """Parse multiple entries from arXiv API response."""
        results = []
        try:
            root = ET.fromstring(xml_text)
            
            for entry in root.findall(f'{self.ATOM_NS}entry'):
                # Skip error entries
                entry_id = entry.find(f'{self.ATOM_NS}id')
                if entry_id is not None and 'api/errors' not in (entry_id.text or ''):
                    metadata = self._parse_entry(entry)
                    if metadata:
                        results.append(metadata)
            
            return results
            
        except ET.ParseError as e:
            logger.error(f"Failed to parse arXiv XML: {e}")
            return []
    
    def _parse_entry(self, entry: ET.Element) -> Optional[ArxivMetadata]:
        """Parse a single entry element into ArxivMetadata."""
        try:
            # Extract arXiv ID from the entry ID URL
            entry_id_elem = entry.find(f'{self.ATOM_NS}id')
            if entry_id_elem is None or not entry_id_elem.text:
                return None
            
            # ID is in format: http://arxiv.org/abs/2301.12345v1
            full_id = entry_id_elem.text
            arxiv_id = full_id.split('/abs/')[-1] if '/abs/' in full_id else full_id
            
            # Title (may have newlines)
            title_elem = entry.find(f'{self.ATOM_NS}title')
            title = ' '.join((title_elem.text or '').split()) if title_elem is not None else ''
            
            # Authors
            authors = []
            for author_elem in entry.findall(f'{self.ATOM_NS}author'):
                name_elem = author_elem.find(f'{self.ATOM_NS}name')
                if name_elem is not None and name_elem.text:
                    authors.append(name_elem.text.strip())
            
            # Abstract/Summary
            summary_elem = entry.find(f'{self.ATOM_NS}summary')
            abstract = ' '.join((summary_elem.text or '').split()) if summary_elem is not None else ''
            
            # Published and updated dates
            published_elem = entry.find(f'{self.ATOM_NS}published')
            published = (published_elem.text or '')[:10] if published_elem is not None else ''
            
            updated_elem = entry.find(f'{self.ATOM_NS}updated')
            updated = (updated_elem.text or '')[:10] if updated_elem is not None else ''
            
            # Categories
            primary_category = ''
            categories = []
            
            primary_cat_elem = entry.find(f'{self.ARXIV_NS}primary_category')
            if primary_cat_elem is not None:
                primary_category = primary_cat_elem.get('term', '')
            
            for cat_elem in entry.findall(f'{self.ATOM_NS}category'):
                term = cat_elem.get('term', '')
                if term:
                    categories.append(term)
            
            # DOI (optional)
            doi = None
            doi_elem = entry.find(f'{self.ARXIV_NS}doi')
            if doi_elem is not None and doi_elem.text:
                doi = doi_elem.text.strip()
            
            # Journal reference (optional)
            journal_ref = None
            journal_elem = entry.find(f'{self.ARXIV_NS}journal_ref')
            if journal_elem is not None and journal_elem.text:
                journal_ref = journal_elem.text.strip()
            
            # Comment (optional)
            comment = None
            comment_elem = entry.find(f'{self.ARXIV_NS}comment')
            if comment_elem is not None and comment_elem.text:
                comment = comment_elem.text.strip()
            
            # Links
            pdf_url = None
            abs_url = None
            for link_elem in entry.findall(f'{self.ATOM_NS}link'):
                link_type = link_elem.get('type', '')
                link_title = link_elem.get('title', '')
                href = link_elem.get('href', '')
                
                if link_title == 'pdf' or link_type == 'application/pdf':
                    pdf_url = href
                elif link_type == 'text/html' or link_elem.get('rel') == 'alternate':
                    abs_url = href
            
            return ArxivMetadata(
                arxiv_id=arxiv_id,
                title=title,
                authors=authors,
                abstract=abstract,
                primary_category=primary_category,
                categories=categories,
                published=published,
                updated=updated,
                doi=doi,
                journal_ref=journal_ref,
                comment=comment,
                pdf_url=pdf_url,
                abs_url=abs_url
            )
            
        except Exception as e:
            logger.error(f"Failed to parse arXiv entry: {e}")
            return None
    
    def test_connection(self) -> bool:
        """Test connection to arXiv API."""
        try:
            self._rate_limit()
            response = self.session.get(
                self.BASE_URL,
                params={'search_query': 'test', 'max_results': 1},
                timeout=10
            )
            return response.status_code == 200
        except Exception:
            return False

