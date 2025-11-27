"""PubMed MCP Client Module - Communicates with PubMed MCP server."""

import json
import re
import time
from typing import Optional, List, Dict, Any, Literal
from dataclasses import dataclass, field
from collections import deque
import requests
from loguru import logger


class SimpleCache:
    """Simple in-memory cache for API responses."""
    
    def __init__(self, max_size: int = 500):
        self._cache: Dict[str, Any] = {}
        self._max_size = max_size
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        return self._cache.get(key)
    
    def set(self, key: str, value: Any):
        """Set value in cache, evicting oldest if at capacity."""
        if len(self._cache) >= self._max_size:
            # Remove first item (oldest)
            first_key = next(iter(self._cache))
            del self._cache[first_key]
        self._cache[key] = value
    
    def has(self, key: str) -> bool:
        """Check if key exists in cache."""
        return key in self._cache
    
    def clear(self):
        """Clear the cache."""
        self._cache.clear()


class RateLimiter:
    """
    Rate limiter for API requests.
    
    NCBI API limits:
    - Without API key: 3 requests/second
    - With API key: 10 requests/second
    
    We use a conservative limit of 2.5 req/s to stay safely under the limit.
    """
    
    def __init__(self, requests_per_second: float = 2.5):
        self.min_interval = 1.0 / requests_per_second  # Minimum time between requests
        self.last_request_time = 0.0
        self._request_times: deque = deque(maxlen=10)  # Track last 10 requests
    
    def wait_if_needed(self):
        """Wait if necessary to stay within rate limits."""
        now = time.time()
        elapsed = now - self.last_request_time
        
        if elapsed < self.min_interval:
            sleep_time = self.min_interval - elapsed
            logger.debug(f"Rate limiting: sleeping {sleep_time:.3f}s")
            time.sleep(sleep_time)
        
        self.last_request_time = time.time()
        self._request_times.append(self.last_request_time)
    
    def get_requests_in_last_second(self) -> int:
        """Count requests made in the last second."""
        now = time.time()
        return sum(1 for t in self._request_times if now - t < 1.0)


@dataclass
class IdConversionResult:
    """Result from ID conversion."""
    input_id: str
    pmid: Optional[str] = None
    pmcid: Optional[str] = None
    doi: Optional[str] = None
    status: str = "success"
    error: Optional[str] = None


@dataclass
class CrossRefMetadata:
    """Metadata from CrossRef API for books, chapters, etc."""
    doi: str
    title: str
    work_type: str  # book-chapter, book, journal-article, etc.
    authors: List[str] = field(default_factory=list)
    editors: List[str] = field(default_factory=list)
    book_title: Optional[str] = None  # For chapters
    container_title: Optional[str] = None  # Journal or series name
    publisher: str = ""
    publisher_location: str = ""
    year: str = ""
    month: str = ""
    volume: str = ""
    issue: str = ""
    pages: str = ""
    isbn: Optional[str] = None
    url: Optional[str] = None

    def get_first_author_label(self) -> str:
        """Generate first author label for citation key."""
        if not self.authors:
            return "Unknown"
        first = self.authors[0].replace(',', ' ').split()
        if len(first) >= 2:
            last_name = first[0]
            initials = ''.join([p[0].upper() for p in first[1:] if p])
            return f"{last_name}{initials}"
        return self.authors[0].replace(' ', '')

    def format_authors_vancouver(self, max_authors: int = 3) -> str:
        """Format authors in Vancouver style."""
        if not self.authors:
            return ""
        if len(self.authors) <= max_authors:
            return ', '.join(self.authors)
        return ', '.join(self.authors[:max_authors]) + ', et al'

    def format_editors_vancouver(self, max_editors: int = 3) -> str:
        """Format editors in Vancouver style."""
        if not self.editors:
            return ""
        if len(self.editors) <= max_editors:
            editors_str = ', '.join(self.editors)
        else:
            editors_str = ', '.join(self.editors[:max_editors]) + ', et al'
        
        # Add "editor" or "editors" suffix
        suffix = "editors" if len(self.editors) > 1 else "editor"
        return f"{editors_str}, {suffix}"


@dataclass
class ArticleMetadata:
    """PubMed article metadata."""
    pmid: str
    title: str
    authors: List[str] = field(default_factory=list)
    journal: str = ""
    journal_abbreviation: str = ""
    year: str = ""
    month: str = ""
    volume: str = ""
    issue: str = ""
    pages: str = ""
    doi: Optional[str] = None
    abstract: str = ""
    pub_date: str = ""
    pmcid: Optional[str] = None

    def get_first_author_label(self) -> str:
        """Generate first author label for citation key."""
        if not self.authors:
            return "Unknown"
        first = self.authors[0].replace(',', ' ').split()
        if len(first) >= 2:
            last_name = first[0]
            initials = ''.join([p[0].upper() for p in first[1:] if p])
            return f"{last_name}{initials}"
        return self.authors[0].replace(' ', '')

    def format_authors_vancouver(self, max_authors: int = 3) -> str:
        """Format authors in Vancouver style."""
        if not self.authors:
            return ""
        if len(self.authors) <= max_authors:
            return ', '.join(self.authors)
        return ', '.join(self.authors[:max_authors]) + ', et al'


class PubMedClient:
    """Client for PubMed MCP server with rate limiting, retry logic, and caching."""

    DEFAULT_SERVER_URL = "http://127.0.0.1:3017/mcp"
    MAX_RETRIES = 4
    # Backoff sequence: 5s, 10s, 20s, 40s (total ~75s max wait)
    RETRY_BACKOFF_SECONDS = [5, 10, 20, 40]

    def __init__(self, server_url: Optional[str] = None, requests_per_second: float = 2.5):
        self.server_url = server_url or self.DEFAULT_SERVER_URL
        self.session = requests.Session()
        
        # Caches to avoid duplicate API calls
        self._pmid_cache = SimpleCache(max_size=500)      # PMID -> ArticleMetadata
        self._conversion_cache = SimpleCache(max_size=500)  # ID -> IdConversionResult
        self._crossref_cache = SimpleCache(max_size=200)   # DOI -> CrossRefMetadata
        
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json, text/event-stream',
        })
        self._request_id = 0
        self._rate_limiter = RateLimiter(requests_per_second)

    def _send_request(self, method: str, params: Dict[str, Any]) -> Optional[Dict]:
        """Send JSON-RPC request to MCP server with rate limiting and retries."""
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": self._request_id,
        }
        self._request_id += 1

        for attempt in range(self.MAX_RETRIES):
            try:
                # Apply rate limiting before each request
                self._rate_limiter.wait_if_needed()
                
                logger.debug(f"Sending request: {method} (attempt {attempt + 1})")
                response = self.session.post(self.server_url, json=payload, timeout=30)
                
                # Handle rate limit (429) with backoff
                if response.status_code == 429:
                    if attempt < self.MAX_RETRIES - 1:
                        backoff_time = self.RETRY_BACKOFF_SECONDS[attempt]
                        logger.warning(f"Rate limited (429). Waiting {backoff_time}s before retry {attempt + 2}/{self.MAX_RETRIES}...")
                        time.sleep(backoff_time)
                        continue
                    else:
                        logger.error("Rate limit exceeded after all retries")
                        return None
                
                response.raise_for_status()

                text = response.text
                if 'data: ' in text:
                    json_str = text.split('data: ', 1)[1].strip()
                    result = json.loads(json_str)
                else:
                    result = response.json()

                if 'error' in result:
                    logger.error(f"MCP error: {result['error']}")
                    return None

                return result.get('result', {})

            except requests.exceptions.ConnectionError:
                logger.error(f"Cannot connect to PubMed MCP at {self.server_url}")
                return None
            except requests.exceptions.Timeout:
                if attempt < self.MAX_RETRIES - 1:
                    logger.warning(f"Request timed out. Retrying...")
                    time.sleep(1)
                    continue
                logger.error("Request timed out after all retries")
                return None
            except json.JSONDecodeError as e:
                logger.error(f"JSON parse error: {e}")
                return None
            except requests.exceptions.HTTPError as e:
                if response.status_code != 429:  # Already handled above
                    logger.error(f"HTTP error: {e}")
                return None
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                return None
        
        return None

    def test_connection(self) -> bool:
        """Test MCP server connection."""
        try:
            result = self._send_request("tools/list", {})
            if result:
                logger.info("Connected to PubMed MCP server")
                return True
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
        return False

    def convert_ids(
        self,
        ids: List[str],
        id_type: Literal["pmcid", "pmid", "doi", "auto"] = "auto",
        target_type: Literal["pmcid", "pmid", "doi", "all"] = "all",
    ) -> List[IdConversionResult]:
        """
        Convert between PMC IDs, PMIDs, and DOIs using NCBI ID Converter.
        
        Args:
            ids: List of identifiers to convert (max 200)
            id_type: Input ID type or "auto" for auto-detection
            target_type: Output type or "all" for all available types
            
        Returns:
            List of IdConversionResult objects
        """
        logger.info(f"Converting {len(ids)} IDs (type={id_type}, target={target_type})")
        
        result = self._send_request("tools/call", {
            "name": "pubmed_convert_ids",
            "arguments": {
                "ids": ids,
                "idType": id_type,
                "targetIdType": target_type,
            }
        })
        
        if not result:
            logger.error("ID conversion request failed")
            return [IdConversionResult(input_id=id_, status="error", error="Request failed") for id_ in ids]
        
        return self._parse_conversion_result(result, ids)
    
    def _parse_conversion_result(self, result: Dict, original_ids: List[str]) -> List[IdConversionResult]:
        """Parse ID conversion response."""
        try:
            content = result.get('content', [])
            if not content:
                return [IdConversionResult(input_id=id_, status="error", error="Empty response") for id_ in original_ids]
            
            text = content[0].get('text', '') if isinstance(content, list) else str(content)
            
            try:
                data = json.loads(text)
            except json.JSONDecodeError as e:
                logger.error(f"JSON parse error in conversion result: {e}")
                return [IdConversionResult(input_id=id_, status="error", error="Parse error") for id_ in original_ids]
            
            conversions = data.get('conversions', [])
            results = []
            
            for conv in conversions:
                results.append(IdConversionResult(
                    input_id=conv.get('inputId', ''),
                    pmid=conv.get('pmid'),
                    pmcid=conv.get('pmcid'),
                    doi=conv.get('doi'),
                    status=conv.get('status', 'unknown'),
                    error=conv.get('error'),
                ))
            
            # Handle any IDs that weren't in the response
            found_ids = {r.input_id for r in results}
            for id_ in original_ids:
                if id_ not in found_ids:
                    results.append(IdConversionResult(
                        input_id=id_,
                        status="error",
                        error="Not in response",
                    ))
            
            return results
            
        except Exception as e:
            logger.error(f"Error parsing conversion result: {e}")
            return [IdConversionResult(input_id=id_, status="error", error=str(e)) for id_ in original_ids]

    def convert_pmcid_to_pmid(self, pmcid: str) -> Optional[str]:
        """Convert a single PMC ID to PMID with caching."""
        # Check cache
        cached = self._conversion_cache.get(f"pmcid:{pmcid}")
        if cached and cached.pmid:
            logger.debug(f"Cache hit for PMCID conversion: {pmcid}")
            return cached.pmid
        
        results = self.convert_ids([pmcid], id_type="pmcid", target_type="pmid")
        if results and results[0].status == "success" and results[0].pmid:
            logger.info(f"Converted {pmcid} → PMID {results[0].pmid}")
            # Cache the result
            self._conversion_cache.set(f"pmcid:{pmcid}", results[0])
            return results[0].pmid
        logger.warning(f"Could not convert {pmcid} to PMID")
        return None

    def convert_doi_to_pmid(self, doi: str) -> Optional[str]:
        """Convert a single DOI to PMID with caching."""
        # Check cache
        cached = self._conversion_cache.get(f"doi:{doi}")
        if cached and cached.pmid:
            logger.debug(f"Cache hit for DOI conversion: {doi}")
            return cached.pmid
        
        results = self.convert_ids([doi], id_type="doi", target_type="pmid")
        if results and results[0].status == "success" and results[0].pmid:
            logger.info(f"Converted DOI {doi} → PMID {results[0].pmid}")
            # Cache the result
            self._conversion_cache.set(f"doi:{doi}", results[0])
            return results[0].pmid
        logger.warning(f"Could not convert DOI {doi} to PMID")
        return None

    def fetch_article_by_pmid(self, pmid: str) -> Optional[ArticleMetadata]:
        """Fetch article metadata by PMID with caching."""
        # Check cache first
        cached = self._pmid_cache.get(pmid)
        if cached is not None:
            logger.debug(f"Cache hit for PMID: {pmid}")
            return cached
        
        logger.info(f"Fetching PMID: {pmid}")

        result = self._send_request("tools/call", {
            "name": "pubmed_fetch_contents",
            "arguments": {
                "pmids": [pmid],
                "detailLevel": "abstract_plus",
                "includeMeshTerms": False,
                "includeGrantInfo": False,
            }
        })

        if not result:
            return None

        metadata = self._parse_fetch_result(result, pmid)
        
        # Supplement missing DOI using ID converter (check conversion cache first)
        if metadata and not metadata.doi:
            conv_cached = self._conversion_cache.get(f"pmid:{pmid}")
            if conv_cached and conv_cached.doi:
                metadata.doi = conv_cached.doi
                if not metadata.pmcid and conv_cached.pmcid:
                    metadata.pmcid = conv_cached.pmcid
            else:
                logger.debug(f"DOI missing for PMID {pmid}, trying ID converter...")
                conversion = self.convert_ids([pmid], id_type="pmid", target_type="all")
                if conversion and conversion[0].status == "success" and conversion[0].doi:
                    metadata.doi = conversion[0].doi
                    logger.info(f"Found DOI via converter: {metadata.doi}")
                    if not metadata.pmcid and conversion[0].pmcid:
                        metadata.pmcid = conversion[0].pmcid
        
        # Cache the result
        if metadata:
            self._pmid_cache.set(pmid, metadata)
        
        return metadata

    def search_by_title(self, title: str, max_results: int = 5) -> List[ArticleMetadata]:
        """Search PubMed by title."""
        clean_title = re.sub(r'[^\w\s\-]', ' ', title)
        clean_title = ' '.join(clean_title.split())[:200]
        logger.info(f"Searching: {clean_title[:60]}...")

        result = self._send_request("tools/call", {
            "name": "pubmed_search_articles",
            "arguments": {
                "queryTerm": clean_title,
                "maxResults": max_results,
                "sortBy": "relevance",
                "fetchBriefSummaries": max_results,
            }
        })

        if not result:
            return []

        return self._parse_search_result(result)

    def verify_article_exists(self, title: str) -> Optional[ArticleMetadata]:
        """Verify article exists in PubMed."""
        results = self.search_by_title(title, max_results=5)
        if not results:
            logger.warning(f"No results for: {title[:60]}...")
            return None

        clean_title = re.sub(r'[^\w\s]', '', title.lower())
        for article in results:
            article_clean = re.sub(r'[^\w\s]', '', article.title.lower())
            # Simple word overlap check
            words1 = set(clean_title.split())
            words2 = set(article_clean.split())
            if words1 and words2:
                overlap = len(words1 & words2) / len(words1 | words2)
                if overlap >= 0.7:
                    logger.info(f"Verified: PMID {article.pmid}")
                    return article

        logger.warning(f"No match found for: {title[:60]}...")
        return None

    def fetch_article_by_pmcid(self, pmcid: str) -> Optional[ArticleMetadata]:
        """Fetch article metadata by PMC ID (e.g., PMC4424793).
        
        Uses the NCBI ID Converter API via pubmed_convert_ids tool.
        """
        logger.info(f"Looking up PMC ID: {pmcid}")
        
        # Normalize PMC ID format (ensure it has PMC prefix)
        if not pmcid.upper().startswith('PMC'):
            pmcid = f"PMC{pmcid}"
        
        # Use the ID converter to get PMID
        pmid = self.convert_pmcid_to_pmid(pmcid)
        
        if pmid:
            return self.fetch_article_by_pmid(pmid)
        
        # Fallback: try searching PubMed directly (less reliable)
        logger.info(f"ID converter failed, trying direct search for {pmcid}")
        clean_pmcid = pmcid.replace('PMC', '')
        result = self._send_request("tools/call", {
            "name": "pubmed_search_articles",
            "arguments": {
                "queryTerm": f"PMC{clean_pmcid}",
                "maxResults": 3,
                "fetchBriefSummaries": 3,
            }
        })

        if result:
            articles = self._parse_search_result(result)
            for article in articles:
                if article.pmcid and clean_pmcid in article.pmcid:
                    logger.info(f"Found PMID {article.pmid} for {pmcid} via search")
                    return self.fetch_article_by_pmid(article.pmid)

        logger.warning(f"Could not find PMID for {pmcid}")
        return None

    def fetch_article_by_doi(self, doi: str) -> Optional[ArticleMetadata]:
        """Fetch article metadata by DOI.
        
        Tries ID converter first (for PMC articles), then falls back to PubMed search.
        """
        logger.info(f"Looking up DOI: {doi}")
        
        # Try ID converter first (works for PMC articles)
        pmid = self.convert_doi_to_pmid(doi)
        if pmid:
            return self.fetch_article_by_pmid(pmid)
        
        # Fallback: Search PubMed using DOI field tag
        logger.info(f"ID converter failed for DOI, trying PubMed search...")
        result = self._send_request("tools/call", {
            "name": "pubmed_search_articles",
            "arguments": {
                "queryTerm": f"{doi}[doi]",
                "maxResults": 1,
                "fetchBriefSummaries": 1,
            }
        })

        if result:
            articles = self._parse_search_result(result)
            if articles:
                logger.info(f"Found PMID {articles[0].pmid} for DOI {doi} via search")
                return self.fetch_article_by_pmid(articles[0].pmid)

        logger.warning(f"Could not find PMID for DOI {doi}")
        return None

    def _parse_fetch_result(self, result: Dict, pmid: str) -> Optional[ArticleMetadata]:
        """Parse fetch result into ArticleMetadata."""
        try:
            content = result.get('content', [])
            if not content:
                return None

            text = content[0].get('text', '') if isinstance(content, list) else str(content)

            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                return None

            articles = data.get('articles', [data]) if isinstance(data, dict) else [data]

            for article in articles:
                if str(article.get('pmid', '')) == str(pmid):
                    return self._article_to_metadata(article)

            if articles:
                return self._article_to_metadata(articles[0])

            return None

        except Exception as e:
            logger.error(f"Parse error: {e}")
            return None

    def _parse_search_result(self, result: Dict) -> List[ArticleMetadata]:
        """Parse search results."""
        try:
            content = result.get('content', [])
            if not content:
                return []

            text = content[0].get('text', '') if isinstance(content, list) else str(content)

            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                return []

            articles = []
            for item in data.get('articles', data.get('results', [])):
                if 'pmid' in item:
                    articles.append(self._article_to_metadata(item))

            return articles

        except Exception as e:
            logger.error(f"Parse error: {e}")
            return []

    def _article_to_metadata(self, article: Dict) -> ArticleMetadata:
        """Convert dict to ArticleMetadata."""
        # Parse authors
        authors = []
        for a in article.get('authors', []):
            if isinstance(a, dict):
                name = a.get('name', f"{a.get('lastName', '')} {a.get('initials', '')}".strip())
                authors.append(name)
            elif isinstance(a, str):
                authors.append(a)

        # Extract journal info (may be nested or flat)
        journal_info = article.get('journalInfo', {})
        
        # Journal name and abbreviation
        journal = (
            journal_info.get('title') or 
            article.get('journal') or 
            article.get('journalTitle', '')
        )
        journal_abbrev = (
            journal_info.get('isoAbbreviation') or
            article.get('journalAbbreviation') or 
            article.get('journalAbbrev', '')
        )
        
        # Volume, issue, pages
        volume = str(journal_info.get('volume') or article.get('volume', ''))
        issue = str(journal_info.get('issue') or article.get('issue', ''))
        pages = journal_info.get('pages') or article.get('pages', '')
        
        # Publication date - check multiple locations
        pub_date_info = journal_info.get('publicationDate', {})
        year = (
            str(pub_date_info.get('year', '')) or 
            article.get('year', '')
        )
        month = (
            str(pub_date_info.get('month', '')) or 
            article.get('month', '')
        )
        
        # Fallback: extract year from various date fields
        if not year:
            pub_date = article.get('pubDate', article.get('publicationDate', ''))
            if pub_date:
                match = re.search(r'(\d{4})', str(pub_date))
                year = match.group(1) if match else ''
        
        # Also check articleDates for electronic publication
        if not year:
            article_dates = article.get('articleDates', [])
            for date_entry in article_dates:
                if isinstance(date_entry, dict) and date_entry.get('year'):
                    year = str(date_entry['year'])
                    if not month:
                        month = str(date_entry.get('month', ''))
                    break

        return ArticleMetadata(
            pmid=str(article.get('pmid', '')),
            title=article.get('title', ''),
            authors=authors,
            journal=journal,
            journal_abbreviation=journal_abbrev,
            year=year,
            month=month,
            volume=volume,
            issue=issue,
            pages=pages,
            doi=article.get('doi'),
            abstract=article.get('abstract', article.get('abstractText', '')),
            pub_date=f"{year} {month}".strip(),
            pmcid=article.get('pmcid'),
        )

    # ============================================================
    # CrossRef API Methods (for non-PubMed items)
    # ============================================================

    def crossref_lookup_doi(self, doi: str) -> Optional[CrossRefMetadata]:
        """
        Look up metadata for a DOI using CrossRef API with caching.
        
        Use this for items not in PubMed: books, book chapters, 
        conference papers, non-indexed journal articles.
        """
        # Check cache first
        cached = self._crossref_cache.get(doi)
        if cached is not None:
            logger.debug(f"Cache hit for CrossRef DOI: {doi}")
            return cached
        
        logger.info(f"CrossRef lookup for DOI: {doi}")
        
        result = self._send_request("tools/call", {
            "name": "crossref_lookup_doi",
            "arguments": {
                "doi": doi,
            }
        })
        
        if not result:
            logger.warning(f"CrossRef lookup failed for DOI: {doi}")
            return None
        
        metadata = self._parse_crossref_result(result, doi)
        
        # Cache the result (even if None to avoid re-fetching)
        self._crossref_cache.set(doi, metadata)
        
        return metadata

    def _parse_crossref_result(self, result: Dict, doi: str) -> Optional[CrossRefMetadata]:
        """Parse CrossRef API response into CrossRefMetadata."""
        try:
            content = result.get('content', [])
            if not content:
                return None
            
            text = content[0].get('text', '') if isinstance(content, list) else str(content)
            
            try:
                data = json.loads(text)
            except json.JSONDecodeError as e:
                logger.error(f"CrossRef JSON parse error: {e}")
                return None
            
            # Check for error response
            if data.get('error'):
                logger.warning(f"CrossRef error: {data.get('error')}")
                return None
            
            # Parse authors
            authors = []
            for a in data.get('authors', []):
                if isinstance(a, dict):
                    if a.get('name'):
                        authors.append(a['name'])
                    elif a.get('family'):
                        name = f"{a.get('family', '')} {a.get('given', '')[:1] if a.get('given') else ''}".strip()
                        authors.append(name)
                elif isinstance(a, str):
                    authors.append(a)
            
            # Parse editors
            editors = []
            for e in data.get('editors', []):
                if isinstance(e, dict):
                    if e.get('name'):
                        editors.append(e['name'])
                    elif e.get('family'):
                        name = f"{e.get('family', '')} {e.get('given', '')[:1] if e.get('given') else ''}".strip()
                        editors.append(name)
                elif isinstance(e, str):
                    editors.append(e)
            
            # Parse date
            pub_date = data.get('publishedDate', {})
            year = str(pub_date.get('year', '')) if isinstance(pub_date, dict) else ''
            month = str(pub_date.get('month', '')) if isinstance(pub_date, dict) else ''
            
            # Handle ISBN (may be array)
            isbn_data = data.get('isbn')
            isbn = isbn_data[0] if isinstance(isbn_data, list) and isbn_data else (isbn_data if isinstance(isbn_data, str) else None)
            
            return CrossRefMetadata(
                doi=data.get('doi', doi),
                title=data.get('title', ''),
                work_type=data.get('type', 'unknown'),
                authors=authors,
                editors=editors,
                book_title=data.get('bookTitle'),
                container_title=data.get('containerTitle'),
                publisher=data.get('publisher', ''),
                publisher_location=data.get('publisherLocation', ''),
                year=year,
                month=month,
                volume=str(data.get('volume', '')),
                issue=str(data.get('issue', '')),
                pages=data.get('pages', ''),
                isbn=isbn,
                url=data.get('url'),
            )
            
        except Exception as e:
            logger.error(f"CrossRef parse error: {e}")
            return None

    def batch_prefetch_conversions(self, ids: List[str], id_type: str = "auto") -> Dict[str, IdConversionResult]:
        """
        Batch prefetch ID conversions to cache for later use.
        
        This is more efficient than converting one at a time because 
        the NCBI API supports up to 200 IDs per request.
        
        Args:
            ids: List of identifiers to convert
            id_type: Type of IDs (pmcid, doi, pmid, or auto)
            
        Returns:
            Dict mapping input ID to conversion result
        """
        if not ids:
            return {}
        
        # Filter out already cached IDs
        uncached_ids = []
        results = {}
        
        for id_ in ids:
            cache_key = f"{id_type}:{id_}" if id_type != "auto" else id_
            cached = self._conversion_cache.get(cache_key)
            if cached:
                results[id_] = cached
                logger.debug(f"Batch prefetch cache hit: {id_}")
            else:
                uncached_ids.append(id_)
        
        if not uncached_ids:
            logger.info(f"All {len(ids)} IDs found in cache")
            return results
        
        logger.info(f"Batch prefetching {len(uncached_ids)} IDs ({len(ids) - len(uncached_ids)} cached)")
        
        # Process in batches of 200 (NCBI limit)
        batch_size = 200
        for i in range(0, len(uncached_ids), batch_size):
            batch = uncached_ids[i:i + batch_size]
            conversions = self.convert_ids(batch, id_type=id_type, target_type="all")
            
            for conv in conversions:
                cache_key = f"{id_type}:{conv.input_id}" if id_type != "auto" else conv.input_id
                self._conversion_cache.set(cache_key, conv)
                results[conv.input_id] = conv
        
        return results

    def get_cache_stats(self) -> Dict[str, int]:
        """Get cache statistics for debugging."""
        return {
            "pmid_cache_size": len(self._pmid_cache._cache),
            "conversion_cache_size": len(self._conversion_cache._cache),
            "crossref_cache_size": len(self._crossref_cache._cache),
        }

