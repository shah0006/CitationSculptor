"""OpenAlex API Client Module.

Provides integration with the OpenAlex API for comprehensive scholarly metadata.
OpenAlex is a free, open catalog of the global research system.
"""

import re
import time
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from loguru import logger

import requests


@dataclass
class OpenAlexWork:
    """Metadata for a scholarly work from OpenAlex."""
    openalex_id: str
    doi: Optional[str]
    title: str
    authors: List[str]
    publication_year: int
    publication_date: Optional[str]
    journal: Optional[str]
    journal_issn: Optional[str]
    volume: Optional[str]
    issue: Optional[str]
    pages: Optional[str]
    abstract: Optional[str]
    cited_by_count: int
    is_open_access: bool
    open_access_url: Optional[str]
    type: str  # journal-article, book-chapter, etc.
    concepts: List[str] = field(default_factory=list)
    references_count: int = 0
    pmid: Optional[str] = None
    pmcid: Optional[str] = None
    
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
        return str(self.publication_year) if self.publication_year else ""


@dataclass
class OpenAlexAuthor:
    """Author information from OpenAlex."""
    openalex_id: str
    display_name: str
    orcid: Optional[str]
    works_count: int
    cited_by_count: int
    affiliations: List[str] = field(default_factory=list)


class OpenAlexClient:
    """
    Client for the OpenAlex API.
    
    API docs: https://docs.openalex.org/
    Free tier: 100,000 requests/day (polite pool with email)
    """
    
    BASE_URL = "https://api.openalex.org"
    
    def __init__(self, email: str = None, request_delay: float = 0.1):
        """
        Initialize the OpenAlex client.
        
        Args:
            email: Contact email for polite pool (recommended, increases rate limits)
            request_delay: Minimum seconds between requests
        """
        self.session = requests.Session()
        self.email = email
        self.request_delay = request_delay
        self.last_request_time = 0.0
        
        headers = {
            'User-Agent': 'CitationSculptor/1.8.0 (https://github.com/yourusername/CitationSculptor)'
        }
        if email:
            headers['User-Agent'] += f'; mailto:{email}'
        self.session.headers.update(headers)
    
    def _rate_limit(self):
        """Enforce rate limiting between requests."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.request_delay:
            time.sleep(self.request_delay - elapsed)
        self.last_request_time = time.time()
    
    def _build_params(self, **kwargs) -> Dict[str, Any]:
        """Build request parameters with email for polite pool."""
        params = {k: v for k, v in kwargs.items() if v is not None}
        if self.email:
            params['mailto'] = self.email
        return params
    
    def fetch_by_doi(self, doi: str) -> Optional[OpenAlexWork]:
        """
        Fetch a work by DOI.
        
        Args:
            doi: DOI string (with or without https://doi.org/ prefix)
        
        Returns:
            OpenAlexWork or None
        """
        # Normalize DOI
        doi = doi.replace('https://doi.org/', '').replace('http://doi.org/', '')
        
        self._rate_limit()
        
        try:
            url = f"{self.BASE_URL}/works/https://doi.org/{doi}"
            params = self._build_params()
            
            response = self.session.get(url, params=params, timeout=30)
            
            if response.status_code == 404:
                return None
            response.raise_for_status()
            
            return self._parse_work(response.json())
            
        except requests.RequestException as e:
            logger.debug(f"OpenAlex DOI lookup failed: {e}")
            return None
    
    def fetch_by_pmid(self, pmid: str) -> Optional[OpenAlexWork]:
        """
        Fetch a work by PubMed ID.
        
        Args:
            pmid: PubMed ID
        
        Returns:
            OpenAlexWork or None
        """
        self._rate_limit()
        
        try:
            url = f"{self.BASE_URL}/works/pmid:{pmid}"
            params = self._build_params()
            
            response = self.session.get(url, params=params, timeout=30)
            
            if response.status_code == 404:
                return None
            response.raise_for_status()
            
            return self._parse_work(response.json())
            
        except requests.RequestException as e:
            logger.debug(f"OpenAlex PMID lookup failed: {e}")
            return None
    
    def search(
        self, 
        query: str, 
        max_results: int = 10,
        filter_type: str = None,
        sort: str = "relevance_score"
    ) -> List[OpenAlexWork]:
        """
        Search for works by title/abstract.
        
        Args:
            query: Search query
            max_results: Maximum number of results
            filter_type: Filter by work type (e.g., 'journal-article')
            sort: Sort order ('relevance_score', 'cited_by_count', 'publication_date')
        
        Returns:
            List of OpenAlexWork objects
        """
        self._rate_limit()
        
        try:
            url = f"{self.BASE_URL}/works"
            params = self._build_params(
                search=query,
                per_page=min(max_results, 200),
                sort=sort
            )
            
            if filter_type:
                params['filter'] = f'type:{filter_type}'
            
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            results = []
            
            for item in data.get('results', []):
                work = self._parse_work(item)
                if work:
                    results.append(work)
            
            return results
            
        except requests.RequestException as e:
            logger.debug(f"OpenAlex search failed: {e}")
            return []
    
    def get_citations(self, work_id: str, max_results: int = 25) -> List[OpenAlexWork]:
        """
        Get works that cite a given work.
        
        Args:
            work_id: OpenAlex work ID or DOI
            max_results: Maximum number of citing works to return
        
        Returns:
            List of citing works
        """
        self._rate_limit()
        
        try:
            # Normalize to OpenAlex ID format
            if work_id.startswith('10.'):
                work_id = f"https://doi.org/{work_id}"
            
            url = f"{self.BASE_URL}/works"
            params = self._build_params(
                filter=f'cites:{work_id}',
                per_page=min(max_results, 200),
                sort='publication_date:desc'
            )
            
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            return [self._parse_work(item) for item in data.get('results', []) if item]
            
        except requests.RequestException as e:
            logger.debug(f"OpenAlex citations lookup failed: {e}")
            return []
    
    def get_references(self, work_id: str, max_results: int = 25) -> List[OpenAlexWork]:
        """
        Get works referenced by a given work.
        
        Args:
            work_id: OpenAlex work ID or DOI
            max_results: Maximum number of referenced works to return
        
        Returns:
            List of referenced works
        """
        self._rate_limit()
        
        try:
            # First get the work to find its references
            if work_id.startswith('10.'):
                url = f"{self.BASE_URL}/works/https://doi.org/{work_id}"
            else:
                url = f"{self.BASE_URL}/works/{work_id}"
            
            params = self._build_params()
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            referenced_works = data.get('referenced_works', [])[:max_results]
            
            # Fetch details for each referenced work
            results = []
            for ref_id in referenced_works:
                work = self._fetch_by_id(ref_id)
                if work:
                    results.append(work)
            
            return results
            
        except requests.RequestException as e:
            logger.debug(f"OpenAlex references lookup failed: {e}")
            return []
    
    def _fetch_by_id(self, openalex_id: str) -> Optional[OpenAlexWork]:
        """Fetch a work by OpenAlex ID."""
        self._rate_limit()
        
        try:
            url = f"{self.BASE_URL}/works/{openalex_id}"
            params = self._build_params()
            
            response = self.session.get(url, params=params, timeout=30)
            if response.status_code == 404:
                return None
            response.raise_for_status()
            
            return self._parse_work(response.json())
            
        except requests.RequestException:
            return None
    
    def _parse_work(self, data: dict) -> Optional[OpenAlexWork]:
        """Parse OpenAlex API response into OpenAlexWork."""
        try:
            # Extract authors
            authors = []
            for authorship in data.get('authorships', []):
                author = authorship.get('author', {})
                name = author.get('display_name', '')
                if name:
                    authors.append(name)
            
            # Extract journal info
            journal = None
            journal_issn = None
            source = data.get('primary_location', {}).get('source') or {}
            if source:
                journal = source.get('display_name')
                issns = source.get('issn', [])
                journal_issn = issns[0] if issns else None
            
            # Extract biblio info
            biblio = data.get('biblio', {})
            
            # Open access
            oa = data.get('open_access', {})
            is_open_access = oa.get('is_oa', False)
            open_access_url = oa.get('oa_url')
            
            # Extract concepts (topics)
            concepts = []
            for concept in data.get('concepts', [])[:5]:
                if concept.get('display_name'):
                    concepts.append(concept['display_name'])
            
            # Extract IDs
            ids = data.get('ids', {})
            pmid = ids.get('pmid', '').replace('https://pubmed.ncbi.nlm.nih.gov/', '') if ids.get('pmid') else None
            pmcid = ids.get('pmcid', '').replace('https://www.ncbi.nlm.nih.gov/pmc/articles/', '') if ids.get('pmcid') else None
            
            return OpenAlexWork(
                openalex_id=data.get('id', ''),
                doi=data.get('doi', '').replace('https://doi.org/', '') if data.get('doi') else None,
                title=data.get('title', ''),
                authors=authors,
                publication_year=data.get('publication_year') or 0,
                publication_date=data.get('publication_date'),
                journal=journal,
                journal_issn=journal_issn,
                volume=biblio.get('volume'),
                issue=biblio.get('issue'),
                pages=f"{biblio.get('first_page', '')}-{biblio.get('last_page', '')}" if biblio.get('first_page') else None,
                abstract=data.get('abstract'),
                cited_by_count=data.get('cited_by_count', 0),
                is_open_access=is_open_access,
                open_access_url=open_access_url,
                type=data.get('type', 'unknown'),
                concepts=concepts,
                references_count=len(data.get('referenced_works', [])),
                pmid=pmid,
                pmcid=pmcid
            )
            
        except Exception as e:
            logger.error(f"Failed to parse OpenAlex work: {e}")
            return None
    
    def test_connection(self) -> bool:
        """Test connection to OpenAlex API."""
        try:
            self._rate_limit()
            response = self.session.get(
                f"{self.BASE_URL}/works",
                params=self._build_params(per_page=1),
                timeout=10
            )
            return response.status_code == 200
        except Exception:
            return False

