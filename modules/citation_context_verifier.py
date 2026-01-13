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
5. Optionally use LLM for deep verification of flagged items
"""

import re
import string
import json
import math
from collections import Counter
from dataclasses import dataclass, field
from typing import List, Set, Tuple, Optional, Dict, Any
from enum import Enum
import requests
from loguru import logger


class ConcernLevel(Enum):
    """Classification of mismatch concern level."""
    HIGH = "high"       # 0.00 - 0.05: Very low overlap
    MODERATE = "moderate"  # 0.05 - 0.15: May be mismatched
    LOW = "low"         # 0.15 - 0.30: Likely fine
    NONE = "none"       # > 0.30: Good match


@dataclass
class ContextMismatch:
    """A citation that may not match its surrounding context."""
    line_number: int
    citation_tag: str
    surrounding_text: str
    citation_text: str
    citation_keywords: List[str]
    context_keywords: List[str]
    overlap_score: float  # 0-1, higher = better match
    concern_level: ConcernLevel
    llm_verification: Optional[Dict[str, Any]] = None  # LLM deep verification results
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "line_number": self.line_number,
            "citation_tag": self.citation_tag,
            "surrounding_text": self.surrounding_text[:200] + "..." if len(self.surrounding_text) > 200 else self.surrounding_text,
            "citation_keywords": self.citation_keywords[:10],
            "context_keywords": self.context_keywords[:10],
            "overlap_score": round(self.overlap_score, 3),
            "concern_level": self.concern_level.value,
            "llm_verification": self.llm_verification,
        }


@dataclass
class VerificationStats:
    """Statistics for tracking verification effectiveness over time."""
    total_documents_processed: int = 0
    total_citations_verified: int = 0
    mismatches_flagged: int = 0
    confirmed_after_llm: int = 0
    false_positives_marked: int = 0  # User marked as "actually correct"
    
    def to_dict(self) -> Dict:
        return {
            "total_documents_processed": self.total_documents_processed,
            "total_citations_verified": self.total_citations_verified,
            "mismatches_flagged": self.mismatches_flagged,
            "confirmed_after_llm": self.confirmed_after_llm,
            "false_positives_marked": self.false_positives_marked,
        }


# Common stopwords to exclude (language-agnostic basics)
# These are LANGUAGE BASICS only - NO domain-specific terms
STOPWORDS = {
    # English articles and prepositions
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
    'being', 'same', 'own', 'now', 'very', 'even', 'because', 'while',
    'whether', 'either', 'neither', 'much', 'many', 'however', 'therefore',
    'thus', 'hence', 'still', 'yet', 'already', 'always', 'never', 'often',
    'sometimes', 'usually', 'perhaps', 'maybe', 'probably', 'certainly',
    # Common citation/reference words to ignore
    'et', 'al', 'doi', 'pmid', 'vol', 'pp', 'ed', 'eds', 'available', 'accessed',
    'retrieved', 'http', 'https', 'www', 'org', 'com', 'edu', 'gov', 'pubmed',
    'ncbi', 'nlm', 'nih', 'journal', 'article', 'review', 'study', 'studies',
    'research', 'results', 'conclusion', 'conclusions', 'methods', 'method',
    # Numbers and common patterns
    'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten',
    'first', 'second', 'third', 'using', 'based', 'including', 'include', 'includes',
}


class CitationContextVerifier:
    """
    Verify citations match their surrounding text context.
    
    Uses DYNAMIC keyword extraction - works on ANY domain.
    Does NOT use hardcoded topic lists.
    """
    
    # Thresholds for concern levels
    # Thresholds for Concern Levels (Adjusted for Inclusion Coefficient)
    HIGH_CONCERN_THRESHOLD = 0.10      # < 10% of citation keywords found in context
    MODERATE_CONCERN_THRESHOLD = 0.30  # < 30% of citation keywords found in context
    LOW_CONCERN_THRESHOLD = 0.50       # < 50% found (Weak match)
    
    # LLM Configuration
    OLLAMA_URL = "http://localhost:11434/api/generate"
    GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
    DEFAULT_LOCAL_MODEL = "deepseek-r1:latest"
    FALLBACK_LOCAL_MODELS = ["qwen2.5:32b-instruct", "llama3:8b"]
    GROQ_MODEL = "deepseek-r1-distill-llama-70b"  # DeepSeek R1 on Groq
    
    # Conservative lemmatization rules (suffix removal) - no external dependencies
    # Only apply rules that are very reliable to avoid over-stemming
    LEMMA_RULES = [
        (r'ies$', 'y'),      # studies -> study, therapies -> therapy
        (r'ves$', 'f'),      # leaves -> leaf
        (r'ches$', 'ch'),    # watches -> watch
        (r'shes$', 'sh'),    # dishes -> dish
        (r'xes$', 'x'),      # boxes -> box
        (r'ings$', 'ing'),   # findings -> finding
        (r's$', ''),         # cats -> cat (last resort, plural removal)
    ]
    
    # Words to never lemmatize (technical/medical terms that look like suffixed words)
    LEMMA_EXCEPTIONS = {
        'amyloidosis', 'diagnosis', 'prognosis', 'analysis', 'synthesis',
        'fibrosis', 'sclerosis', 'stenosis', 'thrombosis', 'necrosis',
        'studies', 'series', 'species', 'process', 'class', 'cases',
        'stress', 'mass', 'bias', 'atlas', 'basis', 'thesis', 'crisis',
        'serious', 'nervous', 'previous', 'obvious', 'various', 'numerous',
    }
    
    def __init__(
        self,
        min_word_length: int = 3,
        top_keywords: int = 15,
        groq_api_key: Optional[str] = None,
        use_lemmatization: bool = True,
        use_keyphrases: bool = True,
        use_idf_weighting: bool = True
    ):
        """
        Initialize verifier.
        
        Args:
            min_word_length: Minimum word length to consider as keyword
            top_keywords: Number of top keywords to extract per text
            groq_api_key: Optional Groq API key for cloud LLM fallback
            use_lemmatization: Apply lemmatization to reduce word variants
            use_keyphrases: Extract n-grams/phrases in addition to unigrams
            use_idf_weighting: Use IDF weighting for better term specificity
        """
        self.min_word_length = min_word_length
        self.top_keywords = top_keywords
        self.groq_api_key = groq_api_key
        self.use_lemmatization = use_lemmatization
        self.use_keyphrases = use_keyphrases
        self.use_idf_weighting = use_idf_weighting
        self.stats = VerificationStats()
        self._idf_cache: Dict[str, float] = {}
        self._document_term_counts: Counter = Counter()
    
    def _lemmatize(self, word: str) -> str:
        """Apply conservative rule-based lemmatization to reduce word variants."""
        if len(word) < 4:  # Don't lemmatize short words
            return word
        
        # Check exceptions (technical terms that look like suffixed words)
        if word.lower() in self.LEMMA_EXCEPTIONS:
            return word
        
        for pattern, replacement in self.LEMMA_RULES:
            new_word = re.sub(pattern, replacement, word)
            if new_word != word and len(new_word) >= 3:
                return new_word
        return word
    
    def _extract_keyphrases(self, text: str, max_ngram: int = 3) -> List[str]:
        """
        Extract meaningful n-gram phrases from text.
        
        Looks for patterns like:
        - Noun phrases: "cardiac amyloidosis", "heart failure"
        - Technical terms: "machine learning", "deep neural network"
        """
        # Clean text but preserve word boundaries
        clean_text = text.lower()
        clean_text = re.sub(r'[^\w\s-]', ' ', clean_text)
        words = clean_text.split()
        
        # Words that typically don't form good phrase boundaries
        skip_words = STOPWORDS | {
            'affect', 'affects', 'affecting', 'affected',
            'include', 'includes', 'including', 'included',
            'show', 'shows', 'showing', 'showed',
            'use', 'uses', 'using', 'used',
            'has', 'have', 'had', 'having',
            'is', 'are', 'was', 'were', 'been', 'being',
        }
        
        keyphrases = []
        
        # Extract 2-grams and 3-grams
        for n in range(2, max_ngram + 1):
            for i in range(len(words) - n + 1):
                phrase_words = words[i:i + n]
                
                # Skip if any word is a stopword, too short, or a skip word
                if any(w in skip_words or len(w) < 3 for w in phrase_words):
                    continue
                
                # Skip phrases that start or end with verbs/prepositions
                if phrase_words[0] in skip_words or phrase_words[-1] in skip_words:
                    continue
                
                # Skip if any word is just a number or starts with digit
                if any(w.isdigit() or re.match(r'^\d', w) for w in phrase_words):
                    continue
                
                phrase = ' '.join(phrase_words)
                keyphrases.append(phrase)
        
        return keyphrases
    
    def extract_keywords(self, text: str, include_phrases: bool = None) -> List[str]:
        """
        Extract significant keywords and keyphrases from text.
        
        Enhanced with:
        - Lemmatization (reduces diagnose/diagnosis/diagnostic variants)
        - Keyphrase extraction (captures "cardiac amyloidosis" as single term)
        - Frequency-based ranking with stopword removal
        
        Works on any language/domain.
        
        Args:
            text: Any text to extract keywords from
            include_phrases: Override instance setting for keyphrase extraction
            
        Returns:
            List of significant keywords/keyphrases (lowercase)
        """
        if not text:
            return []
        
        use_phrases = include_phrases if include_phrases is not None else self.use_keyphrases
        
        # Lowercase and remove punctuation for unigrams
        clean_text = text.lower()
        clean_text = clean_text.translate(str.maketrans('', '', string.punctuation))
        
        # Split into words
        words = clean_text.split()
        
        # Filter: remove stopwords, short words, and numbers
        filtered = [
            w for w in words
            if w not in STOPWORDS
            and len(w) >= self.min_word_length
            and not w.isdigit()
            and not re.match(r'^\d', w)  # Doesn't start with digit
        ]
        
        # Apply lemmatization if enabled
        if self.use_lemmatization:
            filtered = [self._lemmatize(w) for w in filtered]
        
        # Count unigram frequencies
        word_counts = Counter(filtered)
        
        # Extract keyphrases if enabled
        phrase_counts: Counter = Counter()
        if use_phrases:
            keyphrases = self._extract_keyphrases(text)
            # Apply lemmatization to phrase components
            if self.use_lemmatization:
                lemmatized_phrases = []
                for phrase in keyphrases:
                    lemma_phrase = ' '.join(self._lemmatize(w) for w in phrase.split())
                    lemmatized_phrases.append(lemma_phrase)
                keyphrases = lemmatized_phrases
            phrase_counts = Counter(keyphrases)
        
        # Combine: include BOTH keyphrases AND high-frequency unigrams
        # This allows matching at both phrase and word level
        results = []
        added_unigrams = set()
        
        # Add top keyphrases first (more specific, help with precision)
        phrase_slots = self.top_keywords // 2
        for phrase, count in phrase_counts.most_common(phrase_slots):
            if count >= 1:  # At least one occurrence
                results.append(phrase)
        
        # ALWAYS add top unigrams (critical for recall/overlap matching)
        # Don't skip unigrams just because they appear in phrases
        unigram_slots = self.top_keywords - len(results)
        for word, _ in word_counts.most_common(unigram_slots):
            if word not in added_unigrams:
                results.append(word)
                added_unigrams.add(word)
                if len(results) >= self.top_keywords:
                    break
        
        return results[:self.top_keywords]
    
    def _compute_idf(self, term: str, document_corpus: Optional[List[str]] = None) -> float:
        """
        Compute IDF (Inverse Document Frequency) for a term.
        
        Uses cached values when available, or computes from document context.
        Higher IDF = more specific/discriminative term.
        """
        if term in self._idf_cache:
            return self._idf_cache[term]
        
        # Default IDF based on term characteristics (heuristic when no corpus)
        # Generic academic terms get lower IDF
        generic_terms = {
            'study', 'studies', 'research', 'analysis', 'review', 'report',
            'results', 'method', 'methods', 'approach', 'data', 'model',
            'system', 'process', 'effect', 'effects', 'factor', 'factors',
            'patient', 'patients', 'case', 'cases', 'group', 'groups',
            'treatment', 'outcomes', 'findings', 'conclusion', 'background',
            'introduction', 'discussion', 'material', 'materials',
        }
        
        # Assign IDF scores based on term specificity
        if term in generic_terms or any(term in g for g in generic_terms):
            idf = 1.0  # Low IDF for generic terms
        elif len(term) > 10:  # Longer terms tend to be more specific
            idf = 3.0
        elif ' ' in term:  # Phrases are typically more specific
            idf = 2.5
        else:
            idf = 2.0  # Default for normal terms
        
        self._idf_cache[term] = idf
        return idf
    
    def calculate_overlap_score(
        self, 
        context_keywords: List[str], 
        citation_keywords: List[str], 
        metric: str = 'inclusion'
    ) -> float:
        """
        Calculate keyword overlap score between context and citation keywords.
        
        Supports multiple metrics:
        - 'jaccard': Standard Jaccard similarity (symmetric)
        - 'inclusion': Inclusion coefficient (asymmetric, favors citation coverage)
        - 'idf_inclusion': IDF-weighted inclusion (recommended for best results)
        
        Args:
            context_keywords: Keywords from surrounding text
            citation_keywords: Keywords from citation definition
            metric: Similarity metric to use
        
        Returns:
            Float 0-1 (1 = perfect match)
        """
        if not context_keywords or not citation_keywords:
            return 0.0
        
        context_set = set(context_keywords)
        citation_set = set(citation_keywords)
        
        intersection = context_set & citation_set
        
        if metric == 'idf_inclusion' or (metric == 'inclusion' and self.use_idf_weighting):
            # IDF-weighted Inclusion Coefficient
            # Score = sum(IDF of matched citation terms) / sum(IDF of all citation terms)
            if not citation_keywords:
                return 0.0
            
            matched_idf_sum = sum(self._compute_idf(term) for term in intersection)
            total_idf_sum = sum(self._compute_idf(term) for term in citation_set)
            
            if total_idf_sum == 0:
                return 0.0
            
            return matched_idf_sum / total_idf_sum
            
        elif metric == 'inclusion':
            # Standard Inclusion Coefficient (unweighted)
            # What fraction of citation keywords appear in context?
            return len(intersection) / len(citation_set)
            
        else:
            # Default Jaccard similarity
            union = context_set | citation_set
            if len(union) == 0:
                return 0.0
            return len(intersection) / len(union)
    
    def classify_concern_level(self, overlap_score: float) -> ConcernLevel:
        """Classify overlap score into concern level."""
        if overlap_score < self.HIGH_CONCERN_THRESHOLD:
            return ConcernLevel.HIGH
        elif overlap_score < self.MODERATE_CONCERN_THRESHOLD:
            return ConcernLevel.MODERATE
        elif overlap_score < self.LOW_CONCERN_THRESHOLD:
            return ConcernLevel.LOW
        else:
            return ConcernLevel.NONE
    
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
            if re.match(r'^#{1,3}\s*(References|Bibliography|Citations|Works Cited|Sources|Endnotes)', line, re.I):
                ref_start = i
                break
        
        body_lines = lines[:ref_start]
        
        for i, line in enumerate(body_lines):
            # Find all citation references in this line
            for match in re.finditer(r'\[\^([^\]]+)\]', line):
                tag = f"[^{match.group(1)}]"
                
                # Get surrounding context
                start = max(0, i - context_lines)
                end = min(len(body_lines), i + context_lines + 1)
                context = ' '.join(body_lines[start:end]).strip()
                
                contexts.append((i + 1, tag, context))
        
        return contexts
    
    def get_citation_definition(self, tag: str, content: str) -> Optional[str]:
        """Get the full definition text for a citation tag."""
        # Escape special regex characters in tag
        escaped_tag = re.escape(tag)
        # Match definition: [^tag]: content (until next definition or end)
        pattern = escaped_tag + r':\s*(.+?)(?=\n\[\^|\n\n|\Z)'
        
        match = re.search(pattern, content, re.DOTALL)
        return match.group(1).strip() if match else None
    
    def verify_citations(
        self, 
        content: str, 
        deep_verify: bool = False,
        flag_threshold: float = None
    ) -> List[ContextMismatch]:
        """
        Verify all citations match their context using keyword overlap.
        
        Args:
            content: Full document content (any domain)
            deep_verify: Use LLM for deep verification of flagged items
            flag_threshold: Override default threshold for flagging (default: 0.15)
            
        Returns:
            List of potential mismatches (HIGH and MODERATE concern only)
        """
        logger.info("Verifying citation contexts (domain-agnostic)")
        
        if flag_threshold is None:
            flag_threshold = self.MODERATE_CONCERN_THRESHOLD
        
        mismatches = []
        all_contexts = self.extract_citation_contexts(content)
        
        logger.debug(f"Found {len(all_contexts)} citations to verify")
        self.stats.total_citations_verified += len(all_contexts)
        
        for line_num, tag, surrounding_text in all_contexts:
            # Get citation definition
            definition = self.get_citation_definition(tag, content)
            if not definition:
                logger.debug(f"No definition found for {tag}")
                continue
            
            # Extract keywords from both
            citation_keywords = self.extract_keywords(definition)
            context_keywords = self.extract_keywords(surrounding_text)
            
            # Calculate overlap using Inclusion Metric (Citation words IN Context)
            # keywords1 is Context, keywords2 is Citation
            # We want denom to be len(citation_keywords) effectively
            overlap = self.calculate_overlap_score(
                context_keywords, 
                citation_keywords, 
                metric='inclusion'
            )
            concern = self.classify_concern_level(overlap)
            
            # Only flag HIGH and MODERATE concern
            if overlap < flag_threshold and citation_keywords and context_keywords:
                mismatch = ContextMismatch(
                    line_number=line_num,
                    citation_tag=tag,
                    surrounding_text=surrounding_text,
                    citation_text=definition[:300],  # Truncate for report
                    citation_keywords=citation_keywords[:10],
                    context_keywords=context_keywords[:10],
                    overlap_score=overlap,
                    concern_level=concern,
                )
                
                # Deep verification with LLM if requested
                if deep_verify and concern in (ConcernLevel.HIGH, ConcernLevel.MODERATE):
                    llm_result = self._llm_verify(
                        surrounding_text, 
                        definition, 
                        tag
                    )
                    mismatch.llm_verification = llm_result
                    if llm_result and llm_result.get('is_mismatch'):
                        self.stats.confirmed_after_llm += 1
                
                mismatches.append(mismatch)
                logger.debug(
                    f"Potential mismatch at line {line_num}: "
                    f"{tag} (overlap: {overlap:.2%}, concern: {concern.value})"
                )
        
        self.stats.mismatches_flagged += len(mismatches)
        logger.info(f"Context verification complete: {len(mismatches)} potential mismatches")
        return mismatches
    
    def _llm_verify(
        self, 
        context: str, 
        citation: str, 
        tag: str
    ) -> Optional[Dict[str, Any]]:
        """
        Use LLM to verify if a citation matches its context.
        
        Tries local Ollama first, falls back to Groq.
        
        Returns:
            Dict with 'is_mismatch', 'confidence', 'reasoning'
        """
        prompt = f"""You are a citation verification expert. Analyze whether the following citation is appropriate for its surrounding context.

CONTEXT (where the citation appears):
{context[:1000]}

CITATION BEING REFERENCED ({tag}):
{citation[:1500]}

TASK: Determine if this citation is appropriate for this context.

Consider:
1. Does the citation's topic match what's being discussed in the context?
2. Are the key concepts aligned?
3. Could this be a case of citation being placed in the wrong paragraph?

IMPORTANT: You must respond with ONLY a JSON object at the very end of your response.
If you need to think through the problem, put your thoughts in <think></think> tags BEFORE the JSON.

Example format:
<think>Let me analyze this citation...</think>
{{"is_mismatch": false, "confidence": 0.85, "reasoning": "The citation matches the context"}}

Your JSON response (required fields: is_mismatch, confidence, reasoning):"""

        # Try local Ollama first
        result = self._call_ollama(prompt)
        if result:
            return result
        
        # Fall back to Groq if available
        if self.groq_api_key:
            result = self._call_groq(prompt)
            if result:
                return result
        
        logger.warning("LLM verification unavailable - skipping deep verify")
        return None
    
    def _call_ollama(self, prompt: str) -> Optional[Dict[str, Any]]:
        """Call local Ollama for LLM inference.
        
        Tries multiple models in order, with robust error handling for:
        - Connection errors (Ollama not running)
        - Timeouts (model too slow)
        - HTTP errors (model not found, server errors)
        - Invalid responses (malformed JSON, missing fields)
        """
        models_to_try = [self.DEFAULT_LOCAL_MODEL] + self.FALLBACK_LOCAL_MODELS
        
        # Adaptive timeout: shorter for smaller models, longer for reasoning models
        base_timeout = 45  # Reduced from 60s for better UX
        
        for model in models_to_try:
            # Reasoning models need longer timeout
            timeout = base_timeout * 2 if 'r1' in model.lower() or '32b' in model.lower() else base_timeout
            
            try:
                response = requests.post(
                    self.OLLAMA_URL,
                    json={
                        "model": model,
                        "prompt": prompt,
                        "stream": False,
                        "options": {
                            "temperature": 0.1,
                            "num_predict": 800,  # Increased for reasoning + JSON
                        }
                    },
                    timeout=timeout
                )
                
                # Handle various HTTP status codes
                if response.status_code == 200:
                    result = response.json()
                    text = result.get('response', '')
                    if text:
                        parsed = self._parse_llm_response(text)
                        if parsed:
                            logger.debug(f"Ollama success with model {model}")
                            return parsed
                        else:
                            logger.debug(f"Ollama {model} returned unparseable response")
                            continue  # Try next model
                elif response.status_code == 404:
                    logger.debug(f"Ollama model {model} not found, trying next")
                    continue
                elif response.status_code >= 500:
                    logger.warning(f"Ollama server error ({response.status_code}) with model {model}")
                    continue
                else:
                    logger.debug(f"Ollama unexpected status {response.status_code} for {model}")
                    continue
                    
            except requests.exceptions.ConnectionError:
                logger.debug(f"Ollama not running or unreachable")
                break  # No point trying other models if Ollama isn't running
            except requests.exceptions.Timeout:
                logger.warning(f"Ollama timeout ({timeout}s) with model {model}")
                continue  # Try a smaller/faster model
            except requests.exceptions.RequestException as e:
                logger.debug(f"Ollama request error with {model}: {e}")
                continue
            except Exception as e:
                logger.debug(f"Ollama unexpected error with {model}: {e}")
                continue
        
        logger.debug("Ollama not available or all models failed")
        return None
    
    def _call_groq(self, prompt: str) -> Optional[Dict[str, Any]]:
        """Call Groq API for cloud LLM inference."""
        if not self.groq_api_key:
            return None
        
        try:
            response = requests.post(
                self.GROQ_URL,
                headers={
                    "Authorization": f"Bearer {self.groq_api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": self.GROQ_MODEL,
                    "messages": [
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.1,
                    "max_tokens": 500,
                },
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                text = result.get('choices', [{}])[0].get('message', {}).get('content', '')
                return self._parse_llm_response(text)
            else:
                logger.warning(f"Groq API error: {response.status_code}")
                return None
                
        except Exception as e:
            logger.warning(f"Groq API error: {e}")
            return None
    
    def _parse_llm_response(self, text: str) -> Optional[Dict[str, Any]]:
        """Parse LLM JSON response, handling thinking/reasoning model outputs.
        
        Reasoning models like DeepSeek-R1 may include <think>...</think> blocks
        before the JSON response. This method strips those and extracts the last
        valid JSON object to avoid matching JSON-like structures in the reasoning.
        """
        try:
            # Strip thinking blocks first (DeepSeek-R1, o1, etc.)
            text_clean = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL | re.IGNORECASE)
            # Also handle <thinking> variant
            text_clean = re.sub(r'<thinking>.*?</thinking>', '', text_clean, flags=re.DOTALL | re.IGNORECASE)
            # Strip any remaining XML-like tags that might contain JSON-like content
            text_clean = re.sub(r'<[^>]+>.*?</[^>]+>', '', text_clean, flags=re.DOTALL)
            
            # Find ALL JSON-like objects and use the LAST one (avoids matching preamble)
            json_candidates = re.findall(r'\{[^{}]*\}', text_clean, re.DOTALL)
            
            if not json_candidates:
                # Fallback: try the original text
                json_candidates = re.findall(r'\{[^{}]*\}', text, re.DOTALL)
            
            if not json_candidates:
                logger.debug(f"No JSON found in LLM response: {text[:200]}...")
                return None
            
            # Try candidates from last to first (most likely to be the actual response)
            for candidate in reversed(json_candidates):
                try:
                    data = json.loads(candidate)
                    # Validate required fields exist
                    if 'is_mismatch' in data or 'confidence' in data:
                        return {
                            "is_mismatch": bool(data.get('is_mismatch', False)),
                            "confidence": float(data.get('confidence', 0.5)),
                            "reasoning": str(data.get('reasoning', '')),
                        }
                except json.JSONDecodeError:
                    continue
            
            logger.debug(f"No valid JSON with required fields in response: {text[:200]}...")
            return None
            
        except Exception as e:
            logger.debug(f"Failed to parse LLM response: {e}")
            return None
    
    def format_mismatch_report(
        self, 
        mismatches: List[ContextMismatch],
        include_llm: bool = True
    ) -> str:
        """Format mismatches into a readable markdown report."""
        if not mismatches:
            return "✅ **All citations appear to match their context.**"
        
        lines = [
            f"## ⚠️ Potential Context Mismatches ({len(mismatches)} found)",
            "",
            "These citations have low keyword overlap with their surrounding text.",
            "Review manually to confirm they are appropriate for the context.",
            "",
        ]
        
        # Group by concern level
        high_concern = [m for m in mismatches if m.concern_level == ConcernLevel.HIGH]
        moderate_concern = [m for m in mismatches if m.concern_level == ConcernLevel.MODERATE]
        
        if high_concern:
            lines.append("### 🔴 High Concern (very low overlap)")
            lines.append("")
            for m in high_concern:
                self._format_single_mismatch(m, lines, include_llm)
        
        if moderate_concern:
            lines.append("### 🟡 Moderate Concern")
            lines.append("")
            for m in moderate_concern:
                self._format_single_mismatch(m, lines, include_llm)
        
        return "\n".join(lines)
    
    def _format_single_mismatch(
        self, 
        m: ContextMismatch, 
        lines: List[str],
        include_llm: bool
    ) -> None:
        """Format a single mismatch entry."""
        lines.extend([
            f"**Line {m.line_number}**: `{m.citation_tag}`",
            f"- Overlap score: **{m.overlap_score:.1%}**",
            f"- Citation keywords: {', '.join(m.citation_keywords[:5])}",
            f"- Context keywords: {', '.join(m.context_keywords[:5])}",
        ])
        
        # Truncate context for display
        context_preview = m.surrounding_text[:150].replace('\n', ' ')
        lines.append(f"- Context: \"{context_preview}...\"")
        
        # Add LLM verification if available
        if include_llm and m.llm_verification:
            llm = m.llm_verification
            status = "🔴 Likely mismatch" if llm.get('is_mismatch') else "🟢 Likely OK"
            lines.append(f"- **LLM Assessment:** {status} (confidence: {llm.get('confidence', 0):.0%})")
            if llm.get('reasoning'):
                lines.append(f"- *{llm.get('reasoning')[:200]}*")
        
        lines.append("")


# Convenience function for quick verification
def verify_citation_contexts(
    content: str, 
    deep_verify: bool = False,
    groq_api_key: Optional[str] = None
) -> List[ContextMismatch]:
    """
    Quick verification of citation contexts.
    
    Args:
        content: Markdown document content
        deep_verify: Use LLM for deep verification
        groq_api_key: Optional Groq API key for cloud LLM
        
    Returns:
        List of potential mismatches
    """
    verifier = CitationContextVerifier(groq_api_key=groq_api_key)
    return verifier.verify_citations(content, deep_verify=deep_verify)
