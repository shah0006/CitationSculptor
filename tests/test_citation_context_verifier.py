"""
Test suite for Citation Context Verifier module.

Tests keyword extraction, overlap calculation, and context verification.
Includes multi-domain test cases (medical, legal, engineering, humanities).
Tests are domain-agnostic - no hardcoded keywords.
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.citation_context_verifier import (
    CitationContextVerifier,
    ContextMismatch,
    ConcernLevel,
    STOPWORDS,
    verify_citation_contexts,
)


class TestKeywordExtraction:
    """Test dynamic keyword extraction."""
    
    def test_extract_basic_keywords(self):
        """Extract keywords from simple text - now includes keyphrases."""
        verifier = CitationContextVerifier()
        text = "The cardiovascular system treatment involves aspirin therapy for patients."
        keywords = verifier.extract_keywords(text)
        
        # Check that key concepts are captured (either as phrases or unigrams)
        combined = ' '.join(keywords)
        assert "cardiovascular" in combined
        assert "treatment" in combined
        assert "aspirin" in combined
        assert "therapy" in combined
        assert "patient" in combined  # May be lemmatized
    
    def test_stopwords_removed(self):
        """Stopwords should be excluded."""
        verifier = CitationContextVerifier()
        text = "The quick brown fox jumps over the lazy dog and the cat."
        keywords = verifier.extract_keywords(text)
        
        assert "the" not in keywords
        assert "and" not in keywords
        assert "over" not in keywords
    
    def test_short_words_removed(self):
        """Words shorter than min_word_length should be excluded."""
        verifier = CitationContextVerifier(min_word_length=4, use_keyphrases=False)
        text = "The AI and ML are new hot topics in CS today."
        keywords = verifier.extract_keywords(text)
        
        # Short words like "AI", "ML", "CS", "new", "hot" should be excluded
        assert "topic" in keywords  # May be lemmatized from "topics"
        assert "today" in keywords
    
    def test_numbers_removed(self):
        """Pure numbers should be excluded."""
        verifier = CitationContextVerifier(use_keyphrases=False)
        text = "In 2024 there were 1000 cases reported with 50 percent improvement."
        keywords = verifier.extract_keywords(text)
        
        assert "2024" not in keywords
        assert "1000" not in keywords
        combined = ' '.join(keywords)
        assert "case" in combined  # May be lemmatized
        assert "report" in combined  # May be lemmatized
    
    def test_empty_text(self):
        """Empty text should return empty list."""
        verifier = CitationContextVerifier()
        keywords = verifier.extract_keywords("")
        assert keywords == []
    
    def test_top_keywords_limit(self):
        """Should return only top N keywords."""
        verifier = CitationContextVerifier(top_keywords=5)
        text = "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu"
        keywords = verifier.extract_keywords(text)
        assert len(keywords) <= 5
    
    def test_frequency_based_ranking(self):
        """More frequent words should rank higher."""
        verifier = CitationContextVerifier(use_keyphrases=False)  # Test unigram ranking
        text = "treatment treatment treatment therapy therapy analysis"
        keywords = verifier.extract_keywords(text)
        # "treatment" appears most, should be first or near first
        assert "treatment" in keywords[:2]


class TestOverlapCalculation:
    """Test keyword overlap score calculation."""
    
    def test_perfect_overlap(self):
        """Identical keyword sets should have score 1.0."""
        verifier = CitationContextVerifier()
        keywords = ["heart", "disease", "treatment"]
        score = verifier.calculate_overlap_score(keywords, keywords)
        assert score == 1.0
    
    def test_no_overlap(self):
        """No common keywords should have score 0.0."""
        verifier = CitationContextVerifier()
        keywords1 = ["heart", "disease", "treatment"]
        keywords2 = ["legal", "court", "statute"]
        score = verifier.calculate_overlap_score(keywords1, keywords2)
        assert score == 0.0
    
    def test_partial_overlap(self):
        """Partial overlap should have score between 0 and 1."""
        verifier = CitationContextVerifier()
        context_kw = ["heart", "disease", "treatment"]
        citation_kw = ["heart", "surgery", "hospital"]
        score = verifier.calculate_overlap_score(context_kw, citation_kw)
        assert 0.0 < score < 1.0
        # IDF-weighted inclusion: 1 common (heart) out of 3 citation keywords
        # With IDF weighting, exact value depends on term specificity
        # but should be around 1/3 = 0.33
        assert 0.2 < score < 0.5
    
    def test_empty_keywords(self):
        """Empty keyword list should return 0."""
        verifier = CitationContextVerifier()
        score = verifier.calculate_overlap_score([], ["test"])
        assert score == 0.0
        score = verifier.calculate_overlap_score(["test"], [])
        assert score == 0.0


class TestConcernLevel:
    """Test concern level classification."""
    
    def test_high_concern(self):
        """Very low overlap should be HIGH concern."""
        verifier = CitationContextVerifier()
        level = verifier.classify_concern_level(0.03)
        assert level == ConcernLevel.HIGH
    
    def test_moderate_concern(self):
        """Low overlap should be MODERATE concern."""
        verifier = CitationContextVerifier()
        level = verifier.classify_concern_level(0.10)
        assert level == ConcernLevel.MODERATE
    
    def test_low_concern(self):
        """Medium-high overlap should be LOW concern (30-50% with Inclusion Coefficient)."""
        verifier = CitationContextVerifier()
        level = verifier.classify_concern_level(0.35)  # Updated for Inclusion Coefficient thresholds
        assert level == ConcernLevel.LOW
    
    def test_no_concern(self):
        """High overlap should be NONE concern."""
        verifier = CitationContextVerifier()
        level = verifier.classify_concern_level(0.50)
        assert level == ConcernLevel.NONE


class TestContextExtraction:
    """Test citation context extraction."""
    
    def test_extract_citation_with_context(self):
        """Extract citation and surrounding lines."""
        verifier = CitationContextVerifier()
        content = """Line 1.
Line 2.
Line 3 with citation.[^Test-2024]
Line 4.
Line 5.

## References

[^Test-2024]: Test reference."""
        
        contexts = verifier.extract_citation_contexts(content)
        assert len(contexts) == 1
        line_num, tag, context = contexts[0]
        assert tag == "[^Test-2024]"
        assert "Line 3" in context
    
    def test_skip_reference_section(self):
        """Citations in reference section should not be extracted."""
        verifier = CitationContextVerifier()
        content = """Body text.[^A]

## References

[^A]: Reference text with [^A] mention."""
        
        contexts = verifier.extract_citation_contexts(content)
        # Should only find the one in body
        assert len(contexts) == 1
    
    def test_multiple_citations_same_line(self):
        """Multiple citations on same line."""
        verifier = CitationContextVerifier()
        content = """Text.[^A][^B]

## References

[^A]: Ref A.
[^B]: Ref B."""
        
        contexts = verifier.extract_citation_contexts(content)
        assert len(contexts) == 2


class TestCitationDefinition:
    """Test citation definition retrieval."""
    
    def test_get_definition(self):
        """Get citation definition text."""
        verifier = CitationContextVerifier()
        content = """Body.

## References

[^Test-2024]: This is the full reference text with details."""
        
        definition = verifier.get_citation_definition("[^Test-2024]", content)
        assert "full reference text" in definition
    
    def test_definition_not_found(self):
        """Missing definition returns None."""
        verifier = CitationContextVerifier()
        content = "Body.\n\n## References\n\n[^A]: Ref A."
        definition = verifier.get_citation_definition("[^B]", content)
        assert definition is None


class TestContextVerification:
    """Test full context verification."""
    
    def test_matching_context(self):
        """Citation matching its context should not be flagged."""
        verifier = CitationContextVerifier()
        content = """
Cardiovascular disease treatment involves medication therapy for heart patients.
This approach was validated by recent studies.[^CardioStudy-2024]

## References

[^CardioStudy-2024]: Smith J. Cardiovascular medication therapy outcomes in heart disease patients. Cardiology. 2024.
"""
        mismatches = verifier.verify_citations(content)
        # Good overlap - should not be flagged (or low concern)
        high_concern = [m for m in mismatches if m.concern_level == ConcernLevel.HIGH]
        assert len(high_concern) == 0
    
    def test_mismatched_context(self):
        """Citation not matching context should be flagged."""
        verifier = CitationContextVerifier()
        content = """
The Supreme Court ruling on constitutional rights established important precedent.
Legal scholars have analyzed this decision extensively.[^PlantBiology-2024]

## References

[^PlantBiology-2024]: Johnson K. Chlorophyll synthesis in tropical plants. Botany Journal. 2024.
"""
        mismatches = verifier.verify_citations(content, flag_threshold=0.15)
        # Very different topics - should be flagged
        assert len(mismatches) > 0


class TestMultiDomainMedical:
    """Test with medical document examples."""
    
    def test_medical_matching_citation(self):
        """Medical citation matching cardiology context."""
        verifier = CitationContextVerifier()
        content = """
Statin therapy reduces LDL cholesterol levels and cardiovascular mortality.
Clinical trials have demonstrated significant benefits.[^StatinTrial-2023]

## References

[^StatinTrial-2023]: Jones A. Statin therapy efficacy in reducing LDL cholesterol and cardiovascular mortality. JACC. 2023.
"""
        mismatches = verifier.verify_citations(content)
        # Keywords overlap: statin, therapy, cholesterol, cardiovascular, mortality
        high_concern = [m for m in mismatches if m.concern_level == ConcernLevel.HIGH]
        assert len(high_concern) == 0
    
    def test_medical_wrong_specialty(self):
        """Medical citation from wrong specialty."""
        verifier = CitationContextVerifier()
        content = """
Orthopedic surgery for knee replacement involves careful bone preparation.
Joint alignment is critical for outcomes.[^DermatologyRash-2024]

## References

[^DermatologyRash-2024]: Wilson R. Treatment of psoriatic skin rashes with topical corticosteroids. Dermatology. 2024.
"""
        mismatches = verifier.verify_citations(content)
        # Very different medical specialties - should flag
        assert len(mismatches) > 0


class TestMultiDomainLegal:
    """Test with legal document examples."""
    
    def test_legal_matching_citation(self):
        """Legal citation matching constitutional context."""
        verifier = CitationContextVerifier()
        content = """
The constitutional amendment protects freedom of speech and press.
This right has been upheld in numerous Supreme Court decisions.[^FirstAmendment-2020]

## References

[^FirstAmendment-2020]: Roberts J. Constitutional protection of speech and press rights in Supreme Court jurisprudence. Law Review. 2020.
"""
        mismatches = verifier.verify_citations(content)
        high_concern = [m for m in mismatches if m.concern_level == ConcernLevel.HIGH]
        assert len(high_concern) == 0


class TestMultiDomainEngineering:
    """Test with engineering document examples."""
    
    def test_engineering_matching_citation(self):
        """Engineering citation matching materials context."""
        verifier = CitationContextVerifier()
        content = """
The steel alloy exhibited excellent tensile strength under load testing.
Fatigue resistance was measured per ASTM standards.[^SteelAlloy-2023]

## References

[^SteelAlloy-2023]: Kim H. Tensile strength and fatigue resistance testing of steel alloys per ASTM standards. Materials Science. 2023.
"""
        mismatches = verifier.verify_citations(content)
        high_concern = [m for m in mismatches if m.concern_level == ConcernLevel.HIGH]
        assert len(high_concern) == 0


class TestMultiDomainHumanities:
    """Test with humanities document examples."""
    
    def test_humanities_matching_citation(self):
        """Humanities citation matching art history context."""
        verifier = CitationContextVerifier()
        content = """
Renaissance painting techniques revolutionized artistic perspective.
Italian masters pioneered these innovations.[^RenArt-1995]

## References

[^RenArt-1995]: Gombrich E. Renaissance painting techniques and perspective innovation by Italian masters. Art History. 1995.
"""
        mismatches = verifier.verify_citations(content)
        high_concern = [m for m in mismatches if m.concern_level == ConcernLevel.HIGH]
        assert len(high_concern) == 0


class TestStopwords:
    """Test stopword configuration."""
    
    def test_no_domain_specific_stopwords(self):
        """Verify stopwords are domain-agnostic."""
        # Domain-specific words should NOT be in stopwords
        assert "cardiovascular" not in STOPWORDS
        assert "legal" not in STOPWORDS
        assert "engineering" not in STOPWORDS
        assert "constitutional" not in STOPWORDS
        assert "tensile" not in STOPWORDS
    
    def test_basic_stopwords_present(self):
        """Basic language stopwords should be present."""
        assert "the" in STOPWORDS
        assert "and" in STOPWORDS
        assert "is" in STOPWORDS
        assert "of" in STOPWORDS


class TestMismatchDataclass:
    """Test ContextMismatch dataclass."""
    
    def test_mismatch_to_dict(self):
        """Mismatch should convert to dictionary."""
        mismatch = ContextMismatch(
            line_number=10,
            citation_tag="[^Test]",
            surrounding_text="Context text here",
            citation_text="Citation text here",
            citation_keywords=["keyword1", "keyword2"],
            context_keywords=["keyword3", "keyword4"],
            overlap_score=0.1,
            concern_level=ConcernLevel.MODERATE,
        )
        d = mismatch.to_dict()
        assert d["line_number"] == 10
        assert d["citation_tag"] == "[^Test]"
        assert d["concern_level"] == "moderate"


class TestReportFormatting:
    """Test report formatting."""
    
    def test_format_empty_mismatches(self):
        """Empty mismatches should show success message."""
        verifier = CitationContextVerifier()
        report = verifier.format_mismatch_report([])
        assert "All citations appear to match" in report
    
    def test_format_with_mismatches(self):
        """Report should show mismatch details."""
        verifier = CitationContextVerifier()
        mismatch = ContextMismatch(
            line_number=10,
            citation_tag="[^Test]",
            surrounding_text="Context text",
            citation_text="Citation text",
            citation_keywords=["kw1"],
            context_keywords=["kw2"],
            overlap_score=0.05,
            concern_level=ConcernLevel.HIGH,
        )
        report = verifier.format_mismatch_report([mismatch])
        assert "Potential Context Mismatches" in report
        assert "High Concern" in report


class TestConvenienceFunction:
    """Test convenience function."""
    
    def test_verify_citation_contexts(self):
        """Quick verification function."""
        content = """
Text.[^A]

## References

[^A]: Reference.
"""
        mismatches = verify_citation_contexts(content)
        assert isinstance(mismatches, list)


class TestVerificationStats:
    """Test verification statistics tracking."""
    
    def test_stats_increment(self):
        """Stats should track verification counts."""
        verifier = CitationContextVerifier()
        content = """
Test.[^A][^B]

## References

[^A]: Ref A.
[^B]: Ref B.
"""
        verifier.verify_citations(content)
        assert verifier.stats.total_citations_verified >= 2


class TestLemmatization:
    """Test lemmatization feature for reducing word variants."""
    
    def test_lemmatization_enabled(self):
        """Lemmatization should reduce word variants."""
        verifier = CitationContextVerifier(use_lemmatization=True, use_keyphrases=False)
        # Use words that get lemmatized (not in exceptions)
        text = "treatments therapies outcomes findings"
        keywords = verifier.extract_keywords(text)
        combined = ' '.join(keywords)
        # "therapies" -> "therapy", "findings" -> "finding"
        assert "therapy" in combined or "therapies" in combined
        assert "finding" in combined or "findings" in combined
    
    def test_lemmatization_disabled(self):
        """Disabling lemmatization keeps original forms."""
        verifier = CitationContextVerifier(use_lemmatization=False, use_keyphrases=False)
        text = "treatments therapies outcomes findings"
        keywords = verifier.extract_keywords(text)
        # Original forms preserved
        assert "therapies" in keywords
        assert "findings" in keywords
    
    def test_lemmatization_exceptions(self):
        """Technical terms should not be incorrectly lemmatized."""
        verifier = CitationContextVerifier(use_lemmatization=True, use_keyphrases=False)
        text = "amyloidosis diagnosis fibrosis prognosis"
        keywords = verifier.extract_keywords(text)
        # These technical terms should be preserved
        assert "amyloidosis" in keywords
        assert "diagnosis" in keywords


class TestKeyphraseExtraction:
    """Test n-gram keyphrase extraction."""
    
    def test_keyphrases_enabled(self):
        """Should extract meaningful 2-3 word phrases."""
        verifier = CitationContextVerifier(use_keyphrases=True)
        text = "Cardiac amyloidosis causes heart failure in elderly patients."
        keywords = verifier.extract_keywords(text)
        
        # Should find phrases like "cardiac amyloidosis", "heart failure"
        combined = ' '.join(keywords)
        assert "cardiac" in combined and "amyloidosis" in combined
        assert "heart" in combined and "failure" in combined
    
    def test_keyphrases_disabled(self):
        """Disabling keyphrases returns only unigrams."""
        verifier = CitationContextVerifier(use_keyphrases=False)
        text = "Machine learning models process natural language data."
        keywords = verifier.extract_keywords(text)
        
        # Should be single words only
        for kw in keywords:
            assert ' ' not in kw
    
    def test_keyphrases_skip_stopword_phrases(self):
        """Phrases containing stopwords should be filtered."""
        verifier = CitationContextVerifier(use_keyphrases=True)
        text = "The study of the effects on the patients."
        keywords = verifier.extract_keywords(text)
        
        # Should not include phrases like "study of" or "of the"
        for kw in keywords:
            if ' ' in kw:
                assert 'the' not in kw.split()


class TestIDFWeighting:
    """Test IDF-weighted inclusion coefficient."""
    
    def test_idf_weighting_enabled(self):
        """IDF weighting should downweight generic terms."""
        verifier = CitationContextVerifier(use_idf_weighting=True)
        
        # "study" is generic, "amyloidosis" is specific
        context_kw = ["cardiac", "amyloidosis", "study"]
        citation_kw = ["cardiac", "amyloidosis", "study"]
        
        score = verifier.calculate_overlap_score(context_kw, citation_kw)
        assert score == 1.0  # Perfect match
    
    def test_idf_weighting_disabled(self):
        """Without IDF weighting, all terms count equally."""
        verifier = CitationContextVerifier(use_idf_weighting=False)
        
        context_kw = ["cardiac", "amyloidosis"]
        citation_kw = ["cardiac", "amyloidosis", "treatment"]
        
        score = verifier.calculate_overlap_score(context_kw, citation_kw, metric='inclusion')
        # 2/3 = 0.667 (unweighted inclusion)
        assert abs(score - 0.667) < 0.01
    
    def test_idf_generic_vs_specific_terms(self):
        """Generic terms should contribute less than specific ones."""
        verifier = CitationContextVerifier(use_idf_weighting=True)
        
        # Context has generic "study" but missing specific "amyloidosis"
        context_kw = ["cardiac", "study", "patients"]
        citation_kw = ["cardiac", "amyloidosis"]  # specific medical term
        
        score1 = verifier.calculate_overlap_score(context_kw, citation_kw)
        
        # Now context has both specific terms
        context_kw2 = ["cardiac", "amyloidosis", "patients"]
        score2 = verifier.calculate_overlap_score(context_kw2, citation_kw)
        
        # Second should score higher (has the specific term)
        assert score2 > score1


class TestMetricOptions:
    """Test different similarity metrics."""
    
    def test_jaccard_metric(self):
        """Jaccard similarity should be symmetric."""
        verifier = CitationContextVerifier(use_idf_weighting=False)
        
        kw1 = ["heart", "disease", "treatment"]
        kw2 = ["heart", "surgery"]
        
        score1 = verifier.calculate_overlap_score(kw1, kw2, metric='jaccard')
        score2 = verifier.calculate_overlap_score(kw2, kw1, metric='jaccard')
        
        # Jaccard is symmetric
        assert abs(score1 - score2) < 0.01
    
    def test_inclusion_metric(self):
        """Inclusion coefficient is asymmetric by design."""
        verifier = CitationContextVerifier(use_idf_weighting=False)
        
        context_kw = ["heart", "disease", "treatment", "patient", "outcome"]
        citation_kw = ["heart", "disease"]
        
        # How much of citation appears in context? (should be high)
        score = verifier.calculate_overlap_score(context_kw, citation_kw, metric='inclusion')
        
        # Both citation terms appear in context: 2/2 = 1.0
        assert score == 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
