"""
Tests for Document Intelligence Module (v2.3.0)

Tests:
- Link verification
- Citation suggestions
- Citation compliance (plagiarism-style checker)
- Document analysis
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import sys
from pathlib import Path

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from modules.document_intelligence import (
    LinkVerifier,
    LinkStatus,
    LinkVerificationResult,
    CitationSuggestor,
    CitationSuggestion,
    PlagiarismChecker,
    PotentialPlagiarism,
    DocumentIntelligence,
    verify_document_links,
    suggest_document_citations,
    check_citation_compliance,
)


class TestLinkVerifier:
    """Tests for LinkVerifier class."""
    
    def test_init_default(self):
        """Test default initialization."""
        verifier = LinkVerifier()
        assert verifier.check_wayback is True
        assert verifier.max_workers == 5
    
    def test_init_custom(self):
        """Test custom initialization."""
        verifier = LinkVerifier(check_wayback=False, max_workers=10)
        assert verifier.check_wayback is False
        assert verifier.max_workers == 10
    
    def test_verify_invalid_url(self):
        """Test verification of invalid URL."""
        verifier = LinkVerifier()
        
        result = verifier.verify_url("")
        assert result.status == LinkStatus.SKIPPED
        
        result = verifier.verify_url("not-a-url")
        assert result.status == LinkStatus.SKIPPED
    
    @patch('requests.head')
    def test_verify_ok_url(self, mock_head):
        """Test verification of working URL."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.url = "https://example.com"
        mock_response.headers = {'Content-Type': 'text/html'}
        mock_head.return_value = mock_response
        
        verifier = LinkVerifier(check_wayback=False)
        result = verifier.verify_url("https://example.com")
        
        assert result.status == LinkStatus.OK
        assert result.status_code == 200
    
    @patch('requests.head')
    @patch('requests.get')
    def test_verify_redirect(self, mock_get, mock_head):
        """Test detection of redirect."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.url = "https://example.com/redirected"
        mock_response.headers = {'Content-Type': 'text/html'}
        mock_head.return_value = mock_response
        
        verifier = LinkVerifier(check_wayback=False)
        result = verifier.verify_url("https://example.com/original")
        
        assert result.status == LinkStatus.REDIRECT
        assert result.final_url == "https://example.com/redirected"
    
    @patch('requests.head')
    @patch('requests.get')
    def test_verify_broken_url(self, mock_get, mock_head):
        """Test verification of broken URL."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_head.return_value = mock_response
        mock_get.return_value = mock_response
        
        verifier = LinkVerifier(check_wayback=False)
        result = verifier.verify_url("https://example.com/not-found")
        
        assert result.status == LinkStatus.BROKEN
        assert result.status_code == 404
    
    def test_verify_document(self):
        """Test document link extraction."""
        content = """
# Test Document

Here is a [link](https://example.com/page1) and another [link](https://example.com/page2).

Also a raw URL: https://example.com/raw
"""
        verifier = LinkVerifier(check_wayback=False, max_workers=1)
        
        # Mock the verify_url method to avoid actual network calls
        with patch.object(verifier, 'verify_url') as mock_verify:
            mock_verify.return_value = LinkVerificationResult(
                url="https://example.com",
                status=LinkStatus.OK,
                status_code=200
            )
            
            result = verifier.verify_document(content)
            
            assert 'total_urls' in result
            assert result['total_urls'] >= 2  # At least the markdown links


class TestCitationSuggestor:
    """Tests for CitationSuggestor class."""
    
    def test_init(self):
        """Test initialization."""
        suggestor = CitationSuggestor()
        assert suggestor.use_llm is False
        assert suggestor.pubmed_client is None
    
    def test_detect_statistics(self):
        """Test detection of uncited statistics."""
        suggestor = CitationSuggestor()
        
        content = """
Heart failure affects approximately 6.5 million Americans.
The mortality rate is 50% within 5 years of diagnosis.
"""
        suggestions = suggestor.analyze_document(content, search_suggestions=False)
        
        # Should detect percentage and number patterns
        assert len(suggestions) >= 1
        assert any(s.category == 'statistic' for s in suggestions)
    
    def test_detect_claims(self):
        """Test detection of uncited claims."""
        suggestor = CitationSuggestor()
        
        content = """
Studies show that exercise reduces cardiovascular risk.
Research suggests that diet plays a key role.
"""
        suggestions = suggestor.analyze_document(content, search_suggestions=False)
        
        assert len(suggestions) >= 1
        assert any(s.category == 'claim' for s in suggestions)
    
    def test_detect_findings(self):
        """Test detection of uncited findings."""
        suggestor = CitationSuggestor()
        
        content = """
Researchers found that early intervention significantly improved outcomes.
Results show a marked decrease in mortality.
"""
        suggestions = suggestor.analyze_document(content, search_suggestions=False)
        
        assert len(suggestions) >= 1
        assert any(s.category == 'finding' for s in suggestions)
    
    def test_skip_cited_lines(self):
        """Test that lines with citations are skipped."""
        suggestor = CitationSuggestor()
        
        content = """
Studies show that exercise reduces cardiovascular risk. [^Smith-2020-12345678]
The mortality rate is 50% within 5 years of diagnosis [1].
"""
        suggestions = suggestor.analyze_document(content, search_suggestions=False)
        
        # Should not flag already-cited content
        for s in suggestions:
            assert '[^' not in s.text_excerpt or s.line_number != 2
    
    def test_extract_search_terms(self):
        """Test extraction of search terms."""
        suggestor = CitationSuggestor()
        
        terms = suggestor._extract_search_terms("Heart failure affects cardiovascular health in elderly patients")
        
        assert len(terms) > 0
        assert len(terms) <= 5
        # Should filter out stopwords
        assert 'the' not in terms
        assert 'in' not in terms


class TestPlagiarismChecker:
    """Tests for PlagiarismChecker (citation compliance)."""
    
    def test_init(self):
        """Test initialization."""
        checker = PlagiarismChecker()
        assert checker is not None
    
    def test_check_uncited_quote(self):
        """Test detection of uncited quotes."""
        checker = PlagiarismChecker()
        
        content = """
According to the guidelines, "patients with heart failure should receive appropriate medical therapy including ACE inhibitors and beta blockers."
"""
        result = checker.check_document(content)
        
        assert result['total_issues'] >= 1
        assert any(i['issue_type'] == 'uncited_quote' for i in result.get('issues', []))
    
    def test_check_academic_phrases(self):
        """Test detection of academic phrases needing citation."""
        checker = PlagiarismChecker()
        
        content = """
Previous research has shown that statins reduce cardiovascular events.
It is widely accepted that smoking causes lung cancer.
"""
        result = checker.check_document(content)
        
        # Should detect "previous research" and "widely accepted"
        assert result['total_issues'] >= 1
    
    def test_high_severity_claims(self):
        """Test detection of high-severity medical claims."""
        checker = PlagiarismChecker()
        
        content = """
This supplement cures cancer and prevents heart disease.
It has been proven to be 100% effective.
"""
        result = checker.check_document(content)
        
        assert result['high_severity_count'] >= 1
    
    def test_compliance_score(self):
        """Test compliance score calculation."""
        checker = PlagiarismChecker()
        
        # Document with no issues
        good_content = """
# Simple Note

This is just a personal note with no claims.
"""
        result = checker.check_document(good_content)
        assert result['compliance_score'] >= 80
        
        # Document with many issues
        bad_content = """
Studies show this. Research proves that. Evidence indicates the following.
Previous research has demonstrated effectiveness.
"This is a long quote that should be cited properly for academic integrity."
"""
        result = checker.check_document(bad_content)
        assert result['compliance_score'] < 100
    
    def test_skip_headers_and_code(self):
        """Test that headers and code blocks are skipped."""
        checker = PlagiarismChecker()
        
        content = """
# Studies Show Header

```python
# Previous research code
print("This is code")
```

---

Normal text here.
"""
        result = checker.check_document(content)
        
        # Headers and code should be skipped
        for issue in result.get('issues', []):
            assert not issue['text'].startswith('#')
            assert 'print(' not in issue['text']


class TestDocumentIntelligence:
    """Tests for main DocumentIntelligence class."""
    
    def test_init(self):
        """Test initialization."""
        di = DocumentIntelligence()
        assert di.link_verifier is not None
        assert di.citation_suggestor is not None
        assert di.plagiarism_checker is not None
    
    def test_analyze_document_structure(self):
        """Test document analysis returns correct structure."""
        di = DocumentIntelligence()
        
        content = """
# Test Document

This is a test with 50% of patients affected.
Studies show improvement.

[Link](https://example.com)
"""
        
        # Mock link verification to avoid network calls
        with patch.object(di.link_verifier, 'verify_document') as mock_verify:
            mock_verify.return_value = {
                'total_urls': 1,
                'verified': 1,
                'status_summary': {'ok': 1},
                'broken_links': [],
                'redirected_links': [],
                'archived_links': [],
                'paywalled_links': [],
                'all_results': [],
            }
            
            result = di.analyze_document(content, verify_links=True, suggest_citations=True, check_plagiarism=True)
            
            assert 'timestamp' in result
            assert 'document_length' in result
            assert 'line_count' in result
            assert 'overall_health_score' in result
            assert 'link_verification' in result
            assert 'citation_suggestions' in result
            assert 'citation_compliance' in result
    
    def test_verify_single_link(self):
        """Test single link verification."""
        di = DocumentIntelligence()
        
        with patch.object(di.link_verifier, 'verify_url') as mock_verify:
            mock_verify.return_value = LinkVerificationResult(
                url="https://example.com",
                status=LinkStatus.OK,
                status_code=200
            )
            
            result = di.verify_single_link("https://example.com")
            
            assert result['status'] == 'ok'
            assert result['url'] == "https://example.com"


class TestConvenienceFunctions:
    """Tests for module-level convenience functions."""
    
    def test_verify_document_links(self):
        """Test verify_document_links function."""
        content = "No links here."
        
        result = verify_document_links(content)
        
        assert 'total_urls' in result
        assert result['total_urls'] == 0
    
    def test_suggest_document_citations(self):
        """Test suggest_document_citations function."""
        content = "Studies show that 50% of patients respond."
        
        result = suggest_document_citations(content)
        
        assert isinstance(result, list)
    
    def test_check_citation_compliance(self):
        """Test check_citation_compliance function."""
        content = "This is a simple document."
        
        result = check_citation_compliance(content)
        
        assert 'compliance_score' in result
        assert 'total_issues' in result


class TestLinkVerificationResult:
    """Tests for LinkVerificationResult dataclass."""
    
    def test_to_dict(self):
        """Test conversion to dictionary."""
        result = LinkVerificationResult(
            url="https://example.com",
            status=LinkStatus.OK,
            status_code=200,
            reference_number=1,
            title="Example"
        )
        
        d = result.to_dict()
        
        assert d['url'] == "https://example.com"
        assert d['status'] == 'ok'
        assert d['status_code'] == 200
        assert d['reference_number'] == 1
        assert d['title'] == "Example"


class TestCitationSuggestion:
    """Tests for CitationSuggestion dataclass."""
    
    def test_to_dict(self):
        """Test conversion to dictionary."""
        suggestion = CitationSuggestion(
            text_excerpt="Studies show that...",
            line_number=5,
            reason="Claim without citation",
            confidence=0.85,
            suggested_search_terms=["studies", "cardiovascular"],
            category="claim"
        )
        
        d = suggestion.to_dict()
        
        assert d['text_excerpt'] == "Studies show that..."
        assert d['line_number'] == 5
        assert d['confidence'] == 0.85
        assert d['category'] == "claim"


class TestPotentialPlagiarism:
    """Tests for PotentialPlagiarism dataclass."""
    
    def test_to_dict(self):
        """Test conversion to dictionary."""
        issue = PotentialPlagiarism(
            text="Uncited quote here",
            line_number=10,
            issue_type="uncited_quote",
            severity="high",
            explanation="Quote without attribution",
            suggested_action="Add citation"
        )
        
        d = issue.to_dict()
        
        assert d['text'] == "Uncited quote here"
        assert d['line_number'] == 10
        assert d['severity'] == "high"
        assert d['suggested_action'] == "Add citation"


# Integration tests

class TestIntegration:
    """Integration tests for Document Intelligence."""
    
    def test_medical_document_analysis(self):
        """Test analysis of a medical document."""
        content = """
# Heart Failure Management

Heart failure affects approximately 6.5 million Americans and is associated 
with a 50% mortality rate within 5 years of diagnosis.

## Treatment Guidelines

Studies show that ACE inhibitors reduce mortality in heart failure patients.
Beta-blockers have been proven to improve outcomes significantly.

## References

1. [Heart Failure Statistics](https://example.com/stats)
2. [Treatment Guidelines](https://example.com/guidelines)
"""
        
        di = DocumentIntelligence()
        
        # Skip link verification for this test
        result = di.analyze_document(content, verify_links=False, suggest_citations=True, check_plagiarism=True)
        
        # Should detect statistics and claims
        assert result['citation_suggestions']['count'] >= 2
        
        # Compliance score should be less than perfect
        assert result['citation_compliance']['compliance_score'] < 100
    
    def test_well_cited_document(self):
        """Test analysis of a well-cited document."""
        content = """
# Research Notes

Heart failure affects many patients. [^Smith-2020-12345678]

Treatment has improved outcomes. [^Jones-2021-87654321]

## References

[^Smith-2020-12345678]: Smith J. Heart Failure Statistics. J Cardiol. 2020.
[^Jones-2021-87654321]: Jones A. Treatment Advances. Circulation. 2021.
"""
        
        di = DocumentIntelligence()
        result = di.analyze_document(content, verify_links=False, suggest_citations=True, check_plagiarism=True)
        
        # Well-cited document should have high compliance
        assert result['citation_compliance']['compliance_score'] >= 80

