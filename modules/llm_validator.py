"""
LLM-based Metadata Validator for Citation Extraction

This module uses a local LLM (via Ollama) to validate and improve metadata
extracted by regex-based methods. It acts as a quality control layer.

Architecture:
    1. Regex/microdata extraction produces candidate metadata
    2. LLM validates: Are these real author names? Is this the main article date?
    3. LLM can suggest corrections or flag suspicious values

Benefits over pure regex:
    - Catches semantic errors (e.g., "EM Resident" is not a person name)
    - Handles context (related article dates vs main article)
    - Adapts to new layouts without code changes
"""

import json
import re
import requests
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple
from loguru import logger


@dataclass
class ValidationResult:
    """Result of LLM validation."""
    is_valid: bool
    confidence: float  # 0.0 to 1.0
    corrected_value: Optional[str] = None
    reason: str = ""


@dataclass
class MetadataValidationResult:
    """Complete validation result for all extracted metadata."""
    authors_valid: List[str] = field(default_factory=list)  # Validated author names
    authors_rejected: List[Tuple[str, str]] = field(default_factory=list)  # (name, reason)
    date_valid: bool = True
    date_corrected: Optional[str] = None
    date_rejection_reason: str = ""
    title_valid: bool = True
    title_corrected: Optional[str] = None
    overall_confidence: float = 1.0


class LLMValidator:
    """
    Validates extracted metadata using LLM.
    
    Uses Ollama for fast local inference. Falls back gracefully
    if Ollama is unavailable.
    """
    
    OLLAMA_URL = "http://localhost:11434/api/generate"
    DEFAULT_MODEL = "llama3:8b"  # Fast, good for validation
    TIMEOUT = 30  # seconds (validation should be quick)
    
    # Validation prompts
    AUTHOR_VALIDATION_PROMPT = """You are validating author names extracted from a webpage.

For each name, determine if it is a REAL PERSON'S NAME (valid) or NOT a person name (invalid).

INVALID examples:
- "EM Resident" (job title/publication name)
- "Staff Writer" (generic role)
- "Admin" or "Administrator" 
- "Editorial Board"
- Single words that are clearly not names
- Organization names

VALID examples:
- "John Smith" (first + last name)
- "Tara Knox" (first + last name)
- "Mark Olaf, DO" (name with credentials - credentials are OK)
- "J. Robert Smith" (with middle initial)
- "Mary Anne Johnson" (compound first name)

Names to validate:
{names}

Return ONLY valid JSON:
{{
  "valid": ["Name1", "Name2"],
  "invalid": [
    {{"name": "Invalid Name", "reason": "brief reason"}}
  ]
}}

Be strict - if uncertain, mark as invalid.
"""

    DATE_VALIDATION_PROMPT = """You are validating a publication date extracted from a webpage.

Context: The webpage URL is: {url}
The extracted date is: {date}
The page title is: {title}

Other dates found on the page (may be from related articles):
{other_dates}

Question: Is "{date}" likely the MAIN ARTICLE's publication date, or is it from:
- Related/recommended articles sidebar
- Footer/copyright notices
- Comments section
- Unrelated page elements

Return ONLY valid JSON:
{{
  "is_main_article_date": true/false,
  "confidence": 0.0-1.0,
  "reason": "brief explanation",
  "suggested_date": "YYYY-MM-DD or null if original is correct"
}}
"""

    TITLE_VALIDATION_PROMPT = """You are validating an article title extracted from a webpage.

URL: {url}
Extracted title: {title}

Common issues to check:
- Does it include the site name suffix? (e.g., "Article Title | Site Name")
- Is it a navigation element, not the article title?
- Is it truncated or incomplete?
- Does it make sense as an article title?

Return ONLY valid JSON:
{{
  "is_valid": true/false,
  "cleaned_title": "corrected title or original if valid",
  "reason": "brief explanation if invalid"
}}
"""

    def __init__(self, model: str = None, ollama_url: str = None):
        self.model = model or self.DEFAULT_MODEL
        self.ollama_url = ollama_url or self.OLLAMA_URL
        self._available = None  # Cached availability check
    
    def is_available(self) -> bool:
        """Check if Ollama is available for validation."""
        if self._available is not None:
            return self._available
        
        try:
            response = requests.get(
                self.ollama_url.replace('/api/generate', '/api/tags'),
                timeout=5
            )
            self._available = response.status_code == 200
        except:
            self._available = False
        
        if self._available:
            logger.info("LLM validator available via Ollama")
        else:
            logger.warning("LLM validator unavailable - validation will be skipped")
        
        return self._available
    
    def validate_authors(self, authors: List[str]) -> Tuple[List[str], List[Tuple[str, str]]]:
        """
        Validate a list of author names using LLM.
        
        Args:
            authors: List of candidate author names
            
        Returns:
            Tuple of (valid_authors, rejected_authors)
            where rejected_authors is list of (name, reason) tuples
        """
        if not authors:
            return [], []
        
        if not self.is_available():
            # Fallback: basic heuristic validation
            return self._validate_authors_heuristic(authors)
        
        try:
            prompt = self.AUTHOR_VALIDATION_PROMPT.format(
                names='\n'.join(f'- "{a}"' for a in authors)
            )
            
            response = self._call_ollama(prompt)
            if not response:
                return self._validate_authors_heuristic(authors)
            
            result = self._parse_json_response(response)
            if not result:
                return self._validate_authors_heuristic(authors)
            
            valid = result.get('valid', [])
            invalid_list = result.get('invalid', [])
            
            # Process invalid list
            rejected = []
            for item in invalid_list:
                if isinstance(item, dict):
                    rejected.append((item.get('name', ''), item.get('reason', 'LLM rejected')))
                elif isinstance(item, str):
                    rejected.append((item, 'LLM rejected'))
            
            logger.info(f"LLM author validation: {len(valid)} valid, {len(rejected)} rejected")
            return valid, rejected
            
        except Exception as e:
            logger.error(f"LLM author validation failed: {e}")
            return self._validate_authors_heuristic(authors)
    
    def _validate_authors_heuristic(self, authors: List[str]) -> Tuple[List[str], List[Tuple[str, str]]]:
        """Fallback heuristic validation when LLM is unavailable."""
        valid = []
        rejected = []
        
        # Common non-person patterns
        invalid_patterns = [
            r'^(em\s+)?resident$',
            r'^staff\s*(writer|editor)?$',
            r'^admin(istrator)?$',
            r'^editorial(\s+board)?$',
            r'^(the\s+)?editors?$',
            r'^contributor$',
            r'^guest\s+author$',
            r'^anonymous$',
            r'^unknown$',
            r'^\w+$',  # Single word (likely not a full name)
        ]
        
        for author in authors:
            author_lower = author.lower().strip()
            is_invalid = False
            
            for pattern in invalid_patterns:
                if re.match(pattern, author_lower, re.IGNORECASE):
                    rejected.append((author, f"Matches invalid pattern: {pattern}"))
                    is_invalid = True
                    break
            
            if not is_invalid:
                # Check for at least two word parts (first + last name)
                parts = author.split()
                if len(parts) < 2:
                    rejected.append((author, "Single word - likely not a full name"))
                else:
                    valid.append(author)
        
        return valid, rejected
    
    def validate_date(self, date: str, url: str, title: str, 
                      other_dates: List[str] = None) -> ValidationResult:
        """
        Validate if a date is from the main article or related content.
        
        Args:
            date: The extracted date (e.g., "2021", "2021-04-08")
            url: The webpage URL
            title: The article title
            other_dates: Other dates found on the page
            
        Returns:
            ValidationResult with confidence and potential correction
        """
        if not date:
            return ValidationResult(is_valid=False, confidence=0.0, reason="No date provided")
        
        if not self.is_available():
            # Fallback: assume valid if we got a date
            return ValidationResult(is_valid=True, confidence=0.7, reason="LLM unavailable, assuming valid")
        
        try:
            prompt = self.DATE_VALIDATION_PROMPT.format(
                url=url,
                date=date,
                title=title or "Unknown",
                other_dates='\n'.join(f'- {d}' for d in (other_dates or [])) or "None"
            )
            
            response = self._call_ollama(prompt)
            if not response:
                return ValidationResult(is_valid=True, confidence=0.5, reason="LLM response empty")
            
            result = self._parse_json_response(response)
            if not result:
                return ValidationResult(is_valid=True, confidence=0.5, reason="Could not parse LLM response")
            
            is_valid = result.get('is_main_article_date', True)
            confidence = float(result.get('confidence', 0.5))
            reason = result.get('reason', '')
            suggested = result.get('suggested_date')
            
            logger.info(f"LLM date validation: valid={is_valid}, confidence={confidence:.2f}")
            
            return ValidationResult(
                is_valid=is_valid,
                confidence=confidence,
                corrected_value=suggested if not is_valid else None,
                reason=reason
            )
            
        except Exception as e:
            logger.error(f"LLM date validation failed: {e}")
            return ValidationResult(is_valid=True, confidence=0.5, reason=f"Validation error: {e}")
    
    def validate_title(self, title: str, url: str) -> ValidationResult:
        """
        Validate and clean an article title.
        
        Args:
            title: The extracted title
            url: The webpage URL
            
        Returns:
            ValidationResult with potential cleaned title
        """
        if not title:
            return ValidationResult(is_valid=False, confidence=0.0, reason="No title provided")
        
        # Quick heuristic fixes (don't need LLM)
        cleaned = title
        
        # Remove common suffixes
        for sep in [' | ', ' - ', ' – ', ' — ']:
            if sep in cleaned:
                parts = cleaned.rsplit(sep, 1)
                if len(parts) == 2 and len(parts[1]) < 50:
                    cleaned = parts[0].strip()
        
        if cleaned != title:
            return ValidationResult(
                is_valid=True,
                confidence=0.9,
                corrected_value=cleaned,
                reason="Removed site name suffix"
            )
        
        return ValidationResult(is_valid=True, confidence=0.9, reason="Title looks valid")
    
    def validate_metadata(self, authors: List[str], date: str, title: str,
                          url: str, other_dates: List[str] = None) -> MetadataValidationResult:
        """
        Validate all extracted metadata at once.
        
        This is the main entry point for validation.
        
        Args:
            authors: List of extracted author names
            date: Extracted date
            title: Extracted title
            url: Webpage URL
            other_dates: Other dates found on the page
            
        Returns:
            MetadataValidationResult with all validation results
        """
        result = MetadataValidationResult()
        
        # Validate authors
        if authors:
            valid_authors, rejected_authors = self.validate_authors(authors)
            result.authors_valid = valid_authors
            result.authors_rejected = rejected_authors
        
        # Validate date
        if date:
            date_result = self.validate_date(date, url, title, other_dates)
            result.date_valid = date_result.is_valid
            result.date_corrected = date_result.corrected_value
            result.date_rejection_reason = date_result.reason
        
        # Validate title
        if title:
            title_result = self.validate_title(title, url)
            result.title_valid = title_result.is_valid
            result.title_corrected = title_result.corrected_value
        
        # Calculate overall confidence
        confidences = []
        if authors:
            author_confidence = len(result.authors_valid) / len(authors) if authors else 1.0
            confidences.append(author_confidence)
        if result.date_valid:
            confidences.append(0.9)
        else:
            confidences.append(0.3)
        
        result.overall_confidence = sum(confidences) / len(confidences) if confidences else 1.0
        
        logger.info(f"Metadata validation complete: confidence={result.overall_confidence:.2f}, "
                    f"authors={len(result.authors_valid)}/{len(authors) if authors else 0}")
        
        return result
    
    def _call_ollama(self, prompt: str) -> Optional[str]:
        """Call Ollama API for LLM inference."""
        try:
            response = requests.post(
                self.ollama_url,
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.1,  # Low temperature for consistent validation
                        "num_predict": 300,  # Validation responses are short
                    }
                },
                timeout=self.TIMEOUT
            )
            response.raise_for_status()
            
            result = response.json()
            return result.get('response', '')
            
        except requests.exceptions.ConnectionError:
            logger.debug("Ollama not available for validation")
            self._available = False
            return None
        except requests.exceptions.Timeout:
            logger.warning("Ollama validation timed out")
            return None
        except Exception as e:
            logger.error(f"Ollama API error during validation: {e}")
            return None
    
    def _parse_json_response(self, response: str) -> Optional[Dict]:
        """Parse JSON from LLM response (handles markdown code blocks, nested objects)."""
        try:
            # First, try to extract from markdown code block
            code_block_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response, re.DOTALL)
            if code_block_match:
                return json.loads(code_block_match.group(1))
            
            # Try to find the outermost JSON object (handles nested objects)
            # Find all { and } and match them
            start_idx = response.find('{')
            if start_idx == -1:
                return None
            
            depth = 0
            end_idx = start_idx
            for i, char in enumerate(response[start_idx:], start_idx):
                if char == '{':
                    depth += 1
                elif char == '}':
                    depth -= 1
                    if depth == 0:
                        end_idx = i + 1
                        break
            
            if depth == 0:
                json_str = response[start_idx:end_idx]
                return json.loads(json_str)
            
            # Fallback: try the whole response
            return json.loads(response.strip())
            
        except json.JSONDecodeError as e:
            logger.debug(f"Could not parse LLM JSON: {response[:200]}... Error: {e}")
            return None


# Singleton instance for easy access
_validator_instance: Optional[LLMValidator] = None


def get_validator() -> LLMValidator:
    """Get or create the singleton LLM validator instance."""
    global _validator_instance
    if _validator_instance is None:
        _validator_instance = LLMValidator()
    return _validator_instance


def validate_authors(authors: List[str]) -> Tuple[List[str], List[Tuple[str, str]]]:
    """Convenience function to validate author names."""
    return get_validator().validate_authors(authors)


def validate_metadata(authors: List[str], date: str, title: str,
                      url: str, other_dates: List[str] = None) -> MetadataValidationResult:
    """Convenience function to validate all metadata."""
    return get_validator().validate_metadata(authors, date, title, url, other_dates)

