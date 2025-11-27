# CitationSculptor Test Manifest

This document tracks all test sample files and their expected processing outcomes.
Use this to verify backward compatibility after code changes.

---

## Test Files Overview

| File | Format | Sections | CLI Args | Last Verified | Status |
|------|--------|----------|----------|---------------|--------|
| `pelican_bay_preventive_health_comprehensive_report.md` | V1 Simple | Single | (default) | 2025-11-27 | ⚠️ **Already Processed** (need original) |
| `Right Ventricular Dilation...md` | V2 Extended + Mixed | Multi (2) | `--multi-section` | 2025-11-27 | ✅ **PASS** (43 processed, 21 review) |
| `Gene Therapy Approaches...md` | V3 Footnotes (DOI) | Single | `--multi-section` | 2025-11-27 | ✅ **PASS** (9/9, 0 review) |
| `Arrhythmogenic Cardiomyopathies - Genetics.md` | V3 Footnotes (body after) | Single | `--multi-section` | 2025-11-27 | ✅ **PASS** (8/8, 0 review) |

---

## Detailed Test Specifications

### 1. pelican_bay_preventive_health_comprehensive_report.md

**⚠️ STATUS: ALREADY PROCESSED - Need original unprocessed version**

The current file in `test_samples/` is output from a previous run (has `[^AuthorYear]` labels).
If you have the original file with numbered references `[1]`, `[2]`, etc., please provide it.

**Format Version:** V1 Simple  
**Reference Style:** `N. [Title - Source](URL)`  
**Inline Style:** Numeric `[1]`, ranges `[1-3]`, comma lists `[1,2]`

**Expected Outcomes (when original is available):**
- Total references parsed: ~135+
- Citation types: Mostly PubMed articles, some DOI articles, webpages
- Should detect unreferenced citations and filter them
- All inline `[N]` references replaced with `[^AuthorYear-PMID]`

**CLI Command:**
```bash
python citation_sculptor.py "test_samples/pelican_bay_preventive_health_comprehensive_report.md" --no-backup
```

**Key Test Cases:**
- [ ] PubMed URL extraction (e.g., `pubmed.ncbi.nlm.nih.gov/XXXXXXXX`)
- [ ] DOI URL extraction (e.g., `doi.org/10.XXXX/...`)
- [ ] Range replacement `[1-3]` → individual labels
- [ ] Comma list replacement `[1,2]` → individual labels
- [ ] Unreferenced citation filtering

---

### 2. Right Ventricular Dilation in Previously Athletic Individuals...md

**Format Version:** V2 Extended  
**Reference Style:** `N. [Title](URL). Authors. Journal. Year;Vol(Issue):Pages. doi:XXX`  
**Inline Style:** Numeric `[N]`  
**Special:** Multiple independent reference sections

**Expected Outcomes:**
- Multiple reference sections detected (2+)
- Each section processed independently
- Section-specific inline replacements (same `[1]` in different sections → different labels)

**CLI Command:**
```bash
python citation_sculptor.py "test_samples/Right Ventricular Dilation in Previously Athletic Individuals Distinguishing Physiologic Adaptation from Pathology.md" --multi-section --no-backup
```

**Key Test Cases:**
- [ ] Extended format parsing (authors, journal, year inline)
- [ ] Multi-section detection
- [ ] Independent section processing
- [ ] DOI extraction from inline text

---

### 3. Gene Therapy Approaches in Arrhythmogenic Cardiomyopathy.md

**Format Version:** V3 Footnotes  
**Reference Style:** `[^N]: Citation text... URL`  
**Inline Style:** Footnotes `[^N]`

**Expected Outcomes:**
- Footnote definitions parsed correctly
- Inline `[^N]` references replaced with `[^AuthorYear-PMID]`
- URLs extracted from footnote content

**CLI Command:**
```bash
python citation_sculptor.py "test_samples/Gene Therapy Approaches in Arrhythmogenic Cardiomyopathy.md" --multi-section --no-backup
```

**Key Test Cases:**
- [ ] Footnote definition parsing `[^N]:`
- [ ] URL extraction from footnote content
- [ ] Footnote inline replacement

---

### 4. Arrhythmogenic Cardiomyopathies - Genetics.md

**Format Version:** V3 Footnotes (with body after references)  
**Reference Style:** `[^N]: Citation text... URL`  
**Inline Style:** Footnotes `[^N]`  
**Special:** Body text continues AFTER reference definitions

**Expected Outcomes:**
- Footnote definitions parsed
- Body text after references also processed
- Undefined references detected and flagged
- PDF documents searched on PubMed by title
- Webpages scraped for citation metadata

**CLI Command:**
```bash
python citation_sculptor.py "test_samples/Arrhythmogenic Cardiomyopathies - Genetics.md" --multi-section --no-backup
```

**Key Test Cases:**
- [ ] Body content after references processed
- [ ] Undefined reference detection (`[^10]`, `[^18]` not defined)
- [ ] PDF → PubMed title search
- [ ] Webpage metadata scraping (biotech-asia.org)

---

## Running Regression Tests

### Quick Smoke Test (All Files)

```bash
cd "/Users/tusharshah/Main Obsidian (Sync)/20 - Projects/Inactive Projects/Software Projects/CitationSculptor"
source venv/bin/activate

# Test 1: V1 Simple format
python citation_sculptor.py "test_samples/pelican_bay_preventive_health_comprehensive_report.md" --dry-run

# Test 2: V2 Extended + Multi-section
python citation_sculptor.py "test_samples/Right Ventricular Dilation in Previously Athletic Individuals Distinguishing Physiologic Adaptation from Pathology.md" --multi-section --dry-run

# Test 3: V3 Footnotes
python citation_sculptor.py "test_samples/Gene Therapy Approaches in Arrhythmogenic Cardiomyopathy.md" --multi-section --dry-run

# Test 4: V3 Footnotes with body after refs
python citation_sculptor.py "test_samples/Arrhythmogenic Cardiomyopathies - Genetics.md" --multi-section --dry-run
```

### Full Processing Test

Remove `--dry-run` to generate output files. Compare with previous outputs to verify consistency.

---

## Latest Regression Test Results (2025-11-27)

| Test | Result | Citations | Manual Review |
|------|--------|-----------|---------------|
| RV Dilation (Multi-Section) | ✅ PASS | 43 processed | 21 items |
| Gene Therapy (Footnotes) | ✅ PASS | 9/9 (100%) | 0 items |
| Arrhythmogenic Genetics | ✅ PASS | 8/8 (100%) | 0 items |
| Pelican Bay | ⏸️ SKIP | N/A | Need original file |

## Version History

| Date | Changes | Tests Passed |
|------|---------|--------------|
| 2025-11-27 | Initial manifest created | 3/4 (1 needs original) |
| | Added webpage scraping | 3/3 |
| | Added PDF → PubMed lookup | 3/3 |
| | Added undefined ref detection | 3/3 |
| | Created `test_samples/` folder | - |

---

## Notes

- **Server Required:** PubMed MCP server must be running on port 3017
- **Rate Limits:** Allow ~30 seconds between full processing runs to avoid 429 errors
- **Output Location:** Formatted files are created in the same directory as input with `_formatted` suffix
- **Mapping Files:** `_mapping.json` files provide audit trail for debugging

