# CitationSculptor Continuation Prompt

> ## ✅ STATUS: COMPLETE (v2.4.1 Released Jan 13, 2026)
>
> All tasks in this prompt have been implemented, tested, and documented.
> See CHANGELOG.md for full release notes.

## ~~🚨 CRITICAL: v2.4.0 Improvement Sprint Required~~

**Status:** ✅ v2.4.1 COMPLETE  
**Released:** Jan 13, 2026  
**Result:** All critical usability issues fixed, 471+ tests passing

---

## ✅ Implementation Summary

All issues identified have been resolved:

| Issue | Status | Solution |
|-------|--------|----------|
| File not saved after processing | ✅ Fixed | `save_to_file` parameter in `citation_process_document` |
| No duplicate detection | ✅ Fixed | `citation_find_duplicates` tool + `citation_integrity_checker.py` |
| No context verification | ✅ Fixed | `citation_verify_context` tool + `citation_context_verifier.py` |
| No comprehensive audit | ✅ Fixed | `citation_audit_document` tool |
| Security vulnerability | ✅ Fixed | Path traversal protection in backup restore |

### Algorithm Enhancements (v2.4.1)
- **IDF-Weighted Inclusion Coefficient**: Generic terms contribute less, specific terms more
- **Keyphrase Extraction**: Captures multi-word concepts ("cardiac amyloidosis")
- **Conservative Lemmatization**: Reduces word variants while protecting technical terms

### Feature Parity Achieved
All tools accessible via:
- MCP Server (stdio transport)
- HTTP API endpoints
- CLI flags
- Web UI (Document Intelligence section)

---

## 📋 Original Executive Summary (Archived)

During a recent document processing session, the following critical issues were discovered that required **15+ manual citation corrections**:

1. ✅ **No context-aware citation verification** - Fixed with IDF-weighted keyword matching
2. ✅ **No duplicate detection** - Fixed with integrity checker module
3. ✅ **File not saved after processing** - Fixed with `save_to_file` parameter
4. ✅ **No comprehensive audit capability** - Fixed with audit tool

**See:** `docs/IMPROVEMENT_PLAN_v2.4.md` for full analysis with examples.

---

## 🎯 Implementation Tasks (In Priority Order)

### Task 1: Fix File Save Bug in `citation_process_document` (P0 - CRITICAL)

**File:** `mcp_server/server.py`  
**Function:** `process_document_content()`  
**Line ~628-807**

**Current Behavior (Bug):**
```python
# Returns processed content wrapped in markdown code block
# NEVER writes to file, just returns
return "\n".join(output_lines)
```

**Required Fix:**
```python
import json  # ADD THIS IMPORT at top of file

def process_document_content(file_path: Optional[str], content: Optional[str], 
                             style: str = 'vancouver', create_backup_file: bool = True,
                             save_to_file: bool = True) -> str:  # Add save_to_file param
    """
    Process markdown document and optionally save back to file.
    
    Args:
        file_path: Path to markdown file
        content: Markdown content (alternative to file_path)
        style: Citation style (vancouver, apa, mla, chicago, harvard, ieee)
        create_backup_file: Create backup before processing (default True)
        save_to_file: Write processed content back to file (default True)
    
    Returns:
        JSON string with results and statistics
    """
    saved_to = None  # Initialize before use
    
    # ... existing processing code ...
    
    # After processing, SAVE to file if file_path was provided
    if file_path and save_to_file:
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(processed_content)
            saved_to = file_path
        except Exception as e:
            saved_to = None
            # Log error but don't fail - content is still available
            logger.error(f"Failed to save file: {e}")
    
    # Return JSON-style result, NOT markdown code block
    return json.dumps({
        "success": True,
        "saved_to": saved_to,
        "backup_path": backup_path,
        "stats": {
            "total_references": len(parser.references),
            "processed": len(processed_citations),
            "failed": len(failed_refs),
            "inline_replacements": replacements_made
        },
        "failed_refs": failed_refs,
        "processed_content": processed_content  # Include for when save_to_file=False
    })
```

**Test Case to Add:**
```python
# tests/test_process_document_save.py
import json
import os
import tempfile
import pytest

# Import from the mcp_server module
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from mcp_server.server import process_document_content


class TestProcessDocumentSave:
    """Test suite for file save functionality in process_document_content."""
    
    def test_save_to_file_true_writes_file(self):
        """Verify save_to_file=True actually writes to file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write("Test content with [^1] citation.\n\n## References\n\n[^1]: Test reference text")
            temp_path = f.name
        
        try:
            result = process_document_content(temp_path, None, save_to_file=True)
            result_dict = json.loads(result)
            
            assert result_dict['success'], "Processing should succeed"
            assert result_dict['saved_to'] == temp_path, "Should report saved file path"
            
            # Verify file was actually modified
            with open(temp_path, 'r', encoding='utf-8') as f:
                content = f.read()
            assert '[^' in content, "File should contain footnote markers"
        finally:
            os.unlink(temp_path)
    
    def test_save_to_file_false_does_not_modify(self):
        """Verify save_to_file=False returns content but doesn't modify file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            original_content = "Test [^1].\n\n## References\n\n[^1]: Original ref"
            f.write(original_content)
            temp_path = f.name
        
        original_mtime = os.path.getmtime(temp_path)
        
        try:
            result = process_document_content(temp_path, None, save_to_file=False)
            result_dict = json.loads(result)
            
            assert result_dict['saved_to'] is None, "Should not report saved path"
            assert result_dict['processed_content'], "Should return processed content"
            
            # Verify file was NOT modified
            assert os.path.getmtime(temp_path) == original_mtime
        finally:
            os.unlink(temp_path)
    
    def test_backup_created_before_save(self):
        """Verify backup is created BEFORE modifying original file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write("Test [^1].\n\n## References\n\n[^1]: Test ref")
            temp_path = f.name
        
        try:
            result = process_document_content(temp_path, None, save_to_file=True, create_backup_file=True)
            result_dict = json.loads(result)
            
            assert result_dict['backup_path'], "Backup path should be returned"
            assert os.path.exists(result_dict['backup_path']), "Backup file should exist"
        finally:
            os.unlink(temp_path)
            if result_dict.get('backup_path') and os.path.exists(result_dict['backup_path']):
                os.unlink(result_dict['backup_path'])
```

---

### Task 2: Add Duplicate Citation Detection (P0 - HIGH VALUE)

**New File:** `modules/duplicate_citation_detector.py`

This is a **domain-agnostic** module that works on ANY document type.

```python
"""
Duplicate Citation Detector Module

Detects and fixes citation integrity issues in ANY document type:
- Same-citation duplicates: [^A][^A] → [^A]
- Orphaned definitions: defined but never used inline
- Missing definitions: used inline but never defined

This module is DOMAIN-AGNOSTIC - works on medical, legal, engineering,
humanities, or any other document type.
"""

import re
from dataclasses import dataclass, field
from typing import List, Set, Tuple, Optional
from loguru import logger


@dataclass
class DuplicateReport:
    """Complete report of citation integrity issues."""
    same_citation_duplicates: List[Tuple[int, str, str]] = field(default_factory=list)
    orphaned_definitions: List[str] = field(default_factory=list)
    missing_definitions: List[str] = field(default_factory=list)
    
    @property
    def total_issues(self) -> int:
        return (len(self.same_citation_duplicates) + 
                len(self.orphaned_definitions) + 
                len(self.missing_definitions))
    
    @property
    def is_clean(self) -> bool:
        return self.total_issues == 0


class DuplicateCitationDetector:
    """
    Detect and fix duplicate/orphan citations in markdown documents.
    
    Works on ANY document type - medical, legal, engineering, humanities, etc.
    """
    
    # Semantic citation pattern [^Author-Year-ID] or [^Any-Tag]
    CITATION_INLINE_PATTERN = r'\[\^[A-Za-z][^\]]+\]'
    
    # Definition pattern [^Tag]: content
    DEFINITION_PATTERN = r'^\[\^([^\]]+)\]:'
    
    # Consecutive same citations [^A][^A] or [^A] [^A]
    CONSECUTIVE_SAME_PATTERN = r'(\[\^[A-Za-z][^\]]+\])(\s*)\1'
    
    def __init__(self):
        self._last_report: Optional[DuplicateReport] = None
    
    def analyze(self, content: str) -> DuplicateReport:
        """
        Analyze document for citation integrity issues.
        
        Args:
            content: Full markdown document content (any domain)
            
        Returns:
            DuplicateReport with all issues found
        """
        logger.info("Analyzing document for citation duplicates and orphans")
        
        lines = content.split('\n')
        
        # Extract all inline citations (excluding reference section)
        inline_citations = self._extract_inline_citations(lines)
        
        # Extract all definitions
        definitions = self._extract_definitions(lines)
        
        # Find consecutive same citations
        same_duplicates = self._find_same_citation_duplicates(lines)
        
        # Find orphaned definitions (defined but not used)
        orphaned = definitions - inline_citations
        
        # Find missing definitions (used but not defined)
        missing = inline_citations - definitions
        
        report = DuplicateReport(
            same_citation_duplicates=same_duplicates,
            orphaned_definitions=sorted(list(orphaned)),
            missing_definitions=sorted(list(missing))
        )
        
        self._last_report = report
        
        logger.info(f"Analysis complete: {report.total_issues} issues found")
        return report
    
    def _extract_inline_citations(self, lines: List[str]) -> Set[str]:
        """Extract all inline citation tags, excluding the reference section."""
        citations: Set[str] = set()
        in_ref_section = False
        
        for line in lines:
            # Detect reference section start (multiple heading formats)
            if re.match(r'^#{1,3}\s*(References|Bibliography|Citations|Works Cited|Sources)', line, re.I):
                in_ref_section = True
                continue
            
            if in_ref_section:
                continue
            
            for match in re.finditer(self.CITATION_INLINE_PATTERN, line):
                citations.add(match.group(0))
        
        return citations
    
    def _extract_definitions(self, lines: List[str]) -> Set[str]:
        """Extract all citation definition tags."""
        definitions: Set[str] = set()
        
        for line in lines:
            match = re.match(self.DEFINITION_PATTERN, line)
            if match:
                tag = f"[^{match.group(1)}]"
                definitions.add(tag)
        
        return definitions
    
    def _find_same_citation_duplicates(self, lines: List[str]) -> List[Tuple[int, str, str]]:
        """Find consecutive same-citation duplicates."""
        duplicates = []
        
        for i, line in enumerate(lines, 1):
            for match in re.finditer(self.CONSECUTIVE_SAME_PATTERN, line):
                original = match.group(0)
                fixed = match.group(1)
                duplicates.append((i, original, fixed))
        
        return duplicates
    
    def fix_duplicates(self, content: str) -> Tuple[str, int]:
        """
        Remove consecutive same-citation duplicates.
        
        Args:
            content: Document content
            
        Returns:
            Tuple of (fixed_content, number_of_fixes)
        """
        fixes = 0
        result = content
        
        while True:
            new_content = re.sub(
                self.CONSECUTIVE_SAME_PATTERN,
                r'\1',
                result
            )
            if new_content == result:
                break
            result = new_content
            fixes += 1
        
        if fixes > 0:
            logger.info(f"Fixed {fixes} same-citation duplicates")
        
        return result, fixes
```

**Add MCP Tool in `mcp_server/server.py`:**
```python
Tool(
    name="citation_find_duplicates",
    description="Find and optionally fix duplicate citations: same citations appearing consecutively [^A][^A], orphaned definitions (defined but unused), missing definitions (used but undefined). Works on any document type.",
    inputSchema={
        "type": "object",
        "properties": {
            "file_path": {"type": "string", "description": "Path to markdown file"},
            "content": {"type": "string", "description": "Markdown content (alternative)"},
            "auto_fix": {"type": "boolean", "description": "Automatically fix duplicates", "default": False}
        }
    }
)
```

**Handler for `citation_find_duplicates`:**
```python
def handle_find_duplicates(file_path: str = None, content: str = None, auto_fix: bool = False) -> str:
    """Handle citation_find_duplicates MCP tool calls."""
    text_content, error = get_content(file_path, content)
    if error:
        return error
    
    from modules.duplicate_citation_detector import DuplicateCitationDetector
    detector = DuplicateCitationDetector()
    
    # Always analyze first
    report = detector.analyze(text_content)
    
    output = ["# Duplicate Citation Report", ""]
    
    if report.is_clean:
        output.append("✅ No duplicate or orphan issues found.")
        return "\n".join(output)
    
    # Report issues
    if report.same_citation_duplicates:
        output.append(f"## ❌ Same-Citation Duplicates ({len(report.same_citation_duplicates)})")
        for line, orig, fix in report.same_citation_duplicates:
            output.append(f"- Line {line}: `{orig}` → `{fix}`")
        output.append("")
    
    if report.orphaned_definitions:
        output.append(f"## ⚠️ Orphaned Definitions ({len(report.orphaned_definitions)})")
        for orphan in report.orphaned_definitions:
            output.append(f"- {orphan}")
        output.append("")
    
    if report.missing_definitions:
        output.append(f"## ❌ Missing Definitions ({len(report.missing_definitions)})")
        for missing in report.missing_definitions:
            output.append(f"- {missing}")
        output.append("")
    
    # Auto-fix if requested (fixes same-citation duplicates only)
    if auto_fix and report.same_citation_duplicates:
        # NOTE: fix_duplicates() takes only content, no auto_fix param
        fixed_content, fixes_applied = detector.fix_duplicates(text_content)
        output.append(f"## ✅ Auto-Fixed: {fixes_applied} duplicates removed")
        
        # Save back to file if file_path provided
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(fixed_content)
                output.append(f"- Saved to: `{file_path}`")
            except Exception as e:
                output.append(f"- ⚠️ Could not save: {e}")
    
    return "\n".join(output)
```

---

### Task 3: Add Context-Aware Citation Verification (P1 - HIGH IMPACT)

**⚠️ CRITICAL: This must be DOMAIN-AGNOSTIC**

**New File:** `modules/citation_context_verifier.py`

The context verifier must work on ANY document type by using **dynamic keyword extraction** from the citations themselves, NOT hardcoded topic lists.

```python
"""
Citation Context Verifier Module

Verifies that citations match their surrounding text context using
DYNAMIC keyword extraction - NO hardcoded domain-specific keywords.

This module works on ANY document type:
- Medical/Clinical papers
- Engineering documents
- Legal briefs
- Historical research
- Business reports
- Computer science papers
- Any scholarly or professional document

The approach:
1. Extract significant words from citation definition (title, abstract, etc.)
2. Extract significant words from surrounding text
3. Calculate keyword overlap/similarity score
4. Flag low-overlap as potential mismatches
"""

import re
import string
from collections import Counter
from dataclasses import dataclass
from typing import List, Set, Tuple, Optional
from loguru import logger


@dataclass
class ContextMismatch:
    """A citation that may not match its surrounding context."""
    line_number: int
    citation_tag: str
    surrounding_text: str
    citation_keywords: List[str]
    context_keywords: List[str]
    overlap_score: float  # 0-1, higher = better match
    confidence: float  # Confidence this is actually a mismatch


# Common stopwords to exclude (language-agnostic basics)
STOPWORDS = {
    # English
    'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
    'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are', 'were', 'been',
    'be', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
    'should', 'may', 'might', 'must', 'shall', 'can', 'this', 'that', 'these',
    'those', 'it', 'its', 'they', 'them', 'their', 'we', 'our', 'you', 'your',
    'he', 'she', 'him', 'her', 'his', 'i', 'me', 'my', 'not', 'no', 'yes',
    'all', 'any', 'some', 'each', 'every', 'both', 'few', 'more', 'most',
    'other', 'into', 'through', 'during', 'before', 'after', 'above', 'below',
    'between', 'under', 'again', 'further', 'then', 'once', 'here', 'there',
    'when', 'where', 'why', 'how', 'what', 'which', 'who', 'whom', 'whose',
    'if', 'than', 'so', 'such', 'only', 'also', 'just', 'about', 'over',
    # Common citation/reference words to ignore
    'et', 'al', 'doi', 'pmid', 'vol', 'pp', 'ed', 'eds', 'available', 'accessed',
    'retrieved', 'http', 'https', 'www', 'org', 'com', 'edu', 'gov',
}


class CitationContextVerifier:
    """
    Verify citations match their surrounding text context.
    
    Uses DYNAMIC keyword extraction - works on ANY domain.
    Does NOT use hardcoded topic lists.
    """
    
    def __init__(self, min_word_length: int = 3, top_keywords: int = 15):
        """
        Initialize verifier.
        
        Args:
            min_word_length: Minimum word length to consider as keyword
            top_keywords: Number of top keywords to extract per text
        """
        self.min_word_length = min_word_length
        self.top_keywords = top_keywords
    
    def extract_keywords(self, text: str) -> List[str]:
        """
        Extract significant keywords from text.
        
        Uses frequency-based extraction with stopword removal.
        Works on any language/domain.
        
        Args:
            text: Any text to extract keywords from
            
        Returns:
            List of significant keywords (lowercase)
        """
        if not text:
            return []
        
        # Lowercase and remove punctuation
        text = text.lower()
        text = text.translate(str.maketrans('', '', string.punctuation))
        
        # Split into words
        words = text.split()
        
        # Filter: remove stopwords, short words, and numbers
        filtered = [
            w for w in words
            if w not in STOPWORDS
            and len(w) >= self.min_word_length
            and not w.isdigit()
            and not re.match(r'^\d', w)  # Doesn't start with digit
        ]
        
        # Count frequencies
        word_counts = Counter(filtered)
        
        # Return top keywords
        return [word for word, _ in word_counts.most_common(self.top_keywords)]
    
    def calculate_overlap_score(
        self, keywords1: List[str], keywords2: List[str]
    ) -> float:
        """
        Calculate keyword overlap score between two keyword lists.
        
        Returns:
            Float 0-1, where 1 = perfect overlap, 0 = no overlap
        """
        if not keywords1 or not keywords2:
            return 0.0
        
        set1 = set(keywords1)
        set2 = set(keywords2)
        
        intersection = len(set1 & set2)
        union = len(set1 | set2)
        
        if union == 0:
            return 0.0
        
        # Jaccard similarity
        return intersection / union
    
    def extract_citation_contexts(
        self, content: str, context_lines: int = 3
    ) -> List[Tuple[int, str, str]]:
        """
        Extract each inline citation with surrounding context.
        
        Args:
            content: Full document content
            context_lines: Number of lines before/after to include
            
        Returns:
            List of (line_number, citation_tag, context_text)
        """
        lines = content.split('\n')
        contexts = []
        
        # Find where references section starts
        ref_start = len(lines)
        for i, line in enumerate(lines):
            if re.match(r'^#{1,3}\s*(References|Bibliography|Citations|Works Cited|Sources)', line, re.I):
                ref_start = i
                break
        
        body_lines = lines[:ref_start]
        
        for i, line in enumerate(body_lines):
            for match in re.finditer(r'\[\^([A-Za-z][^\]]+)\]', line):
                tag = f"[^{match.group(1)}]"
                
                start = max(0, i - context_lines)
                end = min(len(body_lines), i + context_lines + 1)
                context = ' '.join(body_lines[start:end]).strip()
                
                contexts.append((i + 1, tag, context))
        
        return contexts
    
    def get_citation_definition(self, tag: str, content: str) -> Optional[str]:
        """Get the full definition text for a citation tag."""
        escaped_tag = re.escape(tag)
        pattern = escaped_tag + r':\s*(.+?)(?=\n\[\^|\n\n|\Z)'
        
        match = re.search(pattern, content, re.DOTALL)
        return match.group(1).strip() if match else None
    
    def verify_citations(
        self, content: str, threshold: float = 0.1
    ) -> List[ContextMismatch]:
        """
        Verify all citations match their context using keyword overlap.
        
        Args:
            content: Full document content (any domain)
            threshold: Minimum overlap score (below this = potential mismatch)
            
        Returns:
            List of potential mismatches below threshold
        """
        logger.info("Verifying citation contexts (domain-agnostic)")
        mismatches = []
        
        contexts = self.extract_citation_contexts(content)
        logger.debug(f"Found {len(contexts)} citations to verify")
        
        for line_num, tag, surrounding_text in contexts:
            # Get citation definition
            definition = self.get_citation_definition(tag, content)
            if not definition:
                continue
            
            # Extract keywords from both
            citation_keywords = self.extract_keywords(definition)
            context_keywords = self.extract_keywords(surrounding_text)
            
            # Calculate overlap
            overlap = self.calculate_overlap_score(citation_keywords, context_keywords)
            
            # Flag if below threshold
            if overlap < threshold and citation_keywords and context_keywords:
                confidence = 1.0 - overlap  # Higher confidence when lower overlap
                
                mismatch = ContextMismatch(
                    line_number=line_num,
                    citation_tag=tag,
                    surrounding_text=surrounding_text[:200],
                    citation_keywords=citation_keywords[:5],
                    context_keywords=context_keywords[:5],
                    overlap_score=overlap,
                    confidence=confidence
                )
                mismatches.append(mismatch)
                logger.debug(
                    f"Potential mismatch at line {line_num}: "
                    f"{tag} (overlap: {overlap:.2f})"
                )
        
        logger.info(f"Context verification complete: {len(mismatches)} potential mismatches")
        return mismatches
    
    def format_mismatch_report(self, mismatches: List[ContextMismatch]) -> str:
        """Format mismatches into a readable report."""
        if not mismatches:
            return "✅ All citations appear to match their context."
        
        lines = [
            f"## ⚠️ Potential Context Mismatches ({len(mismatches)} found)",
            "",
            "These citations have low keyword overlap with their surrounding text.",
            "Review manually to confirm they are appropriate for the context.",
            "",
        ]
        
        for m in mismatches:
            lines.extend([
                f"**Line {m.line_number}**: `{m.citation_tag}`",
                f"- Overlap score: **{m.overlap_score:.1%}** (low)",
                f"- Citation keywords: {', '.join(m.citation_keywords)}",
                f"- Context keywords: {', '.join(m.context_keywords)}",
                f"- Context: \"{m.surrounding_text[:100]}...\"",
                "",
            ])
        
        return "\n".join(lines)
```

**Add MCP Tool:**
```python
Tool(
    name="citation_verify_context",
    description="Verify each citation's keywords match its surrounding text context using dynamic keyword extraction. Works on ANY document type (medical, legal, engineering, humanities, etc.). Flags citations with low keyword overlap.",
    inputSchema={
        "type": "object",
        "properties": {
            "file_path": {"type": "string"},
            "content": {"type": "string"},
            "threshold": {"type": "number", "default": 0.1, "description": "Minimum overlap score (0-1). Below this = potential mismatch."}
        }
    }
)
```

---

### Task 4: Add Comprehensive Audit Tool (P1)

**Add to `mcp_server/server.py`:**

```python
Tool(
    name="citation_audit_document",
    description="Comprehensive citation audit for ANY document type: check for duplicates, orphans, missing definitions, and context mismatches. Returns health score and actionable fixes.",
    inputSchema={
        "type": "object",
        "properties": {
            "file_path": {"type": "string"},
            "content": {"type": "string"},
            "auto_fix_duplicates": {"type": "boolean", "default": False}
        }
    }
)
```

**Handler:**
```python
def handle_audit_document(file_path, content, auto_fix_duplicates=False):
    text_content, error = get_content(file_path, content)
    if error:
        return error
    
    from modules.duplicate_citation_detector import DuplicateCitationDetector
    from modules.citation_context_verifier import CitationContextVerifier
    
    dup_detector = DuplicateCitationDetector()
    context_verifier = CitationContextVerifier()
    
    # Duplicate analysis
    dup_report = dup_detector.analyze(text_content)
    
    # Context verification
    mismatches = context_verifier.verify_citations(text_content)
    
    # Calculate health score
    total_issues = dup_report.total_issues + len(mismatches)
    health_score = max(0, 100 - (total_issues * 5))
    
    # Auto-fix if requested
    fixed_content = text_content
    fixes_applied = 0
    if auto_fix_duplicates:
        fixed_content, fixes_applied = dup_detector.fix_duplicates(text_content)
    
    # Build output
    output = [
        "# 📊 Citation Audit Report",
        "",
        f"## Health Score: {health_score}/100",
        "",
        "## Summary",
        f"- Same-citation duplicates: {len(dup_report.same_citation_duplicates)}",
        f"- Orphaned definitions: {len(dup_report.orphaned_definitions)}",
        f"- Missing definitions: {len(dup_report.missing_definitions)}",
        f"- Context mismatches: {len(mismatches)}",
        "",
    ]
    
    if dup_report.same_citation_duplicates:
        output.append("## ❌ Same-Citation Duplicates")
        for line, orig, fix in dup_report.same_citation_duplicates:
            output.append(f"- Line {line}: `{orig}` → `{fix}`")
        output.append("")
    
    if dup_report.orphaned_definitions:
        output.append("## ⚠️ Orphaned Definitions (defined but never used)")
        for orphan in dup_report.orphaned_definitions[:10]:
            output.append(f"- {orphan}")
        if len(dup_report.orphaned_definitions) > 10:
            output.append(f"- ... and {len(dup_report.orphaned_definitions) - 10} more")
        output.append("")
    
    if dup_report.missing_definitions:
        output.append("## ❌ Missing Definitions (used but never defined)")
        for missing in dup_report.missing_definitions[:10]:
            output.append(f"- {missing}")
        if len(dup_report.missing_definitions) > 10:
            output.append(f"- ... and {len(dup_report.missing_definitions) - 10} more")
        output.append("")
    
    if mismatches:
        output.append(context_verifier.format_mismatch_report(mismatches))
    
    if fixes_applied:
        output.append(f"## ✅ Auto-Fixes Applied: {fixes_applied}")
    
    return "\n".join(output)
```

---

### Task 5: Integration into `citation_process_document` (P1)

After implementing Tasks 2-4, integrate them into the main processing flow:

```python
def process_document_content(...):
    # ... existing code up to where content is loaded ...
    
    # NEW: Run duplicate detection FIRST (before normalization)
    from modules.duplicate_citation_detector import DuplicateCitationDetector
    dup_detector = DuplicateCitationDetector()
    
    # fix_duplicates returns (fixed_content, number_of_fixes)
    # NOTE: No auto_fix parameter - it always fixes when called
    content, dup_fixes = dup_detector.fix_duplicates(content)
    
    # ... continue with existing normalization and processing ...
    
    # NEW: After processing, verify context matches
    from modules.citation_context_verifier import CitationContextVerifier
    verifier = CitationContextVerifier()
    mismatches = verifier.verify_citations(processed_content)
    
    # Add mismatches to output (warnings, not errors)
    if mismatches:
        output_lines.extend([
            "## ⚠️ Review Suggested: Potential Context Mismatches",
            "The following citations have low keyword overlap with their text.",
            "This may be fine - please review manually:",
            ""
        ])
        for m in mismatches[:10]:
            output_lines.append(
                f"- Line {m.line_number}: {m.citation_tag} "
                f"(overlap: {m.overlap_score:.0%})"
            )
        if len(mismatches) > 10:
            output_lines.append(f"- ... and {len(mismatches) - 10} more")
    
    # Add duplicate fix stats to output if any were fixed
    if dup_fixes > 0:
        output_lines.extend([
            f"## 🔄 Duplicate Citations Removed: {dup_fixes}",
            ""
        ])
```

---

## 🧪 Test Plan

### New Test Files to Create:

1. `tests/test_duplicate_citation_detector.py` - 15+ tests
2. `tests/test_citation_context_verifier.py` - 20+ tests  
3. `tests/test_citation_audit.py` - 10+ tests
4. `tests/test_process_document_save.py` - 10+ tests

### Critical: Domain-Agnostic Test Cases

**Include tests with different document types:**

```python
# Medical document
medical_doc = """
Treatment with aspirin reduces cardiovascular events.[^SmithJ-2024]

## References
[^SmithJ-2024]: Smith J. Aspirin therapy in cardiovascular disease. Cardiology. 2024.
"""

# Legal document  
legal_doc = """
The court's interpretation of habeas corpus was precedent-setting.[^JonesA-2023]

## References
[^JonesA-2023]: Jones A. Constitutional law interpretations. Law Review. 2023.
"""

# Engineering document
engineering_doc = """
The tensile strength of the alloy exceeded specifications.[^BrownK-2024]

## References
[^BrownK-2024]: Brown K. Advanced materials testing. Engineering Journal. 2024.
"""

# Test that all three work identically
def test_works_on_medical_docs():
    detector = DuplicateCitationDetector()
    report = detector.analyze(medical_doc)
    assert report.is_clean

def test_works_on_legal_docs():
    detector = DuplicateCitationDetector()
    report = detector.analyze(legal_doc)
    assert report.is_clean

def test_works_on_engineering_docs():
    detector = DuplicateCitationDetector()
    report = detector.analyze(engineering_doc)
    assert report.is_clean
```

### Regression Tests:
- Run all existing 398 tests (`pytest tests/ -v`)
- Verify no existing functionality broken
- Current baseline: 398 tests collected

---

## 📁 File Locations

```
CitationSculptor/
├── docs/
│   └── IMPROVEMENT_PLAN_v2.4.md      # Detailed problem analysis
├── modules/
│   ├── duplicate_citation_detector.py  # NEW: Task 2 (domain-agnostic)
│   └── citation_context_verifier.py    # NEW: Task 3 (domain-agnostic)
├── mcp_server/
│   └── server.py                        # MODIFY: Tasks 1, 4, 5
├── tests/
│   ├── test_duplicate_citation_detector.py  # NEW
│   ├── test_citation_context_verifier.py    # NEW (with multi-domain tests)
│   ├── test_citation_audit.py               # NEW
│   └── test_process_document_save.py        # NEW
├── PLANNING.md                          # UPDATE: Add v2.4 roadmap
└── CONTINUATION_PROMPT.md               # THIS FILE
```

---

## ⚡ Quick Start for Implementing Agent

```bash
cd /Users/tusharshah/Developer/MCP-Servers/CitationSculptor
source .venv/bin/activate

# Run existing tests first to establish baseline
.venv/bin/python -m pytest tests/ -v --tb=short

# Implement Task 1 (file save fix)
# Then run tests again

# Implement Task 2 (duplicate detection - domain-agnostic)
# Create tests/test_duplicate_citation_detector.py
# Include multi-domain test cases
# Run new tests

# Continue with Tasks 3, 4, 5...
```

---

## 🔗 Related Documents

- `docs/IMPROVEMENT_PLAN_v2.4.md` - Full problem analysis with examples
- `docs/ARCHITECTURE.md` - System architecture
- `docs/TESTING.md` - Testing guide
- `PLANNING.md` - Overall roadmap
- `CHANGELOG.md` - Version history

---

## ✅ Definition of Done

v2.4.0 is complete when:

1. [ ] `citation_process_document` saves files directly (with backup)
2. [ ] `citation_find_duplicates` tool detects and fixes `[^A][^A]` patterns
3. [ ] `citation_verify_context` tool uses DYNAMIC keyword extraction (no hardcoded topics)
4. [ ] `citation_audit_document` tool provides comprehensive health check
5. [ ] All new features work on ANY document type (medical, legal, engineering, etc.)
6. [ ] All new features have 90%+ test coverage INCLUDING multi-domain tests
7. [ ] All existing 398 tests still pass
8. [ ] Documentation updated (README, PLANNING, CHANGELOG)

---

## ⚠️ Critical Reminders for Implementing Agent

1. **DO NOT hardcode domain-specific keywords** - use dynamic extraction
2. **Test with multiple document types** - not just medical
3. **The example document was medical, but the tool is GENERIC**
4. **Keywords should be extracted FROM the citation content, not from predefined lists**
5. **Stopwords list should be language-basic only, not domain-specific**

---

*Last Updated: 2026-01-13*
*Version: v2.4.0 Implementation Sprint*
