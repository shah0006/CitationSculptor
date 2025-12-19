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
from modules.base_formatter import FormattedCitation
from modules.formatter_factory import get_formatter, get_available_styles, get_style_info, DEFAULT_STYLE

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
        self.cache = CitationCache() if use_cache else None
        self.pubmed_client = PubMedClient()
        self.arxiv_client = ArxivClient()
        self.preprint_client = PreprintClient()
        self.book_client = BookClient()
        self.formatter = get_formatter(style, max_authors=3)
        
        log_level = "DEBUG" if verbose else "WARNING"
        logger.remove()
        logger.add(sys.stderr, level=log_level, format="<level>{level: <8}</level> | <cyan>{message}</cyan>")
    
    def set_style(self, style: str):
        """Change the citation style."""
        self.style = style
        self.formatter = get_formatter(style, max_authors=3)
    
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
        """Auto-detect identifier type and look up accordingly."""
        identifier = identifier.strip()
        
        # ScienceDirect/Elsevier PII URLs (scraping often blocked; DOI may be absent)
        pii_match = re.search(r'/pii/([A-Z]\d{16})', identifier, re.IGNORECASE)
        if pii_match:
            pii = pii_match.group(1).upper()
            try:
                pmid_from_pii = self.pubmed_client.resolve_pii_to_pmid(pii)
                if pmid_from_pii:
                    return self.lookup_pmid(pmid_from_pii)
            except Exception as e:
                logger.debug(f"PII lookup failed for {pii}: {e}")
        
        # PMID (all digits)
        if identifier.isdigit():
            return self.lookup_pmid(identifier)
        
        # PMC ID
        if identifier.upper().startswith('PMC'):
            return self.lookup_pmcid(identifier)
        
        # arXiv ID
        if self.arxiv_client.is_arxiv_id(identifier) or identifier.lower().startswith('arxiv:'):
            return self.lookup_arxiv(identifier)
        
        # ISBN
        if self.book_client.is_isbn(identifier):
            return self.lookup_isbn(identifier)
        
        # DOI (various formats)
        if identifier.startswith('10.') or 'doi.org' in identifier.lower():
            doi = identifier.split('doi.org/')[-1] if 'doi.org/' in identifier else identifier
            # Check if bioRxiv/medRxiv preprint DOI
            if self.preprint_client.is_preprint_doi(doi):
                return self.lookup_preprint(doi)
            return self.lookup_doi(doi)
        
        # Default: title search
        return self.lookup_title(identifier)
    
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
    id_group.add_argument('--title', help='Article title to search')
    id_group.add_argument('--auto', help='Auto-detect identifier type')
    id_group.add_argument('--batch', help='File with identifiers (one per line)')
    id_group.add_argument('--search-multi', dest='search_multi', metavar='QUERY',
                         help='Search PubMed and select from multiple results')
    id_group.add_argument('--interactive', '-i', action='store_true',
                         help='Run in interactive mode (REPL)')
    id_group.add_argument('--list-styles', action='store_true',
                         help='List available citation styles')
    
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
    
    if not any([args.pmid, args.doi, args.pmcid, args.title, args.auto, args.batch, args.search_multi, args.interactive]):
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
