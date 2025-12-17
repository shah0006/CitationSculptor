"""Preprint Server Client Module.

Provides integration with bioRxiv and medRxiv APIs for fetching preprint metadata.
Uses the bioRxiv/medRxiv API (https://api.biorxiv.org).
"""

import re
import time
from dataclasses import dataclass
from typing import Optional, List, Literal
from loguru import logger

import requests


@dataclass
class PreprintMetadata:
    """Metadata for a bioRxiv/medRxiv preprint."""
    doi: str
    title: str
    authors: str  # Semicolon-separated list from API
    abstract: str
    date: str  # YYYY-MM-DD
    server: Literal['biorxiv', 'medrxiv']
    category: str
    version: int
    type: str  # 'new' or 'revised'
    license: str
    jatsxml: Optional[str] = None
    published_doi: Optional[str] = None  # If published in journal
    published_journal: Optional[str] = None
    
    @property
    def authors_list(self) -> List[str]:
        """Parse authors string into list."""
        if not self.authors:
            return []
        # Authors are semicolon-separated: "Smith, J.; Jones, A. B."
        return [a.strip() for a in self.authors.split(';') if a.strip()]
    
    def get_first_author_label(self) -> str:
        """Get label from first author's surname + first initial."""
        authors = self.authors_list
        if not authors:
            return "Unknown"
        first = authors[0]
        # Format is "Surname, Initials" or "Surname, First Middle"
        if ',' in first:
            parts = first.split(',')
            surname = parts[0].strip()
            if len(parts) > 1 and parts[1].strip():
                initial = parts[1].strip()[0]
                return f"{surname}{initial}"
            return surname[:10]
        # No comma, try splitting by space
        parts = first.split()
        if len(parts) >= 2:
            surname = parts[-1]
            initial = parts[0][0] if parts[0] else ""
            return f"{surname}{initial}"
        return first[:10] if first else "Unknown"
    
    @property
    def year(self) -> str:
        """Extract year from date."""
        if self.date and len(self.date) >= 4:
            return self.date[:4]
        return ""
    
    @property
    def month(self) -> str:
        """Extract month from date."""
        if self.date and len(self.date) >= 7:
            return self.date[5:7]
        return ""
    
    @property
    def url(self) -> str:
        """Get URL to preprint page."""
        return f"https://www.{self.server}.org/content/{self.doi}"


class PreprintClient:
    """
    Client for bioRxiv and medRxiv APIs.
    
    API docs: https://api.biorxiv.org/
    """
    
    BASE_URL = "https://api.biorxiv.org"
    
    # Pattern to match bioRxiv/medRxiv DOIs
    PREPRINT_DOI_PATTERN = re.compile(
        r'^10\.1101/((?:19|20)\d{2}\.\d{2}\.\d{2}\.\d+)(?:v\d+)?$'
    )
    
    def __init__(self, request_delay: float = 1.0):
        """
        Initialize the preprint client.
        
        Args:
            request_delay: Minimum seconds between requests
        """
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'CitationSculptor/1.6.0 (https://github.com/yourusername/CitationSculptor)',
            'Accept': 'application/json'
        })
        self.request_delay = request_delay
        self.last_request_time = 0.0
    
    def _rate_limit(self):
        """Enforce rate limiting between requests."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.request_delay:
            time.sleep(self.request_delay - elapsed)
        self.last_request_time = time.time()
    
    def is_preprint_doi(self, doi: str) -> bool:
        """Check if a DOI is from bioRxiv or medRxiv."""
        return bool(self.PREPRINT_DOI_PATTERN.match(doi.strip()))
    
    def _extract_doi_suffix(self, doi: str) -> Optional[str]:
        """Extract the DOI suffix (without 10.1101/ prefix)."""
        match = self.PREPRINT_DOI_PATTERN.match(doi.strip())
        if match:
            return match.group(1)
        return None
    
    def fetch_by_doi(self, doi: str) -> Optional[PreprintMetadata]:
        """
        Fetch metadata for a preprint by DOI.
        
        Args:
            doi: Full DOI (e.g., "10.1101/2024.01.15.575623")
        
        Returns:
            PreprintMetadata object or None if not found
        """
        doi_suffix = self._extract_doi_suffix(doi)
        if not doi_suffix:
            logger.warning(f"Invalid preprint DOI format: {doi}")
            return None
        
        self._rate_limit()
        
        # The bioRxiv API requires the full DOI path, not just the suffix
        # Use the "pubs" endpoint which accepts DOI directly
        for server in ['biorxiv', 'medrxiv']:
            try:
                # Use the newer content API endpoint that works with DOIs
                url = f"https://api.biorxiv.org/pubs/{server}/10.1101/{doi_suffix}"
                response = self.session.get(url, timeout=30)
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get('collection') and len(data['collection']) > 0:
                        return self._parse_entry(data['collection'][0], server)
                        
            except requests.RequestException as e:
                logger.debug(f"{server} lookup failed for {doi}: {e}")
                continue
            except Exception as e:
                logger.error(f"Error parsing {server} response: {e}")
                continue
        
        logger.warning(f"Preprint not found in bioRxiv or medRxiv: {doi}")
        return None
    
    def search(
        self, 
        query: str, 
        server: Literal['biorxiv', 'medrxiv'] = 'biorxiv',
        max_results: int = 10
    ) -> List[PreprintMetadata]:
        """
        Search for preprints.
        
        Note: The bioRxiv/medRxiv API doesn't have a direct search endpoint.
        This method searches by date range and filters by title content.
        For better search, use their website or consider the RSS feed.
        
        Args:
            query: Search terms (matched against title)
            server: Which server to search ('biorxiv' or 'medrxiv')
            max_results: Maximum results to return
        
        Returns:
            List of PreprintMetadata objects
        """
        # API only supports date-range queries, not full text search
        # We'll get recent papers and filter by title
        # This is a limitation of the API
        
        from datetime import datetime, timedelta
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)  # Last 30 days
        
        self._rate_limit()
        
        try:
            url = (
                f"{self.BASE_URL}/details/{server}/"
                f"{start_date.strftime('%Y-%m-%d')}/{end_date.strftime('%Y-%m-%d')}/0/json"
            )
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            results = []
            
            query_lower = query.lower()
            for entry in data.get('collection', []):
                title = entry.get('title', '').lower()
                abstract = entry.get('abstract', '').lower()
                
                # Simple title/abstract matching
                if query_lower in title or query_lower in abstract:
                    metadata = self._parse_entry(entry, server)
                    if metadata:
                        results.append(metadata)
                        if len(results) >= max_results:
                            break
            
            return results
            
        except requests.RequestException as e:
            logger.error(f"{server} search failed: {e}")
            return []
    
    def fetch_recent(
        self,
        server: Literal['biorxiv', 'medrxiv'],
        days: int = 7,
        max_results: int = 50
    ) -> List[PreprintMetadata]:
        """
        Fetch recent preprints from a server.
        
        Args:
            server: Which server ('biorxiv' or 'medrxiv')
            days: Number of days to look back
            max_results: Maximum results to return
        
        Returns:
            List of PreprintMetadata objects
        """
        from datetime import datetime, timedelta
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        self._rate_limit()
        
        try:
            url = (
                f"{self.BASE_URL}/details/{server}/"
                f"{start_date.strftime('%Y-%m-%d')}/{end_date.strftime('%Y-%m-%d')}/0/json"
            )
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            results = []
            
            for entry in data.get('collection', [])[:max_results]:
                metadata = self._parse_entry(entry, server)
                if metadata:
                    results.append(metadata)
            
            return results
            
        except requests.RequestException as e:
            logger.error(f"Failed to fetch recent {server} preprints: {e}")
            return []
    
    def check_publication_status(self, doi: str) -> Optional[dict]:
        """
        Check if a preprint has been published in a journal.
        
        Args:
            doi: Preprint DOI
        
        Returns:
            Dict with 'published_doi' and 'published_journal' if published, else None
        """
        metadata = self.fetch_by_doi(doi)
        if metadata and metadata.published_doi:
            return {
                'published_doi': metadata.published_doi,
                'published_journal': metadata.published_journal
            }
        return None
    
    def _parse_entry(self, entry: dict, server: str) -> Optional[PreprintMetadata]:
        """Parse API response entry into PreprintMetadata."""
        try:
            doi = entry.get('doi', '')
            if not doi:
                return None
            
            # Ensure full DOI format
            if not doi.startswith('10.1101/'):
                doi = f"10.1101/{doi}"
            
            return PreprintMetadata(
                doi=doi,
                title=entry.get('title', '').strip(),
                authors=entry.get('authors', ''),
                abstract=entry.get('abstract', '').strip(),
                date=entry.get('date', ''),
                server=server,
                category=entry.get('category', ''),
                version=int(entry.get('version', 1)),
                type=entry.get('type', 'new'),
                license=entry.get('license', ''),
                jatsxml=entry.get('jatsxml'),
                published_doi=entry.get('published') or None,
                published_journal=entry.get('published_citation_journal')
            )
            
        except Exception as e:
            logger.error(f"Failed to parse preprint entry: {e}")
            return None
    
    def test_connection(self) -> bool:
        """Test connection to bioRxiv API."""
        try:
            self._rate_limit()
            from datetime import datetime, timedelta
            today = datetime.now()
            yesterday = today - timedelta(days=1)
            
            url = (
                f"{self.BASE_URL}/details/biorxiv/"
                f"{yesterday.strftime('%Y-%m-%d')}/{today.strftime('%Y-%m-%d')}/0/json"
            )
            response = self.session.get(url, timeout=10)
            return response.status_code == 200
        except Exception:
            return False

