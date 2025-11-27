"""PubMed MCP Client Module - Communicates with PubMed MCP server."""

import json
import re
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
import requests
from loguru import logger


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
    """Client for PubMed MCP server."""

    DEFAULT_SERVER_URL = "http://127.0.0.1:3017/mcp"

    def __init__(self, server_url: Optional[str] = None):
        self.server_url = server_url or self.DEFAULT_SERVER_URL
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json, text/event-stream',
        })
        self._request_id = 0

    def _send_request(self, method: str, params: Dict[str, Any]) -> Optional[Dict]:
        """Send JSON-RPC request to MCP server."""
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": self._request_id,
        }
        self._request_id += 1

        try:
            logger.debug(f"Sending request: {method}")
            response = self.session.post(self.server_url, json=payload, timeout=30)
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
            logger.error("Request timed out")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
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

    def fetch_article_by_pmid(self, pmid: str) -> Optional[ArticleMetadata]:
        """Fetch article metadata by PMID."""
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

        return self._parse_fetch_result(result, pmid)

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
        authors = []
        for a in article.get('authors', []):
            if isinstance(a, dict):
                name = a.get('name', f"{a.get('lastName', '')} {a.get('initials', '')}".strip())
                authors.append(name)
            elif isinstance(a, str):
                authors.append(a)

        pub_date = article.get('pubDate', article.get('publicationDate', ''))
        year = article.get('year', '')
        if not year and pub_date:
            match = re.search(r'(\d{4})', str(pub_date))
            year = match.group(1) if match else ''

        return ArticleMetadata(
            pmid=str(article.get('pmid', '')),
            title=article.get('title', ''),
            authors=authors,
            journal=article.get('journal', article.get('journalTitle', '')),
            journal_abbreviation=article.get('journalAbbreviation', article.get('journalAbbrev', '')),
            year=str(year),
            month=str(article.get('month', '')),
            volume=str(article.get('volume', '')),
            issue=str(article.get('issue', '')),
            pages=article.get('pages', ''),
            doi=article.get('doi'),
            abstract=article.get('abstract', ''),
            pub_date=str(pub_date),
            pmcid=article.get('pmcid'),
        )

