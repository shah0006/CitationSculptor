"""DataCite API Client Module.

Provides integration with the DataCite API for dataset, software, preprint,
and other non-journal scholarly metadata. DataCite covers content typically
not found in CrossRef (Dryad, Zenodo, Figshare, GitHub DOIs, etc.).

API docs: https://support.datacite.org/docs/api
No API key required.
"""

import time
from dataclasses import dataclass
from typing import Optional, List
from urllib.parse import quote

from loguru import logger
import requests


@dataclass
class DataCiteWork:
    """Metadata for a scholarly work from DataCite."""

    doi: str
    title: str
    authors: List[str]  # "FamilyName, GivenName" or raw "name"
    year: Optional[int]  # publicationYear
    publisher: Optional[str]
    resource_type: Optional[str]  # types.resourceTypeGeneral
    abstract: Optional[str]  # from descriptions where descriptionType == "Abstract"
    url: Optional[str]
    related_doi: Optional[str]  # first IsSupplementTo or IsPartOf DOI


class DataCiteClient:
    """Client for the DataCite REST API.

    API docs: https://support.datacite.org/docs/api
    No authentication required. Be polite with rate limiting.
    """

    BASE_URL = "https://api.datacite.org"

    def __init__(self, request_delay: float = 0.1):
        """Initialize the DataCite client.

        Args:
            request_delay: Minimum seconds between requests.
        """
        self.session = requests.Session()
        self.request_delay = request_delay
        self.last_request_time = 0.0

        self.session.headers.update(
            {
                "User-Agent": "CitationSculptor/1.8.0 (https://github.com/yourusername/CitationSculptor)",
                "Accept": "application/vnd.api+json",
            }
        )

    def _rate_limit(self):
        """Enforce rate limiting between requests."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.request_delay:
            time.sleep(self.request_delay - elapsed)
        self.last_request_time = time.time()

    def fetch_by_doi(self, doi: str) -> Optional[DataCiteWork]:
        """Fetch a work by DOI.

        Args:
            doi: DOI string (with or without https://doi.org/ prefix).

        Returns:
            DataCiteWork or None on failure/not found.
        """
        if not doi or not str(doi).strip():
            return None

        # Normalize: strip URL prefixes
        doi = str(doi).strip()
        doi = doi.replace("https://doi.org/", "").replace("http://doi.org/", "")

        self._rate_limit()

        try:
            encoded_doi = quote(doi, safe="")
            url = f"{self.BASE_URL}/dois/{encoded_doi}"

            response = self.session.get(url, timeout=30)

            if response.status_code == 404:
                return None
            response.raise_for_status()

            data = response.json()
            return self._parse_work(data.get("data", {}))

        except requests.RequestException as e:
            logger.debug(f"DataCite DOI lookup failed: {e}")
            return None

    def search(self, query: str, max_results: int = 5) -> List[DataCiteWork]:
        """Search DataCite for works matching a query.

        Args:
            query: Search query string.
            max_results: Maximum number of results to return.

        Returns:
            List of DataCiteWork objects (empty list on failure).
        """
        self._rate_limit()

        try:
            url = f"{self.BASE_URL}/dois"
            params = {
                "query": query,
                "page[size]": max_results,
            }

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
            logger.debug(f"DataCite search failed: {e}")
            return []

    def _parse_work(self, item: dict) -> Optional[DataCiteWork]:
        """Parse a DataCite API item into a DataCiteWork.

        Args:
            item: A single item from the DataCite response (the 'data' object
                  for single lookups, or an element of the 'data' array for
                  search results).

        Returns:
            DataCiteWork or None on parse failure.
        """
        try:
            attrs = item.get("attributes", {})

            # Title: first entry in titles list
            titles = attrs.get("titles", [])
            title = titles[0].get("title", "") if titles else ""

            # Authors: prefer familyName, givenName; fall back to name
            authors = []
            for creator in attrs.get("creators", []):
                family = creator.get("familyName")
                given = creator.get("givenName")
                if family and given:
                    authors.append(f"{family}, {given}")
                elif creator.get("name"):
                    authors.append(creator["name"])

            # Year
            year = attrs.get("publicationYear")

            # Publisher
            publisher = attrs.get("publisher")

            # Resource type
            types = attrs.get("types", {})
            resource_type = types.get("resourceTypeGeneral") if types else None

            # Abstract: first description with descriptionType == "Abstract"
            abstract = None
            for desc in attrs.get("descriptions", []):
                if desc.get("descriptionType") == "Abstract":
                    abstract = desc.get("description")
                    break

            # URL
            url = attrs.get("url")

            # Related DOI: first IsSupplementTo or IsPartOf with type DOI
            related_doi = None
            for rel in attrs.get("relatedIdentifiers", []):
                if (
                    rel.get("relatedIdentifierType") == "DOI"
                    and rel.get("relationType") in ("IsSupplementTo", "IsPartOf")
                ):
                    related_doi = rel.get("relatedIdentifier")
                    break

            return DataCiteWork(
                doi=attrs.get("doi", ""),
                title=title,
                authors=authors,
                year=year,
                publisher=publisher,
                resource_type=resource_type,
                abstract=abstract,
                url=url,
                related_doi=related_doi,
            )

        except Exception as e:
            logger.error(f"Failed to parse DataCite work: {e}")
            return None
