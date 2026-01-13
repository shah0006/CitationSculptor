# CitationSculptor v2.4.0 Improvement Plan

> ## ✅ STATUS: COMPLETE (v2.4.1 Released Jan 13, 2026)
>
> All issues identified in this plan have been implemented and tested:
> - ✅ File save bug fixed with `save_to_file` parameter
> - ✅ Citation integrity checker module created
> - ✅ Context-aware verification with IDF-weighted inclusion coefficient
> - ✅ Comprehensive audit tool implemented
> - ✅ Feature parity achieved across MCP, HTTP API, CLI, Web UI
> - ✅ Security fix for path traversal vulnerability
> - ✅ 471+ tests passing

## 🎯 Executive Summary

During document processing, the following critical issues were discovered that required **15+ manual corrections** after the automated tool ran. This plan addresses those issues with domain-agnostic solutions that work on ANY document type.

---

## ⚠️ CRITICAL: Domain-Agnostic Design Requirement

**CitationSculptor is a GENERIC tool used across ALL domains:**
- Medical/Clinical research papers
- Legal documents and briefs
- Engineering and technical papers
- Historical and humanities research
- Business and financial reports
- Computer science publications
- Social science research
- Physics, chemistry, biology papers
- Architecture and design documents
- ANY scholarly or professional document

**All solutions in this plan MUST work generically.** The issues were discovered while processing a medical document, but examples are illustrative only - solutions must not contain hardcoded medical or any other domain-specific keywords.

---

## 📋 Problem Analysis

### Problem 1: No Context-Aware Citation Verification

**Issue:** Citations get assigned to the wrong text sections because the tool doesn't verify that citation content matches surrounding text.

**Example Pattern (Generic):**
```markdown
Text discusses Topic A in detail.[^Smith-2024]

[^Smith-2024]: Smith J. Study about Topic B. Journal. 2024.
```

The citation `[^Smith-2024]` is about Topic B but was placed in text about Topic A. This is a **context mismatch**.

**Impact:** In a recent session, ~12 citations were assigned to incorrect topics, requiring manual replacement.

**Root Cause:** The current `citation_process_document` tool:
1. Finds numbered references `[^1]`, `[^2]`, etc.
2. Looks up citations in PubMed by querying the reference text
3. Replaces with semantic tags `[^Author-Year-ID]`
4. **NEVER verifies** the found citation matches the surrounding text

---

### Problem 2: Same-Citation Duplicate Detection Missing

**Issue:** The same citation appears consecutively: `[^A][^A]` or `[^A] [^A]`

**Example:**
```markdown
Original (wrong):
"This finding was confirmed.[^JonesA-2024][^JonesA-2024]"

Expected:
"This finding was confirmed.[^JonesA-2024]"
```

**Impact:** Creates visual noise and suggests automated processing artifacts.

**Root Cause:** When multiple numbered citations exist in source, they can map to the same PubMed result, creating duplicates. No deduplication logic exists.

---

### Problem 3: File Not Saved After Processing

**Issue:** `citation_process_document` returns processed content but **never writes it to the file**.

**Current Behavior:**
```python
# Returns markdown code block with content
# User must manually save to file
return "```markdown\n" + processed_content + "\n```"
```

**Expected Behavior:**
```python
# Actually write to the file
with open(file_path, 'w') as f:
    f.write(processed_content)
return {"saved_to": file_path, "content": processed_content}
```

**Impact:** Every document requires manual copy-paste or file write commands after processing.

---

### Problem 4: No Comprehensive Audit Tool

**Issue:** After processing, there's no way to verify all citations are correct without manual review.

**Needed Capabilities:**
1. List all inline citations and their definitions
2. Flag orphaned definitions (defined but never used)
3. Flag missing definitions (used inline but never defined)
4. Flag duplicate patterns
5. Verify context matches (keyword overlap)
6. Generate health score

---

## 🔧 Proposed Solutions

### Solution 1: Dynamic Keyword-Based Context Verification

**Approach:** Extract keywords from BOTH the citation definition AND the surrounding text, then calculate overlap. Low overlap = potential mismatch.

**Why dynamic, not hardcoded keywords:**
- Works on ANY domain without modification
- Keywords come FROM the document content
- No maintenance of topic lists required
- Adapts to any subject matter automatically

**Algorithm:**
```
1. For each inline citation [^Tag]:
   a. Extract surrounding text (3 lines before/after)
   b. Get citation definition text
   
2. Extract keywords from both:
   a. Lowercase, remove punctuation
   b. Filter stopwords (the, and, of, etc.)
   c. Filter short words (<3 chars)
   d. Count word frequencies
   e. Return top N keywords
   
3. Calculate Jaccard similarity:
   overlap = |keywords1 ∩ keywords2| / |keywords1 ∪ keywords2|
   
4. Flag if overlap < threshold (default 0.1)
```

**Key Design Decisions:**
- Stopwords are language-basic ONLY (the, and, is, etc.)
- NO domain-specific terms in stopwords
- Keywords extracted dynamically from content
- Threshold is configurable per use case

---

### Solution 2: Duplicate Citation Detector

**Features:**
1. **Same-citation duplicates:** `[^A][^A]` → `[^A]`
2. **Orphan detection:** Citations defined but never used inline
3. **Missing detection:** Citations used inline but never defined

**Implementation:**
```python
class DuplicateCitationDetector:
    CONSECUTIVE_SAME = r'(\[\^[A-Za-z][^\]]+\])(\s*)\1'
    
    def analyze(self, content: str) -> Report:
        # Find all patterns
        ...
    
    def fix_duplicates(self, content: str) -> str:
        # Remove consecutive same citations
        return re.sub(CONSECUTIVE_SAME, r'\1', content)
```

---

### Solution 3: File Save Fix in MCP Server

**File:** `mcp_server/server.py`  
**Function:** `process_document_content()`

**Changes:**
1. Add `save_to_file: bool = True` parameter
2. After processing, write to file if `file_path` provided
3. Return structured JSON (not markdown code block)
4. Include success status, backup path, stats

---

### Solution 4: Comprehensive Audit Tool

**New MCP Tool:** `citation_audit_document`

**Output Structure:**
```json
{
  "health_score": 85,
  "issues": {
    "same_citation_duplicates": 2,
    "orphaned_definitions": 3,
    "missing_definitions": 1,
    "context_mismatches": 4
  },
  "details": {
    "duplicates": [...],
    "orphans": [...],
    "missing": [...],
    "mismatches": [...]
  }
}
```

---

## 🗓️ Implementation Checklist

### Day 1: File Save Fix (Task 1) - P0

- [ ] Modify `server.py` `process_document_content()` function
- [ ] Add `save_to_file` parameter (default True)
- [ ] Implement file write with error handling
- [ ] Return JSON structure instead of markdown
- [ ] Update tool schema for backward compatibility
- [ ] Write tests: file saved, file permissions, backup created
- [ ] Run full test suite - all 398 tests pass

### Day 2: Duplicate Detection (Task 2) - P0

- [ ] Create `modules/duplicate_citation_detector.py`
- [ ] Implement `DuplicateCitationDetector` class
- [ ] Add `analyze()` method for reporting
- [ ] Add `fix_duplicates()` method for auto-fix
- [ ] Add MCP tool `citation_find_duplicates`
- [ ] Write tests with MULTIPLE document types (medical, legal, engineering)
- [ ] Run full test suite

### Day 3: Context Verification (Task 3) - P1

- [ ] Create `modules/citation_context_verifier.py`
- [ ] Implement `extract_keywords()` - dynamic, NOT hardcoded
- [ ] Implement `calculate_overlap_score()` using Jaccard similarity
- [ ] Implement `verify_citations()` main method
- [ ] Add MCP tool `citation_verify_context`
- [ ] Write tests with MULTIPLE document types
- [ ] **CRITICAL:** Verify NO domain-specific keywords in code
- [ ] Run full test suite

### Day 4: Audit Tool (Task 4) - P1

- [ ] Add `citation_audit_document` tool to server.py
- [ ] Integrate duplicate detector + context verifier
- [ ] Implement health score calculation
- [ ] Format readable report output
- [ ] Write tests covering all edge cases
- [ ] Run full test suite

### Day 5: Integration & Polish (Task 5)

- [ ] Integrate new modules into `citation_process_document` flow
- [ ] Add duplicate removal as pre-processing step
- [ ] Add context verification as post-processing warning
- [ ] Update README with new tools
- [ ] Update CHANGELOG
- [ ] Full regression test
- [ ] Manual testing with 3 different document types

---

## 🧪 Test Requirements

### Multi-Domain Test Matrix

Each new module must be tested with at least 3 different document types:

| Document Type | Description | Example Keywords |
|--------------|-------------|------------------|
| Medical | Clinical research, drug studies | treatment, patients, efficacy |
| Legal | Court cases, regulations | statute, precedent, jurisdiction |
| Engineering | Technical papers | tensile, modulus, specifications |
| Historical | Historical research | century, era, civilization |
| CS | Computer science papers | algorithm, complexity, neural |

### Test Coverage Requirements

- Duplicate detector: 15+ tests, 90%+ coverage
- Context verifier: 20+ tests, 90%+ coverage, MUST include multi-domain
- Audit tool: 10+ tests
- File save: 10+ tests
- Integration: 5+ end-to-end tests

---

## 📊 Success Metrics

### Quantitative

| Metric | Before | Target |
|--------|--------|--------|
| Manual citation corrections per doc | 15+ | <3 |
| Time to process 100-citation doc | 30min | 5min |
| Test coverage for new code | N/A | >90% |

### Qualitative

- [ ] Works on medical documents
- [ ] Works on legal documents  
- [ ] Works on engineering documents
- [ ] Works on humanities documents
- [ ] Works on any new domain without code changes

---

## ⚠️ Anti-Patterns to Avoid

### ❌ DO NOT: Hardcode Domain Keywords

```python
# WRONG - domain-specific
MEDICAL_KEYWORDS = ['aspirin', 'cardiovascular', 'treatment']
LEGAL_KEYWORDS = ['habeas', 'corpus', 'statute']

def verify_context(text, domain='medical'):
    keywords = MEDICAL_KEYWORDS if domain == 'medical' else LEGAL_KEYWORDS
```

### ✅ DO: Extract Keywords Dynamically

```python
# CORRECT - domain-agnostic
def extract_keywords(text: str) -> List[str]:
    words = tokenize(text)
    words = remove_stopwords(words)
    words = remove_short_words(words)
    return most_common(words, n=15)
```

### ❌ DO NOT: Use Domain-Specific Stopwords

```python
# WRONG - medical stopwords
STOPWORDS = {'patient', 'study', 'treatment', 'efficacy'}
```

### ✅ DO: Use Language-Basic Stopwords Only

```python
# CORRECT - language basics only
STOPWORDS = {'the', 'a', 'an', 'and', 'or', 'but', 'is', 'are', 'was', ...}
```

---

## 📁 File Structure After Implementation

```
CitationSculptor/
├── modules/
│   ├── duplicate_citation_detector.py   # NEW
│   ├── citation_context_verifier.py     # NEW (domain-agnostic)
│   └── ... (existing modules)
├── mcp_server/
│   └── server.py                        # MODIFIED (file save, new tools)
├── tests/
│   ├── test_duplicate_citation_detector.py  # NEW (multi-domain)
│   ├── test_citation_context_verifier.py    # NEW (multi-domain)
│   ├── test_citation_audit.py               # NEW
│   └── test_process_document_save.py        # NEW
├── docs/
│   └── IMPROVEMENT_PLAN_v2.4.md             # THIS FILE
├── CONTINUATION_PROMPT.md                   # Agent handoff
├── PLANNING.md                              # Updated roadmap
├── CHANGELOG.md                             # Updated
└── README.md                                # Updated
```

---

## ✅ Definition of Done

v2.4.0 is complete when ALL of these criteria are met:

1. [ ] `citation_process_document` saves files (with backup) - Task 1
2. [ ] `citation_find_duplicates` detects same-citation patterns - Task 2
3. [ ] `citation_verify_context` uses DYNAMIC keyword extraction (NO hardcoded keywords) - Task 3
4. [ ] `citation_audit_document` provides comprehensive health check - Task 4
5. [ ] All features work on ANY document type (medical, legal, engineering, etc.)
6. [ ] 90%+ test coverage INCLUDING multi-domain tests
7. [ ] All 398 existing tests still pass (run full test suite)
8. [ ] Documentation updated (README, PLANNING, CHANGELOG)

---

*Document Version: 2.4.0*  
*Last Updated: 2026-01-13*  
*Author: AI Assistant (based on real-world usage analysis)*
