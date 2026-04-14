"""Semantic Scholar API Client Module.

Provides integration with the Semantic Scholar API for AI-powered scholarly search.

API docs: https://api.semanticscholar.org/api-docs/
Rate limits: 100 req/5min without key; 10 req/sec with key.
"""

import os
import time
from dataclasses import dataclass, field
from typing import Optional, List

import requests
from loguru import logger


@dataclass
class SemanticScholarWork:
    """Normalized metadata for a scholarly work from Semantic Scholar."""

    s2_id: str
    doi: Optional[str]
    pmid: Optional[str]
    title: str
    authors: List[str]
    year: Optional[int]
    journal: Optional[str]
    publication_date: Optional[str]
    abstract: Optional[str]
    citation_count: int
    open_access_url: Optional[str]


# Backward-compatible alias for existing consumers
SemanticScholarPaper = SemanticScholarWork


class SemanticScholarClient:
    """
    Client for the Semantic Scholar API.

    API docs: https://api.semanticscholar.org/api-docs/
    Free tier: 100 requests per 5 minutes without API key.
    With SEMANTIC_SCHOLAR_API_KEY: 10 requests per second.
    """

    BASE_URL = "https://api.semanticscholar.org/graph/v1"

    PAPER_FIELDS = ",".join([
        "paperId",
        "externalIds",
        "title",
        "authors",
        "year",
        "venue",
        "publicationDate",
        "abstract",
        "citationCount",
        "openAccessPdf",
    ])

    def __init__(self, api_key: str = None, request_delay: float = 0.5):
        """
        Initialize the Semantic Scholar client.

        Args:
            api_key: Optional API key. Falls back to SEMANTIC_SCHOLAR_API_KEY env var.
            request_delay: Minimum seconds between requests (default 0.5).
        """
        self.session = requests.Session()
        self.api_key = api_key or os.environ.get("SEMANTIC_SCHOLAR_API_KEY")
        self.request_delay = request_delay
        self.last_request_time = 0.0

        headers = {"User-Agent": "CitationSculptor/1.8.0"}
        if self.api_key:
            headers["x-api-key"] = self.api_key
        self.session.headers.update(headers)

    # ------------------------------------------------------------------
    # Rate limiting
    # ------------------------------------------------------------------

    def _rate_limit(self):
        """Enforce rate limiting between requests."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.request_delay:
            time.sleep(self.request_delay - elapsed)
        self.last_request_time = time.time()

    # ------------------------------------------------------------------
    # Public API: fetch by identifier
    # ------------------------------------------------------------------

    def fetch_by_doi(self, doi: str) -> Optional[SemanticScholarWork]:
        """
        Fetch a work by DOI.

        Auto-prefixes with ``DOI:`` if not already present.
        Returns None for None/empty input without making an HTTP call.
        """
        if not doi:
            return None

        doi = str(doi).strip()
        if not doi:
            return None

        # Auto-prefix, avoid double-prefix
        if not doi.upper().startswith("DOI:"):
            doi = f"DOI:{doi}"

        return self._fetch_by_id(doi)

    def fetch_by_pmid(self, pmid: str) -> Optional[SemanticScholarWork]:
        """
        Fetch a work by PubMed ID.

        Auto-prefixes with ``PMID:`` if not already present.
        Returns None for None/empty input without making an HTTP call.
        """
        if not pmid:
            return None

        pmid = str(pmid).strip()
        if not pmid:
            return None

        # Auto-prefix, avoid double-prefix
        if not pmid.upper().startswith("PMID:"):
            pmid = f"PMID:{pmid}"

        return self._fetch_by_id(pmid)

    def fetch_by_arxiv(self, arxiv_id: str) -> Optional[SemanticScholarWork]:
        """
        Fetch a work by arXiv ID.

        Args:
            arxiv_id: arXiv ID (e.g., '2301.04104')
        """
        if not arxiv_id:
            return None

        arxiv_id = str(arxiv_id).strip().lower().replace("arxiv:", "")
        if not arxiv_id:
            return None

        return self._fetch_by_id(f"ARXIV:{arxiv_id}")

    # ------------------------------------------------------------------
    # Public API: search
    # ------------------------------------------------------------------

    def search(
        self,
        query: str,
        max_results: int = 5,
        year_range: tuple = None,
        fields_of_study: List[str] = None,
    ) -> List[SemanticScholarWork]:
        """
        Search for papers by query string.

        Returns empty list for None/empty query without making an HTTP call.
        """
        if not query:
            return []

        query = str(query).strip()
        if not query:
            return []

        self._rate_limit()

        try:
            url = f"{self.BASE_URL}/paper/search"
            params = {
                "query": query,
                "limit": min(max_results, 100),
                "fields": self.PAPER_FIELDS,
            }

            if year_range:
                params["year"] = f"{year_range[0]}-{year_range[1]}"
            if fields_of_study:
                params["fieldsOfStudy"] = ",".join(fields_of_study)

            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()

            data = response.json()
            results = []

            for item in data.get("data", []):
                work = self._parse_work(item)
                if work:
                    results.append(work)

            return results

        except requests.RequestException as e:
            logger.debug(f"Semantic Scholar search failed: {e}")
            return []

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _fetch_by_id(self, paper_id: str) -> Optional[SemanticScholarWork]:
        """Fetch a single paper by any supported ID format."""
        self._rate_limit()

        try:
            url = f"{self.BASE_URL}/paper/{paper_id}"
            params = {"fields": self.PAPER_FIELDS}

            response = self.session.get(url, params=params, timeout=30)

            if response.status_code == 404:
                return None
            response.raise_for_status()

            return self._parse_work(response.json())

        except requests.RequestException as e:
            logger.debug(f"Semantic Scholar lookup failed: {e}")
            return None

    def _parse_work(self, data: dict) -> Optional[SemanticScholarWork]:
        """Parse Semantic Scholar API response into SemanticScholarWork."""
        try:
            authors = [
                a.get("name", "")
                for a in data.get("authors", [])
                if a.get("name")
            ]

            external_ids = data.get("externalIds") or {}
            doi = external_ids.get("DOI")
            pmid = external_ids.get("PubMed")

            oa_pdf = data.get("openAccessPdf") or {}
            open_access_url = oa_pdf.get("url")

            return SemanticScholarWork(
                s2_id=data.get("paperId", ""),
                doi=doi,
                pmid=pmid,
                title=data.get("title", ""),
                authors=authors,
                year=data.get("year"),
                journal=data.get("venue"),
                publication_date=data.get("publicationDate"),
                abstract=data.get("abstract"),
                citation_count=data.get("citationCount", 0),
                open_access_url=open_access_url,
            )

        except Exception as e:
            logger.error(f"Failed to parse Semantic Scholar paper: {e}")
            return None

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def test_connection(self) -> bool:
        """Test connection to Semantic Scholar API."""
        try:
            self._rate_limit()
            response = self.session.get(
                f"{self.BASE_URL}/paper/search",
                params={"query": "test", "limit": 1},
                timeout=10,
            )
            return response.status_code == 200
        except Exception:
            return False
