"""
Citation Integrity Checker Module

Detects and fixes citation integrity issues in ANY document type:
- Same-citation duplicates: [^A][^A] → [^A]
- Orphaned definitions: defined but never used inline
- Missing definitions: used inline but never defined

This module is DOMAIN-AGNOSTIC - works on medical, legal, engineering,
humanities, or any other document type.
"""

import re
from dataclasses import dataclass, field
from typing import List, Set, Tuple, Optional, Dict
from loguru import logger


@dataclass
class IntegrityReport:
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
    
    def to_dict(self) -> Dict:
        """Convert report to dictionary for JSON serialization."""
        return {
            "same_citation_duplicates": [
                {"line": line, "original": orig, "fixed": fix}
                for line, orig, fix in self.same_citation_duplicates
            ],
            "orphaned_definitions": self.orphaned_definitions,
            "missing_definitions": self.missing_definitions,
            "total_issues": self.total_issues,
            "is_clean": self.is_clean,
        }


class CitationIntegrityChecker:
    """
    Detect and fix duplicate/orphan citations in markdown documents.
    
    Works on ANY document type - medical, legal, engineering, humanities, etc.
    """
    
    # Semantic citation pattern [^Author-Year-ID] or [^Any-Tag]
    # Matches patterns like [^SmithJ-2024-12345] or [^1] or [^MyRef]
    CITATION_INLINE_PATTERN = r'\[\^[^\]]+\]'
    
    # Definition pattern [^Tag]: content (at start of line)
    DEFINITION_PATTERN = r'^\[\^([^\]]+)\]:'
    
    # Consecutive same citations [^A][^A] or [^A] [^A] (with optional whitespace)
    CONSECUTIVE_SAME_PATTERN = r'(\[\^[^\]]+\])(\s*)\1'
    
    def __init__(self):
        self._last_report: Optional[IntegrityReport] = None
    
    def analyze(self, content: str) -> IntegrityReport:
        """
        Analyze document for citation integrity issues.
        
        Args:
            content: Full markdown document content (any domain)
            
        Returns:
            IntegrityReport with all issues found
        """
        logger.info("Analyzing document for citation integrity issues")
        
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
        
        report = IntegrityReport(
            same_citation_duplicates=same_duplicates,
            orphaned_definitions=sorted(list(orphaned)),
            missing_definitions=sorted(list(missing))
        )
        
        self._last_report = report
        
        logger.info(f"Integrity analysis complete: {report.total_issues} issues found")
        if report.same_citation_duplicates:
            logger.debug(f"  - Same-citation duplicates: {len(report.same_citation_duplicates)}")
        if report.orphaned_definitions:
            logger.debug(f"  - Orphaned definitions: {len(report.orphaned_definitions)}")
        if report.missing_definitions:
            logger.debug(f"  - Missing definitions: {len(report.missing_definitions)}")
        
        return report
    
    def _extract_inline_citations(self, lines: List[str]) -> Set[str]:
        """Extract all inline citation tags, excluding the reference section."""
        citations: Set[str] = set()
        in_ref_section = False
        
        for line in lines:
            # Detect reference section start (multiple heading formats)
            if re.match(r'^#{1,3}\s*(References|Bibliography|Citations|Works Cited|Sources|Endnotes)', line, re.I):
                in_ref_section = True
                continue
            
            if in_ref_section:
                # Skip definition lines in reference section
                if re.match(self.DEFINITION_PATTERN, line):
                    continue
                # If we hit another heading, we might be out of references
                if re.match(r'^#{1,3}\s+', line):
                    in_ref_section = False
                continue
            
            # Find all citation references in the line
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
        """
        Find consecutive same-citation duplicates.
        
        Returns:
            List of (line_number, original_text, fixed_text) tuples
        """
        duplicates = []
        in_ref_section = False
        
        for i, line in enumerate(lines, 1):
            # Skip reference section
            if re.match(r'^#{1,3}\s*(References|Bibliography|Citations|Works Cited|Sources|Endnotes)', line, re.I):
                in_ref_section = True
                continue
            
            if in_ref_section:
                continue
            
            # Find all consecutive duplicates in this line
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
        
        # Keep applying fixes until no more duplicates found
        # (handles cases like [^A][^A][^A] → [^A][^A] → [^A])
        while True:
            # Find where reference section starts to avoid modifying it
            lines = result.split('\n')
            ref_start_idx = len(result)  # Default to end
            
            for i, line in enumerate(lines):
                if re.match(r'^#{1,3}\s*(References|Bibliography|Citations|Works Cited|Sources|Endnotes)', line, re.I):
                    # Calculate character position
                    ref_start_idx = sum(len(l) + 1 for l in lines[:i])
                    break
            
            # Only apply fixes to body content (before references)
            body = result[:ref_start_idx]
            refs = result[ref_start_idx:]
            
            new_body = re.sub(
                self.CONSECUTIVE_SAME_PATTERN,
                r'\1',
                body
            )
            
            if new_body == body:
                break
            
            # Count how many fixes were made this iteration
            iteration_fixes = len(re.findall(self.CONSECUTIVE_SAME_PATTERN, body))
            fixes += iteration_fixes
            
            result = new_body + refs
        
        if fixes > 0:
            logger.info(f"Fixed {fixes} same-citation duplicates")
        
        return result, fixes
    
    def format_report(self, report: Optional[IntegrityReport] = None) -> str:
        """
        Format an integrity report as markdown.
        
        Args:
            report: Report to format (uses last analysis if None)
            
        Returns:
            Markdown-formatted report string
        """
        if report is None:
            report = self._last_report
        
        if report is None:
            return "No analysis has been performed yet."
        
        output = ["# Citation Integrity Report", ""]
        
        if report.is_clean:
            output.append("✅ **No integrity issues found.** Document citations are clean.")
            return "\n".join(output)
        
        output.append(f"**Total issues found:** {report.total_issues}")
        output.append("")
        
        # Same-citation duplicates
        if report.same_citation_duplicates:
            output.append(f"## ❌ Same-Citation Duplicates ({len(report.same_citation_duplicates)})")
            output.append("")
            output.append("These are consecutive identical citations that should be deduplicated:")
            output.append("")
            for line, orig, fix in report.same_citation_duplicates:
                output.append(f"- **Line {line}:** `{orig}` → `{fix}`")
            output.append("")
        
        # Orphaned definitions
        if report.orphaned_definitions:
            output.append(f"## ⚠️ Orphaned Definitions ({len(report.orphaned_definitions)})")
            output.append("")
            output.append("These citations are defined but never used in the document body:")
            output.append("")
            for orphan in report.orphaned_definitions[:20]:  # Limit display
                output.append(f"- `{orphan}`")
            if len(report.orphaned_definitions) > 20:
                output.append(f"- ... and {len(report.orphaned_definitions) - 20} more")
            output.append("")
        
        # Missing definitions
        if report.missing_definitions:
            output.append(f"## ❌ Missing Definitions ({len(report.missing_definitions)})")
            output.append("")
            output.append("These citations are used inline but have no definition:")
            output.append("")
            for missing in report.missing_definitions[:20]:  # Limit display
                output.append(f"- `{missing}`")
            if len(report.missing_definitions) > 20:
                output.append(f"- ... and {len(report.missing_definitions) - 20} more")
            output.append("")
        
        return "\n".join(output)


# Convenience function for quick analysis
def check_citation_integrity(content: str) -> IntegrityReport:
    """
    Quick check for citation integrity issues.
    
    Args:
        content: Markdown document content
        
    Returns:
        IntegrityReport with all issues found
    """
    checker = CitationIntegrityChecker()
    return checker.analyze(content)


# Convenience function for quick fix
def fix_citation_duplicates(content: str) -> Tuple[str, int]:
    """
    Quick fix for consecutive duplicate citations.
    
    Args:
        content: Markdown document content
        
    Returns:
        Tuple of (fixed_content, number_of_fixes)
    """
    checker = CitationIntegrityChecker()
    return checker.fix_duplicates(content)
