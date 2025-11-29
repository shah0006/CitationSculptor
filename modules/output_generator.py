"""Output Generator Module - Generates formatted markdown output."""

import json
import re
import requests
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


# ============================================================================
# Corrections Handler - Generate and apply citation corrections
# ============================================================================

import re


@dataclass
class CorrectionEntry:
    """A single correction entry for a citation."""
    tag: str
    url: str
    current_citation: str
    missing_fields: List[str]
    new_tag: Optional[str] = None
    date: Optional[str] = None
    authors: Optional[str] = None
    organization: Optional[str] = None
    title: Optional[str] = None


class CorrectionsHandler:
    """Handles generation and application of citation corrections."""
    
    def __init__(self):
        self.corrections: List[CorrectionEntry] = []
    
    def generate_corrections_template(self, formatted_content: str, output_path: str) -> str:
        """Generate a corrections template file for citations with Null placeholders."""
        null_citations = self._find_null_citations(formatted_content)
        
        if not null_citations:
            logger.info("No citations need corrections")
            return ""
        
        template = self._build_template(null_citations)
        base_path = Path(output_path)
        corrections_path = base_path.parent / f"{base_path.stem}_corrections.md"
        with open(corrections_path, 'w', encoding='utf-8') as f:
            f.write(template)
        
        logger.info(f"Generated corrections template: {corrections_path}")
        return str(corrections_path)
    
    def _find_null_citations(self, content: str) -> List[Dict]:
        """Find all citations with Null placeholders."""
        citations = []
        pattern = r'^\[(\^[^\]]+)\]:\s*(.+?)\[Link\]\(([^)]+)\)\s*$'
        
        for line in content.split('\n'):
            match = re.match(pattern, line.strip())
            if match:
                tag = match.group(1)
                citation_text = match.group(2).strip()
                url = match.group(3)
                
                missing = []
                if 'Null_Date' in citation_text:
                    missing.append('Date')
                if 'Null_Author' in citation_text:
                    missing.append('Authors')
                if 'Null_Organization' in citation_text:
                    missing.append('Organization')
                if '-ND]' in f'[{tag}]' and 'Date' not in missing:
                    missing.append('Date')
                
                if missing:
                    citations.append({
                        'tag': f'[{tag}]',
                        'citation': citation_text,
                        'url': url,
                        'missing': missing
                    })
        
        return citations
    
    def _build_template(self, citations: List[Dict]) -> str:
        """Build the corrections template markdown."""
        lines = [
            "# Citation Corrections",
            "",
            "This file contains citations that need manual corrections.",
            "Fill in the missing information below, then run:",
            "",
            "```bash",
            'python citation_sculptor.py --apply-corrections "this_file.md" "formatted_document.md"',
            "```",
            "",
            "---",
            "",
            f"## {len(citations)} Citation(s) Need Corrections",
            "",
        ]
        
        for i, cit in enumerate(citations, 1):
            lines.extend([
                f"### {i}. {cit['tag']}",
                "",
                f"**URL**: {cit['url']}",
                "",
                f"**Current Citation**:",
                f"> {cit['citation']}",
                "",
                f"**Missing**: {', '.join(cit['missing'])}",
                "",
                "**Corrections** (fill in below):",
                "",
            ])
            
            if 'Date' in cit['missing']:
                lines.append("- Date: ")
            if 'Authors' in cit['missing']:
                lines.append("- Authors: ")
            if 'Organization' in cit['missing']:
                lines.append("- Organization: ")
            
            lines.append("- New Tag (optional): ")
            lines.append("- Title (optional): ")
            lines.extend(["", "---", ""])
        
        lines.extend([
            "",
            "## Instructions",
            "",
            "1. Open each URL and find the missing information",
            "2. Fill in the fields above (leave blank to skip)",
            "3. For **Date**, use format: YYYY or YYYY-MM-DD",
            "4. For **Authors**, use format: LastName Initials (e.g., Smith J, Jones A)",
            "5. For **New Tag**, use format: [^AuthorAB-Year]",
            "6. Save this file and run the apply command",
            "",
        ])
        
        return '\n'.join(lines)
    
    def parse_corrections_file(self, corrections_path: str) -> List[CorrectionEntry]:
        """Parse a filled-in corrections file."""
        with open(corrections_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        corrections = []
        current_entry = None
        
        for line in content.split('\n'):
            line = line.strip()
            
            tag_match = re.match(r'^###\s*\d+\.\s*(\[\^[^\]]+\])', line)
            if tag_match:
                if current_entry:
                    corrections.append(current_entry)
                current_entry = CorrectionEntry(
                    tag=tag_match.group(1),
                    url='',
                    current_citation='',
                    missing_fields=[]
                )
                continue
            
            if not current_entry:
                continue
            
            if line.startswith('**URL**:'):
                current_entry.url = line.replace('**URL**:', '').strip()
            
            if line.startswith('>'):
                current_entry.current_citation = line[1:].strip()
            
            if line.startswith('**Missing**:'):
                fields_str = line.replace('**Missing**:', '').strip()
                current_entry.missing_fields = [f.strip() for f in fields_str.split(',')]
            
            if line.startswith('- Date:'):
                value = line.replace('- Date:', '').strip()
                if value:
                    current_entry.date = value
            
            if line.startswith('- Authors:'):
                value = line.replace('- Authors:', '').strip()
                if value:
                    current_entry.authors = value
            
            if line.startswith('- Organization:'):
                value = line.replace('- Organization:', '').strip()
                if value:
                    current_entry.organization = value
            
            if line.startswith('- New Tag'):
                value = line.split(':', 1)[1].strip() if ':' in line else ''
                if value:
                    current_entry.new_tag = value
            
            if line.startswith('- Title'):
                value = line.split(':', 1)[1].strip() if ':' in line else ''
                if value:
                    current_entry.title = value
        
        if current_entry:
            corrections.append(current_entry)
        
        corrections = [c for c in corrections if c.date or c.authors or c.organization or c.new_tag or c.title]
        
        logger.info(f"Parsed {len(corrections)} correction(s) from {corrections_path}")
        return corrections
    
    def apply_corrections(self, formatted_content: str, corrections: List[CorrectionEntry]) -> tuple:
        """Apply corrections to a formatted document."""
        updated_content = formatted_content
        applied_count = 0
        
        for correction in corrections:
            pattern = re.escape(correction.tag[:-1]) + r'\]:\s*(.+?)\[Link\]\(([^)]+)\)'
            match = re.search(pattern, updated_content)
            
            if not match:
                logger.warning(f"Could not find citation for tag: {correction.tag}")
                continue
            
            original_line = match.group(0)
            citation_text = match.group(1).strip()
            url = match.group(2)
            
            new_citation = citation_text
            
            if correction.date:
                new_citation = new_citation.replace('Null_Date', correction.date)
            
            if correction.authors:
                new_citation = new_citation.replace('Null_Author.', f'{correction.authors}.')
                new_citation = new_citation.replace('Null_Author', correction.authors)
            
            new_tag = correction.new_tag if correction.new_tag else correction.tag
            new_line = f"{new_tag}: {new_citation} [Link]({url})"
            
            updated_content = updated_content.replace(original_line, new_line)
            
            if correction.new_tag and correction.new_tag != correction.tag:
                updated_content = updated_content.replace(correction.tag, correction.new_tag)
            
            applied_count += 1
            logger.info(f"Applied correction to {correction.tag}")
        
        return updated_content, applied_count
    
    def apply_corrections_to_file(self, formatted_file: str, corrections_file: str) -> tuple:
        """Apply corrections from a corrections file to a formatted document."""
        with open(formatted_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        corrections = self.parse_corrections_file(corrections_file)
        
        if not corrections:
            logger.warning("No valid corrections found in file")
            return formatted_file, 0
        
        updated_content, count = self.apply_corrections(content, corrections)
        
        with open(formatted_file, 'w', encoding='utf-8') as f:
            f.write(updated_content)
        
        logger.info(f"Applied {count} corrections to {formatted_file}")
        return formatted_file, count


# =============================================================================
# Claim Extractor - For finding verified references when originals are hallucinated
# =============================================================================

import webbrowser
from urllib.parse import quote_plus


@dataclass
class ExtractedClaim:
    """Represents an extracted claim with context and search query."""
    claim_text: str
    context: str
    citation_marker: str
    search_query: str
    keywords: List[str]
    ai_extracted: bool = False


class ClaimExtractor:
    """
    Extracts claims from document context and generates search queries.
    
    When a reference can't be verified (hallucinated), this helps find
    the claim being made and generates an optimized search query for
    SciSpace, Semantic Scholar, or PubMed.
    """
    
    SEARCH_URLS = {
        'scispace': 'https://typeset.io/search?q=',
        'semantic_scholar': 'https://www.semanticscholar.org/search?q=',
        'pubmed': 'https://pubmed.ncbi.nlm.nih.gov/?term=',
        'google_scholar': 'https://scholar.google.com/scholar?q=',
    }

    def __init__(self, use_ai: bool = True, ai_endpoint: str = None):
        """
        Initialize the claim extractor.
        
        Args:
            use_ai: Whether to use AI for better claim extraction
            ai_endpoint: Custom AI endpoint URL (e.g., local LLM)
        """
        self.use_ai = use_ai
        self.ai_endpoint = ai_endpoint or "http://localhost:11434/api/generate"  # Default: Ollama

    def extract_context(self, full_text: str, citation_marker: str, 
                       chars_before: int = 500, chars_after: int = 200) -> str:
        """Extract context around a citation marker."""
        escaped = re.escape(citation_marker)
        match = re.search(escaped, full_text)
        
        if not match:
            logger.warning(f"Citation marker '{citation_marker}' not found")
            return ""
        
        start = max(0, match.start() - chars_before)
        end = min(len(full_text), match.end() + chars_after)
        
        context = full_text[start:end]
        
        # Try to align to sentence boundaries
        first_period = context.find('. ')
        if first_period > 0 and first_period < len(context) // 4:
            context = context[first_period + 2:]
        
        last_period = context.rfind('. ')
        if last_period > len(context) * 3 // 4:
            context = context[:last_period + 1]
        
        return context.strip()

    def extract_claim_with_ai(self, context: str, original_ref: str = "") -> str:
        """
        Use AI to extract the specific claim being made.
        
        This calls a local LLM (Ollama) or custom endpoint to understand
        the context and extract the precise claim.
        """
        prompt = f"""You are a medical research assistant. Extract the specific factual claim being made in this text that needs a citation.

Context around the citation:
"{context}"

Original reference (possibly incorrect/hallucinated):
"{original_ref}"

Instructions:
1. Identify the specific medical/scientific claim being made
2. Express it as a concise, searchable statement
3. Include key medical terms, conditions, treatments, or outcomes
4. Output ONLY the claim, nothing else

Claim:"""

        try:
            # Try Ollama first (local LLM)
            response = requests.post(
                self.ai_endpoint,
                json={
                    "model": "llama3.2",  # or mistral, etc.
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.1}
                },
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                claim = result.get('response', '').strip()
                if claim:
                    logger.info(f"AI extracted claim: {claim[:100]}...")
                    return claim
        except Exception as e:
            logger.debug(f"AI extraction failed: {e}")
        
        # Fallback to heuristic extraction
        return self._extract_claim_heuristic(context)

    def _extract_claim_heuristic(self, context: str) -> str:
        """Fallback heuristic claim extraction without AI."""
        # Remove markdown formatting
        text = re.sub(r'\*\*([^*]+)\*\*', r'\1', context)
        text = re.sub(r'\*([^*]+)\*', r'\1', text)
        text = re.sub(r'\[\^[^\]]+\]', '', text)  # Remove citation markers
        text = re.sub(r'\[\d+\]', '', text)
        
        # Get sentences
        sentences = re.split(r'(?<=[.!?])\s+', text)
        
        # Find the most substantive sentence (likely the claim)
        best_sentence = ""
        best_score = 0
        
        medical_terms = {'treatment', 'therapy', 'risk', 'outcome', 'effect', 
                        'increase', 'decrease', 'cause', 'associate', 'patient',
                        'study', 'trial', 'significant', 'mortality', 'morbidity'}
        
        for sent in sentences:
            words = sent.lower().split()
            score = sum(1 for w in words if w in medical_terms)
            score += len(sent) / 100  # Prefer longer sentences
            
            if score > best_score:
                best_score = score
                best_sentence = sent
        
        return best_sentence.strip()

    def generate_scispace_query(self, claim: str, original_title: str = "") -> str:
        """
        Generate an excellent SciSpace search query from the claim.
        
        SciSpace works best with natural language research queries.
        """
        if self.use_ai:
            return self._generate_query_with_ai(claim, original_title)
        else:
            return self._generate_query_heuristic(claim, original_title)

    def _generate_query_with_ai(self, claim: str, original_title: str = "") -> str:
        """Use AI to generate an optimal search query."""
        prompt = f"""You are a medical librarian. Create an optimal search query to find peer-reviewed papers supporting this claim.

Claim: "{claim}"
Original reference title (possibly wrong): "{original_title}"

Instructions:
1. Create a focused search query using key medical/scientific terms
2. Use natural language that works well with SciSpace
3. Include condition names, treatments, outcomes, or mechanisms
4. Keep it to 5-10 words maximum
5. Output ONLY the search query, nothing else

Search query:"""

        try:
            response = requests.post(
                self.ai_endpoint,
                json={
                    "model": "llama3.2",
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.1}
                },
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                query = result.get('response', '').strip()
                # Clean up - remove quotes if present
                query = query.strip('"\'')
                if query and len(query) < 200:
                    logger.info(f"AI generated query: {query}")
                    return query
        except Exception as e:
            logger.debug(f"AI query generation failed: {e}")
        
        return self._generate_query_heuristic(claim, original_title)

    def _generate_query_heuristic(self, claim: str, original_title: str = "") -> str:
        """Fallback heuristic query generation."""
        # Extract key terms
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to',
                     'for', 'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be',
                     'have', 'has', 'had', 'this', 'that', 'these', 'those', 'it'}
        
        text = f"{claim} {original_title}".lower()
        words = re.findall(r'\b[a-zA-Z]{4,}\b', text)
        keywords = [w for w in words if w not in stop_words]
        
        # Remove duplicates while preserving order
        seen = set()
        unique_keywords = []
        for kw in keywords:
            if kw not in seen:
                seen.add(kw)
                unique_keywords.append(kw)
        
        return ' '.join(unique_keywords[:8])

    def open_search(self, query: str, service: str = 'scispace') -> bool:
        """Open search in browser."""
        if service not in self.SEARCH_URLS:
            service = 'scispace'
        
        url = self.SEARCH_URLS[service] + quote_plus(query)
        
        try:
            webbrowser.open(url)
            logger.info(f"Opened {service}: {query[:50]}...")
            return True
        except Exception as e:
            logger.error(f"Failed to open browser: {e}")
            return False

    def find_verified_reference(self, full_text: str, citation_marker: str,
                                original_ref: str = "", service: str = 'scispace') -> ExtractedClaim:
        """
        Complete workflow: extract claim, generate query, open search.
        
        Args:
            full_text: The full document text
            citation_marker: The citation marker (e.g., "[^1]")
            original_ref: Original reference text (possibly hallucinated)
            service: Which search service to use
            
        Returns:
            ExtractedClaim with the extracted info
        """
        # Extract context
        context = self.extract_context(full_text, citation_marker)
        
        # Extract claim (with AI if available)
        if self.use_ai:
            claim = self.extract_claim_with_ai(context, original_ref)
            ai_used = True
        else:
            claim = self._extract_claim_heuristic(context)
            ai_used = False
        
        # Generate search query
        query = self.generate_scispace_query(claim, original_ref)
        
        # Extract keywords for reference
        keywords = re.findall(r'\b[a-zA-Z]{4,}\b', query.lower())
        
        result = ExtractedClaim(
            claim_text=claim,
            context=context,
            citation_marker=citation_marker,
            search_query=query,
            keywords=keywords[:10],
            ai_extracted=ai_used
        )
        
        # Open browser search
        self.open_search(query, service)
        
        return result