"""Semantic Scholar API Client Module.

Provides integration with the Semantic Scholar API for AI-powered scholarly search.
"""

import re
import time
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from loguru import logger

import requests


@dataclass
class SemanticScholarPaper:
    """Metadata for a paper from Semantic Scholar."""
    paper_id: str
    title: str
    authors: List[str]
    year: int
    venue: Optional[str]
    abstract: Optional[str]
    citation_count: int
    influential_citation_count: int
    is_open_access: bool
    open_access_url: Optional[str]
    doi: Optional[str] = None
    arxiv_id: Optional[str] = None
    pmid: Optional[str] = None
    fields_of_study: List[str] = field(default_factory=list)
    tldr: Optional[str] = None  # AI-generated summary
    
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
    def year_str(self) -> str:
        return str(self.year) if self.year else ""


class SemanticScholarClient:
    """
    Client for the Semantic Scholar API.
    
    API docs: https://api.semanticscholar.org/api-docs/
    Free tier: 100 requests per 5 minutes without API key
    """
    
    BASE_URL = "https://api.semanticscholar.org/graph/v1"
    
    # Fields to request from the API
    PAPER_FIELDS = [
        'paperId', 'title', 'authors', 'year', 'venue', 'abstract',
        'citationCount', 'influentialCitationCount', 'isOpenAccess',
        'openAccessPdf', 'externalIds', 'fieldsOfStudy', 'tldr'
    ]
    
    def __init__(self, api_key: str = None, request_delay: float = 0.5):
        """
        Initialize the Semantic Scholar client.
        
        Args:
            api_key: Optional API key for higher rate limits
            request_delay: Minimum seconds between requests
        """
        self.session = requests.Session()
        self.api_key = api_key
        self.request_delay = request_delay
        self.last_request_time = 0.0
        
        headers = {
            'User-Agent': 'CitationSculptor/1.8.0'
        }
        if api_key:
            headers['x-api-key'] = api_key
        self.session.headers.update(headers)
    
    def _rate_limit(self):
        """Enforce rate limiting between requests."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.request_delay:
            time.sleep(self.request_delay - elapsed)
        self.last_request_time = time.time()
    
    def fetch_by_doi(self, doi: str) -> Optional[SemanticScholarPaper]:
        """
        Fetch a paper by DOI.
        
        Args:
            doi: DOI string
        
        Returns:
            SemanticScholarPaper or None
        """
        return self._fetch_by_id(f"DOI:{doi}")
    
    def fetch_by_arxiv(self, arxiv_id: str) -> Optional[SemanticScholarPaper]:
        """
        Fetch a paper by arXiv ID.
        
        Args:
            arxiv_id: arXiv ID (e.g., '2301.04104')
        
        Returns:
            SemanticScholarPaper or None
        """
        # Normalize arXiv ID
        arxiv_id = arxiv_id.lower().replace('arxiv:', '')
        return self._fetch_by_id(f"ARXIV:{arxiv_id}")
    
    def fetch_by_pmid(self, pmid: str) -> Optional[SemanticScholarPaper]:
        """
        Fetch a paper by PubMed ID.
        
        Args:
            pmid: PubMed ID
        
        Returns:
            SemanticScholarPaper or None
        """
        return self._fetch_by_id(f"PMID:{pmid}")
    
    def _fetch_by_id(self, paper_id: str) -> Optional[SemanticScholarPaper]:
        """Fetch a paper by any supported ID format."""
        self._rate_limit()
        
        try:
            url = f"{self.BASE_URL}/paper/{paper_id}"
            params = {'fields': ','.join(self.PAPER_FIELDS)}
            
            response = self.session.get(url, params=params, timeout=30)
            
            if response.status_code == 404:
                return None
            response.raise_for_status()
            
            return self._parse_paper(response.json())
            
        except requests.RequestException as e:
            logger.debug(f"Semantic Scholar lookup failed: {e}")
            return None
    
    def search(
        self, 
        query: str, 
        max_results: int = 10,
        year_range: tuple = None,
        fields_of_study: List[str] = None
    ) -> List[SemanticScholarPaper]:
        """
        Search for papers by query.
        
        Args:
            query: Search query
            max_results: Maximum number of results
            year_range: Optional (start_year, end_year) tuple
            fields_of_study: Optional list of fields to filter by
        
        Returns:
            List of SemanticScholarPaper objects
        """
        self._rate_limit()
        
        try:
            url = f"{self.BASE_URL}/paper/search"
            params = {
                'query': query,
                'limit': min(max_results, 100),
                'fields': ','.join(self.PAPER_FIELDS)
            }
            
            if year_range:
                params['year'] = f"{year_range[0]}-{year_range[1]}"
            
            if fields_of_study:
                params['fieldsOfStudy'] = ','.join(fields_of_study)
            
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            results = []
            
            for item in data.get('data', []):
                paper = self._parse_paper(item)
                if paper:
                    results.append(paper)
            
            return results
            
        except requests.RequestException as e:
            logger.debug(f"Semantic Scholar search failed: {e}")
            return []
    
    def get_recommendations(
        self, 
        paper_id: str, 
        max_results: int = 10,
        based_on: str = "allCitations"
    ) -> List[SemanticScholarPaper]:
        """
        Get paper recommendations based on a seed paper.
        
        Args:
            paper_id: Paper ID (DOI, arXiv, S2 ID, etc.)
            max_results: Maximum number of recommendations
            based_on: 'allCitations' or 'recentCitations'
        
        Returns:
            List of recommended papers
        """
        self._rate_limit()
        
        try:
            url = f"{self.BASE_URL}/recommendations/v1/papers/forpaper/{paper_id}"
            params = {
                'limit': min(max_results, 500),
                'fields': ','.join(self.PAPER_FIELDS),
                'from': based_on
            }
            
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            return [self._parse_paper(p) for p in data.get('recommendedPapers', []) if p]
            
        except requests.RequestException as e:
            logger.debug(f"Semantic Scholar recommendations failed: {e}")
            return []
    
    def get_citations(self, paper_id: str, max_results: int = 25) -> List[SemanticScholarPaper]:
        """
        Get papers that cite a given paper.
        
        Args:
            paper_id: Paper ID
            max_results: Maximum number of citing papers
        
        Returns:
            List of citing papers
        """
        self._rate_limit()
        
        try:
            url = f"{self.BASE_URL}/paper/{paper_id}/citations"
            params = {
                'limit': min(max_results, 1000),
                'fields': ','.join(self.PAPER_FIELDS)
            }
            
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            results = []
            
            for item in data.get('data', []):
                citing_paper = item.get('citingPaper', {})
                if citing_paper:
                    paper = self._parse_paper(citing_paper)
                    if paper:
                        results.append(paper)
            
            return results
            
        except requests.RequestException as e:
            logger.debug(f"Semantic Scholar citations failed: {e}")
            return []
    
    def get_references(self, paper_id: str, max_results: int = 25) -> List[SemanticScholarPaper]:
        """
        Get papers referenced by a given paper.
        
        Args:
            paper_id: Paper ID
            max_results: Maximum number of referenced papers
        
        Returns:
            List of referenced papers
        """
        self._rate_limit()
        
        try:
            url = f"{self.BASE_URL}/paper/{paper_id}/references"
            params = {
                'limit': min(max_results, 1000),
                'fields': ','.join(self.PAPER_FIELDS)
            }
            
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            results = []
            
            for item in data.get('data', []):
                cited_paper = item.get('citedPaper', {})
                if cited_paper:
                    paper = self._parse_paper(cited_paper)
                    if paper:
                        results.append(paper)
            
            return results
            
        except requests.RequestException as e:
            logger.debug(f"Semantic Scholar references failed: {e}")
            return []
    
    def _parse_paper(self, data: dict) -> Optional[SemanticScholarPaper]:
        """Parse Semantic Scholar API response into SemanticScholarPaper."""
        try:
            # Extract authors
            authors = []
            for author in data.get('authors', []):
                name = author.get('name', '')
                if name:
                    authors.append(name)
            
            # Extract external IDs
            external_ids = data.get('externalIds', {}) or {}
            doi = external_ids.get('DOI')
            arxiv_id = external_ids.get('ArXiv')
            pmid = external_ids.get('PubMed')
            
            # Open access
            oa_pdf = data.get('openAccessPdf', {}) or {}
            open_access_url = oa_pdf.get('url')
            
            # TLDR (AI summary)
            tldr_obj = data.get('tldr', {}) or {}
            tldr = tldr_obj.get('text')
            
            return SemanticScholarPaper(
                paper_id=data.get('paperId', ''),
                title=data.get('title', ''),
                authors=authors,
                year=data.get('year') or 0,
                venue=data.get('venue'),
                abstract=data.get('abstract'),
                citation_count=data.get('citationCount', 0),
                influential_citation_count=data.get('influentialCitationCount', 0),
                is_open_access=data.get('isOpenAccess', False),
                open_access_url=open_access_url,
                doi=doi,
                arxiv_id=arxiv_id,
                pmid=pmid,
                fields_of_study=data.get('fieldsOfStudy', []) or [],
                tldr=tldr
            )
            
        except Exception as e:
            logger.error(f"Failed to parse Semantic Scholar paper: {e}")
            return None
    
    def test_connection(self) -> bool:
        """Test connection to Semantic Scholar API."""
        try:
            self._rate_limit()
            response = self.session.get(
                f"{self.BASE_URL}/paper/search",
                params={'query': 'test', 'limit': 1},
                timeout=10
            )
            return response.status_code == 200
        except Exception:
            return False

