# CitationSculptor Planning Document

## Project Status Overview
**Current Version:** 0.2.0
**Last Updated:** 2025-11-27
**Status:** Active Development

---

## ✅ Completed Tasks

### 1. Mac Environment Setup
- [x] Migrated codebase from Windows to Mac.
- [x] Created fresh `venv` (Python 3.9.6).
- [x] Installed all dependencies (`requests`, `rich`, `loguru`, `regex`, etc.).
- [x] Verified MCP server connection (local port 3017).

### 2. Core Functionality Improvements
- [x] **ID Conversion**: Integrated `pubmed_convert_ids` tool for robust PMC ID → PMID conversion.
- [x] **DOI Extraction**: 
    - Fixed regex to handle complex URLs (Wiley, Springer, OUP).
    - Added logic to strip query parameters and trailing article IDs.
- [x] **Metadata Parsing**: 
    - Enhanced to handle nested `journalInfo` (volume, issue, pages).
    - Added support for `book-chapter` and `book` types via CrossRef.
- [x] **Unreferenced Filtering**: Implemented logic to identify and skip citations not used in the body text.
- [x] **Mapping File**: Added generation of `_mapping.json` for audit trails and rollback capability.
- [x] **Rate Limiting**: Implemented `RateLimiter` with exponential backoff to handle NCBI API limits (429 errors).

### 3. Multi-Section Document Support
- [x] **Parser Update**: 
    - Added `multi_section=True` mode to `ReferenceParser`.
    - Successfully parses documents with multiple independent reference sections.
    - **NEW**: Handles body content that appears AFTER reference definitions (mid-document footnotes).
- [x] **Processing Logic**: 
    - Updated `CitationSculptor` to process each section independently.
    - Ensures inline reference replacements (`[^1]`) are scoped to their specific section.

### 4. Text-Only / Unknown Citation Handling
- [x] **Parser Update**:
    - Added support for text-only citations (e.g., "1. Title. Authors. Journal.").
    - Improved title extraction to handle "Title – Author" separators.
- [x] **Processing Logic**:
    - Configured system to attempt PubMed/CrossRef lookup for `CitationType.UNKNOWN` items instead of skipping them.

### 5. Footnote Definition Support
- [x] **Parser Update**:
    - Added `FOOTNOTE_DEF_PATTERN` to recognize `[^N]: Citation...` syntax.
    - Updated section detection to accept footnotes as valid reference content.
    - Added implicit section detection (footnotes without headers).

### 6. PMC ID Fallback to CrossRef (NEW - Nov 27)
- [x] **Issue**: Some PMC articles (e.g., PMC10206993) have no PMID but do have a DOI.
- [x] **Solution**: Updated `fetch_article_by_pmcid` to check for DOI when PMID is missing, then fetch metadata from CrossRef.
- [x] **Result**: Citation 14 in test document now resolves automatically (0 manual review items).

### 7. Alphabetical Reference Sorting (NEW - Nov 27)
- [x] **Feature**: References in output are now sorted alphabetically by citation label (author name).
- [x] **Implementation**: Added `sorted(result['processed'], key=lambda c: c.label.lower())` to `_format_section_references`.

### 8. Undefined Reference Detection (NEW - Nov 27)
- [x] **Feature**: System now detects and flags citations used in text but never defined in reference list.
- [x] **Console Output**: `[!] Warning: 2 undefined reference(s): [10, 18]`
- [x] **Output File**: Adds `### ⚠️ Undefined References` section listing missing definitions.
- [x] **Implementation**: Added `find_undefined_references()` method to `ReferenceParser`.

### 9. PDF Document Processing via PubMed (NEW - Nov 27)
- [x] **Issue**: PDF links (e.g., from `openaccess.sgul.ac.uk`, `sads.org`) were being formatted as generic webpages instead of proper journal citations.
- [x] **Solution**: PDF documents are now treated as potential journal articles and searched on PubMed by title.
- [x] **Result**: PDFs with PubMed-indexed content get full Vancouver citations with authors, journal, volume, pages, DOI, and PMID.

### 10. Long Title Search Fix (NEW - Nov 27)
- [x] **Issue**: PubMed searches with titles >200 characters were returning 0 results.
- [x] **Solution**: Truncated search queries to ~100 characters at word boundaries.
- [x] **Result**: "Standards and guidelines for the interpretation of sequence variants..." (PMID 25741868) now found successfully.

### 11. Full Metadata Fetch After Title Match (NEW - Nov 27)
- [x] **Issue**: When finding articles via title search, only limited metadata was returned (missing journal, volume, pages).
- [x] **Solution**: After a title match is verified, the system now fetches full metadata using `fetch_article_by_pmid`.
- [x] **Result**: All title-matched citations now have complete Vancouver formatting.

### 12. Webpage Metadata Scraping (NEW - Nov 27)
- [x] **Goal**: For webpages not found in PubMed, scrape `citation_*` meta tags from the HTML to extract proper metadata.
- [x] **Implementation**: Added `WebpageScraper` class to `pubmed_client.py` (originally separate file, but Obsidian Sync kept deleting it).
- [x] **Result**: Academic webpages like `biotech-asia.org` now get proper Vancouver citations:
  - **Before**: `[^BiotechAsia-FollowUp-n.d.]: Biotech-Asia. Follow-Up Alterations...`
  - **After**: `[^ShahsavarAR-2016]: Shahsavar AR, Pourvaghar MJ. Follow-Up Alterations... Biosciences Biotechnology Research Asia. 2016;8(2):591-595.`
- [x] **Limitations**: Some sites block scrapers (403 Forbidden), news sites often lack citation meta tags.

---

## 🔄 In Progress

*No tasks currently in progress.*

---

## 📋 Backlog / Future Tasks

### High Priority
- [ ] **Duplicate Detection**: Detect when multiple references point to the same PMID and merge/warn.

### Medium Priority
- [ ] **Better Title Search Fallback**: 
    - If exact title match fails, try fuzzy matching or searching by author + year.
- [ ] **GUI Improvements**:
    - Fix `tkinter` crash on macOS (requires newer Tcl/Tk or switching to a web-based/CLI-only UI).
    - Currently using Rich CLI progress bars (working well).
- [ ] **Refine CrossRef Formatting**:
    - Ensure non-PubMed journal articles (found via CrossRef) match Vancouver style perfectly.
- [ ] **Test Suite Expansion**:
    - Add unit tests for the new `multi_section` parser logic.
    - Add tests for `UNKNOWN` type detection and handling.

### Low Priority
- [ ] **Configurable Output Path**:
    - Allow user to specify exact output filename (currently auto-generated).
- [ ] **Performance Optimization**:
    - Parallelize API calls for even faster processing (careful with rate limits).

### Future Roadmap (from README)
- [ ] **Phase 5: Batch Processing**: Support processing multiple documents in a folder.
- [ ] **Phase 6: Obsidian Plugin**: Wrap this logic into a native Obsidian plugin for seamless usage.

---

## 🧪 Regression Testing

### Test Samples Location
`test_samples/` folder contains original test documents for backward compatibility testing.

### Test Files
| File | Format | Last Result |
|------|--------|-------------|
| `Right Ventricular Dilation...md` | V2 Extended + Multi-Section | ✅ PASS |
| `Gene Therapy Approaches...md` | V3 Footnotes (DOI links) | ✅ PASS |
| `Arrhythmogenic Cardiomyopathies - Genetics.md` | V3 Footnotes (body after refs) | ✅ PASS |
| `pelican_bay...md` | V1 Simple | ⚠️ Need original |

### Running Tests
```bash
# Quick smoke test (dry-run all files)
python citation_sculptor.py "test_samples/Right Ventricular Dilation...md" --multi-section --dry-run
python citation_sculptor.py "test_samples/Gene Therapy Approaches...md" --multi-section --dry-run
python citation_sculptor.py "test_samples/Arrhythmogenic Cardiomyopathies - Genetics.md" --multi-section --dry-run
```

See `test_samples/TEST_MANIFEST.md` for detailed test specifications.

---

## 🐛 Known Issues
- **Tkinter Crash**: The `--gui` flag causes a crash on macOS due to system Python version mismatch. *Workaround: Use CLI progress bars (default).*
- **Duplicate Citations**: If the original document has multiple references to the same article (different ref numbers), they may appear as duplicates in output.
- **Pelican Bay Original Missing**: The `pelican_bay` file in test_samples is already-processed output, not the original input.

---

## 📝 Notes
- **Server**: PubMed MCP server must be running on port 3017.
- **Rate Limits**: NCBI rate limits are stricter without an API key. Current delay is set to 200ms/request.
- **Empty PMID Fix**: Citations from CrossRef (no PMID) no longer show empty `[PMID: ]` links.

---

## 📜 Development Log & Retrospective

### Session: Nov 27, 2025 (Continued)

#### 1. Citation 14 Resolution (PMC10206993)
- **Problem**: PMC10206993 had no PMID in NCBI's ID converter, causing it to be flagged for manual review.
- **Discovery**: The ID converter DID return a DOI (`10.1093/europace/euad122.519`).
- **Fix**: Updated `fetch_article_by_pmcid` to fall back to CrossRef when PMID is missing but DOI is available.
- **Result**: Citation 14 now resolves automatically with full metadata from CrossRef.

#### 2. Body Content After References
- **Problem**: Document "Arrhythmogenic Cardiomyopathies - Genetics.md" had body text AFTER the reference definitions (lines 72-88), but this text wasn't being processed for inline replacements.
- **Fix**: Updated `parse_multi_section` to detect and include body content after references using a `<!-- REF_SECTION_MARKER -->` approach.
- **Result**: All inline references throughout the document are now replaced correctly.

#### 3. PDF Documents to PubMed
- **Problem**: PDF links were being formatted as generic webpages with labels like `[^Openaccess-StandardsGuidelines-n.d.]`.
- **Discovery**: These PDFs are often PubMed-indexed journal articles (e.g., PMID 25741868).
- **Fix**: Changed PDF handling from "treat as webpage" to "treat as potential journal article" and attempt PubMed title search.
- **Result**: Both PDF references in test document now have full Vancouver citations.

#### 4. Long Title Search Bug
- **Problem**: The title "Standards and guidelines for the interpretation of sequence variants: a joint consensus recommendation..." was too long (200+ chars) and caused PubMed search to return 0 results.
- **Fix**: Truncated search queries to ~100 characters at word boundaries.
- **Result**: Search now finds PMID 25741868 successfully.

#### 5. Incomplete Metadata from Title Search
- **Problem**: When finding articles via title search, the returned metadata was incomplete (authors showed as "J, a, m" instead of proper names).
- **Root Cause**: `verify_article_exists` was returning the limited search result metadata instead of fetching full article details.
- **Fix**: After title match verification, now calls `fetch_article_by_pmid` to get complete metadata.
- **Result**: All title-matched citations have proper author names, journal, volume, pages, DOI.

#### 6. Webpage Metadata Scraping
- **Problem**: Webpages not in PubMed were getting generic labels like `[^BiotechAsia-FollowUp-n.d.]`.
- **Solution**: Added `WebpageScraper` class that extracts `citation_*` meta tags from HTML.
- **Challenge**: Original `webpage_scraper.py` file kept getting deleted by Obsidian Sync. Moved code into `pubmed_client.py`.
- **Result**: `biotech-asia.org` citation now formatted as proper Vancouver with authors, journal, volume, issue, pages.

#### 7. Test Results Summary
**Document: Arrhythmogenic Cardiomyopathies - Genetics.md**
| Metric | Before Fixes | After Fixes |
|--------|--------------|-------------|
| Journal Articles | 2 | **4** (includes 2 PDFs) |
| Webpages w/ Scraped Metadata | 0 | **1** |
| Manual Review | 1 | **0** |
| Inline Replacements | 15 | **36** |
| Undefined Refs Flagged | 0 | **2** (`[^10]`, `[^18]`) |

---

### Previous Session: Nov 27, 2025 (Morning)

#### 1. Environment Migration (Windows → Mac)
- Deleted old Windows `venv`, created fresh Python 3.9.6 environment.
- Created new `.env` file for local configuration.

#### 2. Rate Limiting & API Stability
- Implemented `RateLimiter` class (2.5 requests/sec).
- Added exponential backoff retry logic (up to 4 attempts).
- Server delay increased to 200ms.

#### 3. Metadata Quality & Parsing
- Fixed nested `journalInfo` parsing.
- Added CrossRef integration for books/chapters.
- Fixed DOI extraction for complex URLs.

#### 4. Handling "Text-Only" Citations
- `UNKNOWN` citations now attempt title-based lookup.
- Improved title extraction with dash separator handling.

#### 5. Multi-Section Document Architecture
- Rewrote parser to detect multiple `# References` headers.
- Created Multi-Section Mode for independent processing.

#### 6. Footnote Definition Support
- Added `FOOTNOTE_DEF_PATTERN` for `[^N]:` syntax.
- Added implicit section detection (no header required).

#### 7. Search Tool Troubleshooting
- Fixed server's `fetchBriefSummaries` default (0 → 3).
- Updated client parsing for `briefSummaries` field.
