"""
Document Intelligence Module - v2.3.0

Advanced document analysis features:
1. LLM-powered metadata extraction for edge cases
2. Link verification & broken link detection
3. Automatic citation suggestions based on content
4. Plagiarism-style citation checker (detects potentially uncited claims)
"""

import re
import json
import asyncio
import aiohttp
import requests
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Set
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from loguru import logger

# Import existing modules
try:
    from .llm_extractor import LLMMetadataExtractor, ExtractedMetadata
except ImportError:
    from modules.llm_extractor import LLMMetadataExtractor, ExtractedMetadata


class LinkStatus(Enum):
    """Status of a verified link."""
    OK = "ok"
    BROKEN = "broken"
    REDIRECT = "redirect"
    TIMEOUT = "timeout"
    ERROR = "error"
    PAYWALL = "paywall"
    ARCHIVED = "archived"
    SKIPPED = "skipped"


@dataclass
class LinkVerificationResult:
    """Result of a link verification check."""
    url: str
    status: LinkStatus
    status_code: Optional[int] = None
    final_url: Optional[str] = None  # After redirects
    error_message: Optional[str] = None
    response_time_ms: Optional[int] = None
    archived_url: Optional[str] = None  # Wayback Machine fallback
    content_type: Optional[str] = None
    reference_number: Optional[int] = None
    title: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'url': self.url,
            'status': self.status.value,
            'status_code': self.status_code,
            'final_url': self.final_url,
            'error_message': self.error_message,
            'response_time_ms': self.response_time_ms,
            'archived_url': self.archived_url,
            'content_type': self.content_type,
            'reference_number': self.reference_number,
            'title': self.title,
        }


@dataclass 
class CitationSuggestion:
    """A suggested citation for document content."""
    text_excerpt: str  # The text that needs a citation
    line_number: int
    reason: str  # Why this needs a citation
    confidence: float  # 0.0-1.0
    suggested_search_terms: List[str]  # Terms to search for citations
    category: str  # "statistic", "claim", "definition", "finding", etc.
    pubmed_results: List[Dict] = field(default_factory=list)  # Pre-fetched suggestions
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'text_excerpt': self.text_excerpt,
            'line_number': self.line_number,
            'reason': self.reason,
            'confidence': self.confidence,
            'suggested_search_terms': self.suggested_search_terms,
            'category': self.category,
            'pubmed_results': self.pubmed_results,
        }


@dataclass
class PotentialPlagiarism:
    """A passage that may need citation verification."""
    text: str
    line_number: int
    issue_type: str  # "uncited_statistic", "uncited_claim", "suspicious_phrasing"
    severity: str  # "high", "medium", "low"
    explanation: str
    existing_citation_nearby: bool = False
    suggested_action: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'text': self.text,
            'line_number': self.line_number,
            'issue_type': self.issue_type,
            'severity': self.severity,
            'explanation': self.explanation,
            'existing_citation_nearby': self.existing_citation_nearby,
            'suggested_action': self.suggested_action,
        }


class LinkVerifier:
    """
    Verifies URLs in citations are accessible.
    
    Features:
    - Parallel link checking
    - Redirect following
    - Wayback Machine fallback for broken links
    - Paywall detection
    """
    
    # Common paywall indicators
    PAYWALL_INDICATORS = [
        'access denied', 'subscription required', 'purchase article',
        'sign in to view', 'login required', 'institutional access',
        'full text not available', 'buy this article', 'rent this article',
    ]
    
    # Domains that typically require authentication
    PAYWALL_DOMAINS = [
        'sciencedirect.com', 'springer.com', 'wiley.com', 'nature.com',
        'cell.com', 'nejm.org', 'jamanetwork.com', 'thelancet.com',
        'ahajournals.org', 'bmj.com', 'annualreviews.org',
    ]
    
    USER_AGENT = 'CitationSculptor/2.3 (Link Verification Bot; +https://github.com/citationsculptor)'
    TIMEOUT = 15  # seconds
    
    def __init__(self, check_wayback: bool = True, max_workers: int = 5):
        self.check_wayback = check_wayback
        self.max_workers = max_workers
        self.wayback_api = "https://archive.org/wayback/available"
    
    def verify_url(self, url: str, reference_number: int = None, title: str = None) -> LinkVerificationResult:
        """Verify a single URL."""
        if not url or not url.startswith(('http://', 'https://')):
            return LinkVerificationResult(
                url=url or '',
                status=LinkStatus.SKIPPED,
                error_message="Invalid or empty URL",
                reference_number=reference_number,
                title=title,
            )
        
        start_time = datetime.now()
        
        try:
            # Make HEAD request first (faster), fall back to GET
            response = requests.head(
                url,
                headers={'User-Agent': self.USER_AGENT},
                timeout=self.TIMEOUT,
                allow_redirects=True,
            )
            
            # If HEAD fails, try GET
            if response.status_code >= 400:
                response = requests.get(
                    url,
                    headers={'User-Agent': self.USER_AGENT},
                    timeout=self.TIMEOUT,
                    allow_redirects=True,
                    stream=True,  # Don't download full content
                )
            
            elapsed_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            
            # Check for success
            if 200 <= response.status_code < 400:
                status = LinkStatus.OK
                
                # Check for redirect
                if response.url != url:
                    status = LinkStatus.REDIRECT
                
                # Check for paywall on known domains
                domain = urlparse(url).netloc.lower()
                if any(pd in domain for pd in self.PAYWALL_DOMAINS):
                    # Try to detect paywall in content
                    if response.status_code == 200:
                        try:
                            content = response.content[:5000].decode('utf-8', errors='ignore').lower()
                            if any(indicator in content for indicator in self.PAYWALL_INDICATORS):
                                status = LinkStatus.PAYWALL
                        except Exception:
                            pass
                
                return LinkVerificationResult(
                    url=url,
                    status=status,
                    status_code=response.status_code,
                    final_url=response.url if response.url != url else None,
                    response_time_ms=elapsed_ms,
                    content_type=response.headers.get('Content-Type'),
                    reference_number=reference_number,
                    title=title,
                )
            
            # Link appears broken
            archived_url = None
            if self.check_wayback:
                archived_url = self._get_wayback_url(url)
            
            return LinkVerificationResult(
                url=url,
                status=LinkStatus.ARCHIVED if archived_url else LinkStatus.BROKEN,
                status_code=response.status_code,
                error_message=f"HTTP {response.status_code}",
                response_time_ms=elapsed_ms,
                archived_url=archived_url,
                reference_number=reference_number,
                title=title,
            )
            
        except requests.exceptions.Timeout:
            return LinkVerificationResult(
                url=url,
                status=LinkStatus.TIMEOUT,
                error_message="Request timed out",
                reference_number=reference_number,
                title=title,
            )
        except requests.exceptions.RequestException as e:
            archived_url = None
            if self.check_wayback:
                archived_url = self._get_wayback_url(url)
            
            return LinkVerificationResult(
                url=url,
                status=LinkStatus.ARCHIVED if archived_url else LinkStatus.ERROR,
                error_message=str(e),
                archived_url=archived_url,
                reference_number=reference_number,
                title=title,
            )
    
    def _get_wayback_url(self, url: str) -> Optional[str]:
        """Check if URL is archived in Wayback Machine."""
        try:
            response = requests.get(
                self.wayback_api,
                params={'url': url},
                timeout=10,
            )
            if response.status_code == 200:
                data = response.json()
                if data.get('archived_snapshots', {}).get('closest', {}).get('available'):
                    return data['archived_snapshots']['closest']['url']
        except Exception as e:
            logger.debug(f"Wayback lookup failed for {url}: {e}")
        return None
    
    def verify_urls(self, urls: List[Dict[str, Any]]) -> List[LinkVerificationResult]:
        """
        Verify multiple URLs in parallel.
        
        Args:
            urls: List of dicts with 'url', optional 'reference_number', 'title'
        """
        results = []
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_url = {
                executor.submit(
                    self.verify_url, 
                    item.get('url'), 
                    item.get('reference_number'),
                    item.get('title')
                ): item 
                for item in urls
            }
            
            for future in as_completed(future_to_url):
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    item = future_to_url[future]
                    results.append(LinkVerificationResult(
                        url=item.get('url', ''),
                        status=LinkStatus.ERROR,
                        error_message=str(e),
                        reference_number=item.get('reference_number'),
                        title=item.get('title'),
                    ))
        
        return results
    
    def verify_document(self, content: str) -> Dict[str, Any]:
        """
        Extract and verify all URLs from a markdown document.
        
        Returns:
            Dict with verification results and summary statistics
        """
        # Extract URLs from markdown links and raw URLs
        url_pattern = r'\[([^\]]*)\]\((https?://[^)]+)\)'
        raw_url_pattern = r'(?<!\()(https?://[^\s\)<>]+)(?!\))'
        
        urls_to_check = []
        
        # Find markdown links
        for match in re.finditer(url_pattern, content):
            title = match.group(1)
            url = match.group(2)
            line_number = content[:match.start()].count('\n') + 1
            urls_to_check.append({
                'url': url,
                'title': title,
                'line_number': line_number,
            })
        
        # Find raw URLs (not already in markdown links)
        existing_urls = {u['url'] for u in urls_to_check}
        for match in re.finditer(raw_url_pattern, content):
            url = match.group(1).rstrip('.,;:')
            if url not in existing_urls:
                line_number = content[:match.start()].count('\n') + 1
                urls_to_check.append({
                    'url': url,
                    'line_number': line_number,
                })
                existing_urls.add(url)
        
        # Verify all URLs
        logger.info(f"Verifying {len(urls_to_check)} URLs...")
        results = self.verify_urls(urls_to_check)
        
        # Generate summary
        status_counts = {}
        for result in results:
            status = result.status.value
            status_counts[status] = status_counts.get(status, 0) + 1
        
        broken = [r for r in results if r.status in (LinkStatus.BROKEN, LinkStatus.ERROR)]
        redirects = [r for r in results if r.status == LinkStatus.REDIRECT]
        archived = [r for r in results if r.status == LinkStatus.ARCHIVED]
        paywalled = [r for r in results if r.status == LinkStatus.PAYWALL]
        
        return {
            'total_urls': len(urls_to_check),
            'verified': len(results),
            'status_summary': status_counts,
            'broken_links': [r.to_dict() for r in broken],
            'redirected_links': [r.to_dict() for r in redirects],
            'archived_links': [r.to_dict() for r in archived],
            'paywalled_links': [r.to_dict() for r in paywalled],
            'all_results': [r.to_dict() for r in results],
        }


class CitationSuggestor:
    """
    Analyzes document content to suggest where citations might be needed.
    
    Uses pattern matching and optional LLM analysis to identify:
    - Statistics without sources
    - Claims that need evidence
    - Definitions that should be cited
    - Research findings without attribution
    """
    
    # Patterns that indicate citation-worthy content
    STATISTIC_PATTERNS = [
        r'\b(\d+(?:\.\d+)?)\s*%',  # Percentages
        r'\b(\d+(?:,\d{3})*)\s+(?:people|patients|participants|subjects|cases|deaths|studies)',
        r'\b(?:approximately|about|nearly|over|under|more than|less than)\s+(\d+)',
        r'\b(\d+(?:\.\d+)?)\s*(?:fold|times|x)\s+(?:increase|decrease|higher|lower)',
        r'\b(?:odds ratio|OR|hazard ratio|HR|relative risk|RR)\s*(?:of|=|:)?\s*(\d+(?:\.\d+)?)',
        r'\bp\s*[<>=]\s*0?\.\d+',  # P-values
        r'\b95%?\s*CI\b',  # Confidence intervals
    ]
    
    CLAIM_PATTERNS = [
        r'\b(?:studies|research|evidence)\s+(?:show|suggest|indicate|demonstrate|reveal)',
        r'\b(?:has been|have been)\s+(?:shown|demonstrated|proven|established)',
        r'\bit is (?:well )?(?:known|established|recognized|accepted)\s+that',
        r'\baccording to\b(?!\s+\[)',  # Not followed by a citation
        r'\b(?:experts|researchers|scientists)\s+(?:believe|argue|suggest|claim)',
        r'\b(?:recent|new|emerging)\s+(?:research|studies|evidence|data)',
        r'\bthe (?:majority|minority)\s+of\b',
    ]
    
    DEFINITION_PATTERNS = [
        r'\b(?:is defined as|defined as|refers to|is characterized by)\b',
        r'\b(?:the definition of|by definition)\b',
        r'\b(?:known as|termed|called)\b',
    ]
    
    FINDING_PATTERNS = [
        r'\bfound that\b(?!\s*\[)',
        r'\b(?:results|findings|data)\s+(?:show|indicate|suggest|reveal)',
        r'\bwas (?:found|observed|noted|reported)\b',
        r'\b(?:significantly|markedly|substantially)\s+(?:increased|decreased|higher|lower|improved|reduced)',
    ]
    
    def __init__(self, use_llm: bool = False, pubmed_client=None):
        """
        Initialize the citation suggestor.
        
        Args:
            use_llm: Whether to use LLM for advanced analysis
            pubmed_client: PubMed client for searching suggested citations
        """
        self.use_llm = use_llm
        self.pubmed_client = pubmed_client
        if use_llm:
            self.llm_extractor = LLMMetadataExtractor()
    
    def analyze_document(self, content: str, search_suggestions: bool = True) -> List[CitationSuggestion]:
        """
        Analyze a document for passages that need citations.
        
        Args:
            content: Document content
            search_suggestions: Whether to search PubMed for suggested citations
            
        Returns:
            List of CitationSuggestion objects
        """
        suggestions = []
        lines = content.split('\n')
        
        # Track existing citations to avoid flagging cited content
        existing_citations = self._find_existing_citations(content)
        
        for line_num, line in enumerate(lines, 1):
            # Skip lines that already have citations
            if self._line_has_citation(line):
                continue
            
            # Skip headers, code blocks, and metadata
            if line.strip().startswith(('#', '```', '---', 'tags:', 'date:')):
                continue
            
            # Check each pattern category
            suggestions.extend(self._check_statistics(line, line_num))
            suggestions.extend(self._check_claims(line, line_num))
            suggestions.extend(self._check_definitions(line, line_num))
            suggestions.extend(self._check_findings(line, line_num))
        
        # Deduplicate suggestions that overlap
        suggestions = self._deduplicate_suggestions(suggestions)
        
        # Search PubMed for suggested citations
        if search_suggestions and self.pubmed_client:
            for suggestion in suggestions[:10]:  # Limit to first 10
                try:
                    results = self.pubmed_client.search_by_title(
                        ' '.join(suggestion.suggested_search_terms[:3]),
                        max_results=3
                    )
                    suggestion.pubmed_results = [
                        {
                            'pmid': str(r.pmid),
                            'title': r.title,
                            'authors': list(r.authors)[:3] if r.authors else [],
                            'year': r.year,
                        }
                        for r in results
                    ]
                except Exception as e:
                    logger.debug(f"PubMed search failed: {e}")
        
        return suggestions
    
    def _find_existing_citations(self, content: str) -> Set[int]:
        """Find all line numbers that have citations."""
        cited_lines = set()
        lines = content.split('\n')
        
        for i, line in enumerate(lines, 1):
            if self._line_has_citation(line):
                cited_lines.add(i)
        
        return cited_lines
    
    def _line_has_citation(self, line: str) -> bool:
        """Check if a line already has a citation marker."""
        # Footnote style: [^1], [^Author-2020-12345]
        if re.search(r'\[\^[\w-]+\]', line):
            return True
        # Numeric style: [1], [1, 2], [1-3]
        if re.search(r'\[\d+(?:\s*[-,]\s*\d+)*\]', line):
            return True
        # Parenthetical: (Author, 2020)
        if re.search(r'\([A-Z][a-z]+(?:\s+et\s+al\.?)?,?\s*\d{4}\)', line):
            return True
        return False
    
    def _check_statistics(self, line: str, line_num: int) -> List[CitationSuggestion]:
        """Check for uncited statistics."""
        suggestions = []
        
        for pattern in self.STATISTIC_PATTERNS:
            matches = list(re.finditer(pattern, line, re.IGNORECASE))
            for match in matches:
                # Get context around the match
                start = max(0, match.start() - 30)
                end = min(len(line), match.end() + 50)
                excerpt = line[start:end].strip()
                if start > 0:
                    excerpt = '...' + excerpt
                if end < len(line):
                    excerpt = excerpt + '...'
                
                # Generate search terms from context
                search_terms = self._extract_search_terms(line)
                
                suggestions.append(CitationSuggestion(
                    text_excerpt=excerpt,
                    line_number=line_num,
                    reason="Statistical claim without citation",
                    confidence=0.85,
                    suggested_search_terms=search_terms,
                    category="statistic",
                ))
        
        return suggestions
    
    def _check_claims(self, line: str, line_num: int) -> List[CitationSuggestion]:
        """Check for uncited claims."""
        suggestions = []
        
        for pattern in self.CLAIM_PATTERNS:
            if re.search(pattern, line, re.IGNORECASE):
                search_terms = self._extract_search_terms(line)
                
                suggestions.append(CitationSuggestion(
                    text_excerpt=line.strip()[:150],
                    line_number=line_num,
                    reason="Claim referencing external evidence without citation",
                    confidence=0.75,
                    suggested_search_terms=search_terms,
                    category="claim",
                ))
                break  # One suggestion per line for claims
        
        return suggestions
    
    def _check_definitions(self, line: str, line_num: int) -> List[CitationSuggestion]:
        """Check for uncited definitions."""
        suggestions = []
        
        for pattern in self.DEFINITION_PATTERNS:
            if re.search(pattern, line, re.IGNORECASE):
                search_terms = self._extract_search_terms(line)
                
                suggestions.append(CitationSuggestion(
                    text_excerpt=line.strip()[:150],
                    line_number=line_num,
                    reason="Definition or terminology should cite authoritative source",
                    confidence=0.65,
                    suggested_search_terms=search_terms,
                    category="definition",
                ))
                break
        
        return suggestions
    
    def _check_findings(self, line: str, line_num: int) -> List[CitationSuggestion]:
        """Check for uncited research findings."""
        suggestions = []
        
        for pattern in self.FINDING_PATTERNS:
            if re.search(pattern, line, re.IGNORECASE):
                search_terms = self._extract_search_terms(line)
                
                suggestions.append(CitationSuggestion(
                    text_excerpt=line.strip()[:150],
                    line_number=line_num,
                    reason="Research finding or result should cite source",
                    confidence=0.80,
                    suggested_search_terms=search_terms,
                    category="finding",
                ))
                break
        
        return suggestions
    
    def _extract_search_terms(self, text: str) -> List[str]:
        """Extract relevant search terms from text."""
        # Remove common words and punctuation
        stopwords = {
            'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
            'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
            'should', 'may', 'might', 'must', 'shall', 'can', 'need', 'of', 'in',
            'to', 'for', 'with', 'on', 'at', 'by', 'from', 'as', 'into', 'through',
            'that', 'which', 'who', 'whom', 'this', 'these', 'those', 'it', 'its',
            'and', 'or', 'but', 'if', 'then', 'else', 'when', 'where', 'why', 'how',
            'all', 'each', 'every', 'both', 'few', 'more', 'most', 'other', 'some',
            'such', 'no', 'nor', 'not', 'only', 'own', 'same', 'so', 'than', 'too',
            'very', 'just', 'also', 'now', 'here', 'there', 'about', 'after', 'before',
        }
        
        # Clean text
        text = re.sub(r'[^\w\s-]', ' ', text.lower())
        words = text.split()
        
        # Filter and prioritize
        terms = []
        for word in words:
            if len(word) > 3 and word not in stopwords:
                # Prioritize medical/scientific terms
                if any(suffix in word for suffix in ['emia', 'itis', 'osis', 'tion', 'sion', 'ment']):
                    terms.insert(0, word)
                else:
                    terms.append(word)
        
        # Return top 5 unique terms
        seen = set()
        unique_terms = []
        for term in terms:
            if term not in seen:
                seen.add(term)
                unique_terms.append(term)
                if len(unique_terms) >= 5:
                    break
        
        return unique_terms
    
    def _deduplicate_suggestions(self, suggestions: List[CitationSuggestion]) -> List[CitationSuggestion]:
        """Remove duplicate suggestions on the same line."""
        seen_lines = {}
        result = []
        
        for suggestion in suggestions:
            key = suggestion.line_number
            if key not in seen_lines:
                seen_lines[key] = suggestion
                result.append(suggestion)
            else:
                # Keep higher confidence suggestion
                if suggestion.confidence > seen_lines[key].confidence:
                    result.remove(seen_lines[key])
                    seen_lines[key] = suggestion
                    result.append(suggestion)
        
        return sorted(result, key=lambda s: (-s.confidence, s.line_number))


class PlagiarismChecker:
    """
    Checks document for potentially problematic passages:
    - Statistics without sources
    - Direct quotes without attribution
    - Suspicious academic phrasing without citations
    - Claims presented as fact without evidence
    
    This is NOT a plagiarism detector for copied content,
    but rather a citation compliance checker.
    """
    
    # Patterns that suggest content may be directly quoted
    QUOTE_PATTERNS = [
        r'"[^"]{20,}"',  # Long quoted text
        r"'[^']{20,}'",  # Long single-quoted text
    ]
    
    # Academic phrases that typically require citation
    ACADEMIC_PHRASES = [
        r'\bprevious research\b',
        r'\bprior studies\b',
        r'\bliterature suggests\b',
        r'\bevidence indicates\b',
        r'\bwidely accepted\b',
        r'\bgenerally agreed\b',
        r'\bscientific consensus\b',
        r'\bclinical guidelines\b',
        r'\bstandard of care\b',
        r'\bbest practices\b',
        r'\bmeta-analysis\b',
        r'\bsystematic review\b',
        r'\brandomized (?:controlled )?trial\b',
    ]
    
    # High-severity patterns (strong claims without evidence)
    HIGH_SEVERITY_PATTERNS = [
        r'\bcauses\b.*\b(?:cancer|death|disease)\b',
        r'\b(?:proven|proved)\s+to\b',
        r'\bdefinitively\s+(?:shows?|demonstrates?)\b',
        r'\b(?:cures?|treats?|prevents?)\b.*\b(?:cancer|disease|infection)\b',
        r'\b100%\s+(?:effective|safe|accurate)\b',
    ]
    
    def __init__(self):
        pass
    
    def check_document(self, content: str) -> Dict[str, Any]:
        """
        Check a document for citation compliance issues.
        
        Returns:
            Dict with issues, statistics, and recommendations
        """
        issues: List[PotentialPlagiarism] = []
        lines = content.split('\n')
        
        for line_num, line in enumerate(lines, 1):
            # Skip empty lines, headers, code
            if not line.strip() or line.strip().startswith(('#', '```', '---')):
                continue
            
            # Skip lines with existing citations
            has_citation = bool(re.search(r'\[\^?\d+\]|\([A-Z][a-z]+.*\d{4}\)', line))
            
            # Check for quotes without attribution
            issues.extend(self._check_quotes(line, line_num, has_citation))
            
            # Check for academic phrases
            issues.extend(self._check_academic_phrases(line, line_num, has_citation))
            
            # Check for high-severity claims
            issues.extend(self._check_high_severity(line, line_num, has_citation))
        
        # Calculate summary statistics
        high_severity = [i for i in issues if i.severity == 'high']
        medium_severity = [i for i in issues if i.severity == 'medium']
        low_severity = [i for i in issues if i.severity == 'low']
        
        # Generate overall compliance score (0-100)
        total_lines = len([l for l in lines if l.strip() and not l.strip().startswith(('#', '```'))])
        issue_penalty = (len(high_severity) * 10 + len(medium_severity) * 5 + len(low_severity) * 2)
        compliance_score = max(0, min(100, 100 - (issue_penalty / max(1, total_lines)) * 100))
        
        return {
            'compliance_score': round(compliance_score, 1),
            'total_issues': len(issues),
            'high_severity_count': len(high_severity),
            'medium_severity_count': len(medium_severity),
            'low_severity_count': len(low_severity),
            'issues': [i.to_dict() for i in issues],
            'recommendations': self._generate_recommendations(issues),
        }
    
    def _check_quotes(self, line: str, line_num: int, has_citation: bool) -> List[PotentialPlagiarism]:
        """Check for quoted text without attribution."""
        issues = []
        
        for pattern in self.QUOTE_PATTERNS:
            matches = re.findall(pattern, line)
            for match in matches:
                if not has_citation:
                    issues.append(PotentialPlagiarism(
                        text=match,
                        line_number=line_num,
                        issue_type="uncited_quote",
                        severity="high",
                        explanation="Direct quotation without source attribution",
                        existing_citation_nearby=False,
                        suggested_action="Add citation immediately after the quote",
                    ))
        
        return issues
    
    def _check_academic_phrases(self, line: str, line_num: int, has_citation: bool) -> List[PotentialPlagiarism]:
        """Check for academic phrases that need citations."""
        issues = []
        
        for pattern in self.ACADEMIC_PHRASES:
            if re.search(pattern, line, re.IGNORECASE):
                if not has_citation:
                    match = re.search(pattern, line, re.IGNORECASE)
                    issues.append(PotentialPlagiarism(
                        text=line.strip()[:100],
                        line_number=line_num,
                        issue_type="uncited_claim",
                        severity="medium",
                        explanation=f"Academic phrase '{match.group()}' typically requires citation",
                        existing_citation_nearby=False,
                        suggested_action="Add citation to support this claim",
                    ))
                break  # One issue per line
        
        return issues
    
    def _check_high_severity(self, line: str, line_num: int, has_citation: bool) -> List[PotentialPlagiarism]:
        """Check for high-severity uncited claims."""
        issues = []
        
        for pattern in self.HIGH_SEVERITY_PATTERNS:
            if re.search(pattern, line, re.IGNORECASE):
                if not has_citation:
                    issues.append(PotentialPlagiarism(
                        text=line.strip()[:100],
                        line_number=line_num,
                        issue_type="uncited_medical_claim",
                        severity="high",
                        explanation="Strong medical/scientific claim requires authoritative citation",
                        existing_citation_nearby=False,
                        suggested_action="Add primary source citation immediately; verify claim accuracy",
                    ))
                break
        
        return issues
    
    def _generate_recommendations(self, issues: List[PotentialPlagiarism]) -> List[str]:
        """Generate actionable recommendations based on issues found."""
        recommendations = []
        
        high_count = sum(1 for i in issues if i.severity == 'high')
        medium_count = sum(1 for i in issues if i.severity == 'medium')
        
        if high_count > 0:
            recommendations.append(
                f"🔴 {high_count} high-severity issue(s) found. "
                "These include direct quotes without attribution or strong claims without evidence. "
                "Address these first."
            )
        
        if medium_count > 0:
            recommendations.append(
                f"🟡 {medium_count} medium-severity issue(s) found. "
                "These are academic phrases that typically require citations."
            )
        
        uncited_quotes = sum(1 for i in issues if i.issue_type == 'uncited_quote')
        if uncited_quotes > 0:
            recommendations.append(
                "Add source citations immediately after quoted text, or rephrase as paraphrase with citation."
            )
        
        if not issues:
            recommendations.append(
                "✅ No obvious citation compliance issues detected. "
                "Document appears to have appropriate source attribution."
            )
        
        return recommendations


class DocumentIntelligence:
    """
    Main interface for all Document Intelligence features.
    
    Combines:
    - LLM-powered metadata extraction
    - Link verification
    - Citation suggestions
    - Plagiarism checking
    """
    
    def __init__(self, pubmed_client=None, use_llm: bool = False):
        """
        Initialize Document Intelligence.
        
        Args:
            pubmed_client: PubMed client for searching citations
            use_llm: Whether to use LLM for advanced analysis
        """
        self.link_verifier = LinkVerifier()
        self.citation_suggestor = CitationSuggestor(use_llm=use_llm, pubmed_client=pubmed_client)
        self.plagiarism_checker = PlagiarismChecker()
        self.llm_extractor = LLMMetadataExtractor() if use_llm else None
        self.pubmed_client = pubmed_client
    
    def analyze_document(self, content: str, 
                         verify_links: bool = True,
                         suggest_citations: bool = True,
                         check_plagiarism: bool = True,
                         search_suggestions: bool = False) -> Dict[str, Any]:
        """
        Perform comprehensive document analysis.
        
        Args:
            content: Document content (markdown)
            verify_links: Whether to verify all URLs
            suggest_citations: Whether to suggest missing citations
            check_plagiarism: Whether to run citation compliance check
            search_suggestions: Whether to search PubMed for suggestions
            
        Returns:
            Dict with all analysis results
        """
        results = {
            'timestamp': datetime.now().isoformat(),
            'document_length': len(content),
            'line_count': content.count('\n') + 1,
        }
        
        if verify_links:
            logger.info("Verifying document links...")
            results['link_verification'] = self.link_verifier.verify_document(content)
        
        if suggest_citations:
            logger.info("Analyzing for citation suggestions...")
            suggestions = self.citation_suggestor.analyze_document(
                content, 
                search_suggestions=search_suggestions
            )
            results['citation_suggestions'] = {
                'count': len(suggestions),
                'suggestions': [s.to_dict() for s in suggestions],
            }
        
        if check_plagiarism:
            logger.info("Running citation compliance check...")
            results['citation_compliance'] = self.plagiarism_checker.check_document(content)
        
        # Calculate overall document health score
        scores = []
        if 'link_verification' in results:
            total = results['link_verification'].get('total_urls', 0)
            broken = len(results['link_verification'].get('broken_links', []))
            if total > 0:
                scores.append(((total - broken) / total) * 100)
        
        if 'citation_compliance' in results:
            scores.append(results['citation_compliance'].get('compliance_score', 100))
        
        results['overall_health_score'] = round(sum(scores) / len(scores), 1) if scores else 100.0
        
        return results
    
    def extract_metadata_llm(self, url: str, html_content: str) -> Optional[Dict[str, Any]]:
        """
        Extract metadata from a webpage using LLM.
        
        Args:
            url: Webpage URL
            html_content: Raw HTML content
            
        Returns:
            Dict with extracted metadata or None
        """
        if not self.llm_extractor:
            logger.warning("LLM extractor not initialized")
            return None
        
        metadata = self.llm_extractor.extract_metadata(url, html_content)
        if metadata:
            return {
                'title': metadata.title,
                'authors': metadata.authors,
                'date': metadata.date,
                'year': metadata.year,
                'month': metadata.month,
                'organization': metadata.organization,
                'publication_name': metadata.publication_name,
            }
        return None
    
    def verify_single_link(self, url: str) -> Dict[str, Any]:
        """Verify a single URL."""
        result = self.link_verifier.verify_url(url)
        return result.to_dict()
    
    def verify_links_batch(self, urls: List[str]) -> List[Dict[str, Any]]:
        """Verify multiple URLs."""
        url_items = [{'url': url} for url in urls]
        results = self.link_verifier.verify_urls(url_items)
        return [r.to_dict() for r in results]


# Convenience functions
def verify_document_links(content: str) -> Dict[str, Any]:
    """Quick link verification for a document."""
    verifier = LinkVerifier()
    return verifier.verify_document(content)


def suggest_document_citations(content: str, pubmed_client=None) -> List[Dict[str, Any]]:
    """Quick citation suggestion analysis."""
    suggestor = CitationSuggestor(pubmed_client=pubmed_client)
    suggestions = suggestor.analyze_document(content)
    return [s.to_dict() for s in suggestions]


def check_citation_compliance(content: str) -> Dict[str, Any]:
    """Quick citation compliance check."""
    checker = PlagiarismChecker()
    return checker.check_document(content)

