"""
LLM-based Metadata Extractor for Webpage Citations

This module uses a local LLM (via Ollama) to intelligently extract citation
metadata from webpages. It uses a site rules database to provide domain-specific
hints and can learn from successful extractions.

Architecture:
    1. Load site rules from YAML database
    2. Fetch webpage content
    3. Send to LLM with appropriate prompt + site-specific hints
    4. Parse structured response into ExtractedMetadata
    5. Optionally save new rules for unknown sites
"""

import json
import re
import requests
import yaml
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse
from loguru import logger


@dataclass
class ExtractedMetadata:
    """Structured metadata extracted by LLM."""
    title: str = ""
    authors: List[str] = None
    date: str = ""  # Could be "2024", "Spring 2024", "2024-03-15", etc.
    year: str = ""
    month: str = ""
    organization: str = ""
    publication_name: str = ""  # e.g., "LipidSpin", "Health Affairs Blog"
    
    def __post_init__(self):
        if self.authors is None:
            self.authors = []


class SiteRulesDatabase:
    """Manages the site rules YAML database."""
    
    def __init__(self, rules_path: Optional[Path] = None):
        if rules_path is None:
            # Default path relative to this module
            rules_path = Path(__file__).parent.parent / "data" / "site_rules.yaml"
        
        self.rules_path = rules_path
        self.rules: Dict = {}
        self._load_rules()
    
    def _load_rules(self) -> None:
        """Load rules from YAML file."""
        try:
            if self.rules_path.exists():
                with open(self.rules_path, 'r', encoding='utf-8') as f:
                    self.rules = yaml.safe_load(f) or {}
                logger.debug(f"Loaded {len(self.rules)} site rules from {self.rules_path}")
            else:
                logger.warning(f"Site rules file not found: {self.rules_path}")
                self.rules = {}
        except Exception as e:
            logger.error(f"Failed to load site rules: {e}")
            self.rules = {}
    
    def get_rules_for_domain(self, url: str) -> Optional[Dict]:
        """Get site-specific rules for a domain."""
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower().replace('www.', '')
            
            # Try exact match first
            if domain in self.rules:
                return self.rules[domain]
            
            # Try parent domain (e.g., subdomain.example.com -> example.com)
            parts = domain.split('.')
            if len(parts) > 2:
                parent_domain = '.'.join(parts[-2:])
                if parent_domain in self.rules:
                    return self.rules[parent_domain]
            
            return None
        except Exception as e:
            logger.error(f"Error getting rules for {url}: {e}")
            return None
    
    def get_default_instructions(self) -> str:
        """Get default extraction instructions."""
        default = self.rules.get('_default', {})
        return default.get('instructions', '')
    
    def save_rules_for_domain(self, domain: str, rules: Dict) -> bool:
        """Save new rules for a domain."""
        try:
            self.rules[domain] = rules
            
            # Ensure directory exists
            self.rules_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.rules_path, 'w', encoding='utf-8') as f:
                yaml.dump(self.rules, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
            logger.info(f"Saved new rules for domain: {domain}")
            return True
        except Exception as e:
            logger.error(f"Failed to save rules for {domain}: {e}")
            return False


class LLMMetadataExtractor:
    """
    Extracts citation metadata from webpages using LLM.
    
    Uses Ollama for local LLM inference with site-specific hints
    from the rules database.
    """
    
    # Ollama configuration
    OLLAMA_URL = "http://localhost:11434/api/generate"
    # Use qwen2.5:32b-instruct for best instruction following and JSON output
    DEFAULT_MODEL = "qwen2.5:32b-instruct"
    FALLBACK_MODELS = ["deepseek-r1:latest", "gemma3:27b", "qwen3:latest", "llama3:8b"]
    TIMEOUT = 60  # seconds
    
    # Extraction prompt template
    EXTRACTION_PROMPT = """You are a citation metadata extractor. Extract the following information from this webpage content and return it as JSON.

Required fields:
- title: The main article/page title (clean, without site name suffix)
- authors: List of author names (first and last name only, no credentials like MD/PhD)
- date: Publication date (any format: "2024", "Spring 2024", "March 15, 2024", etc.)
- organization: The publisher or website organization name
- publication_name: Specific publication name if applicable (e.g., "LipidSpin", "Health Affairs Blog")

{site_instructions}

Return ONLY valid JSON in this exact format:
{{
  "title": "Article Title Here",
  "authors": ["First Last", "First Last"],
  "date": "2024" or "Spring 2024" or "2024-03-15",
  "organization": "Organization Name",
  "publication_name": "Publication Name or empty string"
}}

If a field cannot be determined, use null for strings or empty array for authors.
Do not include any explanation, just the JSON.

---
URL: {url}

WEBPAGE CONTENT:
{content}
"""
    
    def __init__(self, model: str = None, ollama_url: str = None):
        self.model = model or self.DEFAULT_MODEL
        self.ollama_url = ollama_url or self.OLLAMA_URL
        self.site_rules = SiteRulesDatabase()
    
    def extract_metadata(self, url: str, html_content: str) -> Optional[ExtractedMetadata]:
        """
        Extract metadata from webpage content using LLM.
        
        Args:
            url: The webpage URL
            html_content: Raw HTML or text content of the page
            
        Returns:
            ExtractedMetadata if successful, None otherwise
        """
        # Get site-specific rules
        site_rules = self.site_rules.get_rules_for_domain(url)
        
        # Build site-specific instructions
        if site_rules:
            site_instructions = f"""
SITE-SPECIFIC HINTS for {urlparse(url).netloc}:
Organization: {site_rules.get('organization', 'Unknown')}
Publication Type: {site_rules.get('publication_type', 'webpage')}
Publication Name: {site_rules.get('publication_name', '')}

{site_rules.get('instructions', '')}
"""
        else:
            site_instructions = self.site_rules.get_default_instructions()
        
        # Clean HTML to text for LLM processing
        clean_content = self._html_to_text(html_content)
        
        # Truncate if too long (keep first ~8000 chars which usually contains metadata)
        if len(clean_content) > 8000:
            clean_content = clean_content[:8000] + "\n...[content truncated]..."
        
        # Build prompt
        prompt = self.EXTRACTION_PROMPT.format(
            site_instructions=site_instructions,
            url=url,
            content=clean_content
        )
        
        # Call LLM
        response = self._call_ollama(prompt)
        if not response:
            return None
        
        # Parse response
        metadata = self._parse_llm_response(response, url, site_rules)
        return metadata
    
    def _html_to_text(self, html: str) -> str:
        """Convert HTML to readable text for LLM processing."""
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, 'html.parser')
            
            # Remove script and style elements
            for element in soup(['script', 'style', 'nav', 'footer', 'aside']):
                element.decompose()
            
            # Get text with newlines preserved
            text = soup.get_text(separator='\n')
            
            # Clean up excessive whitespace
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            full_text = '\n'.join(lines)
            
            # If there's an "Article By" or "By:" section, make sure it's included
            # by extracting it separately and prepending
            author_section = ""
            by_markers = ['Article By:', 'Written By:', 'By:']
            for marker in by_markers:
                idx = full_text.find(marker)
                if idx > 0:
                    # Extract ~1500 chars from this section
                    author_section = f"\n=== AUTHOR SECTION ===\n{full_text[idx:idx+1500]}\n=== END AUTHOR SECTION ===\n\n"
                    break
            
            return author_section + full_text
            
        except ImportError:
            # Fallback: basic HTML tag removal
            text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r'<[^>]+>', '\n', text)
            text = re.sub(r'\s+', ' ', text)
            return text.strip()
    
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
                        "temperature": 0.1,  # Low temperature for consistent extraction
                        "num_predict": 500,  # Limit response length
                    }
                },
                timeout=self.TIMEOUT
            )
            response.raise_for_status()
            
            result = response.json()
            return result.get('response', '')
            
        except requests.exceptions.ConnectionError:
            logger.warning("Ollama not available - LLM extraction disabled")
            return None
        except requests.exceptions.Timeout:
            logger.warning("Ollama request timed out")
            return None
        except Exception as e:
            logger.error(f"Ollama API error: {e}")
            return None
    
    def _parse_llm_response(self, response: str, url: str, site_rules: Optional[Dict]) -> Optional[ExtractedMetadata]:
        """Parse LLM JSON response into ExtractedMetadata."""
        try:
            # Extract JSON from response (LLM might include extra text)
            json_match = re.search(r'\{[^{}]*\}', response, re.DOTALL)
            if not json_match:
                logger.warning(f"No JSON found in LLM response: {response[:200]}")
                return None
            
            data = json.loads(json_match.group())
            
            # Extract and normalize fields
            title = data.get('title') or ""
            
            # Clean title (remove site name suffix like " | Site Name")
            if title and '|' in title:
                title = title.split('|')[0].strip()
            if title and ' - ' in title:
                # Only remove suffix if it looks like a site name
                parts = title.rsplit(' - ', 1)
                if len(parts) == 2 and len(parts[1]) < 50:
                    title = parts[0].strip()
            
            # Process authors
            raw_authors = data.get('authors') or []
            authors = []
            for author in raw_authors:
                if author and isinstance(author, str):
                    # Clean author name (remove credentials)
                    clean_name = self._clean_author_name(author)
                    if clean_name:
                        authors.append(clean_name)
            
            # Process date
            date_str = data.get('date') or ""
            year, month = self._parse_date(date_str, url)
            
            # Get organization (prefer site rules, then LLM extraction)
            organization = ""
            if site_rules:
                organization = site_rules.get('organization', '')
            if not organization:
                organization = data.get('organization') or ""
            
            # Get publication name
            publication_name = ""
            if site_rules:
                publication_name = site_rules.get('publication_name', '')
            if not publication_name:
                publication_name = data.get('publication_name') or ""
            
            metadata = ExtractedMetadata(
                title=title,
                authors=authors,
                date=date_str,
                year=year,
                month=month,
                organization=organization,
                publication_name=publication_name
            )
            
            logger.info(f"LLM extracted: title='{title[:50]}...', {len(authors)} authors, year={year}")
            return metadata
            
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse LLM JSON: {e}")
            return None
        except Exception as e:
            logger.error(f"Error parsing LLM response: {e}")
            return None
    
    def _clean_author_name(self, name: str) -> str:
        """Clean author name by removing credentials and normalizing."""
        if not name:
            return ""
        
        # Remove common credentials
        credentials = r',?\s*(?:MD|PhD|DO|FNLA|MPH|MS|RN|NP|PA|DrPH|FACC|FAHA|FACS|FACEP|MBA|JD|Esq|MSCI|FCCP|BSN|DNP|FNP|APRN)\*?\.?'
        clean = re.sub(credentials, '', name, flags=re.IGNORECASE)
        
        # Remove asterisks (footnote markers)
        clean = clean.replace('*', '')
        
        # Clean up whitespace and punctuation
        clean = re.sub(r'\s+', ' ', clean).strip()
        clean = re.sub(r'[,;]+$', '', clean).strip()
        
        return clean
    
    def _parse_date(self, date_str: str, url: str) -> Tuple[str, str]:
        """Parse date string into year and month."""
        year = ""
        month = ""
        
        if not date_str:
            # Try to extract from URL
            return self._extract_date_from_url(url)
        
        date_lower = date_str.lower()
        
        # Check for seasonal dates
        seasons = {
            'spring': '03', 'summer': '06', 'fall': '09', 'autumn': '09', 'winter': '12'
        }
        for season, month_num in seasons.items():
            if season in date_lower:
                month = month_num
                # Extract year
                year_match = re.search(r'(\d{4})', date_str)
                if year_match:
                    year = year_match.group(1)
                break
        
        # If no season found, try standard date formats
        if not year:
            year_match = re.search(r'(\d{4})', date_str)
            if year_match:
                year = year_match.group(1)
        
        if not month:
            # Try month name
            months = {
                'january': '01', 'february': '02', 'march': '03', 'april': '04',
                'may': '05', 'june': '06', 'july': '07', 'august': '08',
                'september': '09', 'october': '10', 'november': '11', 'december': '12',
                'jan': '01', 'feb': '02', 'mar': '03', 'apr': '04',
                'jun': '06', 'jul': '07', 'aug': '08', 'sep': '09',
                'oct': '10', 'nov': '11', 'dec': '12'
            }
            for month_name, month_num in months.items():
                if month_name in date_lower:
                    month = month_num
                    break
            
            # Try numeric month (e.g., 2024-03-15)
            if not month:
                date_match = re.search(r'(\d{4})[-/](\d{2})', date_str)
                if date_match:
                    year = date_match.group(1)
                    month = date_match.group(2)
        
        return year, month
    
    def _extract_date_from_url(self, url: str) -> Tuple[str, str]:
        """Extract date from URL patterns."""
        year = ""
        month = ""
        
        # Seasonal pattern: /spring-2024/
        seasonal = re.search(r'/(spring|summer|fall|autumn|winter)[-_](\d{4})(?:/|$)', url, re.IGNORECASE)
        if seasonal:
            seasons = {'spring': '03', 'summer': '06', 'fall': '09', 'autumn': '09', 'winter': '12'}
            month = seasons.get(seasonal.group(1).lower(), '')
            year = seasonal.group(2)
            return year, month
        
        # Numeric pattern: /2024/03/15/ or /2024-03-15/
        numeric = re.search(r'/(\d{4})[-/](\d{2})(?:[-/](\d{2}))?(?:/|$)', url)
        if numeric:
            year = numeric.group(1)
            month = numeric.group(2)
            return year, month
        
        # Year only: /2024/
        year_only = re.search(r'/(\d{4})/', url)
        if year_only:
            year = year_only.group(1)
        
        return year, month
    
    def learn_from_extraction(self, url: str, metadata: ExtractedMetadata, 
                              html_content: str = "",
                              user_corrections: Optional[Dict] = None) -> bool:
        """
        Learn from a successful extraction and save rules for this domain.
        
        Args:
            url: The webpage URL
            metadata: Successfully extracted metadata
            html_content: Original HTML content (used to generate better instructions)
            user_corrections: Optional corrections provided by user
            
        Returns:
            True if rules were saved/updated
        """
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower().replace('www.', '')
            
            # Check if we already have rules for this domain
            existing_rules = self.site_rules.get_rules_for_domain(url)
            if existing_rules and not user_corrections:
                logger.debug(f"Rules already exist for {domain}")
                return False
            
            # Generate instructions based on what we learned
            instructions = self._generate_learned_instructions(url, metadata, html_content)
            
            # Build new rules
            new_rules = {
                'organization': metadata.organization,
                'publication_name': metadata.publication_name or "",
                'instructions': instructions,
                'learned': True,
                'date_added': datetime.now().isoformat(),
            }
            
            # Determine publication type based on content patterns
            if metadata.publication_name:
                new_rules['publication_type'] = 'publication'
            elif any(word in domain for word in ['news', 'times', 'post', 'journal']):
                new_rules['publication_type'] = 'news'
            elif '.gov' in domain:
                new_rules['publication_type'] = 'government'
            elif '.edu' in domain:
                new_rules['publication_type'] = 'academic'
            elif '.org' in domain:
                new_rules['publication_type'] = 'organization'
            else:
                new_rules['publication_type'] = 'webpage'
            
            if user_corrections:
                new_rules['user_corrections'] = user_corrections
                new_rules['instructions'] += f"\n\nUser corrections applied: {user_corrections}"
            
            # Save rules
            return self.site_rules.save_rules_for_domain(domain, new_rules)
            
        except Exception as e:
            logger.error(f"Failed to learn from extraction: {e}")
            return False
    
    def _generate_learned_instructions(self, url: str, metadata: ExtractedMetadata, 
                                       html_content: str) -> str:
        """Generate extraction instructions based on successful extraction."""
        instructions = []
        
        instructions.append(f"Organization: {metadata.organization}")
        
        if metadata.publication_name:
            instructions.append(f"Publication: {metadata.publication_name}")
        
        # Document author pattern
        if metadata.authors:
            instructions.append(f"Authors: Found {len(metadata.authors)} author(s)")
            # Try to identify where authors were found
            if html_content:
                if 'Article By' in html_content or 'article by' in html_content.lower():
                    instructions.append("Authors appear under 'Article By:' section")
                elif 'Written by' in html_content or 'written by' in html_content.lower():
                    instructions.append("Authors appear in 'Written by' byline")
                elif 'By:' in html_content:
                    instructions.append("Authors appear after 'By:' marker")
        else:
            instructions.append("Authors: Not typically available or institutional authorship")
        
        # Document date pattern
        if metadata.date:
            instructions.append(f"Date format: {metadata.date}")
            if 'spring' in metadata.date.lower() or 'summer' in metadata.date.lower() or \
               'fall' in metadata.date.lower() or 'winter' in metadata.date.lower():
                instructions.append("Uses seasonal date format")
        elif metadata.year:
            # Check if date came from URL
            if metadata.year in url:
                instructions.append("Date extracted from URL path")
        else:
            instructions.append("Date: Check URL path or page content for publication date")
        
        return '\n'.join(instructions)


# Convenience function for quick extraction
def extract_webpage_metadata(url: str, html_content: str) -> Optional[ExtractedMetadata]:
    """
    Quick extraction of webpage metadata using LLM.
    
    Args:
        url: The webpage URL
        html_content: Raw HTML content
        
    Returns:
        ExtractedMetadata if successful, None otherwise
    """
    extractor = LLMMetadataExtractor()
    return extractor.extract_metadata(url, html_content)
