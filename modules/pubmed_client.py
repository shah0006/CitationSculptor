"""PubMed MCP Client Module - Communicates with PubMed MCP server."""

import json
import re
import time
from typing import Optional, List, Dict, Any, Literal, Tuple
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
        clean_title = ' '.join(clean_title.split())
        # Truncate to ~100 chars for better search results (long queries often fail)
        # But try to break at a word boundary
        if len(clean_title) > 100:
            clean_title = clean_title[:100].rsplit(' ', 1)[0]
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
        """Verify article exists in PubMed and return full metadata."""
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
                
                matched = False
                # Check 1: Strong overlap
                if overlap >= 0.7:
                    logger.info(f"Verified (high overlap {overlap:.2f}): PMID {article.pmid}")
                    matched = True
                
                # Check 2: Subset match (all significant query words are in result)
                # Good for when query is a shortened version of the full title
                if not matched:
                    sig_words1 = {w for w in words1 if len(w) > 3}
                    if sig_words1 and sig_words1.issubset(words2):
                        logger.info(f"Verified (subset match): PMID {article.pmid}")
                        matched = True
                
                if matched:
                    # Fetch full metadata using the PMID (search results have limited data)
                    full_metadata = self.fetch_article_by_pmid(article.pmid)
                    if full_metadata:
                        return full_metadata
                    # Fall back to search result if full fetch fails
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
            
        # Try ID conversion using batch converter logic (returns full object)
        # We use convert_ids directly to get access to DOI if PMID is missing
        results = self.convert_ids([pmcid], id_type="pmcid", target_type="all")
        
        if results and results[0].status == "success":
            res = results[0]
            
            # 1. If PMID found, use it (Standard path)
            if res.pmid:
                return self.fetch_article_by_pmid(res.pmid)
                
            # 2. If no PMID but DOI found, try CrossRef (Backup path)
            # Note: Only convert to ArticleMetadata for journal-article types.
            # For book-chapters, books, etc., return None so the caller can 
            # use crossref_lookup_doi() directly and format appropriately.
            if res.doi:
                logger.info(f"No PMID for {pmcid}, but found DOI: {res.doi}. Fetching from CrossRef...")
                crossref_meta = self.crossref_lookup_doi(res.doi)
                if crossref_meta:
                    if crossref_meta.work_type == 'journal-article':
                        return self._crossref_to_article_metadata(crossref_meta, pmcid=pmcid)
                    else:
                        # For non-journal types (book-chapter, book, etc.), 
                        # store DOI for caller to handle via CrossRef path
                        logger.info(f"CrossRef returned work_type='{crossref_meta.work_type}', not converting to ArticleMetadata")
                        # Return None - caller should use crossref_lookup_doi() directly
                        return None
        
        # 3. Fallback: Direct search (legacy, but might catch something)
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

        logger.warning(f"Could not find PMID or usable metadata for {pmcid}")
        return None

    def _crossref_to_article_metadata(self, cm: CrossRefMetadata, pmcid: Optional[str] = None) -> ArticleMetadata:
        """Convert CrossRef metadata to ArticleMetadata."""
        return ArticleMetadata(
            pmid="",  # No PMID available
            title=cm.title,
            authors=cm.authors,
            journal=cm.container_title or "",
            journal_abbreviation=cm.container_title or "",
            year=cm.year or "",
            month=cm.month or "",
            volume=cm.volume or "",
            issue=cm.issue or "",
            pages=cm.pages or "",
            doi=cm.doi,
            abstract="",  # CrossRef usually doesn't provide abstract
            pub_date=f"{cm.year} {cm.month}".strip(),
            pmcid=pmcid
        )

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
            # Check for various keys used by different server versions
            # The search tool now returns 'briefSummaries'
            items = data.get('articles') or data.get('briefSummaries') or data.get('results') or []
            
            for item in items:
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

    def crossref_search_title(self, title: str) -> Optional[CrossRefMetadata]:
        """
        Search CrossRef by title and return best match.
        
        Uses the CrossRef REST API directly since MCP server may not have this.
        """
        import urllib.parse
        
        # Clean title for search
        clean_title = re.sub(r'[^\w\s\-]', ' ', title)
        clean_title = ' '.join(clean_title.split())
        
        # Truncate for better results
        if len(clean_title) > 100:
            clean_title = clean_title[:100].rsplit(' ', 1)[0]
        
        logger.info(f"CrossRef title search: {clean_title[:50]}...")
        
        try:
            encoded_title = urllib.parse.quote(clean_title)
            url = f"https://api.crossref.org/works?query.title={encoded_title}&rows=5"
            
            response = requests.get(url, headers={
                'User-Agent': 'CitationSculptor/1.0 (mailto:support@example.com)'
            }, timeout=15)
            response.raise_for_status()
            
            data = response.json()
            items = data.get('message', {}).get('items', [])
            
            if not items:
                logger.warning(f"No CrossRef results for title: {clean_title[:40]}...")
                return None
            
            # Check for title match
            # Normalize both titles the same way - remove all non-alphanumeric except spaces
            title_normalized = re.sub(r'[^\w\s]', '', clean_title.lower())
            title_words = set(title_normalized.split())
            for item in items:
                item_title = item.get('title', [''])[0] if item.get('title') else ''
                item_normalized = re.sub(r'[^\w\s]', '', item_title.lower())
                item_words = set(item_normalized.split())
                
                if title_words and item_words:
                    overlap = len(title_words & item_words) / len(title_words)
                    if overlap >= 0.7:
                        # Good match - parse it
                        doi = item.get('DOI', '')
                        logger.info(f"CrossRef match (overlap {overlap:.2f}): DOI {doi}")
                        return self._parse_crossref_item(item, doi)
            
            logger.warning(f"No good title match in CrossRef results")
            return None
            
        except Exception as e:
            logger.warning(f"CrossRef title search failed: {e}")
            return None
    
    def _parse_crossref_item(self, item: dict, doi: str) -> CrossRefMetadata:
        """Parse a CrossRef API item into CrossRefMetadata."""
        title = item.get('title', [''])[0] if item.get('title') else ''
        
        # Authors
        authors = []
        for author in item.get('author', []):
            family = author.get('family', '')
            given = author.get('given', '')
            if family:
                authors.append(f"{family} {given}".strip())
        
        # Container (journal for articles, book title for chapters)
        container = item.get('container-title', [])
        container_title = container[0] if container else ''
        
        # Date
        year = ''
        date_parts = item.get('published', {}).get('date-parts', [[]])
        if date_parts and date_parts[0]:
            year = str(date_parts[0][0])
        
        # Pages
        pages = item.get('page', '')
        
        # Volume/issue
        volume = item.get('volume', '')
        issue = item.get('issue', '')
        
        # Work type
        work_type = item.get('type', 'journal-article')
        
        return CrossRefMetadata(
            doi=doi,
            title=title,
            work_type=work_type,
            authors=authors,
            container_title=container_title,
            book_title=container_title if work_type == 'book-chapter' else '',
            publisher=item.get('publisher', ''),
            year=year,
            volume=volume,
            issue=issue,
            pages=pages,
        )
    
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


@dataclass
class WebpageMetadata:
    """Metadata extracted from a webpage's citation meta tags."""
    title: str
    url: str
    authors: List[str] = field(default_factory=list)
    journal: str = ""
    volume: str = ""
    issue: str = ""
    first_page: str = ""
    last_page: str = ""
    year: str = ""
    month: str = ""
    doi: str = ""
    site_name: str = ""  # From og:site_name - organization/publisher name
    published_date: str = ""  # Full date string (YYYY-MM-DD) if available
    
    @property
    def pages(self) -> str:
        if self.first_page and self.last_page:
            return f"{self.first_page}-{self.last_page}"
        return self.first_page
    
    def get_first_author_label(self) -> str:
        if not self.authors:
            return "Unknown"
        first = self.authors[0].replace(',', ' ').split()
        if len(first) >= 2:
            last_name = first[-1] if len(first[-1]) > 2 else first[0]
            initials = ''.join([p[0].upper() for p in first if p != last_name and len(p) > 0])
            return f"{last_name}{initials}"
        return self.authors[0].replace(' ', '')[:10]
    
    def format_authors_vancouver(self, max_authors: int = 3) -> str:
        if not self.authors:
            return ""
        formatted = []
        for author in self.authors[:max_authors]:
            parts = author.strip().split()
            if len(parts) >= 2:
                last_name = parts[-1]
                initials = ''.join([p[0].upper() for p in parts[:-1]])
                formatted.append(f"{last_name} {initials}")
            else:
                formatted.append(author)
        if len(self.authors) > max_authors:
            return ', '.join(formatted) + ', et al'
        return ', '.join(formatted)


class WebpageScraper:
    """Scrapes citation metadata from webpages (both academic and general)."""
    
    # Known news/media domains for better organization name extraction
    KNOWN_DOMAINS = {
        'politico.com': 'Politico',
        'nytimes.com': 'The New York Times',
        'washingtonpost.com': 'The Washington Post',
        'wsj.com': 'The Wall Street Journal',
        'reuters.com': 'Reuters',
        'bbc.com': 'BBC',
        'cnn.com': 'CNN',
        'fiercehealthcare.com': 'FierceHealthcare',
        'healthaffairs.org': 'Health Affairs',
        'kff.org': 'Kaiser Family Foundation (KFF)',
        'cbpp.org': 'Center on Budget and Policy Priorities (CBPP)',
        'mckinsey.com': 'McKinsey & Company',
    }
    
    # Meta tag patterns for academic pages
    ACADEMIC_PATTERNS = {
        'title': ['citation_title', 'dc.title'],
        'author': ['citation_author', 'dc.creator'],
        'journal': ['citation_journal_title', 'citation_journal_abbrev', 'dc.source'],
        'volume': ['citation_volume'],
        'issue': ['citation_issue'],
        'first_page': ['citation_firstpage'],
        'last_page': ['citation_lastpage'],
        'doi': ['citation_doi', 'dc.identifier'],
        'year': ['citation_year'],
        'date': ['citation_publication_date', 'citation_date', 'dc.date'],
    }
    
    # Meta tag patterns for general webpages (Open Graph, etc.)
    GENERAL_PATTERNS = {
        'title': ['og:title', 'twitter:title'],
        'site_name': ['og:site_name', 'application-name'],
        'author': ['author', 'article:author', 'm_authors', 'm_author'],
        'date': ['article:published_time', 'article:modified_time', 'pubdate', 
                 'publishdate', 'date', 'og:updated_time'],
        'description': ['description', 'og:description'],
    }
    
    
    def __init__(self, timeout: int = 10):
        self.timeout = timeout
    
    def extract_metadata(self, url: str) -> Optional[WebpageMetadata]:
        """Extract citation metadata from a webpage's meta tags."""
        result, _ = self.extract_metadata_with_status(url)
        return result
    
    def extract_metadata_with_status(self, url: str) -> Tuple[Optional[WebpageMetadata], Optional[str]]:
        """
        Extract citation metadata with failure reason.
        
        Returns:
            Tuple of (metadata, failure_reason)
            - If successful: (WebpageMetadata, None)
            - If failed: (None, "reason string")
        """
        try:
            logger.info(f"Scraping metadata from: {url[:60]}...")
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
                'Accept': 'text/html,application/xhtml+xml',
                'Accept-Language': 'en-US,en;q=0.9',
            }
            response = requests.get(url, headers=headers, timeout=self.timeout)
            response.raise_for_status()
            
            # Check for Cloudflare or JavaScript challenge pages
            if 'Just a moment' in response.text or 'challenge-platform' in response.text:
                logger.warning(f"Site uses bot protection (Cloudflare): {url}")
                # Try URL-based extraction as fallback
                url_metadata = self._extract_metadata_from_url(url)
                return url_metadata, "blocked_cloudflare"
            
            if 'Enable JavaScript' in response.text and len(response.text) < 10000:
                logger.warning(f"Site requires JavaScript: {url}")
                # Try URL-based extraction as fallback
                url_metadata = self._extract_metadata_from_url(url)
                return url_metadata, "blocked_javascript"
            
            metadata = self._parse_html(response.text, url)
            return metadata, None
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 403:
                logger.warning(f"Access forbidden (403): {url}")
                # Try URL-based extraction as fallback
                url_metadata = self._extract_metadata_from_url(url)
                return url_metadata, "blocked_403"
            elif e.response.status_code == 401:
                logger.warning(f"Authentication required (401): {url}")
                return None, "blocked_auth"
            else:
                logger.warning(f"HTTP error {e.response.status_code}: {url}")
                return None, f"http_error_{e.response.status_code}"
        except requests.exceptions.Timeout:
            logger.warning(f"Request timed out: {url}")
            # Try URL-based extraction as fallback
            url_metadata = self._extract_metadata_from_url(url)
            return url_metadata, "timeout"
        except Exception as e:
            logger.warning(f"Failed to scrape {url}: {e}")
            return None, "error"
    
    def _extract_metadata_from_url(self, url: str) -> Optional[WebpageMetadata]:
        """
        Extract metadata from URL patterns when page scraping fails.
        
        Extracts:
        - Organization from domain (using known domains or capitalizing)
        - Title from URL slug
        - Date from URL path patterns (/2025/04/09/)
        """
        import urllib.parse
        
        try:
            parsed = urllib.parse.urlparse(url)
            domain = parsed.netloc.lower().replace('www.', '')
            path = parsed.path
            
            # Get organization name
            site_name = ""
            for known_domain, org_name in self.KNOWN_DOMAINS.items():
                if known_domain in domain:
                    site_name = org_name
                    break
            
            if not site_name:
                # Capitalize the domain name
                domain_parts = domain.split('.')
                if domain_parts:
                    site_name = domain_parts[0].capitalize()
            
            # Extract date from URL path: /2025/04/09/ or /2025-04-09/
            year, month, day = "", "", ""
            date_match = re.search(r'/(\d{4})/(\d{2})/(\d{2})(?:/|$)', path)
            if date_match:
                year, month, day = date_match.groups()
            else:
                date_match = re.search(r'/(\d{4})-(\d{2})-(\d{2})(?:/|$|-)', path)
                if date_match:
                    year, month, day = date_match.groups()
            
            # Extract title from URL slug
            title = ""
            # Get the last meaningful path segment
            path_parts = [p for p in path.strip('/').split('/') if p]
            if path_parts:
                # Skip date parts and get the slug
                slug = path_parts[-1]
                # Remove file extension
                slug = re.sub(r'\.\w+$', '', slug)
                # Remove trailing IDs (e.g., -00276442, -12345678)
                slug = re.sub(r'[-_]\d{6,}$', '', slug)
                # Skip if it looks like just an ID
                if not re.match(r'^[\d-]+$', slug) and len(slug) > 5:
                    # Convert slug to title
                    title = slug.replace('-', ' ').replace('_', ' ')
                    # Title case
                    title = ' '.join(word.capitalize() for word in title.split())
            
            if not title and not year:
                return None  # Nothing useful extracted
            
            published_date = ""
            if year and month and day:
                published_date = f"{year}-{month}-{day}"
            
            logger.info(f"Extracted from URL: title={title[:30]}..., site={site_name}, date={year}")
            
            return WebpageMetadata(
                title=title,
                url=url,
                authors=[],
                journal="",
                volume="",
                issue="",
                first_page="",
                last_page="",
                year=year,
                month=month,
                doi="",
                site_name=site_name,
                published_date=published_date,
            )
            
        except Exception as e:
            logger.warning(f"URL extraction failed: {e}")
            return None
    
    def _parse_html(self, html: str, url: str) -> Optional[WebpageMetadata]:
        meta_tags = self._extract_meta_tags(html)
        if not meta_tags:
            return None
        
        # Check for academic citation meta tags
        has_citation_tags = any(k.startswith('citation_') or k.startswith('dc.') for k in meta_tags.keys())
        
        if has_citation_tags:
            # Academic page - use academic patterns
            return self._parse_academic_page(meta_tags, html, url)
        else:
            # General webpage - use general patterns
            return self._parse_general_page(meta_tags, html, url)
    
    def _parse_academic_page(self, meta_tags: Dict[str, List[str]], html: str, url: str) -> Optional[WebpageMetadata]:
        """Parse academic pages with citation_* meta tags."""
        title = self._get_first_value(meta_tags, self.ACADEMIC_PATTERNS['title'])
        if not title:
            title = self._get_first_value(meta_tags, ['og:title'])
        if not title:
            m = re.search(r'<title>([^<]+)</title>', html, re.IGNORECASE)
            if m:
                title = m.group(1).strip()
        if not title:
            return None
        
        authors = self._get_all_values(meta_tags, self.ACADEMIC_PATTERNS['author'])
        journal = self._get_first_value(meta_tags, self.ACADEMIC_PATTERNS['journal']) or ""
        volume = self._get_first_value(meta_tags, self.ACADEMIC_PATTERNS['volume']) or ""
        issue = self._get_first_value(meta_tags, self.ACADEMIC_PATTERNS['issue']) or ""
        first_page = self._get_first_value(meta_tags, self.ACADEMIC_PATTERNS['first_page']) or ""
        last_page = self._get_first_value(meta_tags, self.ACADEMIC_PATTERNS['last_page']) or ""
        
        doi = self._get_first_value(meta_tags, self.ACADEMIC_PATTERNS['doi']) or ""
        if doi:
            doi = re.sub(r'^doi:\s*', '', doi, flags=re.IGNORECASE)
            m = re.search(r'(10\.\d{4,}/[^\s]+)', doi)
            if m:
                doi = m.group(1)
            else:
                # Not a valid DOI, clear it
                doi = ""
        
        year, month, day = self._extract_date(meta_tags, self.ACADEMIC_PATTERNS['date'])
        
        site_name = self._get_first_value(meta_tags, self.GENERAL_PATTERNS['site_name']) or ""
        
        # Detect StatPearls content hosted on NCBI Bookshelf
        if 'ncbi.nlm.nih.gov/books/' in url:
            # Check if this is StatPearls content
            if 'statpearls' in html.lower() or 'stat pearls' in html.lower():
                journal = "StatPearls [Internet]"
                site_name = "StatPearls Publishing"
            elif site_name == "NCBI Bookshelf":
                # Keep as NCBI Books but format properly
                journal = "NCBI Bookshelf [Internet]"
        
        logger.info(f"Extracted academic: {title[:50]}... by {len(authors)} authors")
        return WebpageMetadata(
            title=title.strip(), url=url, authors=authors, journal=journal.strip(),
            volume=volume.strip(), issue=issue.strip(), first_page=first_page.strip(),
            last_page=last_page.strip(), year=year, month=month, doi=doi.strip(),
            site_name=site_name.strip(), published_date=f"{year}-{month}-{day}" if day else ""
        )
    
    def _parse_general_page(self, meta_tags: Dict[str, List[str]], html: str, url: str) -> Optional[WebpageMetadata]:
        """Parse general webpages using Open Graph and other common meta tags."""
        title = self._get_first_value(meta_tags, self.GENERAL_PATTERNS['title'])
        if not title:
            m = re.search(r'<title>([^<]+)</title>', html, re.IGNORECASE)
            if m:
                title = m.group(1).strip()
        if not title:
            return None
        
        # Try multiple methods to extract organization name, then pick the most specific
        site_name_candidates = []
        
        # Method 1: Meta tags (og:site_name, application-name)
        meta_site = self._get_first_value(meta_tags, self.GENERAL_PATTERNS['site_name']) or ""
        if meta_site:
            site_name_candidates.append(('meta', meta_site))
        
        # Method 2: URL domain (especially for .edu domains)
        url_site = self._extract_org_from_url(url)
        if url_site:
            site_name_candidates.append(('url', url_site))
        
        # Method 3: Title hierarchy (» or | separators)
        if title and ('»' in title or '&raquo;' in title):
            parts = re.split(r'\s*(?:»|&raquo;)\s*', title)
            if len(parts) >= 2:
                title_site = parts[-1].strip()
                # For .edu domains, try to get a fuller name with Division
                if '.edu' in url and len(parts) >= 3:
                    last_part = parts[-1].strip()  # e.g., "University of Florida"
                    second_last = parts[-2].strip()  # e.g., "College of Medicine"
                    third_last = parts[-3].strip() if len(parts) >= 3 else ""
                    
                    # Build organization name - prioritize Division over College
                    if 'Division' in third_last:
                        title_site = f"{last_part} {third_last}"
                    elif 'Division' in second_last:
                        title_site = f"{last_part} {second_last}"
                
                if title_site:
                    site_name_candidates.append(('title', title_site))
        
        # Method 4: Use local LLM (Ollama) as fallback for complex cases
        if not site_name_candidates or all(len(c[1]) < 15 for c in site_name_candidates):
            llm_site = self._extract_org_with_llm(title, url)
            if llm_site:
                site_name_candidates.append(('llm', llm_site))
        
        # Pick the most specific (longest) organization name
        site_name = ""
        if site_name_candidates:
            # Sort by length (descending) and pick the longest
            site_name_candidates.sort(key=lambda x: len(x[1]), reverse=True)
            site_name = site_name_candidates[0][1]
            logger.debug(f"Site name candidates: {site_name_candidates}, picked: '{site_name}'")
        
        # Get authors (less common on general webpages)
        # Filter out obvious non-author values (CMS usernames, system accounts, etc.)
        raw_authors = self._get_all_values(meta_tags, self.GENERAL_PATTERNS['author'])
        authors = [a for a in raw_authors if self._is_valid_author(a)]
        
        # If no authors in meta tags, try JSON-LD
        if not authors:
            authors = self._extract_author_from_jsonld(html)
        
        # Try meta description "By: Author Name" pattern (more reliable than HTML)
        if not authors:
            description = self._get_first_value(meta_tags, self.GENERAL_PATTERNS['description']) or ""
            if description:
                # Pattern matches "By: First Last" with optional credentials like ", Esq."
                by_match = re.match(r'By:\s*([A-Z][a-z]+\s+[A-Z][a-z]+)(?:,?\s*(?:Esq|JD|MD|PhD|DO)\.?)?', description)
                if by_match:
                    author = by_match.group(1).strip()  # Only capture the name, not credentials
                    if self._is_valid_author(author):
                        authors = [author]
                        logger.debug(f"Extracted author from meta description: {author}")
        
        # If still no authors, try HTML patterns (bylines, author links, etc.)
        if not authors:
            authors = self._extract_author_from_html(html)
        
        # Extract date from various patterns (meta tags first)
        year, month, day = self._extract_date(meta_tags, self.GENERAL_PATTERNS['date'])
        
        # If no date in meta tags, try JSON-LD structured data
        if not year:
            year, month, day = self._extract_date_from_jsonld(html)
        
        # Also try to extract date from URL (e.g., /2025-05-12/ or /2025/05/12/)
        if not year:
            url_date = re.search(r'/(\d{4})[-/](\d{2})[-/](\d{2})(?:/|$|-)', url)
            if url_date:
                year = url_date.group(1)
                month = url_date.group(2)
                day = url_date.group(3)
        
        # Try to extract date from common HTML patterns
        if not year:
            year, month, day = self._extract_date_from_html(html)
        
        # Check if this is an evergreen page type (typically no date expected)
        is_evergreen = self._is_evergreen_page(url, title)
        if not year and is_evergreen:
            # Don't flag as Null_Date - use empty string (formatter will handle)
            logger.debug(f"Evergreen page detected, not flagging for missing date: {url[:60]}")
        
        published_date = ""
        if year and month and day:
            published_date = f"{year}-{month}-{day}"
        elif year and month:
            published_date = f"{year}-{month}"
        
        logger.info(f"Extracted general: {title[:50]}... site={site_name}, year={year}, evergreen={is_evergreen}")
        return WebpageMetadata(
            title=title.strip(), url=url, authors=authors, journal="",
            volume="", issue="", first_page="", last_page="",
            year=year if year else ("" if is_evergreen else ""), month=month, doi="",
            site_name=site_name.strip(), published_date=published_date
        )
    
    def _is_evergreen_page(self, url: str, title: str) -> bool:
        """Detect if a page is evergreen content that typically doesn't have dates."""
        url_lower = url.lower()
        title_lower = title.lower() if title else ""
        
        # URL patterns indicating evergreen/institutional pages
        evergreen_url_patterns = [
            '/about', '/about-us', '/our-team', '/contact', '/services',
            '/patient-care', '/clinical-services', '/departments',
            '/programs', '/specialties', '/divisions', '/clinics',
            '/find-', '/locations', '/staff', '/faculty',
            '/practice', '/procedures', '/treatments',
            '/what-we-do', '/who-we-are', '/our-mission',
            '/resources', '/tools', '/calculators',
            '/faq', '/help', '/support',
        ]
        
        # Check URL patterns
        for pattern in evergreen_url_patterns:
            if pattern in url_lower:
                return True
        
        # Title patterns indicating evergreen content
        evergreen_title_patterns = [
            'about us', 'contact us', 'our services', 'our team',
            'find a doctor', 'find a provider', 'patient care',
            'clinical services', 'our practice', 'meet our',
            'locations', 'directions', 'hours',
        ]
        
        for pattern in evergreen_title_patterns:
            if pattern in title_lower:
                return True
        
        # Domain patterns - organization homepages often don't have dates
        # But only if URL path is short (landing page)
        from urllib.parse import urlparse
        parsed = urlparse(url)
        path = parsed.path.strip('/')
        
        # Short paths on organization domains are likely landing pages
        if len(path.split('/')) <= 1 and not any(c.isdigit() for c in path):
            # Check if it's likely an org domain (not a news site or blog)
            news_indicators = ['news', 'blog', 'article', 'post', 'story']
            if not any(ind in url_lower for ind in news_indicators):
                return True
        
        return False
    
    def _extract_date(self, meta_tags: Dict[str, List[str]], date_keys: List[str]) -> Tuple[str, str, str]:
        """Extract year, month, day from date meta tags."""
        date_str = self._get_first_value(meta_tags, date_keys) or ""
        
        if not date_str:
            return "", "", ""
        
        # Try ISO format: 2025-05-12T... or 2025-05-12
        m = re.match(r'(\d{4})[-/](\d{2})[-/](\d{2})', date_str)
        if m:
            return m.group(1), m.group(2), m.group(3)
        
        # Try year-month format: 2025-05 or 2025/05
        m = re.match(r'(\d{4})[-/](\d{2})', date_str)
        if m:
            return m.group(1), m.group(2), ""
        
        # Try just year: 2025
        m = re.match(r'(\d{4})', date_str)
        if m:
            return m.group(1), "", ""
        
        return "", "", ""
    
    def _extract_date_from_html(self, html: str) -> Tuple[str, str, str]:
        """Extract date from common HTML patterns like <time> or date divs."""
        # Month name mapping
        months = {
            'january': '01', 'february': '02', 'march': '03', 'april': '04',
            'may': '05', 'june': '06', 'july': '07', 'august': '08',
            'september': '09', 'october': '10', 'november': '11', 'december': '12',
            'jan': '01', 'feb': '02', 'mar': '03', 'apr': '04',
            'jun': '06', 'jul': '07', 'aug': '08', 'sep': '09', 
            'oct': '10', 'nov': '11', 'dec': '12'
        }
        
        # Try <time datetime="..."> first
        time_match = re.search(r'<time[^>]*datetime=["\']([^"\']+)["\']', html, re.IGNORECASE)
        if time_match:
            dt = time_match.group(1)
            m = re.match(r'(\d{4})[-/](\d{2})[-/](\d{2})', dt)
            if m:
                return m.group(1), m.group(2), m.group(3)
        
        # Try common date patterns in HTML: <div class="article-date">, <span class="date">, etc.
        date_patterns = [
            r'class=["\'](?:article-date|post-date|entry-date|published|date)["\'][^>]*>([^<]+)<',
            r'class=["\'][^"\']*date[^"\']*["\'][^>]*>([^<]+)<',
        ]
        
        for pattern in date_patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                date_text = match.group(1).strip()
                # Try "October 30, 2018" format
                m = re.match(r'([A-Za-z]+)\s+(\d{1,2}),?\s+(\d{4})', date_text)
                if m:
                    month_name = m.group(1).lower()
                    day = m.group(2).zfill(2)
                    year = m.group(3)
                    month = months.get(month_name, "")
                    if month:
                        logger.debug(f"Extracted date from HTML: {year}-{month}-{day}")
                        return year, month, day
                
                # Try "30 October 2018" format
                m = re.match(r'(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})', date_text)
                if m:
                    day = m.group(1).zfill(2)
                    month_name = m.group(2).lower()
                    year = m.group(3)
                    month = months.get(month_name, "")
                    if month:
                        logger.debug(f"Extracted date from HTML: {year}-{month}-{day}")
                        return year, month, day
                
                # Try ISO format in text
                m = re.match(r'(\d{4})[-/](\d{1,2})[-/](\d{1,2})', date_text)
                if m:
                    return m.group(1), m.group(2).zfill(2), m.group(3).zfill(2)
        
        return "", "", ""
    
    def _extract_author_from_html(self, html: str) -> List[str]:
        """Extract authors from common HTML patterns like bylines and author links."""
        authors = []
        
        # Pattern 1: <p id='publication-byline'>by <a...>Author Name</a></p>
        byline_match = re.search(
            r'(?:id|class)=["\'](?:publication-byline|byline|author-name)["\'][^>]*>.*?by\s*<a[^>]*>([^<]+)</a>',
            html, re.IGNORECASE | re.DOTALL
        )
        if byline_match:
            author = byline_match.group(1).strip()
            if self._is_valid_author(author):
                authors.append(author)
                logger.debug(f"Extracted author from byline: {author}")
                return authors
        
        # Pattern 2: <a rel='author'...>Author Name</a>
        author_links = re.findall(r'<a[^>]*rel=["\']author["\'][^>]*>([^<]+)</a>', html, re.IGNORECASE)
        for author in author_links:
            author = author.strip()
            if self._is_valid_author(author) and author not in authors:
                authors.append(author)
        if authors:
            logger.debug(f"Extracted authors from rel=author links: {authors}")
            return authors
        
        # Pattern 3: <span class="author">Author Name</span> or similar
        author_spans = re.findall(
            r'<(?:span|div)[^>]*class=["\'][^"\']*author[^"\']*["\'][^>]*>([^<]+)</(?:span|div)>',
            html, re.IGNORECASE
        )
        for author in author_spans:
            author = author.strip()
            if self._is_valid_author(author) and author not in authors:
                authors.append(author)
        if authors:
            logger.debug(f"Extracted authors from author spans: {authors}")
            return authors
        
        # Pattern 4: "By Author Name" or "Written by Author Name" in text
        by_pattern = re.search(
            r'(?:written\s+)?by\s+([A-Z][a-z]+(?:\s+[A-Z]\.?\s*)?[A-Z][a-z]+)',
            html
        )
        if by_pattern:
            author = by_pattern.group(1).strip()
            if self._is_valid_author(author):
                authors.append(author)
                logger.debug(f"Extracted author from 'by' text: {author}")
        
        return authors
    
    def _extract_org_from_url(self, url: str) -> str:
        """Extract organization name from URL, especially for .edu domains."""
        from urllib.parse import urlparse
        
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        
        # Known .edu domain mappings
        edu_orgs = {
            'ufl.edu': 'University of Florida',
            'harvard.edu': 'Harvard University',
            'stanford.edu': 'Stanford University',
            'mit.edu': 'MIT',
            'yale.edu': 'Yale University',
            'columbia.edu': 'Columbia University',
            'upenn.edu': 'University of Pennsylvania',
            'jhu.edu': 'Johns Hopkins University',
            'duke.edu': 'Duke University',
            'unc.edu': 'University of North Carolina',
            'ucla.edu': 'UCLA',
            'usc.edu': 'USC',
            'nyu.edu': 'NYU',
            'cornell.edu': 'Cornell University',
            'bc.edu': 'Boston College',
            'bu.edu': 'Boston University',
            'mayo.edu': 'Mayo Clinic',
        }
        
        # Check if it's an .edu domain
        if '.edu' in domain:
            # Find the base .edu domain
            for edu_domain, org_name in edu_orgs.items():
                if domain.endswith(edu_domain) or domain == edu_domain:
                    # Check for subdomain that indicates department/division
                    subdomain = domain.replace(edu_domain, '').rstrip('.')
                    if subdomain:
                        parts = subdomain.split('.')
                        # cardiology.medicine.ufl.edu -> ["cardiology", "medicine"]
                        if parts:
                            dept = parts[0].title()  # "cardiology" -> "Cardiology"
                            if dept.lower() in ['cardiology', 'medicine', 'health', 'nursing', 
                                                'pharmacy', 'dentistry', 'law', 'business',
                                                'engineering', 'science', 'arts']:
                                return f"{org_name} {dept}"
                    return org_name
            
            # Generic .edu handling - extract from domain
            # e.g., "someuniv.edu" -> "Someuniv"
            base = domain.split('.')[0] if '.' in domain else domain
            if base and base not in ['www', 'web']:
                return base.replace('-', ' ').title()
        
        return ""
    
    def _extract_org_with_llm(self, title: str, url: str) -> str:
        """Use local Ollama LLM to extract organization name from title/URL."""
        try:
            prompt = f"""Extract the organization or institution name from this webpage information.
Return ONLY the organization name, nothing else. Be concise but complete.

Title: {title}
URL: {url}

Examples:
- "Preventive Cardiology » Division of Cardiovascular Medicine » University of Florida" → "University of Florida Division of Cardiovascular Medicine"
- "Understanding ABNs - Florida Healthcare Lawfirm" → "Florida Healthcare Law Firm"
- "Risk Pooling | American Academy of Actuaries" → "American Academy of Actuaries"

Organization name:"""

            response = requests.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": "llama3:8b",
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.1, "num_predict": 50}
                },
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json().get('response', '').strip()
                # Clean up the result - remove quotes, newlines, etc.
                result = result.strip('"\'').split('\n')[0].strip()
                if result and len(result) > 3 and len(result) < 100:
                    logger.debug(f"LLM extracted organization: {result}")
                    return result
        except requests.exceptions.ConnectionError:
            logger.debug("Ollama not available for org extraction")
        except Exception as e:
            logger.debug(f"LLM org extraction failed: {e}")
        
        return ""
    
    def _extract_date_from_jsonld(self, html: str) -> Tuple[str, str, str]:
        """Extract publication date from JSON-LD structured data."""
        data_list = self._parse_all_jsonld(html)
        
        for data in data_list:
            result = self._extract_date_from_jsonld_object(data)
            if result[0]:  # If year found
                return result
        
        return "", "", ""
    
    def _clean_author_name(self, name: str) -> str:
        """Clean up author name by removing organization suffixes."""
        if not name:
            return ""
        
        # Remove organization suffixes like "Author Name - Organization" or "Author | Org"
        # Common patterns: " - KFF Health News", " | Reuters", " for NPR"
        separators = [' - ', ' | ', ' for ', ' at ', ' of ']
        for sep in separators:
            if sep in name:
                parts = name.split(sep)
                # Keep only the first part if it looks like a person name
                first_part = parts[0].strip()
                # Check if it looks like a person name (has First Last pattern)
                if re.match(r'^[A-Z][a-z]+\s+[A-Z][a-z]+', first_part):
                    name = first_part
                    break
        
        # Remove trailing credentials
        name = re.sub(r',?\s*(?:Esq|JD|MD|PhD|DO|RN|MBA)\.?\s*$', '', name, flags=re.IGNORECASE)
        
        return name.strip()
    
    def _extract_author_from_jsonld(self, html: str) -> List[str]:
        """Extract authors from JSON-LD structured data."""
        data_list = self._parse_all_jsonld(html)
        authors = []
        
        for data in data_list:
            if not isinstance(data, dict):
                continue
            
            author_data = data.get('author')
            if author_data:
                if isinstance(author_data, list):
                    for a in author_data:
                        if isinstance(a, dict) and a.get('name'):
                            authors.append(self._clean_author_name(a['name']))
                        elif isinstance(a, str):
                            authors.append(self._clean_author_name(a))
                elif isinstance(author_data, dict) and author_data.get('name'):
                    authors.append(self._clean_author_name(author_data['name']))
                elif isinstance(author_data, str):
                    authors.append(self._clean_author_name(author_data))
            
            # Check nested @graph
            if '@graph' in data and isinstance(data['@graph'], list):
                for item in data['@graph']:
                    if isinstance(item, dict):
                        item_author = item.get('author')
                        if item_author:
                            if isinstance(item_author, dict) and item_author.get('name'):
                                authors.append(item_author['name'])
                            elif isinstance(item_author, str):
                                authors.append(item_author)
                        
                        # Check description for "By: Author Name" pattern
                        desc = item.get('description', '')
                        if desc and not authors:
                            by_match = re.match(r'By:\s*([A-Z][a-z]+(?:\s+[A-Z]\.?\s*)?[A-Z][a-z]+(?:,?\s*(?:Esq|JD|MD|PhD|DO)\.?)?)', desc)
                            if by_match:
                                authors.append(by_match.group(1).strip())
                        
                        # Check articleSection which sometimes contains author names
                        article_section = item.get('articleSection', [])
                        if isinstance(article_section, list) and not authors:
                            for section in article_section:
                                if isinstance(section, str) and re.match(r'^[A-Z][a-z]+\s+[A-Z][a-z]+$', section):
                                    # Looks like a name (First Last)
                                    if self._is_valid_author(section):
                                        authors.append(section)
                                        break
        
        # Filter and deduplicate
        return list(dict.fromkeys([a for a in authors if self._is_valid_author(a)]))
    
    def _parse_all_jsonld(self, html: str) -> List[Dict]:
        """Parse all JSON-LD blocks from HTML, handling HTML entities."""
        import json
        import html as html_module
        
        result = []
        
        # Find all JSON-LD script blocks
        jsonld_pattern = r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>'
        matches = re.findall(jsonld_pattern, html, re.DOTALL | re.IGNORECASE)
        
        for match in matches:
            try:
                # Decode HTML entities (e.g., &quot; -> ")
                decoded = html_module.unescape(match.strip())
                data = json.loads(decoded)
                
                # Handle array of objects
                if isinstance(data, list):
                    result.extend(data)
                else:
                    result.append(data)
                        
            except json.JSONDecodeError:
                continue
        
        return result
    
    def _extract_date_from_jsonld_object(self, data: Dict) -> Tuple[str, str, str]:
        """Extract date from a single JSON-LD object."""
        if not isinstance(data, dict):
            return "", "", ""
        
        # Common date fields in JSON-LD
        date_fields = ['datePublished', 'dateCreated', 'dateModified', 'publishDate']
        
        for field in date_fields:
            if field in data and data[field]:
                date_str = str(data[field])
                # Parse ISO format: 2021-06-07T10:38:13-0400 or 2021-06-07
                # Also handle non-padded dates: 2023-1-2
                m = re.match(r'(\d{4})[-/](\d{1,2})[-/](\d{1,2})', date_str)
                if m:
                    logger.debug(f"Found date in JSON-LD {field}: {date_str}")
                    # Pad month and day to 2 digits
                    year = m.group(1)
                    month = m.group(2).zfill(2)
                    day = m.group(3).zfill(2)
                    return year, month, day
        
        # Check nested @graph array (common in Schema.org)
        if '@graph' in data and isinstance(data['@graph'], list):
            for item in data['@graph']:
                result = self._extract_date_from_jsonld_object(item)
                if result[0]:
                    return result
        
        return "", "", ""
    
    def _extract_meta_tags(self, html: str) -> Dict[str, List[str]]:
        tags: Dict[str, List[str]] = {}
        # Match both name="..." content="..." and property="..." content="..."
        # Also handle reversed order: content="..." name="..."
        patterns = [
            r'<meta\s+(?:name|property)=["\']([^"\']+)["\']\s+content=["\']([^"\']*)["\']',
            r'<meta\s+content=["\']([^"\']*)["\'](?:\s+(?:name|property)=["\']([^"\']+)["\'])',
        ]
        for pattern in patterns:
            for m in re.finditer(pattern, html, re.IGNORECASE):
                if pattern.startswith(r'<meta\s+content'):
                    # Reversed order
                    content = m.group(1)
                    name = m.group(2).lower() if m.group(2) else ""
                else:
                    name = m.group(1).lower()
                    content = m.group(2)
                
                if name:
                    if name not in tags:
                        tags[name] = []
                    if content and content not in tags[name]:
                        tags[name].append(content)
        return tags
    
    def _get_first_value(self, tags: Dict[str, List[str]], keys: List[str]) -> Optional[str]:
        for key in keys:
            if key.lower() in tags and tags[key.lower()]:
                return tags[key.lower()][0]
        return None
    
    def _get_all_values(self, tags: Dict[str, List[str]], keys: List[str]) -> List[str]:
        values = []
        for key in keys:
            if key.lower() in tags:
                for v in tags[key.lower()]:
                    if v and v not in values:
                        values.append(v)
        return values
    
    def _is_valid_author(self, author: str) -> bool:
        """Check if an author string looks like a real person's name, not a CMS username."""
        if not author:
            return False
        
        # Reject obvious system/CMS usernames
        invalid_patterns = [
            r'^[a-z]+_[a-z]+$',  # underscore usernames like "kpage_drupal_sso"
            r'^admin',  # admin accounts
            r'@',  # email addresses
            r'drupal|wordpress|cms|sso|system|user|guest',  # CMS terms
            r'^\d+$',  # just numbers
            r'^[a-z]{1,3}\d+',  # short letter + number like "u123"
        ]
        
        author_lower = author.lower()
        for pattern in invalid_patterns:
            if re.search(pattern, author_lower):
                return False
        
        # Valid authors usually have spaces (first last) or commas (last, first)
        # Or at least look like names (capitalized, no underscores)
        if ' ' in author or ',' in author:
            return True
        
        # Single word that's capitalized and has no underscores might be okay
        if author[0].isupper() and '_' not in author and len(author) > 2:
            return True
        
        return False

