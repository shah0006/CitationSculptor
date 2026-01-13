"""
Test suite for Citation Integrity Checker module.

Tests duplicate detection, orphan detection, and missing definition detection.
Includes multi-domain test cases (medical, legal, engineering, humanities).
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.citation_integrity_checker import (
    CitationIntegrityChecker,
    IntegrityReport,
    check_citation_integrity,
    fix_citation_duplicates,
)


class TestIntegrityReport:
    """Test the IntegrityReport dataclass."""
    
    def test_empty_report_is_clean(self):
        """Empty report should be clean."""
        report = IntegrityReport()
        assert report.is_clean
        assert report.total_issues == 0
    
    def test_report_with_duplicates_not_clean(self):
        """Report with duplicates should not be clean."""
        report = IntegrityReport(
            same_citation_duplicates=[(1, "[^A][^A]", "[^A]")]
        )
        assert not report.is_clean
        assert report.total_issues == 1
    
    def test_report_to_dict(self):
        """Report should convert to dictionary correctly."""
        report = IntegrityReport(
            same_citation_duplicates=[(1, "[^A][^A]", "[^A]")],
            orphaned_definitions=["[^B]"],
            missing_definitions=["[^C]"]
        )
        d = report.to_dict()
        assert d["total_issues"] == 3
        assert not d["is_clean"]
        assert len(d["same_citation_duplicates"]) == 1


class TestDuplicateDetection:
    """Test consecutive same-citation duplicate detection."""
    
    def test_no_duplicates(self):
        """Document with no duplicates should be clean."""
        content = """
# Test Document

This is a test.[^Smith-2024]

Another point.[^Jones-2023]

## References

[^Smith-2024]: Smith J. Title. Journal. 2024.
[^Jones-2023]: Jones A. Title. Journal. 2023.
"""
        checker = CitationIntegrityChecker()
        report = checker.analyze(content)
        assert len(report.same_citation_duplicates) == 0
    
    def test_consecutive_same_citations(self):
        """Detect [^A][^A] patterns."""
        content = """
# Test Document

This is a test.[^Smith-2024][^Smith-2024]

## References

[^Smith-2024]: Smith J. Title. Journal. 2024.
"""
        checker = CitationIntegrityChecker()
        report = checker.analyze(content)
        assert len(report.same_citation_duplicates) == 1
        assert report.same_citation_duplicates[0][1] == "[^Smith-2024][^Smith-2024]"
        assert report.same_citation_duplicates[0][2] == "[^Smith-2024]"
    
    def test_consecutive_with_space(self):
        """Detect [^A] [^A] patterns (with space)."""
        content = """
This is a test.[^Smith-2024] [^Smith-2024]

## References

[^Smith-2024]: Smith J. Title. Journal. 2024.
"""
        checker = CitationIntegrityChecker()
        report = checker.analyze(content)
        assert len(report.same_citation_duplicates) == 1
    
    def test_different_citations_not_duplicates(self):
        """[^A][^B] should not be flagged as duplicate."""
        content = """
This is a test.[^Smith-2024][^Jones-2023]

## References

[^Smith-2024]: Smith J. Title. 2024.
[^Jones-2023]: Jones A. Title. 2023.
"""
        checker = CitationIntegrityChecker()
        report = checker.analyze(content)
        assert len(report.same_citation_duplicates) == 0
    
    def test_triple_duplicates(self):
        """Detect [^A][^A][^A] patterns."""
        content = """
Test.[^A][^A][^A]

## References

[^A]: Test ref.
"""
        checker = CitationIntegrityChecker()
        report = checker.analyze(content)
        # At least one duplicate pattern found
        assert len(report.same_citation_duplicates) >= 1


class TestOrphanDetection:
    """Test orphaned definition detection."""
    
    def test_no_orphans(self):
        """All definitions used - no orphans."""
        content = """
Test.[^A]

## References

[^A]: Test ref.
"""
        checker = CitationIntegrityChecker()
        report = checker.analyze(content)
        assert len(report.orphaned_definitions) == 0
    
    def test_orphaned_definition(self):
        """Definition exists but never used inline."""
        content = """
Test.[^A]

## References

[^A]: Used ref.
[^B]: Orphaned ref - never used in body.
"""
        checker = CitationIntegrityChecker()
        report = checker.analyze(content)
        assert "[^B]" in report.orphaned_definitions
    
    def test_multiple_orphans(self):
        """Multiple orphaned definitions."""
        content = """
Test.[^A]

## References

[^A]: Used.
[^B]: Orphan 1.
[^C]: Orphan 2.
[^D]: Orphan 3.
"""
        checker = CitationIntegrityChecker()
        report = checker.analyze(content)
        assert len(report.orphaned_definitions) == 3


class TestMissingDefinitions:
    """Test missing definition detection."""
    
    def test_no_missing(self):
        """All citations have definitions."""
        content = """
Test.[^A]

## References

[^A]: Defined.
"""
        checker = CitationIntegrityChecker()
        report = checker.analyze(content)
        assert len(report.missing_definitions) == 0
    
    def test_missing_definition(self):
        """Citation used but never defined."""
        content = """
Test.[^A]
Also this.[^B]

## References

[^A]: Defined.
"""
        checker = CitationIntegrityChecker()
        report = checker.analyze(content)
        assert "[^B]" in report.missing_definitions
    
    def test_multiple_missing(self):
        """Multiple missing definitions."""
        content = """
Test.[^A][^B][^C]

## References

[^A]: Only this is defined.
"""
        checker = CitationIntegrityChecker()
        report = checker.analyze(content)
        assert len(report.missing_definitions) == 2


class TestFixDuplicates:
    """Test automatic duplicate fixing."""
    
    def test_fix_single_duplicate(self):
        """Fix [^A][^A] -> [^A]."""
        content = "Test.[^A][^A]\n\n## References\n\n[^A]: Ref."
        checker = CitationIntegrityChecker()
        fixed, count = checker.fix_duplicates(content)
        assert count == 1
        assert "[^A][^A]" not in fixed
        assert "[^A]" in fixed
    
    def test_fix_multiple_duplicates(self):
        """Fix multiple duplicate patterns in one document."""
        content = """
First.[^A][^A]
Second.[^B][^B]

## References

[^A]: Ref A.
[^B]: Ref B.
"""
        checker = CitationIntegrityChecker()
        fixed, count = checker.fix_duplicates(content)
        assert count == 2
    
    def test_fix_preserves_reference_section(self):
        """Fixing should not modify reference section."""
        content = """
Test.[^A][^A]

## References

[^A]: Reference with [^A] in text should not be modified.
"""
        checker = CitationIntegrityChecker()
        fixed, count = checker.fix_duplicates(content)
        # Reference section should be preserved
        assert "Reference with [^A] in text" in fixed


class TestMultiDomainMedical:
    """Test with medical document examples."""
    
    def test_medical_document_clean(self):
        """Medical document with no issues."""
        content = """
# Treatment Guidelines

Aspirin reduces cardiovascular events.[^SmithJ-2024]
Statins are recommended.[^JonesA-2023]

## References

[^SmithJ-2024]: Smith J. Aspirin therapy. Cardiology. 2024.
[^JonesA-2023]: Jones A. Statin guidelines. JACC. 2023.
"""
        report = check_citation_integrity(content)
        assert report.is_clean
    
    def test_medical_document_with_duplicates(self):
        """Medical document with duplicates."""
        content = """
Blood pressure control is important.[^ACC-2024][^ACC-2024]

## References

[^ACC-2024]: ACC/AHA Guidelines. Circulation. 2024.
"""
        report = check_citation_integrity(content)
        assert len(report.same_citation_duplicates) == 1


class TestMultiDomainLegal:
    """Test with legal document examples."""
    
    def test_legal_document_clean(self):
        """Legal document with no issues."""
        content = """
# Case Analysis

The precedent was established in Brown v. Board.[^Brown-1954]
This was later affirmed.[^RoeV-1973]

## References

[^Brown-1954]: Brown v. Board of Education, 347 U.S. 483 (1954).
[^RoeV-1973]: Roe v. Wade, 410 U.S. 113 (1973).
"""
        report = check_citation_integrity(content)
        assert report.is_clean
    
    def test_legal_document_missing_citation(self):
        """Legal document with missing definition."""
        content = """
The court held in Miranda.[^Miranda-1966]
See also Terry.[^Terry-1968]

## References

[^Miranda-1966]: Miranda v. Arizona, 384 U.S. 436 (1966).
"""
        report = check_citation_integrity(content)
        assert "[^Terry-1968]" in report.missing_definitions


class TestMultiDomainEngineering:
    """Test with engineering document examples."""
    
    def test_engineering_document_clean(self):
        """Engineering document with no issues."""
        content = """
# Materials Analysis

The tensile strength was measured.[^ASTM-2023]
Modulus followed specifications.[^ISO-2024]

## References

[^ASTM-2023]: ASTM E8 Standard. Materials Testing. 2023.
[^ISO-2024]: ISO 6892-1. Metallic materials. 2024.
"""
        report = check_citation_integrity(content)
        assert report.is_clean
    
    def test_engineering_orphaned_standard(self):
        """Engineering document with orphaned reference."""
        content = """
Testing followed ASTM guidelines.[^ASTM-2023]

## References

[^ASTM-2023]: ASTM E8 Standard. 2023.
[^MIL-STD-810]: MIL-STD-810 Environmental. 2019.
"""
        report = check_citation_integrity(content)
        assert "[^MIL-STD-810]" in report.orphaned_definitions


class TestMultiDomainHumanities:
    """Test with humanities document examples."""
    
    def test_humanities_document_clean(self):
        """Humanities document with no issues."""
        content = """
# Renaissance Art Analysis

The period saw dramatic changes.[^Vasari-1550]
Later scholars expanded on this.[^Gombrich-1995]

## Bibliography

[^Vasari-1550]: Vasari G. Lives of the Artists. 1550.
[^Gombrich-1995]: Gombrich EH. The Story of Art. 1995.
"""
        report = check_citation_integrity(content)
        assert report.is_clean
    
    def test_humanities_works_cited_section(self):
        """Humanities document with 'Works Cited' heading."""
        content = """
Shakespeare's influence.[^Bloom-1998]

## Works Cited

[^Bloom-1998]: Bloom H. Shakespeare: The Invention of the Human. 1998.
"""
        report = check_citation_integrity(content)
        assert report.is_clean


class TestConvenienceFunctions:
    """Test convenience functions."""
    
    def test_check_citation_integrity(self):
        """Quick integrity check function."""
        content = "Test.[^A]\n\n## References\n\n[^A]: Ref."
        report = check_citation_integrity(content)
        assert isinstance(report, IntegrityReport)
    
    def test_fix_citation_duplicates(self):
        """Quick duplicate fix function."""
        content = "Test.[^A][^A]\n\n## References\n\n[^A]: Ref."
        fixed, count = fix_citation_duplicates(content)
        assert count == 1


class TestReportFormatting:
    """Test report formatting."""
    
    def test_format_clean_report(self):
        """Clean report formatting."""
        checker = CitationIntegrityChecker()
        content = "Test.[^A]\n\n## References\n\n[^A]: Ref."
        checker.analyze(content)
        report_text = checker.format_report()
        assert "No integrity issues found" in report_text
    
    def test_format_report_with_issues(self):
        """Report with issues formatting."""
        checker = CitationIntegrityChecker()
        content = "Test.[^A][^A]\n\n## References\n\n[^A]: Ref.\n[^B]: Orphan."
        checker.analyze(content)
        report_text = checker.format_report()
        assert "Same-Citation Duplicates" in report_text
        assert "Orphaned Definitions" in report_text


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
