"""Europe PMC API Client Module.

Provides integration with the Europe PMC REST API for scholarly metadata.
Europe PMC is a free, open science platform providing access to life science
publications and preprints. No API key required.

API docs: https://europepmc.org/RestfulWebService
"""

import time
from dataclasses import dataclass
from typing import Optional, List

import requests
from loguru import logger


@dataclass
class EuropePMCWork:
    """Metadata for a scholarly work from Europe PMC."""
    pmid: Optional[str]
    pmcid: Optional[str]
    doi: Optional[str]
    title: str
    authors: List[str]
    year: Optional[int]
    journal: Optional[str]
    volume: Optional[str]
    issue: Optional[str]
    pages: Optional[str]
    abstract: Optional[str]
    source: str  # "MED" for PubMed, "PPR" for preprint, etc.


class EuropePMCClient:
    """Client for the Europe PMC REST API.

    API docs: https://europepmc.org/RestfulWebService
    No API key required. Rate-limited by simple sleep between requests.
    """

    BASE_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest"

    def __init__(self, request_delay: float = 0.15):
        """Initialize the Europe PMC client.

        Args:
            request_delay: Minimum seconds between requests.
        """
        self.session = requests.Session()
        self.request_delay = request_delay
        self.last_request_time = 0.0

        self.session.headers.update({
            "User-Agent": "CitationSculptor/1.8.0 (https://github.com/yourusername/CitationSculptor)",
            "Accept": "application/json",
        })

    def _rate_limit(self):
        """Enforce rate limiting between requests."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.request_delay:
            time.sleep(self.request_delay - elapsed)
        self.last_request_time = time.time()

    def _search_raw(self, query: str, page_size: int = 5) -> Optional[dict]:
        """Execute a search query and return raw JSON response.

        Returns None on any failure.
        """
        self._rate_limit()
        try:
            response = self.session.get(
                f"{self.BASE_URL}/search",
                params={
                    "query": query,
                    "format": "json",
                    "resultType": "core",
                    "pageSize": page_size,
                },
                timeout=30,
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.debug(f"Europe PMC request failed: {e}")
            return None

    def _parse_work(self, data: dict) -> Optional[EuropePMCWork]:
        """Parse a single Europe PMC result dict into an EuropePMCWork."""
        try:
            # Parse authors from authorString
            author_string = data.get("authorString", "")
            if author_string:
                authors = [a.strip() for a in author_string.split(",") if a.strip()]
            else:
                authors = []

            # Parse year
            pub_year_raw = data.get("pubYear")
            year = None
            if pub_year_raw is not None:
                try:
                    year = int(pub_year_raw)
                except (ValueError, TypeError):
                    year = None

            return EuropePMCWork(
                pmid=data.get("pmid"),
                pmcid=data.get("pmcid"),
                doi=data.get("doi"),
                title=data.get("title", ""),
                authors=authors,
                year=year,
                journal=data.get("journalTitle"),
                volume=data.get("journalVolume"),
                issue=data.get("issue"),
                pages=data.get("pageInfo"),
                abstract=data.get("abstractText"),
                source=data.get("source", ""),
            )
        except Exception as e:
            logger.error(f"Failed to parse Europe PMC result: {e}")
            return None

    def _first_result(self, raw: Optional[dict]) -> Optional[EuropePMCWork]:
        """Extract and parse the first result from a raw API response."""
        if raw is None:
            return None
        results = raw.get("resultList", {}).get("result", [])
        if not results:
            return None
        return self._parse_work(results[0])

    def fetch_by_pmid(self, pmid: str) -> Optional[EuropePMCWork]:
        """Fetch a work by PubMed ID.

        Args:
            pmid: PubMed ID string.

        Returns:
            EuropePMCWork or None on failure / not found.
        """
        if not pmid:
            return None

        query = f"EXT_ID:{pmid} AND SRC:MED"
        raw = self._search_raw(query, page_size=1)
        return self._first_result(raw)

    def fetch_by_doi(self, doi: str) -> Optional[EuropePMCWork]:
        """Fetch a work by DOI.

        Args:
            doi: DOI string.

        Returns:
            EuropePMCWork or None on failure / not found.
        """
        if not doi:
            return None

        query = f"DOI:{doi}"
        raw = self._search_raw(query, page_size=1)
        return self._first_result(raw)

    def search(self, query: str, max_results: int = 5) -> List[EuropePMCWork]:
        """Search Europe PMC by free text query.

        Args:
            query: Search query string.
            max_results: Maximum number of results to return.

        Returns:
            List of EuropePMCWork objects (empty list on failure).
        """
        if not query:
            return []

        raw = self._search_raw(query, page_size=max_results)
        if raw is None:
            return []

        results = raw.get("resultList", {}).get("result", [])
        works = []
        for item in results:
            work = self._parse_work(item)
            if work:
                works.append(work)
        return works
