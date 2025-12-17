"""Duplicate Citation Detector Module.

Detects and manages duplicate citations using:
- Exact identifier matching
- Fuzzy title matching
- Author/year heuristics
"""

import re
import hashlib
from dataclasses import dataclass
from typing import Optional, List, Dict, Any, Tuple, Set
from difflib import SequenceMatcher
from loguru import logger


@dataclass
class DuplicateMatch:
    """A potential duplicate match."""
    original_id: str
    duplicate_id: str
    match_type: str  # 'exact_doi', 'exact_pmid', 'fuzzy_title', 'author_year'
    confidence: float  # 0.0 to 1.0
    original_title: str
    duplicate_title: str
    reason: str


class DuplicateDetector:
    """
    Detects duplicate citations using multiple strategies.
    """
    
    # Words to ignore when comparing titles
    STOP_WORDS = {
        'a', 'an', 'the', 'of', 'in', 'on', 'for', 'to', 'and', 'or', 'with',
        'from', 'by', 'at', 'as', 'is', 'are', 'was', 'were', 'be', 'been',
        'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
        'could', 'should', 'may', 'might', 'can', 'this', 'that', 'these',
        'those', 'it', 'its', 'their', 'our', 'your'
    }
    
    def __init__(
        self, 
        title_threshold: float = 0.85,
        author_threshold: float = 0.7
    ):
        """
        Initialize the duplicate detector.
        
        Args:
            title_threshold: Similarity threshold for title matching (0-1)
            author_threshold: Similarity threshold for author matching (0-1)
        """
        self.title_threshold = title_threshold
        self.author_threshold = author_threshold
        
        # Cache for normalized strings
        self._cache: Dict[str, str] = {}
    
    def find_duplicates(
        self, 
        citations: List[Dict[str, Any]]
    ) -> List[DuplicateMatch]:
        """
        Find all duplicates in a list of citations.
        
        Args:
            citations: List of citation dictionaries with 'id', 'title', 'authors', 
                      'year', 'doi', 'pmid' keys
        
        Returns:
            List of DuplicateMatch objects
        """
        duplicates = []
        seen_dois: Dict[str, str] = {}  # doi -> id
        seen_pmids: Dict[str, str] = {}  # pmid -> id
        seen_titles: List[Tuple[str, str, str, str]] = []  # (id, title, authors, year)
        
        for citation in citations:
            cid = str(citation.get('id', ''))
            doi = citation.get('doi', '')
            pmid = citation.get('pmid', '')
            title = citation.get('title', '')
            authors = citation.get('authors', [])
            if isinstance(authors, str):
                authors = [authors]
            year = str(citation.get('year', ''))
            
            # Check exact DOI match
            if doi:
                normalized_doi = self._normalize_doi(doi)
                if normalized_doi in seen_dois:
                    duplicates.append(DuplicateMatch(
                        original_id=seen_dois[normalized_doi],
                        duplicate_id=cid,
                        match_type='exact_doi',
                        confidence=1.0,
                        original_title=title,
                        duplicate_title=title,
                        reason=f"Same DOI: {doi}"
                    ))
                    continue
                seen_dois[normalized_doi] = cid
            
            # Check exact PMID match
            if pmid:
                if pmid in seen_pmids:
                    duplicates.append(DuplicateMatch(
                        original_id=seen_pmids[pmid],
                        duplicate_id=cid,
                        match_type='exact_pmid',
                        confidence=1.0,
                        original_title=title,
                        duplicate_title=title,
                        reason=f"Same PMID: {pmid}"
                    ))
                    continue
                seen_pmids[pmid] = cid
            
            # Check fuzzy title match
            normalized_title = self._normalize_title(title)
            first_author = self._get_first_author_surname(authors)
            
            for prev_id, prev_title, prev_authors, prev_year in seen_titles:
                # Quick year filter
                if year and prev_year and year != prev_year:
                    continue
                
                # Check title similarity
                prev_normalized = self._normalize_title(prev_title)
                similarity = self._title_similarity(normalized_title, prev_normalized)
                
                if similarity >= self.title_threshold:
                    # Verify with author check if available
                    prev_first_author = self._get_first_author_surname(
                        prev_authors if isinstance(prev_authors, list) else [prev_authors]
                    )
                    
                    author_match = True
                    if first_author and prev_first_author:
                        author_match = self._author_similarity(
                            first_author, prev_first_author
                        ) >= self.author_threshold
                    
                    if author_match:
                        duplicates.append(DuplicateMatch(
                            original_id=prev_id,
                            duplicate_id=cid,
                            match_type='fuzzy_title',
                            confidence=similarity,
                            original_title=prev_title,
                            duplicate_title=title,
                            reason=f"Title similarity: {similarity:.0%}"
                        ))
                        break
            
            seen_titles.append((cid, title, authors, year))
        
        return duplicates
    
    def is_duplicate(
        self, 
        citation1: Dict[str, Any], 
        citation2: Dict[str, Any]
    ) -> Optional[DuplicateMatch]:
        """
        Check if two citations are duplicates.
        
        Returns:
            DuplicateMatch if duplicate, None otherwise
        """
        results = self.find_duplicates([citation1, citation2])
        return results[0] if results else None
    
    def find_in_existing(
        self, 
        new_citation: Dict[str, Any],
        existing_citations: List[Dict[str, Any]]
    ) -> List[DuplicateMatch]:
        """
        Check if a new citation duplicates any existing ones.
        
        Args:
            new_citation: The new citation to check
            existing_citations: List of existing citations
        
        Returns:
            List of matches with existing citations
        """
        all_citations = existing_citations + [new_citation]
        all_duplicates = self.find_duplicates(all_citations)
        
        new_id = str(new_citation.get('id', len(existing_citations)))
        return [d for d in all_duplicates if d.duplicate_id == new_id]
    
    def suggest_merge(
        self, 
        citation1: Dict[str, Any], 
        citation2: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Suggest a merged citation from two duplicates.
        
        Prefers citation1 but fills in missing data from citation2.
        """
        merged = dict(citation1)
        
        for key, value in citation2.items():
            if key not in merged or not merged[key]:
                merged[key] = value
            elif key == 'authors' and isinstance(value, list):
                # Prefer longer author list
                if len(value) > len(merged.get('authors', [])):
                    merged['authors'] = value
            elif key == 'abstract':
                # Prefer longer abstract
                if len(str(value)) > len(str(merged.get('abstract', ''))):
                    merged['abstract'] = value
        
        return merged
    
    def _normalize_doi(self, doi: str) -> str:
        """Normalize DOI for comparison."""
        doi = doi.lower().strip()
        doi = re.sub(r'^https?://(?:dx\.)?doi\.org/', '', doi)
        return doi
    
    def _normalize_title(self, title: str) -> str:
        """Normalize title for comparison."""
        if title in self._cache:
            return self._cache[title]
        
        normalized = title.lower()
        
        # Remove punctuation
        normalized = re.sub(r'[^\w\s]', ' ', normalized)
        
        # Remove extra whitespace
        normalized = ' '.join(normalized.split())
        
        # Remove stop words
        words = normalized.split()
        words = [w for w in words if w not in self.STOP_WORDS]
        normalized = ' '.join(words)
        
        self._cache[title] = normalized
        return normalized
    
    def _title_similarity(self, title1: str, title2: str) -> float:
        """Calculate similarity between two normalized titles."""
        if not title1 or not title2:
            return 0.0
        
        # Use SequenceMatcher for fuzzy matching
        return SequenceMatcher(None, title1, title2).ratio()
    
    def _get_first_author_surname(self, authors: List[str]) -> str:
        """Extract first author's surname."""
        if not authors:
            return ""
        
        first = authors[0]
        
        # Handle "Surname, Given" format
        if ',' in first:
            return first.split(',')[0].strip().lower()
        
        # Handle "Given Surname" format
        parts = first.split()
        if parts:
            return parts[-1].strip().lower()
        
        return first.lower()
    
    def _author_similarity(self, author1: str, author2: str) -> float:
        """Calculate similarity between two author names."""
        if not author1 or not author2:
            return 0.0
        
        # Normalize
        a1 = re.sub(r'[^\w]', '', author1.lower())
        a2 = re.sub(r'[^\w]', '', author2.lower())
        
        # Exact match
        if a1 == a2:
            return 1.0
        
        # Prefix match (for abbreviated names)
        if a1.startswith(a2) or a2.startswith(a1):
            return 0.9
        
        # Fuzzy match
        return SequenceMatcher(None, a1, a2).ratio()
    
    def generate_fingerprint(self, citation: Dict[str, Any]) -> str:
        """
        Generate a fingerprint for a citation.
        
        Useful for quick duplicate detection.
        """
        title = self._normalize_title(citation.get('title', ''))
        year = str(citation.get('year', ''))
        authors = citation.get('authors', [])
        first_author = self._get_first_author_surname(
            authors if isinstance(authors, list) else [authors]
        )
        
        fingerprint = f"{first_author}:{year}:{title[:50]}"
        return hashlib.md5(fingerprint.encode()).hexdigest()[:16]

