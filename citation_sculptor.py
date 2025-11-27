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
"""

import sys
import argparse
from pathlib import Path
from typing import List, Optional

from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.panel import Panel
from loguru import logger

from modules.file_handler import FileHandler
from modules.reference_parser import ReferenceParser, ParsedReference
from modules.type_detector import CitationTypeDetector, CitationType
from modules.pubmed_client import PubMedClient, ArticleMetadata
from modules.vancouver_formatter import VancouverFormatter, FormattedCitation
from modules.inline_replacer import InlineReplacer
from modules.output_generator import OutputGenerator, OutputDocument, ManualReviewItem

console = Console()


class CitationSculptor:
    """Main application class for processing citations."""

    def __init__(
        self,
        input_path: str,
        output_path: Optional[str] = None,
        verbose: bool = False,
        dry_run: bool = False,
        create_backup: bool = True,
    ):
        self.input_path = input_path
        self.output_path = output_path
        self.verbose = verbose
        self.dry_run = dry_run
        self.create_backup = create_backup

        # Configure logging
        log_level = "DEBUG" if verbose else "INFO"
        logger.remove()
        logger.add(
            sys.stderr,
            level=log_level,
            format="<level>{level: <8}</level> | <cyan>{message}</cyan>",
        )

        # Initialize components
        self.file_handler = FileHandler(input_path)
        self.type_detector = CitationTypeDetector()
        self.pubmed_client = PubMedClient()
        self.formatter = VancouverFormatter(max_authors=3)
        self.output_generator = OutputGenerator()

        # Processing state
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
            # Step 1: Read and backup file
            self._step_read_file()

            # Step 2: Parse references
            parser = self._step_parse_references()
            if not parser.references:
                console.print("[yellow]No references found. Nothing to process.[/yellow]")
                return False

            # Step 3: Categorize references
            categorized = self._step_categorize_references(parser.references)

            # Step 4: Test PubMed connection
            if not self._step_test_pubmed():
                console.print("[red]Cannot proceed without PubMed MCP server.[/red]")
                return False

            # Step 5: Process journal articles
            journal_refs = categorized.get(CitationType.JOURNAL_ARTICLE, [])
            if journal_refs:
                self._step_process_journal_articles(journal_refs)

            # Step 6: Update inline references
            body_content = self._step_update_inline_references(parser.get_body_content())

            # Step 7: Generate output
            if not self.dry_run:
                self._step_generate_output(body_content, categorized, parser)
            else:
                self._step_preview_output()

            # Summary
            self._print_summary()
            return True

        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            logger.exception("Processing failed")
            return False

    def _step_read_file(self):
        """Read input file and create backup."""
        with console.status("[bold green]Reading input file..."):
            self.file_handler.read_file()
            file_info = self.file_handler.get_file_info()

        console.print(f"[green]✓[/green] Loaded: {file_info['name']} ({file_info['size_bytes']:,} bytes)")

        if self.create_backup and not self.dry_run:
            backup_path = self.file_handler.create_backup()
            console.print(f"[green]✓[/green] Backup created: {backup_path.name}")

    def _step_parse_references(self) -> ReferenceParser:
        """Parse the reference section."""
        with console.status("[bold green]Parsing references..."):
            parser = ReferenceParser(self.file_handler.original_content)
            parser.find_reference_section()
            parser.parse_references()

        if parser.reference_section_start:
            console.print(f"[green]✓[/green] Found reference section at line {parser.reference_section_start + 1}")
            console.print(f"[green]✓[/green] Parsed {len(parser.references)} references")

        return parser

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
            console.print("[green]✓[/green] Connected to PubMed MCP server")
        else:
            console.print("[red]✗[/red] Failed to connect to PubMed MCP server")
            console.print("[yellow]  Ensure server is running at http://127.0.0.1:3017/mcp[/yellow]")

        return connected

    def _step_process_journal_articles(self, journal_refs: List[ParsedReference]):
        """Process journal article references via PubMed."""
        console.print(f"\n[bold]Processing {len(journal_refs)} journal articles...[/bold]\n")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Processing...", total=len(journal_refs))

            for ref in journal_refs:
                progress.update(task, description=f"Processing #{ref.original_number}...")

                try:
                    result = self._process_single_journal_article(ref)
                    if result:
                        self.processed_citations.append(result)
                        self.number_to_label_map[ref.original_number] = result.label
                        ref.processed = True
                        ref.new_label = result.label
                except Exception as e:
                    logger.error(f"Error processing #{ref.original_number}: {e}")
                    self._add_manual_review(ref, f"Processing error: {str(e)}", "Manually verify")

                progress.advance(task)

        console.print(f"\n[green]✓[/green] Processed {len(self.processed_citations)} journal articles")
        if self.manual_review_items:
            console.print(f"[yellow]![/yellow] {len(self.manual_review_items)} items need manual review")

    def _process_single_journal_article(self, ref: ParsedReference) -> Optional[FormattedCitation]:
        """Process a single journal article reference."""
        pmid = self.type_detector.extract_pmid(ref.url) if ref.url else None
        pmcid = self.type_detector.extract_pmcid(ref.url) if ref.url else None

        metadata: Optional[ArticleMetadata] = None

        if pmid:
            logger.info(f"Fetching PMID: {pmid}")
            metadata = self.pubmed_client.fetch_article_by_pmid(pmid)
        elif pmcid:
            self._add_manual_review(ref, f"PMC article ({pmcid}), needs PMID", "Look up PMID")
            return None
        else:
            logger.info(f"Searching by title: {ref.title[:50]}...")
            metadata = self.pubmed_client.verify_article_exists(ref.title)
            if not metadata:
                self._add_manual_review(ref, "Article not found in PubMed", "Verify citation")
                return None

        if not metadata:
            self._add_manual_review(ref, "Failed to fetch metadata", "Manual lookup needed")
            return None

        return self.formatter.format_journal_article(metadata, ref.original_number)

    def _step_update_inline_references(self, body_content: str) -> str:
        """Update inline references in document body."""
        if not self.number_to_label_map:
            console.print("[yellow]No mappings to apply[/yellow]")
            return body_content

        with console.status("[bold green]Updating inline references..."):
            replacer = InlineReplacer(self.number_to_label_map)
            result = replacer.replace_all(body_content)

        console.print(f"[green]✓[/green] Made {result.replacements_made} inline reference replacements")
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

        console.print(f"[green]✓[/green] Output written to: {output_path}")

        # Generate summary report
        report = self.output_generator.generate_summary_report(output_doc)
        report_path = output_path.parent / f"{output_path.stem}_report.md"
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report)
        console.print(f"[green]✓[/green] Report: {report_path.name}")

    def _step_preview_output(self):
        """Preview what would be generated (dry run)."""
        console.print("\n[bold yellow]DRY RUN - No files written[/bold yellow]\n")

        console.print("[bold]Processed Citations:[/bold]")
        for citation in self.processed_citations[:5]:
            console.print(f"  • {citation.label}: PMID {citation.pmid}")
        if len(self.processed_citations) > 5:
            console.print(f"  ... and {len(self.processed_citations) - 5} more")

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

    parser.add_argument("input_file", help="Path to input markdown file")
    parser.add_argument("--output", "-o", help="Output file path")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")
    parser.add_argument("--dry-run", "-n", action="store_true", help="Preview only")
    parser.add_argument("--no-backup", action="store_true", help="Skip backup")

    args = parser.parse_args()

    if not Path(args.input_file).exists():
        console.print(f"[red]Error: File not found: {args.input_file}[/red]")
        sys.exit(1)

    sculptor = CitationSculptor(
        input_path=args.input_file,
        output_path=args.output,
        verbose=args.verbose,
        dry_run=args.dry_run,
        create_backup=not args.no_backup,
    )

    success = sculptor.run()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

