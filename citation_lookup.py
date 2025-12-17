#!/usr/bin/env python3
"""
Citation Lookup Tool - Generate Vancouver-style citations from identifiers.

Usage:
    python citation_lookup.py --pmid 32755608
    python citation_lookup.py --doi "10.1186/s12968-020-00607-1"
    python citation_lookup.py --pmcid PMC7039045
    python citation_lookup.py --title "Standardized cardiovascular magnetic resonance"
    python citation_lookup.py --search-multi "heart failure guidelines"
    python citation_lookup.py --batch citations.txt

Options:
    --copy              Copy result to clipboard (macOS)
    --no-cache          Bypass the cache for this lookup
"""

import sys
import argparse
import json
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
from modules.vancouver_formatter import VancouverFormatter, FormattedCitation

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
    
    def _make_key(self, identifier_type: str, identifier: str) -> str:
        return hashlib.md5(f"{identifier_type}:{identifier.lower().strip()}".encode()).hexdigest()
    
    def get(self, identifier_type: str, identifier: str) -> Optional[Dict[str, Any]]:
        key = self._make_key(identifier_type, identifier)
        entry = self.cache.get(key)
        if entry:
            if time.time() - entry.get('timestamp', 0) < CACHE_EXPIRY_DAYS * 86400:
                return entry.get('data')
            else:
                del self.cache[key]
                self._save_cache()
        return None
    
    def set(self, identifier_type: str, identifier: str, data: Dict[str, Any]):
        key = self._make_key(identifier_type, identifier)
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
    
    def __init__(self, verbose: bool = False, use_cache: bool = True):
        self.verbose = verbose
        self.use_cache = use_cache
        self.cache = CitationCache() if use_cache else None
        self.pubmed_client = PubMedClient()
        self.formatter = VancouverFormatter(max_authors=3)
        
        log_level = "DEBUG" if verbose else "WARNING"
        logger.remove()
        logger.add(sys.stderr, level=log_level, format="<level>{level: <8}</level> | <cyan>{message}</cyan>")
    
    def test_connection(self) -> bool:
        return self.pubmed_client.test_connection()
    
    def _check_cache(self, identifier_type: str, identifier: str) -> Optional[LookupResult]:
        if self.cache:
            cached = self.cache.get(identifier_type, identifier)
            if cached:
                return LookupResult(**cached)
        return None
    
    def _cache_result(self, result: LookupResult):
        if self.cache and result.success:
            self.cache.set(result.identifier_type, result.identifier, asdict(result))
    
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
            return LookupResult(success=False, identifier=doi, identifier_type="doi",
                               error=f"DOI {doi} not found in PubMed or CrossRef")
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
        identifier = identifier.strip()
        if identifier.isdigit():
            return self.lookup_pmid(identifier)
        if identifier.upper().startswith('PMC'):
            return self.lookup_pmcid(identifier)
        if identifier.startswith('10.') or 'doi.org' in identifier.lower():
            doi = identifier.split('doi.org/')[-1] if 'doi.org/' in identifier else identifier
            return self.lookup_doi(doi)
        return self.lookup_title(identifier)
    
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


def main():
    parser = argparse.ArgumentParser(description="Look up citations and generate Vancouver-style references")
    
    id_group = parser.add_mutually_exclusive_group()
    id_group.add_argument('--pmid', help='PubMed ID to look up')
    id_group.add_argument('--doi', help='DOI to look up')
    id_group.add_argument('--pmcid', help='PMC ID to look up')
    id_group.add_argument('--title', help='Article title to search')
    id_group.add_argument('--auto', help='Auto-detect identifier type')
    id_group.add_argument('--batch', help='File with identifiers (one per line)')
    id_group.add_argument('--search-multi', dest='search_multi', metavar='QUERY',
                         help='Search PubMed and select from multiple results')
    
    parser.add_argument('--format', '-f', choices=['inline', 'endnote', 'full', 'json'], default='full')
    parser.add_argument('--output', '-o', help='Output file (default: stdout)')
    parser.add_argument('--copy', '-c', action='store_true', help='Copy result to clipboard (macOS)')
    parser.add_argument('--no-cache', dest='no_cache', action='store_true', help='Bypass cache')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    
    args = parser.parse_args()
    
    if not any([args.pmid, args.doi, args.pmcid, args.title, args.auto, args.batch, args.search_multi]):
        parser.print_help()
        sys.exit(1)
    
    lookup = CitationLookup(verbose=args.verbose, use_cache=not args.no_cache)
    
    if not lookup.test_connection():
        console.print("[red]Error: Cannot connect to PubMed API[/red]")
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
