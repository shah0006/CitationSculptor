#!/usr/bin/env python3
"""
Citation Lookup Tool - Generate citations from identifiers in multiple styles.

Usage:
    python citation_lookup.py --pmid 32755608
    python citation_lookup.py --doi "10.1186/s12968-020-00607-1" --style apa
    python citation_lookup.py --pmcid PMC7039045
    python citation_lookup.py --title "Standardized cardiovascular magnetic resonance"
    python citation_lookup.py --search-multi "heart failure guidelines"
    python citation_lookup.py --batch citations.txt --style mla

Options:
    --style             Citation style: vancouver (default), apa, mla, chicago, harvard, ieee
    --copy              Copy result to clipboard (macOS)
    --no-cache          Bypass the cache for this lookup
"""

import sys
import argparse
import json
import re
import subprocess
import hashlib
import time
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, asdict

from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt
from loguru import logger

from modules.pubmed_client import PubMedClient, ArticleMetadata, CrossRefMetadata
from modules.arxiv_client import ArxivClient, ArxivMetadata
from modules.preprint_client import PreprintClient, PreprintMetadata
from modules.book_client import BookClient, BookMetadata
from modules.openalex_client import OpenAlexClient
from modules.semantic_scholar_client import SemanticScholarClient
from modules.europe_pmc_client import EuropePMCClient
from modules.datacite_client import DataCiteClient
from modules.base_formatter import FormattedCitation
from modules.formatter_factory import get_formatter, get_available_styles, get_style_info, DEFAULT_STYLE
from modules.citation_cache import PersistentCitationCache

console = Console()

CACHE_DIR = Path(__file__).parent / ".cache"
CACHE_FILE = CACHE_DIR / "citation_cache.json"
CACHE_EXPIRY_DAYS = 30


class CitationCache:
    """Persistent cache for citation lookups."""
    
    def __init__(self):
        CACHE_DIR.mkdir(exist_ok=True)
        self.cache = self._load_cache()
    
    def _load_cache(self) -> Dict[str, Any]:
        if CACHE_FILE.exists():
            try:
                return json.loads(CACHE_FILE.read_text())
            except json.JSONDecodeError:
                return {}
        return {}
    
    def _save_cache(self):
        CACHE_FILE.write_text(json.dumps(self.cache, indent=2))
    
    def _make_key(self, identifier_type: str, identifier: str, style: str = "vancouver") -> str:
        return hashlib.md5(f"{style}:{identifier_type}:{identifier.lower().strip()}".encode()).hexdigest()
    
    def get(self, identifier_type: str, identifier: str, style: str = "vancouver") -> Optional[Dict[str, Any]]:
        key = self._make_key(identifier_type, identifier, style)
        entry = self.cache.get(key)
        if entry:
            if time.time() - entry.get('timestamp', 0) < CACHE_EXPIRY_DAYS * 86400:
                return entry.get('data')
            else:
                del self.cache[key]
                self._save_cache()
        return None
    
    def set(self, identifier_type: str, identifier: str, data: Dict[str, Any], style: str = "vancouver"):
        key = self._make_key(identifier_type, identifier, style)
        self.cache[key] = {'timestamp': time.time(), 'data': data}
        self._save_cache()


def copy_to_clipboard(text: str) -> bool:
    """Copy text to clipboard using pbcopy (macOS)."""
    try:
        process = subprocess.Popen(['pbcopy'], stdin=subprocess.PIPE)
        process.communicate(text.encode('utf-8'))
        return process.returncode == 0
    except FileNotFoundError:
        return False


@dataclass
class LookupResult:
    """Result from a citation lookup."""
    success: bool
    identifier: str
    identifier_type: str
    inline_mark: str = ""
    endnote_citation: str = ""
    full_citation: str = ""
    metadata: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class CitationLookup:
    """Look up and format citations from various identifiers."""
    
    def __init__(self, verbose: bool = False, use_cache: bool = True, style: str = DEFAULT_STYLE):
        self.verbose = verbose
        self.use_cache = use_cache
        self.style = style
        self.cache = PersistentCitationCache() if use_cache else None
        self.pubmed_client = PubMedClient()
        self.arxiv_client = ArxivClient()
        self.preprint_client = PreprintClient()
        self.book_client = BookClient()
        self.openalex_client = OpenAlexClient()
        self.semantic_scholar_client = SemanticScholarClient()
        self.europe_pmc_client = EuropePMCClient()
        self.datacite_client = DataCiteClient()
        self.formatter = get_formatter(style, max_authors=3)
        
        log_level = "DEBUG" if verbose else "WARNING"
        logger.remove()
        logger.add(sys.stderr, level=log_level, format="<level>{level: <8}</level> | <cyan>{message}</cyan>")
    
    def set_style(self, style: str):
        """Change the citation style.
        
        Note: This mutates instance state. For thread-safe operations,
        prefer passing style to individual methods or use get_formatter_for_style().
        """
        self.style = style
        self.formatter = get_formatter(style, max_authors=3)
    
    def get_formatter_for_style(self, style: Optional[str] = None):
        """Get a formatter for the specified style, or use instance default.
        
        This method is thread-safe - it returns a new formatter if style differs
        from the instance default, avoiding global state mutation.
        
        Args:
            style: Citation style (vancouver, apa, etc.) or None for instance default
            
        Returns:
            Formatter instance for the requested style
        """
        if style is None or style == self.style:
            return self.formatter
        return get_formatter(style, max_authors=3)
    
    def test_connection(self) -> bool:
        return self.pubmed_client.test_connection()
    
    def _check_cache(self, identifier_type: str, identifier: str) -> Optional[LookupResult]:
        if self.cache:
            cached = self.cache.get(identifier_type, identifier, self.style)
            if cached:
                return LookupResult(**cached)
        return None
    
    def _cache_result(self, result: LookupResult):
        if self.cache and result.success:
            self.cache.set(result.identifier_type, result.identifier, asdict(result), self.style)
    
    def lookup_pmid(self, pmid: str) -> LookupResult:
        cached = self._check_cache("pmid", pmid)
        if cached:
            return cached
        try:
            metadata = self.pubmed_client.fetch_article_by_pmid(pmid)
            if metadata:
                citation = self.formatter.format_journal_article(metadata, original_number=0)
                result = LookupResult(
                    success=True, identifier=pmid, identifier_type="pmid",
                    inline_mark=citation.label, endnote_citation=citation.full_citation,
                    full_citation=citation.full_citation, metadata=self._metadata_to_dict(metadata),
                )
                self._cache_result(result)
                return result
            return LookupResult(success=False, identifier=pmid, identifier_type="pmid",
                               error=f"PMID {pmid} not found in PubMed")
        except Exception as e:
            return LookupResult(success=False, identifier=pmid, identifier_type="pmid", error=str(e))
    
    def lookup_doi(self, doi: str) -> LookupResult:
        cached = self._check_cache("doi", doi)
        if cached:
            return cached
        try:
            metadata = self.pubmed_client.fetch_article_by_doi(doi)
            if metadata:
                citation = self.formatter.format_journal_article(metadata, original_number=0)
                result = LookupResult(
                    success=True, identifier=doi, identifier_type="doi",
                    inline_mark=citation.label, endnote_citation=citation.full_citation,
                    full_citation=citation.full_citation, metadata=self._metadata_to_dict(metadata),
                )
                self._cache_result(result)
                return result
            
            crossref = self.pubmed_client.crossref_lookup_doi(doi)
            if crossref:
                if crossref.work_type == 'book-chapter':
                    citation = self.formatter.format_book_chapter(crossref, original_number=0)
                elif crossref.work_type in ('book', 'monograph'):
                    citation = self.formatter.format_book(crossref, original_number=0)
                else:
                    citation = self.formatter.format_crossref_journal_article(crossref, original_number=0)
                result = LookupResult(
                    success=True, identifier=doi, identifier_type="doi",
                    inline_mark=citation.label, endnote_citation=citation.full_citation,
                    full_citation=citation.full_citation, metadata=self._crossref_to_dict(crossref),
                )
                self._cache_result(result)
                return result
            # Semantic Scholar: may surface a PMID not found by PubMed direct DOI lookup
            s2 = self.semantic_scholar_client.fetch_by_doi(doi)
            if s2:
                if s2.pmid:
                    r = self.lookup_pmid(s2.pmid)
                    if r.success:
                        return r
                elif s2.doi:
                    # S2 returned a canonical DOI -- re-try PubMed with it
                    meta = self.pubmed_client.fetch_article_by_doi(s2.doi)
                    if meta:
                        citation = self.formatter.format_journal_article(meta, original_number=0)
                        result = LookupResult(
                            success=True, identifier=doi, identifier_type="doi",
                            inline_mark=citation.label, endnote_citation=citation.full_citation,
                            full_citation=citation.full_citation, metadata=self._metadata_to_dict(meta),
                        )
                        self._cache_result(result)
                        return result

            # Europe PMC: strong biomedical coverage, often has PMID when PubMed direct lookup fails
            epmc = self.europe_pmc_client.fetch_by_doi(doi)
            if epmc and epmc.pmid:
                r = self.lookup_pmid(epmc.pmid)
                if r.success:
                    return r

            # DataCite: covers datasets, software, preprints with DOIs not in PubMed/CrossRef
            dc = self.datacite_client.fetch_by_doi(doi)
            if dc:
                result = LookupResult(
                    success=True, identifier=doi, identifier_type="doi",
                    inline_mark=f"[^{dc.doi.split('/')[-1][:20]}]",
                    endnote_citation=f"{', '.join(dc.authors[:3])}. {dc.title}. {dc.publisher or ''}. {dc.year or ''}. doi:{dc.doi}",
                    full_citation=f"{', '.join(dc.authors[:3])}. {dc.title}. {dc.publisher or ''}. {dc.year or ''}. doi:{dc.doi}",
                    metadata={"doi": dc.doi, "title": dc.title, "authors": dc.authors, "year": dc.year, "type": dc.resource_type},
                )
                self._cache_result(result)
                return result

            return LookupResult(success=False, identifier=doi, identifier_type="doi",
                               error=f"DOI {doi} not found in PubMed, CrossRef, Semantic Scholar, Europe PMC, or DataCite")
        except Exception as e:
            return LookupResult(success=False, identifier=doi, identifier_type="doi", error=str(e))
    
    def lookup_pmcid(self, pmcid: str) -> LookupResult:
        cached = self._check_cache("pmcid", pmcid)
        if cached:
            return cached
        try:
            metadata = self.pubmed_client.fetch_article_by_pmcid(pmcid)
            if metadata:
                citation = self.formatter.format_journal_article(metadata, original_number=0)
                result = LookupResult(
                    success=True, identifier=pmcid, identifier_type="pmcid",
                    inline_mark=citation.label, endnote_citation=citation.full_citation,
                    full_citation=citation.full_citation, metadata=self._metadata_to_dict(metadata),
                )
                self._cache_result(result)
                return result
            return LookupResult(success=False, identifier=pmcid, identifier_type="pmcid",
                               error=f"PMC ID {pmcid} not found or has no PMID")
        except Exception as e:
            return LookupResult(success=False, identifier=pmcid, identifier_type="pmcid", error=str(e))
    
    def lookup_title(self, title: str) -> LookupResult:
        cached = self._check_cache("title", title)
        if cached:
            return cached
        try:
            metadata = self.pubmed_client.verify_article_exists(title)
            if metadata:
                citation = self.formatter.format_journal_article(metadata, original_number=0)
                result = LookupResult(
                    success=True, identifier=title, identifier_type="title",
                    inline_mark=citation.label, endnote_citation=citation.full_citation,
                    full_citation=citation.full_citation, metadata=self._metadata_to_dict(metadata),
                )
                self._cache_result(result)
                return result
            
            crossref = self.pubmed_client.crossref_search_title(title)
            if crossref:
                if crossref.work_type == 'book-chapter':
                    citation = self.formatter.format_book_chapter(crossref, original_number=0)
                elif crossref.work_type in ('book', 'monograph'):
                    citation = self.formatter.format_book(crossref, original_number=0)
                else:
                    citation = self.formatter.format_crossref_journal_article(crossref, original_number=0)
                result = LookupResult(
                    success=True, identifier=title, identifier_type="title",
                    inline_mark=citation.label, endnote_citation=citation.full_citation,
                    full_citation=citation.full_citation, metadata=self._crossref_to_dict(crossref),
                )
                self._cache_result(result)
                return result
            # Semantic Scholar title search: broad coverage, useful for non-PubMed journals
            s2_results = self.semantic_scholar_client.search(title, max_results=1)
            if s2_results:
                s2 = s2_results[0]
                if s2.pmid:
                    r = self.lookup_pmid(s2.pmid)
                    if r.success:
                        return r
                elif s2.doi:
                    r = self.lookup_doi(s2.doi)
                    if r.success:
                        return r

            # Europe PMC title search: strong biomedical coverage, includes preprints
            epmc_results = self.europe_pmc_client.search(title, max_results=1)
            if epmc_results:
                epmc = epmc_results[0]
                if epmc.pmid:
                    r = self.lookup_pmid(epmc.pmid)
                    if r.success:
                        return r
                elif epmc.doi:
                    r = self.lookup_doi(epmc.doi)
                    if r.success:
                        return r

            return LookupResult(success=False, identifier=title, identifier_type="title",
                               error=f"No article found matching: {title[:50]}...")
        except Exception as e:
            return LookupResult(success=False, identifier=title, identifier_type="title", error=str(e))
    
    def search_multiple(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """Search PubMed and return multiple results for selection."""
        try:
            return self.pubmed_client.search_pubmed(query, max_results=max_results)
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []
    
    def lookup_auto(self, identifier: str) -> LookupResult:
        """Auto-detect identifier type and look up accordingly.

        Detection order (first match wins):
        1. Strip institutional proxy wrapper (EZProxy) -- normalizes all URLs before detection
        2. ScienceDirect/Elsevier PII URL  -> PubMed PMID via resolve_pii_to_pmid()
        3. Plain PMID (all digits)          -> lookup_pmid()
        4. PMC ID (starts with PMC)         -> lookup_pmcid()
        5. arXiv ID                         -> lookup_arxiv()
        6. ISBN                             -> lookup_isbn()
        7. DOI (10.xxx or doi.org/...)      -> lookup_doi()
        8. Scopus EID URL                   -> OpenAlex EID lookup -> lookup_doi()
        9. Google Scholar scholar_lookup URL -> extract title/year -> lookup_title()
        10. Full citation text              -> extract title -> lookup_title()
        11. Default                         -> lookup_title()

        Proxy stripping (step 1) handles institutional EZProxy URLs where
        doi.org becomes doi-org.proxy.lib.INSTITUTION.edu. This runs first
        so all downstream detection logic sees canonical URLs.

        Args:
            identifier: Any string: URL, DOI, PMID, title, full citation text.

        Returns:
            LookupResult with success=True if found, success=False otherwise.
        """
        from modules.type_detector import CitationTypeDetector
        detector = CitationTypeDetector()

        identifier = identifier.strip()

        # Step 1: Strip institutional proxy wrapper (EZProxy normalization)
        identifier = detector.strip_proxy_url(identifier) or identifier

        # Step 2: ScienceDirect/Elsevier PII URL
        pii_match = re.search(r'/pii/([A-Z]\d{16})', identifier, re.IGNORECASE)
        if pii_match:
            pii = pii_match.group(1).upper()
            try:
                pmid_from_pii = self.pubmed_client.resolve_pii_to_pmid(pii)
                if pmid_from_pii:
                    return self.lookup_pmid(pmid_from_pii)
            except Exception as e:
                logger.debug(f"PII lookup failed for {pii}: {e}")

        # Step 3: PMID (all digits)
        if identifier.isdigit():
            return self.lookup_pmid(identifier)

        # Step 4: PMC ID
        if identifier.upper().startswith('PMC'):
            return self.lookup_pmcid(identifier)

        # Step 5: arXiv ID
        if self.arxiv_client.is_arxiv_id(identifier) or identifier.lower().startswith('arxiv:'):
            return self.lookup_arxiv(identifier)

        # Step 6: ISBN
        if self.book_client.is_isbn(identifier):
            return self.lookup_isbn(identifier)

        # Step 7: DOI
        if identifier.startswith('10.') or 'doi.org' in identifier.lower():
            doi = identifier.split('doi.org/')[-1] if 'doi.org/' in identifier else identifier
            if self.preprint_client.is_preprint_doi(doi):
                return self.lookup_preprint(doi)
            return self.lookup_doi(doi)

        # Step 8: Scopus EID URL -> OpenAlex EID lookup
        scopus_eid = detector.extract_scopus_eid(identifier)
        if scopus_eid:
            oa_work = self.openalex_client.fetch_by_scopus_eid(scopus_eid)
            if oa_work:
                if oa_work.doi:
                    result = self.lookup_doi(oa_work.doi)
                    if result.success:
                        return result
                if oa_work.pmid:
                    result = self.lookup_pmid(oa_work.pmid)
                    if result.success:
                        return result
            # EID found but OpenAlex had no match -- fall through to Scholar/title paths

        # Step 9: Google Scholar scholar_lookup URL
        scholar_data = detector.parse_scholar_lookup_url(identifier)
        if scholar_data:
            title = scholar_data["title"]
            # If year is available, PubMed title+year search is more precise
            # Pass year as part of title for now; PubMed client already does fuzzy matching
            result = self.lookup_title(title)
            if result.success:
                return result
            # Scholar URL found but title lookup failed -- fall through to default

        # Step 10: Full citation text -- extract title and try lookup
        if not identifier.startswith('10.') and '. ' in identifier and re.search(r'\b(19|20)\d{2}\b', identifier):
            extracted_title = self._extract_title_from_citation_text(identifier)
            if extracted_title and len(extracted_title.split()) >= 4:
                logger.info(f"Citation text detected, extracted title: {extracted_title[:60]}...")
                result = self.lookup_title(extracted_title)
                if result.success:
                    return result

        # Step 11: Default title search
        return self.lookup_title(identifier)
    
    def _extract_title_from_citation_text(self, citation_text: str) -> Optional[str]:
        """
        Extract probable article title from a full citation string.
        
        Uses two-format detection: period-delimited (Vancouver) and dash-delimited.
        """
        text = citation_text.strip()

        # Dash-delimited format: "Author Year - Title - Journal"
        if text.count(' - ') >= 2:
            parts = text.split(' - ')
            if len(parts) >= 3:
                return parts[1].strip().strip('*')

        # Period-delimited Vancouver format: "Authors. Title. Journal. Year;..."
        parts = text.split('. ')
        if len(parts) >= 3:
            candidate = parts[1].strip()
            if (len(candidate.split()) >= 4 and
                    not re.match(r'^(19|20)\d{2}', candidate) and
                    not re.match(r'^\d', candidate) and
                    len(candidate) > 20):
                return candidate

        return None

    def lookup_arxiv(self, arxiv_id: str) -> LookupResult:
        """Look up an arXiv preprint by ID."""
        cached = self._check_cache("arxiv", arxiv_id)
        if cached:
            return cached
        try:
            metadata = self.arxiv_client.fetch_by_id(arxiv_id)
            if metadata:
                citation = self.formatter.format_preprint(metadata, original_number=0)
                result = LookupResult(
                    success=True, identifier=arxiv_id, identifier_type="arxiv",
                    inline_mark=citation.label, endnote_citation=citation.full_citation,
                    full_citation=citation.full_citation, metadata=self._arxiv_to_dict(metadata),
                )
                self._cache_result(result)
                return result
            return LookupResult(success=False, identifier=arxiv_id, identifier_type="arxiv",
                               error=f"arXiv ID {arxiv_id} not found")
        except Exception as e:
            return LookupResult(success=False, identifier=arxiv_id, identifier_type="arxiv", error=str(e))
    
    def lookup_preprint(self, doi: str) -> LookupResult:
        """Look up a bioRxiv/medRxiv preprint by DOI."""
        cached = self._check_cache("preprint", doi)
        if cached:
            return cached
        try:
            metadata = self.preprint_client.fetch_by_doi(doi)
            if metadata:
                citation = self.formatter.format_biorxiv_preprint(metadata, original_number=0)
                result = LookupResult(
                    success=True, identifier=doi, identifier_type="preprint",
                    inline_mark=citation.label, endnote_citation=citation.full_citation,
                    full_citation=citation.full_citation, metadata=self._preprint_to_dict(metadata),
                )
                self._cache_result(result)
                return result
            return LookupResult(success=False, identifier=doi, identifier_type="preprint",
                               error=f"Preprint DOI {doi} not found in bioRxiv/medRxiv")
        except Exception as e:
            return LookupResult(success=False, identifier=doi, identifier_type="preprint", error=str(e))
    
    def lookup_isbn(self, isbn: str) -> LookupResult:
        """Look up a book by ISBN."""
        cached = self._check_cache("isbn", isbn)
        if cached:
            return cached
        try:
            metadata = self.book_client.fetch_by_isbn(isbn)
            if metadata:
                citation = self.formatter.format_book_from_isbn(metadata, original_number=0)
                result = LookupResult(
                    success=True, identifier=isbn, identifier_type="isbn",
                    inline_mark=citation.label, endnote_citation=citation.full_citation,
                    full_citation=citation.full_citation, metadata=self._book_to_dict(metadata),
                )
                self._cache_result(result)
                return result
            return LookupResult(success=False, identifier=isbn, identifier_type="isbn",
                               error=f"ISBN {isbn} not found")
        except Exception as e:
            return LookupResult(success=False, identifier=isbn, identifier_type="isbn", error=str(e))
    
    def batch_lookup_pmids(self, pmids: List[str]) -> List[LookupResult]:
        """Look up multiple PMIDs in optimized batched API calls.

        Uses PubMedClient.batch_fetch_by_pmids() for efficient bulk fetching,
        then formats each result. Cache-aware: checks cache before fetching,
        stores results after fetching.

        Args:
            pmids: List of PMID strings

        Returns:
            List of LookupResult, one per input PMID, in same order.
            Failed lookups have success=False.
        """
        if not pmids:
            return []

        # Split into cached vs uncached
        cached_results: Dict[str, LookupResult] = {}
        uncached_pmids: List[str] = []

        for pmid in pmids:
            cached = self._check_cache("pmid", pmid)
            if cached:
                cached_results[pmid] = cached
            else:
                uncached_pmids.append(pmid)

        # Batch fetch uncached PMIDs
        fetched: Dict[str, Any] = {}
        if uncached_pmids:
            fetched = self.pubmed_client.batch_fetch_by_pmids(uncached_pmids)

        # Build results in original order
        results: List[LookupResult] = []
        for pmid in pmids:
            if pmid in cached_results:
                results.append(cached_results[pmid])
                continue

            meta = fetched.get(pmid)
            if meta:
                try:
                    citation = self.formatter.format_journal_article(meta, original_number=0)
                    result = LookupResult(
                        success=True, identifier=pmid, identifier_type="pmid",
                        inline_mark=citation.label, endnote_citation=citation.full_citation,
                        full_citation=citation.full_citation, metadata=self._metadata_to_dict(meta),
                    )
                    self._cache_result(result)
                    results.append(result)
                except Exception as e:
                    results.append(LookupResult(
                        success=False, identifier=pmid, identifier_type="pmid", error=str(e),
                    ))
            else:
                results.append(LookupResult(
                    success=False, identifier=pmid, identifier_type="pmid",
                    error=f"PMID {pmid} not found in batch fetch",
                ))

        return results

    def batch_lookup(self, identifiers: List[str]) -> List[LookupResult]:
        results = []
        for identifier in identifiers:
            identifier = identifier.strip()
            if identifier and not identifier.startswith('#'):
                results.append(self.lookup_auto(identifier))
        return results
    
    def _metadata_to_dict(self, metadata: ArticleMetadata) -> Dict[str, Any]:
        return {
            'pmid': metadata.pmid, 'title': metadata.title, 'authors': metadata.authors,
            'journal': metadata.journal, 'journal_abbreviation': metadata.journal_abbreviation,
            'year': metadata.year, 'month': metadata.month, 'volume': metadata.volume,
            'issue': metadata.issue, 'pages': metadata.pages, 'doi': metadata.doi,
            'abstract': metadata.abstract[:200] + '...' if metadata.abstract and len(metadata.abstract) > 200 else metadata.abstract,
        }
    
    def _arxiv_to_dict(self, metadata: ArxivMetadata) -> Dict[str, Any]:
        return {
            'arxiv_id': metadata.arxiv_id, 'title': metadata.title, 
            'authors': metadata.authors, 'abstract': metadata.abstract[:200] + '...' if len(metadata.abstract) > 200 else metadata.abstract,
            'primary_category': metadata.primary_category, 'published': metadata.published,
            'doi': metadata.doi, 'journal_ref': metadata.journal_ref,
            'pdf_url': metadata.pdf_url, 'abs_url': metadata.abs_url,
        }
    
    def _preprint_to_dict(self, metadata: PreprintMetadata) -> Dict[str, Any]:
        return {
            'doi': metadata.doi, 'title': metadata.title, 
            'authors': metadata.authors_list, 'abstract': metadata.abstract[:200] + '...' if len(metadata.abstract) > 200 else metadata.abstract,
            'server': metadata.server, 'category': metadata.category, 'date': metadata.date,
            'published_doi': metadata.published_doi, 'published_journal': metadata.published_journal,
            'url': metadata.url,
        }
    
    def _book_to_dict(self, metadata: BookMetadata) -> Dict[str, Any]:
        return {
            'isbn': metadata.display_isbn, 'title': metadata.title, 'authors': metadata.authors,
            'publisher': metadata.publisher, 'published_date': metadata.published_date,
            'page_count': metadata.page_count, 'categories': metadata.categories,
            'info_link': metadata.info_link, 'source': metadata.source,
        }
    
    def _crossref_to_dict(self, metadata: CrossRefMetadata) -> Dict[str, Any]:
        return {
            'doi': metadata.doi, 'title': metadata.title, 'work_type': metadata.work_type,
            'authors': metadata.authors, 'editors': metadata.editors, 'book_title': metadata.book_title,
            'container_title': metadata.container_title, 'publisher': metadata.publisher,
            'year': metadata.year, 'volume': metadata.volume, 'pages': metadata.pages,
        }


def format_output(result: LookupResult, output_format: str) -> str:
    if output_format == 'inline':
        return result.inline_mark if result.success else f"# Error: {result.error}"
    elif output_format == 'endnote':
        return result.endnote_citation if result.success else f"# Error: {result.error}"
    elif output_format == 'json':
        return json.dumps(asdict(result), indent=2)
    else:
        if result.success:
            return f"Inline: {result.inline_mark}\n\n{result.full_citation}"
        return f"# Error looking up '{result.identifier}': {result.error}"


def display_search_results(results: List[Dict[str, Any]]) -> Optional[int]:
    if not results:
        console.print("[yellow]No results found.[/yellow]")
        return None
    
    table = Table(title="Search Results", show_lines=True)
    table.add_column("#", style="cyan", width=3)
    table.add_column("Title", style="white", max_width=60)
    table.add_column("Authors", style="dim", max_width=25)
    table.add_column("Year", style="green", width=6)
    table.add_column("PMID", style="magenta", width=10)
    
    for i, r in enumerate(results, 1):
        authors = r.get('authors', ['Unknown'])
        author_str = authors[0] if authors else 'Unknown'
        if len(authors) > 1:
            author_str += " et al."
        table.add_row(str(i), r.get('title', 'Unknown')[:60], author_str,
                      str(r.get('year', '')), str(r.get('pmid', '')))
    
    console.print(table)
    choice = Prompt.ask("Select article number (or 'q' to quit)", default="1")
    if choice.lower() == 'q':
        return None
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(results):
            return idx
    except ValueError:
        pass
    console.print("[red]Invalid selection[/red]")
    return None


def run_interactive_mode(lookup: CitationLookup, output_format: str, auto_copy: bool):
    """Run in interactive REPL mode."""
    console.print("\n[bold cyan]CitationSculptor Interactive Mode[/bold cyan]")
    console.print(f"[dim]Style: {lookup.style} | Enter identifiers (PMID, DOI, PMC ID, or title)[/dim]")
    console.print("[dim]Commands: /search, /style, /format, /help, /quit[/dim]\n")
    
    current_format = output_format
    
    while True:
        try:
            user_input = Prompt.ask("[bold green]>[/bold green]").strip()
            
            if not user_input:
                continue
            
            # Handle commands
            if user_input.startswith('/'):
                cmd_parts = user_input[1:].split(maxsplit=1)
                cmd = cmd_parts[0].lower()
                cmd_arg = cmd_parts[1] if len(cmd_parts) > 1 else ""
                
                if cmd in ('quit', 'q', 'exit'):
                    console.print("[yellow]Goodbye![/yellow]")
                    break
                
                elif cmd == 'help':
                    console.print("""
[bold]Commands:[/bold]
  /search <query>  - Search PubMed and select from results
  /style <name>    - Set citation style (vancouver, apa, mla, chicago, harvard, ieee)
  /style           - Show current style and list available styles
  /format <type>   - Set output format (inline, endnote, full, json)
  /cache clear     - Clear the citation cache
  /cache stats     - Show cache statistics
  /help            - Show this help
  /quit            - Exit interactive mode

[bold]Direct Input:[/bold]
  Just type a PMID, DOI, PMC ID, or article title to look it up.
  Examples:
    37622666
    10.1093/eurheartj/ehad195
    PMC7039045
    ESC Guidelines heart failure
""")
                    continue
                
                elif cmd == 'search' and cmd_arg:
                    search_results = lookup.search_multiple(cmd_arg)
                    idx = display_search_results(search_results)
                    if idx is not None:
                        pmid = search_results[idx].get('pmid')
                        if pmid:
                            result = lookup.lookup_pmid(str(pmid))
                            output = format_output(result, current_format)
                            console.print(f"\n{output}\n")
                            if auto_copy and result.success:
                                if copy_to_clipboard(output.strip()):
                                    console.print("[dim green]✓ Copied to clipboard[/dim green]\n")
                    continue
                
                elif cmd == 'style':
                    if cmd_arg:
                        available = get_available_styles()
                        if cmd_arg.lower() in available:
                            lookup.set_style(cmd_arg.lower())
                            console.print(f"[green]Citation style set to: {lookup.style}[/green]")
                        else:
                            console.print(f"[red]Unknown style. Available: {', '.join(available)}[/red]")
                    else:
                        console.print(f"[cyan]Current style: {lookup.style}[/cyan]")
                        console.print("[dim]Available styles:[/dim]")
                        for style, desc in get_style_info().items():
                            marker = "[green]→[/green]" if style == lookup.style else " "
                            console.print(f"  {marker} {style}: {desc}")
                    continue
                
                elif cmd == 'format' and cmd_arg:
                    if cmd_arg in ('inline', 'endnote', 'full', 'json'):
                        current_format = cmd_arg
                        console.print(f"[green]Output format set to: {current_format}[/green]")
                    else:
                        console.print("[red]Invalid format. Use: inline, endnote, full, json[/red]")
                    continue
                
                elif cmd == 'cache':
                    if cmd_arg == 'clear':
                        if lookup.cache:
                            lookup.cache.cache = {}
                            lookup.cache._save_cache()
                            console.print("[green]Cache cleared[/green]")
                    elif cmd_arg == 'stats':
                        if lookup.cache:
                            count = len(lookup.cache.cache)
                            console.print(f"[cyan]Cache entries: {count}[/cyan]")
                        else:
                            console.print("[yellow]Cache is disabled[/yellow]")
                    continue
                
                else:
                    console.print(f"[red]Unknown command: /{cmd}[/red]")
                    continue
            
            # Regular lookup
            result = lookup.lookup_auto(user_input)
            output = format_output(result, current_format)
            
            if result.success:
                console.print(f"\n{output}\n")
                if auto_copy:
                    if copy_to_clipboard(output.strip()):
                        console.print("[dim green]✓ Copied to clipboard[/dim green]\n")
            else:
                console.print(f"[red]{output}[/red]\n")
        
        except KeyboardInterrupt:
            console.print("\n[yellow]Use /quit to exit[/yellow]")
        except EOFError:
            break


def main():
    parser = argparse.ArgumentParser(
        description="Look up citations and generate references in multiple styles",
        epilog="Available styles: " + ", ".join(get_available_styles())
    )
    
    id_group = parser.add_mutually_exclusive_group()
    id_group.add_argument('--pmid', help='PubMed ID to look up')
    id_group.add_argument('--doi', help='DOI to look up')
    id_group.add_argument('--pmcid', help='PMC ID to look up')
    id_group.add_argument('--arxiv', help='arXiv ID to look up (e.g., 2301.07041)')
    id_group.add_argument('--isbn', help='ISBN to look up (e.g., 978-0-13-468599-1)')
    id_group.add_argument('--title', help='Article title to search')
    id_group.add_argument('--auto', help='Auto-detect identifier type')
    id_group.add_argument('--batch', help='File with identifiers (one per line)')
    id_group.add_argument('--search-multi', dest='search_multi', metavar='QUERY',
                         help='Search PubMed and select from multiple results')
    id_group.add_argument('--interactive', '-i', action='store_true',
                         help='Run in interactive mode (REPL)')
    id_group.add_argument('--list-styles', action='store_true',
                         help='List available citation styles')
    id_group.add_argument('--export-bibtex', dest='export_bibtex', metavar='FILE',
                         help='Export citations from file to BibTeX format')
    id_group.add_argument('--export-ris', dest='export_ris', metavar='FILE',
                         help='Export citations from file to RIS format')
    id_group.add_argument('--import-bibtex', dest='import_bibtex', metavar='FILE',
                         help='Import BibTeX file and show entries')
    id_group.add_argument('--import-ris', dest='import_ris', metavar='FILE',
                         help='Import RIS file and show entries')
    id_group.add_argument('--extract-pdf', dest='extract_pdf', metavar='FILE',
                         help='Extract citation metadata from PDF file')
    
    parser.add_argument('--style', '-s', choices=get_available_styles(), default=DEFAULT_STYLE,
                       help=f'Citation style (default: {DEFAULT_STYLE})')
    parser.add_argument('--format', '-f', choices=['inline', 'endnote', 'full', 'json'], default='full')
    parser.add_argument('--output', '-o', help='Output file (default: stdout)')
    parser.add_argument('--copy', '-c', action='store_true', help='Copy result to clipboard (macOS)')
    parser.add_argument('--no-cache', dest='no_cache', action='store_true', help='Bypass cache')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    
    args = parser.parse_args()
    
    # Handle --list-styles
    if args.list_styles:
        console.print("\n[bold cyan]Available Citation Styles:[/bold cyan]\n")
        for style, description in get_style_info().items():
            console.print(f"  [green]{style:12}[/green] {description}")
        console.print()
        sys.exit(0)
    
    if not any([args.pmid, args.doi, args.pmcid, args.arxiv, args.isbn, args.title, args.auto, 
                args.batch, args.search_multi, args.interactive, args.export_bibtex, args.export_ris,
                args.import_bibtex, args.import_ris, args.extract_pdf]):
        parser.print_help()
        sys.exit(1)
    
    lookup = CitationLookup(verbose=args.verbose, use_cache=not args.no_cache, style=args.style)
    
    if not lookup.test_connection():
        console.print("[red]Error: Cannot connect to PubMed API[/red]")
        sys.exit(1)
    
    # Interactive mode
    if args.interactive:
        run_interactive_mode(lookup, args.format, args.copy)
        sys.exit(0)
    
    # Handle import/export modes (don't need PubMed connection test)
    if args.import_bibtex:
        from modules.bibtex_handler import BibTeXParser
        parser_bib = BibTeXParser()
        entries = parser_bib.parse_file(args.import_bibtex)
        if not entries:
            console.print("[red]No BibTeX entries found.[/red]")
            sys.exit(1)
        console.print(f"\n[bold cyan]BibTeX Import: {len(entries)} entries[/bold cyan]\n")
        for i, entry in enumerate(entries, 1):
            console.print(f"[green]{i}. {entry.cite_key}[/green] ({entry.entry_type})")
            console.print(f"   Title: {entry.title[:60]}...")
            if entry.authors:
                console.print(f"   Authors: {', '.join(entry.authors[:3])}")
            if entry.year:
                console.print(f"   Year: {entry.year}")
            console.print()
        sys.exit(0)
    
    if args.import_ris:
        from modules.ris_handler import RISParser
        parser_ris = RISParser()
        entries = parser_ris.parse_file(args.import_ris)
        if not entries:
            console.print("[red]No RIS entries found.[/red]")
            sys.exit(1)
        console.print(f"\n[bold cyan]RIS Import: {len(entries)} entries[/bold cyan]\n")
        for i, entry in enumerate(entries, 1):
            console.print(f"[green]{i}.[/green] ({entry.entry_type})")
            console.print(f"   Title: {entry.title[:60]}...")
            if entry.authors:
                console.print(f"   Authors: {', '.join(entry.authors[:3])}")
            if entry.year:
                console.print(f"   Year: {entry.year}")
            console.print()
        sys.exit(0)
    
    if args.extract_pdf:
        try:
            from modules.pdf_extractor import PDFExtractor, PYMUPDF_AVAILABLE
            if not PYMUPDF_AVAILABLE:
                console.print("[red]Error: PyMuPDF not installed. Run: pip install PyMuPDF[/red]")
                sys.exit(1)
            extractor = PDFExtractor()
            metadata = extractor.extract(args.extract_pdf)
            if not metadata:
                console.print("[red]Could not extract metadata from PDF.[/red]")
                sys.exit(1)
            console.print(f"\n[bold cyan]PDF Metadata Extraction[/bold cyan]\n")
            console.print(f"[dim]File: {args.extract_pdf}[/dim]")
            if metadata.title:
                console.print(f"[green]Title:[/green] {metadata.title}")
            if metadata.authors:
                console.print(f"[green]Authors:[/green] {', '.join(metadata.authors)}")
            if metadata.doi:
                console.print(f"[green]DOI:[/green] {metadata.doi}")
            if metadata.pmid:
                console.print(f"[green]PMID:[/green] {metadata.pmid}")
            if metadata.arxiv_id:
                console.print(f"[green]arXiv:[/green] {metadata.arxiv_id}")
            console.print(f"[dim]Pages: {metadata.page_count}, Size: {metadata.file_size:,} bytes[/dim]")
            if metadata.has_identifier:
                id_type, id_value = metadata.best_identifier
                console.print(f"\n[cyan]Best identifier: {id_type.upper()} = {id_value}[/cyan]")
            sys.exit(0)
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            sys.exit(1)
    
    results = []
    
    if args.search_multi:
        search_results = lookup.search_multiple(args.search_multi)
        idx = display_search_results(search_results)
        if idx is not None:
            pmid = search_results[idx].get('pmid')
            if pmid:
                results.append(lookup.lookup_pmid(str(pmid)))
    elif args.pmid:
        results.append(lookup.lookup_pmid(args.pmid))
    elif args.doi:
        results.append(lookup.lookup_doi(args.doi))
    elif args.pmcid:
        results.append(lookup.lookup_pmcid(args.pmcid))
    elif args.arxiv:
        results.append(lookup.lookup_arxiv(args.arxiv))
    elif args.isbn:
        results.append(lookup.lookup_isbn(args.isbn))
    elif args.title:
        results.append(lookup.lookup_title(args.title))
    elif args.auto:
        results.append(lookup.lookup_auto(args.auto))
    elif args.batch:
        batch_file = Path(args.batch)
        if not batch_file.exists():
            console.print(f"[red]Error: File not found: {args.batch}[/red]")
            sys.exit(1)
        identifiers = batch_file.read_text().strip().split('\n')
        results = lookup.batch_lookup(identifiers)
    elif args.export_bibtex:
        # Export to BibTeX from file with identifiers
        batch_file = Path(args.export_bibtex)
        if not batch_file.exists():
            console.print(f"[red]Error: File not found: {args.export_bibtex}[/red]")
            sys.exit(1)
        identifiers = batch_file.read_text().strip().split('\n')
        results = lookup.batch_lookup(identifiers)
        
        from modules.bibtex_handler import BibTeXExporter
        exporter = BibTeXExporter()
        bibtex_entries = []
        for r in results:
            if r.success and r.metadata:
                entry = exporter.metadata_to_bibtex(r.metadata)
                bibtex_entries.append(entry)
        
        output_text = "\n\n".join(bibtex_entries)
        if args.output:
            Path(args.output).write_text(output_text)
            console.print(f"[green]BibTeX exported to: {args.output}[/green]")
        else:
            print(output_text)
        sys.exit(0)
    elif args.export_ris:
        # Export to RIS from file with identifiers
        batch_file = Path(args.export_ris)
        if not batch_file.exists():
            console.print(f"[red]Error: File not found: {args.export_ris}[/red]")
            sys.exit(1)
        identifiers = batch_file.read_text().strip().split('\n')
        results = lookup.batch_lookup(identifiers)
        
        from modules.ris_handler import RISExporter
        exporter = RISExporter()
        ris_entries = []
        for r in results:
            if r.success and r.metadata:
                entry = exporter.metadata_to_ris(r.metadata)
                ris_entries.append(entry)
        
        output_text = "\n".join(ris_entries)
        if args.output:
            Path(args.output).write_text(output_text)
            console.print(f"[green]RIS exported to: {args.output}[/green]")
        else:
            print(output_text)
        sys.exit(0)
    
    output_lines = []
    for result in results:
        output_lines.append(format_output(result, args.format))
        if args.format == 'full':
            output_lines.append('')
    
    output_text = '\n'.join(output_lines)
    
    if args.output:
        Path(args.output).write_text(output_text)
        console.print(f"[green]Output written to: {args.output}[/green]")
    else:
        print(output_text)
    
    if args.copy and output_text.strip():
        if copy_to_clipboard(output_text.strip()):
            console.print("[green]Copied to clipboard[/green]")
        else:
            console.print("[yellow]Clipboard copy failed (pbcopy not available)[/yellow]")
    
    if args.batch and len(results) > 1:
        success_count = sum(1 for r in results if r.success)
        console.print(f"\n[cyan]Processed {len(results)} identifiers: {success_count} successful, {len(results) - success_count} failed[/cyan]")


if __name__ == "__main__":
    main()
