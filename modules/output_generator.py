"""Output Generator Module - Generates formatted markdown output."""

from typing import List, Dict
from dataclasses import dataclass, field
from datetime import datetime
from loguru import logger

from .reference_parser import ParsedReference
from .type_detector import CitationType
from .vancouver_formatter import FormattedCitation


@dataclass
class ManualReviewItem:
    """Item flagged for manual review."""
    original_number: int
    original_text: str
    reason: str
    suggested_action: str = ""
    additional_info: Dict = field(default_factory=dict)


@dataclass
class OutputDocument:
    """Complete output document structure."""
    body_content: str
    journal_articles: List[FormattedCitation]
    book_chapters: List[ParsedReference]
    books: List[ParsedReference]
    newspaper_articles: List[ParsedReference]
    webpages: List[ParsedReference]
    web_articles: List[ParsedReference]
    blogs: List[ParsedReference]
    manual_review_items: List[ManualReviewItem]
    processing_notes: List[str] = field(default_factory=list)


class OutputGenerator:
    """Generates formatted output documents."""

    def __init__(self):
        self.processing_notes: List[str] = []

    def generate(self, doc: OutputDocument) -> str:
        """Generate complete formatted markdown."""
        sections = [doc.body_content, "", "# References", ""]

        # Processed journal articles
        if doc.journal_articles:
            sections.extend(["## Journal Articles", ""])
            for citation in sorted(doc.journal_articles, key=lambda x: x.label):
                sections.extend([citation.full_citation, ""])

        # Pending sections
        pending = [
            ("## Book Chapters", doc.book_chapters),
            ("## Books", doc.books),
            ("## Newspaper Articles", doc.newspaper_articles),
            ("## Webpages", doc.webpages),
            ("## Web Articles", doc.web_articles),
            ("## Blogs", doc.blogs),
        ]

        for header, items in pending:
            if items:
                sections.extend([header, ""])
                for ref in sorted(items, key=lambda x: x.original_number):
                    sections.extend([f"{ref.original_number}. {ref.original_text}", ""])

        # Manual review section
        if doc.manual_review_items:
            sections.extend(["---", "", "## Needs Manual Review", "",
                           "> The following citations require manual attention.", ""])

            for item in doc.manual_review_items:
                sections.extend([
                    f"### Reference #{item.original_number}", "",
                    f"**Original:** {item.original_text}", "",
                    f"**Issue:** {item.reason}", "",
                ])
                if item.suggested_action:
                    sections.extend([f"**Suggested Action:** {item.suggested_action}", ""])
                sections.extend(["---", ""])

        # Processing notes
        sections.extend(["", f"<!-- CitationSculptor - Processed: {datetime.now().isoformat()} -->"])

        return '\n'.join(sections)

    def generate_summary_report(self, doc: OutputDocument) -> str:
        """Generate processing summary report."""
        lines = [
            "# CitationSculptor Processing Report", "",
            f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", "",
            "## Summary", "",
            "| Category | Count |",
            "|----------|-------|",
            f"| Journal Articles (processed) | {len(doc.journal_articles)} |",
            f"| Book Chapters (pending) | {len(doc.book_chapters)} |",
            f"| Books (pending) | {len(doc.books)} |",
            f"| Newspaper Articles (pending) | {len(doc.newspaper_articles)} |",
            f"| Webpages (pending) | {len(doc.webpages)} |",
            f"| Web Articles (pending) | {len(doc.web_articles)} |",
            f"| Blogs (pending) | {len(doc.blogs)} |",
            f"| **Needs Manual Review** | {len(doc.manual_review_items)} |",
            "",
        ]
        return '\n'.join(lines)

    def create_output_document(
        self,
        body_content: str,
        categorized_refs: Dict[CitationType, List[ParsedReference]],
        processed_citations: List[FormattedCitation],
        manual_review: List[ManualReviewItem],
    ) -> OutputDocument:
        """Create OutputDocument from components."""
        processed_numbers = {c.original_number for c in processed_citations}

        def filter_pending(refs: List[ParsedReference]) -> List[ParsedReference]:
            return [r for r in refs if r.original_number not in processed_numbers]

        return OutputDocument(
            body_content=body_content,
            journal_articles=processed_citations,
            book_chapters=filter_pending(categorized_refs.get(CitationType.BOOK_CHAPTER, [])),
            books=filter_pending(categorized_refs.get(CitationType.BOOK, [])),
            newspaper_articles=filter_pending(categorized_refs.get(CitationType.NEWSPAPER_ARTICLE, [])),
            webpages=filter_pending(categorized_refs.get(CitationType.WEBPAGE, [])),
            web_articles=filter_pending(categorized_refs.get(CitationType.WEB_ARTICLE, [])),
            blogs=filter_pending(categorized_refs.get(CitationType.BLOG, [])),
            manual_review_items=manual_review,
            processing_notes=self.processing_notes,
        )

    def add_processing_note(self, note: str):
        """Add a processing note."""
        self.processing_notes.append(note)
        logger.info(f"Note: {note}")

