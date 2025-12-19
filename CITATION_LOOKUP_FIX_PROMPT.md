# CitationSculptor: AI-Enhanced Lookup Fix - Continuation Prompt

## Project Location
```
/Users/tusharshah/Developer/MCP-Servers/CitationSculptor
```

## Current State
- **Version**: 2.1.0
- **Test File**: `30 - Areas/Medicine/Cardiology/Cardiovascular Prevention/The NLRP3 Inflammasome A Central Hub for Cardiovascular Inflammation and a Translational Target for Therapy.md`
- **Current Success Rate**: 48/64 citations with PMID (~75%)
- **Target Success Rate**: >95% (less than 5% failure)

## The Core Problem

The document processing is failing to resolve ~16 academic references that SHOULD be findable in PubMed. The system has multiple lookup strategies but they're not working correctly due to implementation bugs.

### Example Failing Reference (Reference 48)

**Original Text:**
```
48. (Author(s) not specified). Up-regulated NLRP3 inflammasome activation in patients with type 2 diabetes. _Diabetes_. 2013;62(1):194-206. doi:10.2337/db12-1102. [Link](https://diabetesjournals.org/diabetes/article/62/1/194/15121/Upregulated-NLRP3-Inflammasome-Activation-in)
```

**What's Happening:**
1. DOI `10.2337/db12-1102` is extracted from metadata ✅
2. DOI lookup via CrossRef/PubMed fails ❌ (DOI not resolving)
3. Title search on "(Author(s) not specified)" fails ❌ (wrong field used)
4. AI-enhanced lookup is triggered but builds a bad query ❌

**The Actual Article:**
- **PMID**: 23086037
- **Title**: "Upregulated NLRP3 inflammasome activation in patients with type 2 diabetes"
- **Journal**: Diabetes
- **Year**: 2013

## Root Cause Analysis

### Bug #1: AI-Enhanced PubMed Query Format is Wrong

**Location**: `mcp_server/http_server.py`, method `_ai_enhanced_lookup()` around line 2100-2150

**Current Code Builds:**
```
regulated NLRP3 inflammasome activation patients AND 2013[pdat] AND Diabetes[Journal]
```
This returns **0 results**.

**Should Build:**
```
NLRP3 inflammasome activation diabetes Diabetes[Journal] 2013
```
This returns **3 results** including the correct PMID 23086037.

**The Fix:**
1. Remove explicit `AND` operators - PubMed uses implicit AND for space-separated terms
2. Remove `[pdat]` qualifier - just append the year as a plain term
3. Keep `[Journal]` qualifier - it works
4. Include disease/topic keywords from title (e.g., "diabetes")

### Bug #2: Title Words Extraction Excludes Important Terms

**Current Code:**
```python
title_words = [w for w in clean_title.split() if len(w) > 3 and w.lower() not in 
              ['with', 'from', 'that', 'this', 'their', 'have', 'been', 'were', 'into', 'than', 'type']][:5]
```

**Problem**: "type" is excluded, but "type 2 diabetes" is a key search term.

**Better Approach:**
- Keep disease-related terms like "diabetes", "cardiovascular", etc.
- Use bigrams for medical terms ("type 2", "heart failure")
- Prioritize MeSH-like terms (inflammasome, NLRP3, etc.)

### Bug #3: DOI-to-PMID Conversion Not Using All Available Tools

The system has MCP tools for ID conversion (`mcp_pubmed-mcp-server_pubmed_convert_ids`) but isn't using them. When a DOI doesn't resolve directly, it should:
1. Try the NCBI ID Converter API
2. Try searching PubMed for the DOI string
3. Try CrossRef for metadata, then search PubMed by title/authors

## Files to Modify

### Primary File: `mcp_server/http_server.py`

**Method `_ai_enhanced_lookup()` (around line 2053-2160)**

Current implementation has flawed query building. Needs to be rewritten to:

```python
def _ai_enhanced_lookup(self, ref: ParsedReference) -> Optional[Dict[str, Any]]:
    """
    Use AI-enhanced title extraction and optimized PubMed search.
    """
    try:
        import re
        
        original_text = getattr(ref, 'original_text', '') or ''
        if not original_text or len(original_text) < 20:
            return None
        
        # Extract journal name from italics
        journal = None
        italic_match = re.search(r'[_*]([A-Z][a-zA-Z\s&]+)[_*]', original_text)
        if italic_match:
            journal = italic_match.group(1).strip()
        
        # Extract title - find longest text segment that's not a URL/author/journal
        title = self._extract_title_from_reference_text(original_text, journal)
        if not title:
            return None
        
        # Extract year
        year_match = re.search(r'\b(19|20)\d{2}\b', original_text)
        year = year_match.group(0) if year_match else None
        
        # Build optimized query - NO explicit AND operators
        # Format: "key words journal[Journal] year"
        clean_title = title.replace('-', ' ')
        # Keep important medical terms, including disease names
        key_words = [w for w in clean_title.split() 
                     if len(w) > 3 and w.lower() not in 
                     ['with', 'from', 'that', 'this', 'their', 'have', 'been', 'were']][:6]
        
        query_parts = [' '.join(key_words)]
        if journal:
            query_parts.append(f'{journal}[Journal]')
        if year:
            query_parts.append(year)  # Just the year, no [pdat]
        
        query = ' '.join(query_parts)
        logger.info(f"AI-enhanced query: {query}")
        
        # Search PubMed
        results = self.lookup.pubmed_client.search_pubmed(query, max_results=5)
        
        if results:
            for pmid_info in results:
                pmid = pmid_info.get('pmid') if isinstance(pmid_info, dict) else pmid_info
                result = self.lookup.lookup_pmid(str(pmid))
                if result.success:
                    # Validate title similarity
                    if self._titles_match(title, result.metadata.get('title', '')):
                        return self._format_result(result)
        
        return None
        
    except Exception as e:
        logger.debug(f"AI-enhanced lookup failed: {e}")
        return None
```

### Supporting Method to Add:

```python
def _extract_title_from_reference_text(self, text: str, journal: str = None) -> Optional[str]:
    """Extract article title from reference text."""
    import re
    
    parts = text.split('.')
    candidates = []
    
    for part in parts:
        clean = part.strip()
        
        # Skip reference number
        if re.match(r'^\d+', clean):
            clean = re.sub(r'^\d+\s*', '', clean)
        
        # Skip if it's exactly the journal name
        if journal and clean.strip('_* ').lower() == journal.lower():
            continue
        
        # Skip author patterns
        if clean.startswith('(') or 'not specified' in clean.lower():
            continue
        
        # Skip DOI, links, year patterns
        if clean.lower().startswith(('doi:', 'link', 'http', '[link')):
            continue
        if re.match(r'^(19|20)\d{2}', clean):
            continue
        
        # Skip URLs
        if 'http' in clean.lower() or '://' in clean or 'org/' in clean.lower():
            continue
        if re.search(r'/\d+/', clean):  # URL path pattern
            continue
        
        # Good candidate: 25+ chars, not too many commas
        if len(clean) > 25 and clean.count(',') < 3:
            candidates.append((len(clean), clean))
    
    if candidates:
        candidates.sort(reverse=True)
        return candidates[0][1]
    
    return None

def _titles_match(self, ref_title: str, result_title: str, threshold: float = 0.5) -> bool:
    """Check if titles are similar enough."""
    ref_words = set(w.lower() for w in ref_title.split() if len(w) > 3)
    result_words = set(w.lower() for w in result_title.split() if len(w) > 3)
    
    if not ref_words or not result_words:
        return False
    
    overlap = len(ref_words & result_words)
    min_len = min(len(ref_words), len(result_words))
    
    return overlap / min_len >= threshold
```

## Testing Commands

### Start the Server
```bash
cd /Users/tusharshah/Developer/MCP-Servers/CitationSculptor
pkill -f "http_server" 2>/dev/null
.venv/bin/python -m mcp_server.http_server --port 3019 &
```

### Test Document Processing
```bash
curl -s -X POST http://localhost:3019/api/process-document \
  -H "Content-Type: application/json" \
  -d '{"file_path": "30 - Areas/Medicine/Cardiology/Cardiovascular Prevention/The NLRP3 Inflammasome A Central Hub for Cardiovascular Inflammation and a Translational Target for Therapy.md", "create_backup": false}' | jq -r '.processed_content' | grep -E "^\[\^" > /tmp/test_citations.txt

echo "Total: $(wc -l < /tmp/test_citations.txt)"
echo "With PMID: $(grep -c 'PMID:' /tmp/test_citations.txt)"
```

### Verify Specific Reference
```bash
# Test that PMID 23086037 is found for reference 48
grep "23086037" /tmp/test_citations.txt
```

### Test PubMed Query Directly
```python
from citation_lookup import CitationLookup
lookup = CitationLookup()

# This query SHOULD return results
results = lookup.pubmed_client.search_pubmed(
    "NLRP3 inflammasome activation diabetes Diabetes[Journal] 2013", 
    max_results=5
)
print(results)  # Should include PMID 23086037
```

## Success Criteria

1. **Reference 48** resolves to PMID 23086037
2. **Overall success rate** > 95% (at least 61/64 citations with PMID)
3. **No duplicate citations** in output
4. **Proper inline marks** like `[^Lee-2013-23086037]` not `[^Diabetesjour-Upregu-2025-ref48]`

## Iteration Instructions

1. Read this file and understand the problem
2. Implement the fixes in `mcp_server/http_server.py`
3. Restart the server and test
4. Check the success rate
5. If < 95%, analyze remaining failures and iterate
6. Repeat until success rate > 95%

## Additional Context

- The Learning Engine (`modules/learning_engine.py`) can record failures for future improvement
- The test file has ~70 references, mostly academic articles
- Many references already have DOIs in metadata from `reference_parser.py`
- The system should use all available data: URL, DOI, title, journal, year

## Environment

- Python virtual environment: `.venv`
- Server runs on port 3019
- Obsidian vault: `/Users/tusharshah/Main Obsidian (Sync)`
- Configuration: `modules/config.py` and `.env`







