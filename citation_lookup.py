#!/usr/bin/env python3
"""
Citation Lookup Tool - Generate Vancouver-style citations from identifiers.

This tool is designed for creating citations when building atomic notes.
It takes a PMID, DOI, PMC ID, or article title and returns a properly
formatted Vancouver citation with mnemonic label.

Usage:
    python citation_lookup.py --pmid 32755608
    python citation_lookup.py --doi "10.1186/s12968-020-00607-1"
    python citation_lookup.py --pmcid PMC7039045
    python citation_lookup.py --title "Standardized cardiovascular magnetic resonance"
    python citation_lookup.py --batch citations.txt  # One identifier per line

Output formats:
    --format inline     Just the inline reference mark: [^KramerCM-2020-32755608]
    --format endnote    Just the endnote citation
    --format full       Both inline mark and endnote (default)
    --format json       JSON with all metadata

Examples:
    # Get citation for SCMR 2020 protocols paper
    python citation_lookup.py --pmid 32755608
    
    # Search by title
    python citation_lookup.py --title "Lake Louise Criteria myocarditis"
    
    # Batch process from file
    python citation_lookup.py --batch my_references.txt --output citations_output.md
"""

import sys
import argparse
import json
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, asdict

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from loguru import logger

# Import from existing modules
from modules.pubmed_client import PubMedClient, ArticleMetadata, CrossRefMetadata
from modules.vancouver_formatter import VancouverFormatter, FormattedCitation

console = Console()


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
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.pubmed_client = PubMedClient()
        self.formatter = VancouverFormatter(max_authors=3)
        
        log_level = "DEBUG" if verbose else "WARNING"
        logger.remove()
        logger.add(sys.stderr, level=log_level, format="<level>{level: <8}</level> | <cyan>{message}</cyan>")
    
    def test_connection(self) -> bool:
        """Test connection to PubMed MCP server."""
        return self.pubmed_client.test_connection()
    
    def lookup_pmid(self, pmid: str) -> LookupResult:
        """Look up article by PMID."""
        try:
            metadata = self.pubmed_client.fetch_article_by_pmid(pmid)
            if metadata:
                citation = self.formatter.format_journal_article(metadata, original_number=0)
                return LookupResult(
                    success=True,
                    identifier=pmid,
                    identifier_type="pmid",
                    inline_mark=citation.label,
                    endnote_citation=citation.full_citation,
                    full_citation=citation.full_citation,
                    metadata=self._metadata_to_dict(metadata),
                )
            return LookupResult(
                success=False,
                identifier=pmid,
                identifier_type="pmid",
                error=f"PMID {pmid} not found in PubMed",
            )
        except Exception as e:
            return LookupResult(
                success=False,
                identifier=pmid,
                identifier_type="pmid",
                error=str(e),
            )
    
    def lookup_doi(self, doi: str) -> LookupResult:
        """Look up article by DOI (tries PubMed first, then CrossRef)."""
        try:
            # Try PubMed first
            metadata = self.pubmed_client.fetch_article_by_doi(doi)
            if metadata:
                citation = self.formatter.format_journal_article(metadata, original_number=0)
                return LookupResult(
                    success=True,
                    identifier=doi,
                    identifier_type="doi",
                    inline_mark=citation.label,
                    endnote_citation=citation.full_citation,
                    full_citation=citation.full_citation,
                    metadata=self._metadata_to_dict(metadata),
                )
            
            # Try CrossRef
            crossref = self.pubmed_client.crossref_lookup_doi(doi)
            if crossref:
                if crossref.work_type == 'book-chapter':
                    citation = self.formatter.format_book_chapter(crossref, original_number=0)
                elif crossref.work_type in ('book', 'monograph'):
                    citation = self.formatter.format_book(crossref, original_number=0)
                else:
                    citation = self.formatter.format_crossref_journal_article(crossref, original_number=0)
                
                return LookupResult(
                    success=True,
                    identifier=doi,
                    identifier_type="doi",
                    inline_mark=citation.label,
                    endnote_citation=citation.full_citation,
                    full_citation=citation.full_citation,
                    metadata=self._crossref_to_dict(crossref),
                )
            
            return LookupResult(
                success=False,
                identifier=doi,
                identifier_type="doi",
                error=f"DOI {doi} not found in PubMed or CrossRef",
            )
        except Exception as e:
            return LookupResult(
                success=False,
                identifier=doi,
                identifier_type="doi",
                error=str(e),
            )
    
    def lookup_pmcid(self, pmcid: str) -> LookupResult:
        """Look up article by PMC ID."""
        try:
            metadata = self.pubmed_client.fetch_article_by_pmcid(pmcid)
            if metadata:
                citation = self.formatter.format_journal_article(metadata, original_number=0)
                return LookupResult(
                    success=True,
                    identifier=pmcid,
                    identifier_type="pmcid",
                    inline_mark=citation.label,
                    endnote_citation=citation.full_citation,
                    full_citation=citation.full_citation,
                    metadata=self._metadata_to_dict(metadata),
                )
            return LookupResult(
                success=False,
                identifier=pmcid,
                identifier_type="pmcid",
                error=f"PMC ID {pmcid} not found or has no PMID",
            )
        except Exception as e:
            return LookupResult(
                success=False,
                identifier=pmcid,
                identifier_type="pmcid",
                error=str(e),
            )
    
    def lookup_title(self, title: str) -> LookupResult:
        """Search for article by title."""
        try:
            metadata = self.pubmed_client.verify_article_exists(title)
            if metadata:
                citation = self.formatter.format_journal_article(metadata, original_number=0)
                return LookupResult(
                    success=True,
                    identifier=title,
                    identifier_type="title",
                    inline_mark=citation.label,
                    endnote_citation=citation.full_citation,
                    full_citation=citation.full_citation,
                    metadata=self._metadata_to_dict(metadata),
                )
            
            # Try CrossRef title search
            crossref = self.pubmed_client.crossref_search_title(title)
            if crossref:
                if crossref.work_type == 'book-chapter':
                    citation = self.formatter.format_book_chapter(crossref, original_number=0)
                elif crossref.work_type in ('book', 'monograph'):
                    citation = self.formatter.format_book(crossref, original_number=0)
                else:
                    citation = self.formatter.format_crossref_journal_article(crossref, original_number=0)
                
                return LookupResult(
                    success=True,
                    identifier=title,
                    identifier_type="title",
                    inline_mark=citation.label,
                    endnote_citation=citation.full_citation,
                    full_citation=citation.full_citation,
                    metadata=self._crossref_to_dict(crossref),
                )
            
            return LookupResult(
                success=False,
                identifier=title,
                identifier_type="title",
                error=f"No article found matching: {title[:50]}...",
            )
        except Exception as e:
            return LookupResult(
                success=False,
                identifier=title,
                identifier_type="title",
                error=str(e),
            )
    
    def lookup_auto(self, identifier: str) -> LookupResult:
        """Auto-detect identifier type and look up."""
        identifier = identifier.strip()
        
        # Check for PMID (all digits)
        if identifier.isdigit():
            return self.lookup_pmid(identifier)
        
        # Check for PMC ID
        if identifier.upper().startswith('PMC'):
            return self.lookup_pmcid(identifier)
        
        # Check for DOI
        if identifier.startswith('10.') or 'doi.org' in identifier.lower():
            # Extract DOI if it's a URL
            if 'doi.org/' in identifier:
                doi = identifier.split('doi.org/')[-1]
            else:
                doi = identifier
            return self.lookup_doi(doi)
        
        # Default to title search
        return self.lookup_title(identifier)
    
    def batch_lookup(self, identifiers: List[str]) -> List[LookupResult]:
        """Look up multiple identifiers."""
        results = []
        for identifier in identifiers:
            identifier = identifier.strip()
            if identifier and not identifier.startswith('#'):  # Skip empty lines and comments
                result = self.lookup_auto(identifier)
                results.append(result)
        return results
    
    def _metadata_to_dict(self, metadata: ArticleMetadata) -> Dict[str, Any]:
        """Convert ArticleMetadata to dictionary."""
        return {
            'pmid': metadata.pmid,
            'title': metadata.title,
            'authors': metadata.authors,
            'journal': metadata.journal,
            'journal_abbreviation': metadata.journal_abbreviation,
            'year': metadata.year,
            'month': metadata.month,
            'volume': metadata.volume,
            'issue': metadata.issue,
            'pages': metadata.pages,
            'doi': metadata.doi,
            'abstract': metadata.abstract[:200] + '...' if metadata.abstract and len(metadata.abstract) > 200 else metadata.abstract,
        }
    
    def _crossref_to_dict(self, metadata: CrossRefMetadata) -> Dict[str, Any]:
        """Convert CrossRefMetadata to dictionary."""
        return {
            'doi': metadata.doi,
            'title': metadata.title,
            'work_type': metadata.work_type,
            'authors': metadata.authors,
            'editors': metadata.editors,
            'book_title': metadata.book_title,
            'container_title': metadata.container_title,
            'publisher': metadata.publisher,
            'year': metadata.year,
            'volume': metadata.volume,
            'pages': metadata.pages,
        }


def format_output(result: LookupResult, output_format: str) -> str:
    """Format result for output."""
    if output_format == 'inline':
        return result.inline_mark if result.success else f"# Error: {result.error}"
    elif output_format == 'endnote':
        return result.endnote_citation if result.success else f"# Error: {result.error}"
    elif output_format == 'json':
        return json.dumps(asdict(result), indent=2)
    else:  # full
        if result.success:
            return f"Inline: {result.inline_mark}\n\n{result.full_citation}"
        return f"# Error looking up '{result.identifier}': {result.error}"


def main():
    parser = argparse.ArgumentParser(
        description="Look up citations and generate Vancouver-style references"
    )
    
    # Identifier options (mutually exclusive)
    id_group = parser.add_mutually_exclusive_group()
    id_group.add_argument('--pmid', help='PubMed ID to look up')
    id_group.add_argument('--doi', help='DOI to look up')
    id_group.add_argument('--pmcid', help='PMC ID to look up')
    id_group.add_argument('--title', help='Article title to search')
    id_group.add_argument('--auto', help='Auto-detect identifier type')
    id_group.add_argument('--batch', help='File with identifiers (one per line)')
    
    # Output options
    parser.add_argument('--format', '-f', 
                        choices=['inline', 'endnote', 'full', 'json'],
                        default='full',
                        help='Output format (default: full)')
    parser.add_argument('--output', '-o', help='Output file (default: stdout)')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    
    args = parser.parse_args()
    
    # Check if any identifier provided
    if not any([args.pmid, args.doi, args.pmcid, args.title, args.auto, args.batch]):
        parser.print_help()
        sys.exit(1)
    
    lookup = CitationLookup(verbose=args.verbose)
    
    # Test connection
    if not lookup.test_connection():
        console.print("[red]Error: Cannot connect to PubMed MCP server[/red]")
        console.print("[yellow]Ensure server is running: npm run start:http[/yellow]")
        sys.exit(1)
    
    results = []
    
    if args.pmid:
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
    
    # Format output
    output_lines = []
    for result in results:
        output_lines.append(format_output(result, args.format))
        if args.format == 'full':
            output_lines.append('')  # Blank line between entries
    
    output_text = '\n'.join(output_lines)
    
    # Write output
    if args.output:
        Path(args.output).write_text(output_text)
        console.print(f"[green]Output written to: {args.output}[/green]")
    else:
        print(output_text)
    
    # Summary for batch
    if args.batch and len(results) > 1:
        success_count = sum(1 for r in results if r.success)
        console.print(f"\n[cyan]Processed {len(results)} identifiers: {success_count} successful, {len(results) - success_count} failed[/cyan]")


if __name__ == "__main__":
    main()

