"""Output Generator Module - Generates formatted markdown output."""

import json
from typing import List, Dict, Optional
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from loguru import logger

from .reference_parser import ParsedReference
from .type_detector import CitationType
from .vancouver_formatter import FormattedCitation


@dataclass
class ReferenceMapping:
    """Mapping from old reference number to new label."""
    original_number: int
    original_text: str
    new_label: Optional[str] = None
    status: str = "pending"  # pending, processed, manual_review, skipped
    citation_type: str = ""
    pmid: Optional[str] = None
    doi: Optional[str] = None
    error_reason: Optional[str] = None


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
    book_chapters: List[FormattedCitation]  # Processed via CrossRef
    books: List[FormattedCitation]  # Processed via CrossRef
    newspaper_articles: List[FormattedCitation]  # Processed locally
    webpages: List[FormattedCitation]  # Processed locally
    web_articles: List[ParsedReference]  # Pending
    blogs: List[FormattedCitation]  # Processed locally
    manual_review_items: List[ManualReviewItem]
    processing_notes: List[str] = field(default_factory=list)


class OutputGenerator:
    """Generates formatted output documents."""

    def __init__(self):
        self.processing_notes: List[str] = []

    def generate(self, doc: OutputDocument) -> str:
        """Generate complete formatted markdown."""
        sections = [doc.body_content, "", "# References", ""]

        # Processed sections (FormattedCitation objects)
        processed_sections = [
            ("## Journal Articles", doc.journal_articles),
            ("## Book Chapters", doc.book_chapters),
            ("## Books", doc.books),
            ("## Newspaper Articles", doc.newspaper_articles),
            ("## Webpages", doc.webpages),
            ("## Blogs", doc.blogs),
        ]

        for header, citations in processed_sections:
            if citations:
                sections.extend([header, ""])
                for citation in sorted(citations, key=lambda x: x.label):
                    sections.extend([citation.full_citation, ""])

        # Pending sections (ParsedReference objects - not yet processed)
        pending_sections = [
            ("## Web Articles", doc.web_articles),
        ]

        for header, items in pending_sections:
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
            f"| Journal Articles | {len(doc.journal_articles)} |",
            f"| Book Chapters | {len(doc.book_chapters)} |",
            f"| Books | {len(doc.books)} |",
            f"| Newspaper Articles | {len(doc.newspaper_articles)} |",
            f"| Webpages | {len(doc.webpages)} |",
            f"| Blogs | {len(doc.blogs)} |",
            f"| Web Articles (pending) | {len(doc.web_articles)} |",
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

        # Separate processed citations by type
        def filter_by_type(citations: List[FormattedCitation], *types: str) -> List[FormattedCitation]:
            return [c for c in citations if c.citation_type in types]

        return OutputDocument(
            body_content=body_content,
            journal_articles=filter_by_type(processed_citations, 'journal_article'),
            book_chapters=filter_by_type(processed_citations, 'book_chapter'),
            books=filter_by_type(processed_citations, 'book'),
            newspaper_articles=filter_by_type(processed_citations, 'newspaper_article'),
            webpages=filter_by_type(processed_citations, 'webpage'),
            web_articles=filter_pending(categorized_refs.get(CitationType.WEB_ARTICLE, [])),
            blogs=filter_by_type(processed_citations, 'blog'),
            manual_review_items=manual_review,
            processing_notes=self.processing_notes,
        )

    def add_processing_note(self, note: str):
        """Add a processing note."""
        self.processing_notes.append(note)
        logger.info(f"Note: {note}")

    def generate_reference_mapping(
        self,
        all_references: List[ParsedReference],
        processed_citations: List[FormattedCitation],
        manual_review: List[ManualReviewItem],
        number_to_label_map: Dict[int, str],
    ) -> List[ReferenceMapping]:
        """Generate complete mapping of all references."""
        mappings = []
        
        # Create lookup sets for quick access
        processed_numbers = {c.original_number: c for c in processed_citations}
        review_numbers = {m.original_number: m for m in manual_review}
        
        for ref in all_references:
            mapping = ReferenceMapping(
                original_number=ref.original_number,
                original_text=ref.original_text,
                citation_type=getattr(ref, 'citation_type', 'unknown'),
            )
            
            if ref.original_number in processed_numbers:
                citation = processed_numbers[ref.original_number]
                mapping.new_label = citation.label
                mapping.status = "processed"
                mapping.pmid = citation.pmid
                mapping.doi = citation.doi
            elif ref.original_number in review_numbers:
                review_item = review_numbers[ref.original_number]
                mapping.status = "manual_review"
                mapping.error_reason = review_item.reason
            elif ref.original_number in number_to_label_map:
                mapping.new_label = number_to_label_map[ref.original_number]
                mapping.status = "processed"
            else:
                mapping.status = "pending"
            
            mappings.append(mapping)
        
        return mappings

    def save_mapping_file(
        self,
        mappings: List[ReferenceMapping],
        output_path: Path,
    ) -> Path:
        """Save reference mapping to JSON file for backup/rollback."""
        mapping_path = output_path.parent / f"{output_path.stem}_mapping.json"
        
        mapping_data = {
            "generated": datetime.now().isoformat(),
            "source_file": str(output_path.name),
            "summary": {
                "total": len(mappings),
                "processed": sum(1 for m in mappings if m.status == "processed"),
                "manual_review": sum(1 for m in mappings if m.status == "manual_review"),
                "pending": sum(1 for m in mappings if m.status == "pending"),
            },
            "mappings": [
                {
                    "original_number": m.original_number,
                    "original_text": m.original_text,
                    "new_label": m.new_label,
                    "status": m.status,
                    "citation_type": m.citation_type,
                    "pmid": m.pmid,
                    "doi": m.doi,
                    "error_reason": m.error_reason,
                }
                for m in sorted(mappings, key=lambda x: x.original_number)
            ]
        }
        
        with open(mapping_path, 'w', encoding='utf-8') as f:
            json.dump(mapping_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Mapping saved: {mapping_path}")
        return mapping_path

