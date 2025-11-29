#!/usr/bin/env python3
"""
CitationSculptor - Transform LLM-generated references into Vancouver-style citations.

Usage:
    python citation_sculptor.py "path/to/document.md" [options]

Options:
    --output, -o     Output file path (default: filename_formatted.md)
    --verbose, -v    Enable detailed logging
    --dry-run, -n    Preview changes without writing output
    --no-backup      Skip creating backup file
    --gui            Show progress in a popup dialog window
    --multi-section  Process documents with multiple reference sections independently
"""

import sys
import argparse
from pathlib import Path
from typing import List, Optional

from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.panel import Panel
from loguru import logger

from modules.file_handler import FileHandler
from modules.reference_parser import ReferenceParser, ParsedReference, DocumentSection
from modules.type_detector import CitationTypeDetector, CitationType
from modules.pubmed_client import PubMedClient, ArticleMetadata
from modules.vancouver_formatter import VancouverFormatter, FormattedCitation
from modules.inline_replacer import InlineReplacer
from modules.output_generator import OutputGenerator, OutputDocument, ManualReviewItem

console = Console(force_terminal=True)


class CitationSculptor:
    """Main application class for processing citations."""

    def __init__(
        self,
        input_path: str,
        output_path: Optional[str] = None,
        verbose: bool = False,
        dry_run: bool = False,
        create_backup: bool = True,
        use_gui: bool = False,
        multi_section: bool = False,
    ):
        self.input_path = input_path
        self.output_path = output_path
        self.verbose = verbose
        self.dry_run = dry_run
        self.create_backup = create_backup
        self.use_gui = use_gui
        self.multi_section = multi_section
        self.gui_dialog = None

        log_level = "DEBUG" if verbose else "INFO"
        logger.remove()
        logger.add(
            sys.stderr,
            level=log_level,
            format="<level>{level: <8}</level> | <cyan>{message}</cyan>",
        )

        self.file_handler = FileHandler(input_path)
        self.type_detector = CitationTypeDetector()
        self.pubmed_client = PubMedClient()
        self.formatter = VancouverFormatter(max_authors=3)
        self.output_generator = OutputGenerator()
        
        # Initialize webpage scraper for extracting metadata from academic sites
        try:
            from modules.pubmed_client import WebpageScraper
            self.webpage_scraper = WebpageScraper(timeout=10)
        except ImportError:
            self.webpage_scraper = None
            logger.warning("WebpageScraper not available")

        self.processed_citations: List[FormattedCitation] = []
        self.manual_review_items: List[ManualReviewItem] = []
        self.number_to_label_map: dict = {}

    def run(self) -> bool:
        """Run the citation processing pipeline."""
        console.print(Panel.fit(
            "[bold blue]CitationSculptor[/bold blue]\n"
            "Transform LLM-generated references to Vancouver-style citations",
            border_style="blue"
        ))

        try:
            self._step_read_file()
            
            if self.multi_section:
                return self._run_multi_section()
            else:
                return self._run_single_section()

        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            logger.exception("Processing failed")
            return False
    
    def _run_single_section(self) -> bool:
        """Run single-section processing (original behavior)."""
        parser = self._step_parse_references()
        if not parser.references:
            console.print("[yellow]No references found. Nothing to process.[/yellow]")
            return False

        # Filter out unreferenced citations early
        used_refs, unused_refs = self._step_filter_unreferenced(parser)
        
        categorized = self._step_categorize_references(used_refs)

        if not self._step_test_pubmed():
            console.print("[red]Cannot proceed without PubMed MCP server.[/red]")
            return False

        # Initialize GUI dialog if enabled
        if self.use_gui:
            from modules.progress_dialog import MultiTaskProgressDialog
            tasks = []
            journal_refs = categorized.get(CitationType.JOURNAL_ARTICLE, [])
            # Treat UNKNOWN references as potential journal articles to be looked up by title
            journal_refs.extend(categorized.get(CitationType.UNKNOWN, []))
            
            webpage_refs = categorized.get(CitationType.WEBPAGE, [])
            blog_refs = categorized.get(CitationType.BLOG, [])
            newspaper_refs = categorized.get(CitationType.NEWSPAPER_ARTICLE, [])
            
            # Treat PDF documents as potential journal articles (try PubMed lookup by title)
            pdf_refs = categorized.get(CitationType.PDF_DOCUMENT, [])
            if pdf_refs:
                journal_refs.extend(pdf_refs)
            
            if journal_refs:
                tasks.append(("Processing Journal Articles (via PubMed)", len(journal_refs)))
            if webpage_refs:
                tasks.append(("Processing Webpages", len(webpage_refs)))
            if blog_refs:
                tasks.append(("Processing Blogs", len(blog_refs)))
            if newspaper_refs:
                tasks.append(("Processing Newspaper Articles", len(newspaper_refs)))
            
            self.gui_dialog = MultiTaskProgressDialog()
            self.gui_dialog.show(tasks)
        else:
            journal_refs = categorized.get(CitationType.JOURNAL_ARTICLE, [])
            # Treat UNKNOWN references as potential journal articles to be looked up by title
            journal_refs.extend(categorized.get(CitationType.UNKNOWN, []))
            
            webpage_refs = categorized.get(CitationType.WEBPAGE, [])
            blog_refs = categorized.get(CitationType.BLOG, [])
            newspaper_refs = categorized.get(CitationType.NEWSPAPER_ARTICLE, [])
            
            # Treat PDF documents as potential journal articles (try PubMed lookup by title)
            pdf_refs = categorized.get(CitationType.PDF_DOCUMENT, [])
            if pdf_refs:
                journal_refs.extend(pdf_refs)

        task_idx = 0
        if journal_refs:
            # Batch prefetch ID conversions for efficiency
            self._prefetch_journal_ids(journal_refs)
            
            if self.gui_dialog:
                self.gui_dialog.start_task(task_idx)
                task_idx += 1
            self._step_process_journal_articles(journal_refs)

        # Process webpages (no API calls needed)
        if webpage_refs:
            if self.gui_dialog:
                self.gui_dialog.start_task(task_idx)
                task_idx += 1
            self._step_process_webpages(webpage_refs)

        # Process blogs (no API calls needed)  
        if blog_refs:
            if self.gui_dialog:
                self.gui_dialog.start_task(task_idx)
                task_idx += 1
            self._step_process_blogs(blog_refs)

        # Process newspaper articles (no API calls needed)
        if newspaper_refs:
            if self.gui_dialog:
                self.gui_dialog.start_task(task_idx)
                task_idx += 1
            self._step_process_newspapers(newspaper_refs)

        # Close GUI dialog
        if self.gui_dialog:
            self.gui_dialog.close()
            self.gui_dialog = None

        # Detect inline reference style from body content
        body = parser.get_body_content()
        inline_style = parser._detect_inline_style(body)
        body_content = self._step_update_inline_references(body, style=inline_style)

        if not self.dry_run:
            self._step_generate_output(body_content, categorized, parser)
        else:
            self._step_preview_output()

        self._print_summary()
        return True
    
    def _run_multi_section(self) -> bool:
        """Run multi-section processing for documents with multiple reference lists."""
        console.print("\n[bold cyan]Multi-Section Mode[/bold cyan]")
        console.print("Processing each reference section independently...\n")
        
        parser = ReferenceParser(self.file_handler.original_content, multi_section=True)
        sections = parser.parse_multi_section()
        
        if not sections:
            console.print("[yellow]No reference sections found. Nothing to process.[/yellow]")
            return False
        
        console.print(f"[green][OK][/green] Found {len(sections)} document section(s)")
        
        if not self._step_test_pubmed():
            console.print("[red]Cannot proceed without PubMed MCP server.[/red]")
            return False
        
        # Track all section results for combined output
        all_section_results = []
        
        for section in sections:
            console.print(f"\n[bold]━━━ Section {section.section_index + 1} ━━━[/bold]")
            console.print(f"  Body: lines {section.body_start + 1}-{section.body_end}")
            console.print(f"  References: lines {section.ref_start + 1}-{section.ref_end}")
            console.print(f"  Inline style: {section.inline_ref_style}")
            console.print(f"  References: {len(section.references)}")
            
            # Reset state for this section
            self.processed_citations = []
            self.manual_review_items = []
            self.number_to_label_map = {}
            
            # Filter unreferenced for this section
            used_refs, unused_refs = self._filter_section_unreferenced(parser, section)
            
            # Check for undefined references (used in body but not defined)
            defined_numbers = {ref.original_number for ref in section.references}
            undefined_refs = parser.find_undefined_references(
                section.body_content, 
                defined_numbers, 
                style=section.inline_ref_style
            )
            if undefined_refs:
                console.print(f"[red][!] Warning: {len(undefined_refs)} undefined reference(s): {sorted(undefined_refs)}[/red]")
                console.print(f"[dim]    These citations are used in the text but have no definition.[/dim]")
            
            if not used_refs:
                console.print("[yellow]  No used references in this section[/yellow]")
                all_section_results.append({
                    'section': section,
                    'body_content': section.body_content,
                    'processed': [],
                    'manual_review': [],
                    'mapping': {},
                })
                continue
            
            # Categorize and process
            categorized = self._step_categorize_references(used_refs)
            
            journal_refs = categorized.get(CitationType.JOURNAL_ARTICLE, [])
            # Treat UNKNOWN references as potential journal articles to be looked up by title
            journal_refs.extend(categorized.get(CitationType.UNKNOWN, []))
            
            webpage_refs = categorized.get(CitationType.WEBPAGE, [])
            blog_refs = categorized.get(CitationType.BLOG, [])
            newspaper_refs = categorized.get(CitationType.NEWSPAPER_ARTICLE, [])
            
            # Treat PDF documents as potential journal articles (try PubMed lookup by title)
            pdf_refs = categorized.get(CitationType.PDF_DOCUMENT, [])
            if pdf_refs:
                journal_refs.extend(pdf_refs)
                console.print(f"[dim]  Including {len(pdf_refs)} PDF documents for PubMed title search[/dim]")
            
            if journal_refs:
                self._prefetch_journal_ids(journal_refs)
                self._step_process_journal_articles(journal_refs)
            
            if webpage_refs:
                self._step_process_webpages(webpage_refs)
            
            if blog_refs:
                self._step_process_blogs(blog_refs)
            
            if newspaper_refs:
                self._step_process_newspapers(newspaper_refs)
            
            # Update inline references for this section
            updated_body = self._step_update_inline_references(
                section.body_content, 
                style=section.inline_ref_style
            )
            
            all_section_results.append({
                'section': section,
                'body_content': updated_body,
                'categorized': categorized,
                'processed': list(self.processed_citations),
                'manual_review': list(self.manual_review_items),
                'mapping': dict(self.number_to_label_map),
                'undefined_refs': undefined_refs,  # Track undefined references
            })
        
        # Generate combined output
        if not self.dry_run:
            self._generate_multi_section_output(all_section_results, parser)
        else:
            self._step_preview_output()
        
        # Print combined summary
        total_processed = sum(len(r['processed']) for r in all_section_results)
        total_review = sum(len(r['manual_review']) for r in all_section_results)
        total_mapped = sum(len(r['mapping']) for r in all_section_results)
        
        console.print("\n" + "=" * 60)
        console.print("[bold]Multi-Section Processing Complete![/bold]")
        console.print("=" * 60)
        
        # Count Null placeholders in processed citations
        null_date_count = sum(
            1 for r in all_section_results 
            for c in r['processed'] 
            if 'Null_Date' in c.full_citation
        )
        null_author_count = sum(
            1 for r in all_section_results 
            for c in r['processed'] 
            if 'Null_Author' in c.full_citation
        )
        total_null = null_date_count + null_author_count
        
        table = Table(show_header=False)
        table.add_column("Metric", style="cyan")
        table.add_column("Value", justify="right", style="green")
        table.add_row("Sections processed", str(len(sections)))
        table.add_row("Total citations processed", str(total_processed))
        table.add_row("Total inline references updated", str(total_mapped))
        table.add_row("Total items needing review", str(total_review))
        console.print(table)
        
        # Show Null placeholder summary if any exist
        if total_null > 0:
            console.print(f"\n[yellow][!][/yellow] {total_null} citations have incomplete data (search for 'Null_' to fix)")
            if null_date_count > 0:
                console.print(f"    - Null_Date: {null_date_count}")
            if null_author_count > 0:
                console.print(f"    - Null_Author: {null_author_count}")
        
        return True
    
    def _filter_section_unreferenced(self, parser: ReferenceParser, section: DocumentSection):
        """Filter unreferenced citations for a specific section."""
        referenced_numbers = parser.find_referenced_numbers(
            body_content=section.body_content,
            style=section.inline_ref_style
        )
        
        used = []
        unused = []
        
        for ref in section.references:
            if ref.original_number in referenced_numbers:
                used.append(ref)
            else:
                unused.append(ref)
        
        if unused:
            console.print(f"[yellow][!][/yellow] Skipping {len(unused)} unreferenced citations in section")
        
        console.print(f"[green][OK][/green] {len(used)} citations are used in section body")
        return used, unused
    
    def _generate_multi_section_output(self, section_results: List[dict], parser: ReferenceParser):
        """Generate output for multi-section document."""
        # Reconstruct document with updated sections
        output_parts = []
        
        for result in section_results:
            section = result['section']
            body_content = result['body_content']
            
            # Check if body content has the marker (meaning text exists after references)
            if '<!-- REF_SECTION_MARKER -->' in body_content:
                # Split body into before and after reference section
                body_before, body_after = body_content.split('<!-- REF_SECTION_MARKER -->', 1)
                
                # Add body before references
                output_parts.append(body_before.rstrip())
                
                # Add formatted reference section
                ref_section = self._format_section_references(result)
                output_parts.append(ref_section)
                
                # Add body after references
                output_parts.append(body_after.lstrip())
            else:
                # Simple case: body is only before references
                output_parts.append(body_content)
                
                # Add formatted reference section
                ref_section = self._format_section_references(result)
                output_parts.append(ref_section)
        
        output_content = '\n'.join(output_parts)
        output_path = self.file_handler.write_output(output_content, self.output_path)
        console.print(f"\n[green][OK][/green] Output written to: {output_path}")
        
        # Generate combined mapping file
        all_mappings = []
        for result in section_results:
            section = result['section']
            for num, label in result['mapping'].items():
                all_mappings.append({
                    'section': section.section_index + 1,
                    'original_number': num,
                    'new_label': label,
                })
        
        mapping_path = output_path.parent / f"{output_path.stem}_mapping.json"
        import json
        with open(mapping_path, 'w', encoding='utf-8') as f:
            json.dump({
                'sections': len(section_results),
                'total_mappings': len(all_mappings),
                'mappings': all_mappings,
            }, f, indent=2)
        console.print(f"[green][OK][/green] Mapping: {mapping_path.name}")
    
    def _format_section_references(self, result: dict) -> str:
        """Format reference section for output."""
        lines = ["\n## References\n"]
        
        # Add processed citations (sorted alphabetically by label)
        sorted_citations = sorted(result['processed'], key=lambda c: c.label.lower())
        for citation in sorted_citations:
            lines.append(citation.full_citation)
            lines.append("")
        
        # Count Null placeholders in citations
        all_citations_text = '\n'.join(lines)
        null_author_count = all_citations_text.count('Null_Author')
        null_date_count = all_citations_text.count('Null_Date')
        total_null_count = null_author_count + null_date_count
        
        # Add Null placeholder note if any exist
        if total_null_count > 0:
            lines.append("\n### Incomplete Citations\n")
            lines.append(f"**{total_null_count} citations have missing information.** Search for `Null_` to find and fix them.")
            if null_author_count > 0:
                lines.append(f"- `Null_Author`: {null_author_count} citations")
            if null_date_count > 0:
                lines.append(f"- `Null_Date`: {null_date_count} citations")
            lines.append("")
        
        # Add manual review section only for truly problematic cases
        if result['manual_review']:
            lines.append("\n### Needs Manual Review\n")
            lines.append("*These citations could not be resolved automatically and need manual attention.*\n")
            for item in result['manual_review']:
                lines.append(f"#### #{item.original_number}: {item.reason}")
                
                # Show original citation text
                if item.original_text:
                    # Truncate if too long but show meaningful portion
                    orig_text = item.original_text
                    if len(orig_text) > 120:
                        orig_text = orig_text[:120] + "..."
                    lines.append(f"**Original:** `{orig_text}`")
                
                # Show the URL
                url = item.additional_info.get('url', '')
                if url:
                    lines.append(f"**URL:** {url}")
                
                # Fallback for old-style entries
                if item.suggested_action:
                    lines.append(f"**Suggested:** {item.suggested_action}")
                
                lines.append("")  # Single blank line between entries
        
        # Add undefined references warning if any
        undefined_refs = result.get('undefined_refs', set())
        if undefined_refs:
            lines.append("\n### ⚠️ Undefined References\n")
            lines.append("> The following citation numbers are used in the text but have no definition in the reference list.\n")
            lines.append("> These may be errors in the original document.\n")
            for num in sorted(undefined_refs):
                lines.append(f"- `[^{num}]` - No definition found")
            lines.append("")
        
        return '\n'.join(lines)

    def _step_read_file(self):
        """Read input file and create backup."""
        with console.status("[bold green]Reading input file..."):
            self.file_handler.read_file()
            file_info = self.file_handler.get_file_info()

        console.print(f"[green][OK][/green] Loaded: {file_info['name']} ({file_info['size_bytes']:,} bytes)")

        if self.create_backup and not self.dry_run:
            backup_path = self.file_handler.create_backup()
            console.print(f"[green][OK][/green] Backup created: {backup_path.name}")

    def _step_parse_references(self) -> ReferenceParser:
        """Parse the reference section."""
        with console.status("[bold green]Parsing references..."):
            parser = ReferenceParser(self.file_handler.original_content)
            parser.find_reference_section()
            parser.parse_references()

        if parser.reference_section_start:
            console.print(f"[green][OK][/green] Found reference section at line {parser.reference_section_start + 1}")
            console.print(f"[green][OK][/green] Parsed {len(parser.references)} references")

        return parser

    def _step_filter_unreferenced(self, parser: ReferenceParser):
        """Filter out citations not used in the document body."""
        with console.status("[bold green]Checking for unreferenced citations..."):
            used_refs, unused_refs = parser.filter_unreferenced()
        
        if unused_refs:
            console.print(f"[yellow][!][/yellow] Skipping {len(unused_refs)} unreferenced citations:")
            for ref in unused_refs[:5]:  # Show first 5
                console.print(f"    - #{ref.original_number}: {ref.title[:50]}...")
            if len(unused_refs) > 5:
                console.print(f"    ... and {len(unused_refs) - 5} more")
        
        console.print(f"[green][OK][/green] {len(used_refs)} citations are used in document")
        return used_refs, unused_refs

    def _step_categorize_references(self, references: List[ParsedReference]) -> dict:
        """Categorize references by type."""
        with console.status("[bold green]Categorizing references..."):
            categorized = self.type_detector.categorize_references(references)

        table = Table(title="Reference Types Detected")
        table.add_column("Type", style="cyan")
        table.add_column("Count", justify="right", style="green")

        for ct in CitationType:
            count = len(categorized.get(ct, []))
            if count > 0:
                table.add_row(ct.value.replace('_', ' ').title(), str(count))

        console.print(table)
        return categorized

    def _step_test_pubmed(self) -> bool:
        """Test connection to PubMed MCP server."""
        with console.status("[bold green]Testing PubMed MCP connection..."):
            connected = self.pubmed_client.test_connection()

        if connected:
            console.print("[green][OK][/green] Connected to PubMed MCP server")
        else:
            console.print("[red][X][/red] Failed to connect to PubMed MCP server")
            console.print("[yellow]  Ensure server is running at http://127.0.0.1:3017/mcp[/yellow]")

        return connected

    def _prefetch_journal_ids(self, journal_refs: List[ParsedReference]):
        """
        Batch prefetch ID conversions for journal articles.
        
        This is more efficient than converting one ID at a time because
        the NCBI API can handle up to 200 IDs per request.
        """
        # Collect all PMC IDs and DOIs that need conversion
        pmcids = []
        dois = []
        
        for ref in journal_refs:
            if ref.url:
                pmcid = self.type_detector.extract_pmcid(ref.url)
                doi = self.type_detector.extract_doi(ref.url)
                pmid = self.type_detector.extract_pmid(ref.url)
                
                # Only need to convert if we don't have a direct PMID
                if not pmid:
                    if pmcid:
                        pmcids.append(pmcid)
                    elif doi:
                        dois.append(doi)
        
        # Batch convert PMC IDs
        if pmcids:
            console.print(f"[dim]Prefetching {len(pmcids)} PMC ID conversions...[/dim]")
            self.pubmed_client.batch_prefetch_conversions(pmcids, id_type="pmcid")
        
        # Batch convert DOIs
        if dois:
            console.print(f"[dim]Prefetching {len(dois)} DOI conversions...[/dim]")
            self.pubmed_client.batch_prefetch_conversions(dois, id_type="doi")

    def _deduplicate_references(self, refs: List[ParsedReference]) -> tuple:
        """
        Deduplicate references by URL to avoid redundant API calls.
        
        For grouped references (V6 format), multiple [^N] IDs point to the same source.
        We only need to process each unique URL once.
        
        Returns:
            tuple: (unique_refs, url_to_numbers_map)
            - unique_refs: List of references with unique URLs (first occurrence)
            - url_to_numbers_map: Dict mapping URL -> list of all reference numbers for that URL
        """
        url_to_numbers: dict = {}
        url_to_ref: dict = {}
        no_url_refs = []
        
        for ref in refs:
            if ref.url:
                if ref.url not in url_to_numbers:
                    url_to_numbers[ref.url] = []
                    url_to_ref[ref.url] = ref  # Keep first occurrence
                url_to_numbers[ref.url].append(ref.original_number)
            else:
                # References without URLs can't be deduplicated
                no_url_refs.append(ref)
        
        unique_refs = list(url_to_ref.values()) + no_url_refs
        
        # Log deduplication stats
        if len(refs) != len(unique_refs):
            logger.info(f"Deduplicated {len(refs)} refs -> {len(unique_refs)} unique URLs")
        
        return unique_refs, url_to_numbers

    def _step_process_journal_articles(self, journal_refs: List[ParsedReference]):
        """Process journal article references via PubMed."""
        # Deduplicate references by URL to avoid redundant API calls
        unique_refs, url_to_numbers = self._deduplicate_references(journal_refs)
        
        total = len(unique_refs)
        processed_count = 0
        error_count = 0

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TextColumn("[cyan]{task.completed}/{task.total}[/cyan]"),
            console=console,
            disable=self.use_gui,  # Disable CLI progress if GUI is enabled
        ) as progress:
            task = progress.add_task("Processing journal articles...", total=total)

            for i, ref in enumerate(unique_refs):
                status_msg = f"Article #{ref.original_number}..."
                progress.update(task, description=status_msg)
                
                # Update GUI dialog if enabled
                if self.gui_dialog:
                    self.gui_dialog.update_task(i, status_msg)

                try:
                    result = self._process_single_journal_article(ref)
                    if result:
                        self.processed_citations.append(result)
                        
                        # Apply the label to ALL reference numbers pointing to this URL
                        if ref.url and ref.url in url_to_numbers:
                            for num in url_to_numbers[ref.url]:
                                self.number_to_label_map[num] = result.label
                        else:
                            self.number_to_label_map[ref.original_number] = result.label
                        
                        ref.processed = True
                        ref.new_label = result.label
                        processed_count += 1
                except Exception as e:
                    logger.error(f"Error processing #{ref.original_number}: {e}")
                    self._add_manual_review(ref, f"Processing error: {str(e)}", "Manually verify")
                    error_count += 1
                
                progress.update(task, advance=1)
                if self.gui_dialog:
                    self.gui_dialog.update_task(i + 1, status_msg)

        console.print(f"[green][OK][/green] Processed {processed_count} unique sources" +
                     (f" ({len(journal_refs)} total refs)" if len(journal_refs) != processed_count else "") +
                     (f" ({error_count} errors)" if error_count else ""))
        if self.manual_review_items:
            console.print(f"[yellow][!][/yellow] {len(self.manual_review_items)} items need manual review")

    def _process_single_journal_article(self, ref: ParsedReference) -> Optional[FormattedCitation]:
        """Process a single journal article reference."""
        pmid = self.type_detector.extract_pmid(ref.url) if ref.url else None
        pmcid = self.type_detector.extract_pmcid(ref.url) if ref.url else None
        doi = self.type_detector.extract_doi(ref.url) if ref.url else None

        metadata: Optional[ArticleMetadata] = None

        # Priority 1: Direct PMID lookup
        if pmid:
            logger.info(f"Fetching PMID: {pmid}")
            metadata = self.pubmed_client.fetch_article_by_pmid(pmid)

        # Priority 2: PMC ID lookup
        elif pmcid:
            logger.info(f"Looking up PMC ID: {pmcid}")
            metadata = self.pubmed_client.fetch_article_by_pmcid(pmcid)
            if not metadata:
                # PMC lookup returned None - could be a book chapter or other non-journal type
                # Try to get DOI via ID conversion and use CrossRef directly
                logger.info(f"PMC lookup returned None, trying ID conversion for DOI...")
                conversions = self.pubmed_client.convert_ids([pmcid], id_type="pmcid", target_type="all")
                if conversions and conversions[0].doi:
                    doi = conversions[0].doi  # Use discovered DOI for CrossRef lookup below
                    logger.info(f"Found DOI via conversion: {doi}")
                else:
                    self._add_manual_review(ref, f"PMC article ({pmcid}), no PMID or DOI found", "Manually look up")
                    return None

        # Priority 3: DOI lookup
        elif doi:
            logger.info(f"Looking up DOI: {doi}")
            metadata = self.pubmed_client.fetch_article_by_doi(doi)
            if not metadata:
                # Fall back to title search
                logger.info(f"DOI not in PubMed, trying title search...")
                metadata = self.pubmed_client.verify_article_exists(ref.title)

        # Priority 4: Title search
        else:
            logger.info(f"Searching by title: {ref.title[:50]}...")
            metadata = self.pubmed_client.verify_article_exists(ref.title)

        # If found in PubMed, format as journal article
        if metadata:
            return self.formatter.format_journal_article(metadata, ref.original_number)

        # Priority 5: Try CrossRef for non-PubMed items (books, chapters, etc.)
        crossref_metadata = None
        
        if doi:
            logger.info(f"Trying CrossRef for DOI: {doi}")
            crossref_metadata = self.pubmed_client.crossref_lookup_doi(doi)
        
        # Also try CrossRef title search if DOI lookup failed or no DOI
        if not crossref_metadata and ref.title:
            logger.info(f"Trying CrossRef title search: {ref.title[:50]}...")
            crossref_metadata = self.pubmed_client.crossref_search_title(ref.title)
            
        if crossref_metadata:
            logger.info(f"Found in CrossRef: {crossref_metadata.work_type}")
            
            # Format based on work type
            if crossref_metadata.work_type == 'book-chapter':
                return self.formatter.format_book_chapter(crossref_metadata, ref.original_number)
            elif crossref_metadata.work_type in ('book', 'monograph'):
                return self.formatter.format_book(crossref_metadata, ref.original_number)
            elif crossref_metadata.work_type == 'journal-article':
                # Journal article not in PubMed - format from CrossRef
                return self.formatter.format_crossref_journal_article(crossref_metadata, ref.original_number)
            else:
                # For other types (proceedings, reports, etc.)
                # Add to manual review with CrossRef info
                self._add_manual_review(
                    ref, 
                    f"Found in CrossRef as '{crossref_metadata.work_type}' but format not supported",
                    f"Use CrossRef metadata: {crossref_metadata.title[:50]}..."
                )
                return None

        self._add_manual_review(ref, "Article not found in PubMed or CrossRef", "Verify citation exists and format manually")
        return None

    def _step_process_webpages(self, references: List[ParsedReference]):
        """Process webpage references, attempting to scrape metadata first."""
        # Deduplicate references by URL
        unique_refs, url_to_numbers = self._deduplicate_references(references)
        
        total = len(unique_refs)
        processed_count = 0
        scraped_count = 0
        error_count = 0
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TextColumn("[cyan]{task.completed}/{task.total}[/cyan]"),
            console=console,
            disable=self.use_gui,
        ) as progress:
            task = progress.add_task("Processing webpages...", total=total)
            
            for i, ref in enumerate(unique_refs):
                status_msg = f"Webpage #{ref.original_number}..."
                if self.gui_dialog:
                    self.gui_dialog.update_task(i, status_msg)
                
                try:
                    citation = None
                    scraped_metadata = None
                    scrape_failure = None
                    
                    # Try to scrape metadata from the webpage first
                    if ref.url and self.webpage_scraper:
                        scraped_metadata, scrape_failure = self.webpage_scraper.extract_metadata_with_status(ref.url)
                        if scraped_metadata and scraped_metadata.authors:
                            # Use scraped metadata for journal-style formatting (has authors)
                            citation = self.formatter.format_scraped_webpage(
                                metadata=scraped_metadata,
                                original_number=ref.original_number,
                            )
                            scraped_count += 1
                    
                    # Fall back to basic webpage formatting
                    # Pass scraped metadata for site_name and year if available
                    if not citation:
                        # Use scraped site_name and year if available, otherwise fall back to parsed values
                        site_name = ref.source_name
                        year = None
                        is_evergreen = False
                        if scraped_metadata:
                            if scraped_metadata.site_name:
                                site_name = scraped_metadata.site_name
                            if scraped_metadata.year:
                                year = scraped_metadata.year
                            # Check if this is an evergreen page (no date expected)
                            is_evergreen = getattr(scraped_metadata, 'is_evergreen', False)
                        
                        citation = self.formatter.format_webpage(
                            title=ref.title,
                            url=ref.url or "",
                            source_name=site_name,
                            original_number=ref.original_number,
                            year=year,
                            is_evergreen=is_evergreen,
                        )
                        
                        # Note: Blocked sites now use Null_Author, Null_Date, etc. placeholders
                        # in the citation text instead of being added to manual review.
                        # User can search for "Null_" to find citations needing attention.
                    
                    self.processed_citations.append(citation)
                    
                    # Apply the label to ALL reference numbers pointing to this URL
                    if ref.url and ref.url in url_to_numbers:
                        for num in url_to_numbers[ref.url]:
                            self.number_to_label_map[num] = citation.label
                    else:
                        self.number_to_label_map[ref.original_number] = citation.label
                    
                    ref.processed = True
                    ref.new_label = citation.label
                    processed_count += 1
                    
                except Exception as e:
                    logger.error(f"Error processing webpage #{ref.original_number}: {e}")
                    self._add_manual_review(ref, f"Formatting error: {str(e)}", "Review and format manually")
                    error_count += 1
                
                progress.update(task, advance=1)
                if self.gui_dialog:
                    self.gui_dialog.update_task(i + 1, status_msg)
        
        result_msg = f"[green][OK][/green] Processed {processed_count} unique webpages"
        if len(references) != processed_count:
            result_msg += f" ({len(references)} total refs)"
        if scraped_count > 0:
            result_msg += f" ({scraped_count} with scraped metadata)"
        if error_count > 0:
            result_msg += f" ({error_count} errors)"
        console.print(result_msg)

    def _step_process_blogs(self, references: List[ParsedReference]):
        """Process blog references, attempting to scrape metadata for dates/authors."""
        # Deduplicate references by URL
        unique_refs, url_to_numbers = self._deduplicate_references(references)
        
        total = len(unique_refs)
        processed_count = 0
        scraped_count = 0
        error_count = 0
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TextColumn("[cyan]{task.completed}/{task.total}[/cyan]"),
            console=console,
            disable=self.use_gui,
        ) as progress:
            task = progress.add_task("Processing blogs...", total=total)
            
            for i, ref in enumerate(unique_refs):
                status_msg = f"Blog #{ref.original_number}..."
                if self.gui_dialog:
                    self.gui_dialog.update_task(i, status_msg)
                
                try:
                    citation = None
                    
                    # Try to scrape metadata for additional info (dates, authors)
                    if ref.url and self.webpage_scraper:
                        scraped_metadata, _ = self.webpage_scraper.extract_metadata_with_status(ref.url)
                        if scraped_metadata and scraped_metadata.authors:
                            # Use scraped metadata for author-based blog citation
                            citation = self.formatter.format_scraped_webpage(
                                metadata=scraped_metadata,
                                original_number=ref.original_number,
                            )
                            citation.citation_type = "blog"  # Override type
                            scraped_count += 1
                        elif scraped_metadata:
                            # Use scraped year if available, even without authors
                            year = scraped_metadata.year
                            if not year and scraped_metadata.published_date:
                                import re
                                m = re.match(r'(\d{4})', scraped_metadata.published_date)
                                if m:
                                    year = m.group(1)
                            site_name = scraped_metadata.site_name or ref.source_name
                            citation = self.formatter.format_blog(
                                title=ref.title,
                                url=ref.url or "",
                                source_name=site_name,
                                original_number=ref.original_number,
                                year=year,
                            )
                    
                    # Fall back to basic formatting if no scraping
                    if not citation:
                        citation = self.formatter.format_blog(
                            title=ref.title,
                            url=ref.url or "",
                            source_name=ref.source_name,
                            original_number=ref.original_number,
                        )
                    
                    self.processed_citations.append(citation)
                    
                    # Apply the label to ALL reference numbers pointing to this URL
                    if ref.url and ref.url in url_to_numbers:
                        for num in url_to_numbers[ref.url]:
                            self.number_to_label_map[num] = citation.label
                    else:
                        self.number_to_label_map[ref.original_number] = citation.label
                    
                    ref.processed = True
                    ref.new_label = citation.label
                    processed_count += 1
                    
                except Exception as e:
                    logger.error(f"Error processing blog #{ref.original_number}: {e}")
                    self._add_manual_review(ref, f"Formatting error: {str(e)}", "Review and format manually")
                    error_count += 1
                
                progress.update(task, advance=1)
                if self.gui_dialog:
                    self.gui_dialog.update_task(i + 1, status_msg)
        
        console.print(f"[green][OK][/green] Processed {processed_count} unique blogs" +
                     (f" ({len(references)} total refs)" if len(references) != processed_count else "") +
                     (f" ({scraped_count} with scraped metadata)" if scraped_count else "") +
                     (f" ({error_count} errors)" if error_count else ""))

    def _step_process_newspapers(self, references: List[ParsedReference]):
        """Process newspaper article references (no API calls needed)."""
        # Deduplicate references by URL
        unique_refs, url_to_numbers = self._deduplicate_references(references)
        
        total = len(unique_refs)
        processed_count = 0
        error_count = 0
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TextColumn("[cyan]{task.completed}/{task.total}[/cyan]"),
            console=console,
            disable=self.use_gui,
        ) as progress:
            task = progress.add_task("Processing newspapers...", total=total)
            
            for i, ref in enumerate(unique_refs):
                status_msg = f"Newspaper #{ref.original_number}..."
                if self.gui_dialog:
                    self.gui_dialog.update_task(i, status_msg)
                
                try:
                    citation = self.formatter.format_newspaper_article(
                        title=ref.title,
                        url=ref.url or "",
                        source_name=ref.source_name,
                        original_number=ref.original_number,
                    )
                    
                    self.processed_citations.append(citation)
                    
                    # Apply the label to ALL reference numbers pointing to this URL
                    if ref.url and ref.url in url_to_numbers:
                        for num in url_to_numbers[ref.url]:
                            self.number_to_label_map[num] = citation.label
                    else:
                        self.number_to_label_map[ref.original_number] = citation.label
                    
                    ref.processed = True
                    ref.new_label = citation.label
                    processed_count += 1
                    
                except Exception as e:
                    logger.error(f"Error processing newspaper #{ref.original_number}: {e}")
                    self._add_manual_review(ref, f"Formatting error: {str(e)}", "Review and format manually")
                    error_count += 1
                
                progress.update(task, advance=1)
                if self.gui_dialog:
                    self.gui_dialog.update_task(i + 1, status_msg)
        
        console.print(f"[green][OK][/green] Processed {processed_count} unique newspaper articles" +
                     (f" ({len(references)} total refs)" if len(references) != processed_count else "") +
                     (f" ({error_count} errors)" if error_count else ""))

    def _step_update_inline_references(self, body_content: str, style: str = "numeric") -> str:
        """Update inline references in document body."""
        if not self.number_to_label_map:
            console.print("[yellow]No mappings to apply[/yellow]")
            return body_content

        with console.status("[bold green]Updating inline references..."):
            replacer = InlineReplacer(self.number_to_label_map, style=style)
            result = replacer.replace_all(body_content)

        console.print(f"[green][OK][/green] Made {result.replacements_made} inline reference replacements")
        return result.modified_text

    def _step_generate_output(self, body_content: str, categorized: dict, parser: ReferenceParser):
        """Generate and write output file."""
        with console.status("[bold green]Generating output..."):
            output_doc = self.output_generator.create_output_document(
                body_content=body_content,
                categorized_refs=categorized,
                processed_citations=self.processed_citations,
                manual_review=self.manual_review_items,
            )

            output_content = self.output_generator.generate(output_doc)
            output_path = self.file_handler.write_output(output_content, self.output_path)

        console.print(f"[green][OK][/green] Output written to: {output_path}")

        # Generate summary report
        report = self.output_generator.generate_summary_report(output_doc)
        report_path = output_path.parent / f"{output_path.stem}_report.md"
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report)
        console.print(f"[green][OK][/green] Report: {report_path.name}")

        # Generate reference mapping file (for backup/rollback)
        mappings = self.output_generator.generate_reference_mapping(
            all_references=parser.references,
            processed_citations=self.processed_citations,
            manual_review=self.manual_review_items,
            number_to_label_map=self.number_to_label_map,
        )
        mapping_path = self.output_generator.save_mapping_file(mappings, output_path)
        console.print(f"[green][OK][/green] Mapping: {mapping_path.name}")

    def _step_preview_output(self):
        """Preview what would be generated (dry run)."""
        console.print("\n[bold yellow]DRY RUN - No files written[/bold yellow]\n")

        console.print("[bold]Processed Citations:[/bold]")
        for citation in self.processed_citations[:5]:
            console.print(f"  - {citation.label}: PMID {citation.pmid}")
        if len(self.processed_citations) > 5:
            console.print(f"  ... and {len(self.processed_citations) - 5} more")

    def _get_missing_fields(self, scraped_metadata) -> List[dict]:
        """
        Get list of missing fields with guidance for manual lookup.
        
        Returns list of dicts with 'field' and 'hint' keys.
        """
        missing = []
        
        # Check what's missing
        has_author = scraped_metadata and scraped_metadata.authors
        has_year = scraped_metadata and scraped_metadata.year
        has_org = scraped_metadata and scraped_metadata.site_name
        
        if not has_author:
            missing.append({
                'field': 'Author',
                'hint': 'Look for byline, "Written by", or "By" near the title'
            })
        if not has_year:
            missing.append({
                'field': 'Publication Date',
                'hint': 'Check article header, footer, or "Published on"'
            })
        if not has_org:
            missing.append({
                'field': 'Organization',
                'hint': 'Check page header, logo, or About page'
            })
        
        return missing
    
    def _add_manual_review(self, ref: ParsedReference, reason: str, suggested_action: str):
        """Add item to manual review list."""
        self.manual_review_items.append(ManualReviewItem(
            original_number=ref.original_number,
            original_text=ref.original_text,
            reason=reason,
            suggested_action=suggested_action,
            additional_info={'url': ref.url, 'title': ref.title}
        ))
        ref.needs_review = True
        ref.review_reason = reason
    
    def _add_manual_review_detailed(
        self, 
        ref: ParsedReference, 
        reason: str, 
        label: str,
        missing_fields: List[dict],
        scrape_failure: str = "",
    ):
        """Add item to manual review list with detailed field information."""
        self.manual_review_items.append(ManualReviewItem(
            original_number=ref.original_number,
            original_text=ref.original_text,
            reason=reason,
            suggested_action="",  # We'll use missing_fields instead
            additional_info={
                'url': ref.url, 
                'title': ref.title,
                'label': label,
                'missing_fields': missing_fields,
                'scrape_failure': scrape_failure,
            }
        ))
        ref.needs_review = True
        ref.review_reason = reason

    def _print_summary(self):
        """Print final processing summary."""
        console.print("\n" + "=" * 60)
        console.print("[bold]Processing Complete![/bold]")
        console.print("=" * 60)

        table = Table(show_header=False)
        table.add_column("Metric", style="cyan")
        table.add_column("Value", justify="right", style="green")

        table.add_row("Journal articles processed", str(len(self.processed_citations)))
        table.add_row("Inline references updated", str(len(self.number_to_label_map)))
        table.add_row("Items needing review", str(len(self.manual_review_items)))

        console.print(table)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Transform LLM-generated references to Vancouver-style citations"
    )

    parser.add_argument("input_file", nargs='?', help="Path to input markdown file")
    parser.add_argument("--output", "-o", help="Output file path")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")
    parser.add_argument("--dry-run", "-n", action="store_true", help="Preview only")
    parser.add_argument("--no-backup", action="store_true", help="Skip backup")
    parser.add_argument("--gui", action="store_true", help="Show progress in popup dialog")
    parser.add_argument("--multi-section", "-m", action="store_true", 
                       help="Process documents with multiple reference sections independently")
    
    # Corrections workflow
    parser.add_argument("--generate-corrections", action="store_true",
                       help="Generate a corrections template for incomplete citations")
    parser.add_argument("--apply-corrections", metavar="FILE",
                       help="Apply corrections from a filled template file")

    args = parser.parse_args()

    # Handle apply-corrections mode
    if args.apply_corrections:
        if not args.input_file:
            console.print("[red]Error: Must provide formatted document path with --apply-corrections[/red]")
            sys.exit(1)
        
        from modules.output_generator import CorrectionsHandler
        handler = CorrectionsHandler()
        
        if not Path(args.apply_corrections).exists():
            console.print(f"[red]Error: Corrections file not found: {args.apply_corrections}[/red]")
            sys.exit(1)
        
        if not Path(args.input_file).exists():
            console.print(f"[red]Error: Formatted file not found: {args.input_file}[/red]")
            sys.exit(1)
        
        try:
            output_path, count = handler.apply_corrections_to_file(
                args.input_file,
                args.apply_corrections
            )
            console.print(f"[green]✓ Applied {count} correction(s) to {output_path}[/green]")
            sys.exit(0)
        except Exception as e:
            console.print(f"[red]Error applying corrections: {e}[/red]")
            sys.exit(1)

    # Require input file for normal processing
    if not args.input_file:
        parser.print_help()
        sys.exit(1)

    if not Path(args.input_file).exists():
        console.print(f"[red]Error: File not found: {args.input_file}[/red]")
        sys.exit(1)

    sculptor = CitationSculptor(
        input_path=args.input_file,
        output_path=args.output,
        verbose=args.verbose,
        dry_run=args.dry_run,
        create_backup=not args.no_backup,
        use_gui=args.gui,
        multi_section=args.multi_section,
    )

    success = sculptor.run()
    
    # Generate corrections template if requested or if there are Null citations
    if success and args.generate_corrections:
        from modules.output_generator import CorrectionsHandler
        handler = CorrectionsHandler()
        
        output_path = sculptor.output_path or str(Path(args.input_file).with_stem(
            Path(args.input_file).stem + '_formatted'
        ).with_suffix('.md'))
        
        if Path(output_path).exists():
            with open(output_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if 'Null_' in content:
                corrections_path = handler.generate_corrections_template(content, output_path)
                if corrections_path:
                    console.print(f"[yellow]📋 Corrections template created: {corrections_path}[/yellow]")
            else:
                console.print("[green]✓ No corrections needed - all citations complete[/green]")
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
