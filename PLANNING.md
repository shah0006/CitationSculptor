# CitationSculptor Planning Document

## Project Status Overview
**Current Version:** 0.4.1
**Last Updated:** 2025-11-28
**Status:** Active Development

---

## 🚀 Where We Left Off

Based on our session today, here are some suggestions for what we could tackle next:

### 🎯 High-Value Quick Wins

#### 1. **Get the Original Pelican Bay File**
The `pelican_bay_preventive_health_comprehensive_report.md` in `test_samples/` is already processed output. If you have the original with numbered `[1]`, `[2]` references, providing it would complete our regression test suite and let us test the V1 Simple format.

#### 2. ~~**Add BeautifulSoup to Requirements**~~ ✅ DONE
Added `beautifulsoup4>=4.12.0` to requirements.txt.

### 📋 Medium Priority (Future Sessions)

#### 3. **Duplicate Citation Detection**
Currently if the same article appears twice with different reference numbers, both get processed separately. We could:
- Detect duplicates by PMID/DOI
- Warn the user
- Optionally merge them

#### 4. **Better Error Recovery**
When the MCP server is down or rate-limited, the program could:
- Cache successful lookups to a local file
- Resume from where it left off on retry
- Provide a "retry failed only" mode

#### 5. **Test the Pelican Bay Format**
Once we have the original, run a full regression to ensure V1 Simple format (numeric inline refs like `[1-3]`, `[1,2]`) still works perfectly.

### 🤔 Questions for Next Session

1. **Do you have the original Pelican Bay file?** (Pre-processed version with numbered refs)
2. **Any new sample documents to test?** We've been improving the system - would be good to stress-test with fresh content.

### ✅ Session Accomplishments (2025-11-28) - Part 2
- DOI path date extraction (e.g., `forefront.20201130` → 2020)
- Blog scraping for author/date metadata (previously only webpages)
- Console summary shows Null placeholder counts at end of processing
- Published date fallback (extract year from `published_date` when `year` empty)
- Added `beautifulsoup4` to requirements.txt
- Manual citation editing workflow (user adds corrections → AI applies them)
- Cleaned up samples/ and test_samples/ directories

### ✅ Session Accomplishments (2025-11-28) - Part 1
- V6 Grouped Footnotes format support
- JSON-LD date extraction for webpages (handles non-padded dates like `2023-1-2`)
- DOI text extraction from plain text references
- CrossRef title search fallback (finds articles not in PubMed)
- Smart organization abbreviation handling
- URL-based title recovery for truncated titles
- URL year extraction from paths (e.g., `/2019/article-title`)
- URL metadata fallback for blocked sites (extracts title, date, org from URL)
- Author + Organization combined citations
- Ellipsis removal from truncated titles
- Social media URL handling (skip garbage from LinkedIn/Twitter URLs)
- Custom meta tag support (`m_authors` for Milliman, etc.)
- Null placeholder system for missing data:
  - `Null_Date`, `Null_Author` in citation text (searchable)
  - `ND` in tags (compact)
  - Eliminates manual review section for blocked sites

### ✅ Session Accomplishments (2025-11-27)
- Webpage metadata scraping
- Regression testing infrastructure
- Housekeeping & documentation
- All tests passing
- GitHub updated (v0.3.0)

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

### 13. V6 Grouped Footnotes Format (NEW - Nov 28)
- [x] **Format**: `[^1] [^47] [^49] Title | Source` with URL on separate line `<https://...>`
- [x] **Implementation**:
  - Added `FOOTNOTE_NO_COLON_PATTERN` for grouped footnotes without colons
  - Multi-line parsing for angle-bracket URLs
  - Many-to-one deduplication (all grouped IDs → same output label)
  - `**Sources:**` recognized as reference header
- [x] **Result**: Document with 89 inline references → 39 unique citations processed

### 14. DOI Text Extraction (NEW - Nov 28)
- [x] **Issue**: Plain text references like `"...doi: 10.1234/xyz"` weren't being linked.
- [x] **Solution**: Added regex extraction for `doi:10.xxx` patterns in reference text.
- [x] **Result**: "Right Ventricular Dilation" article improved from 21 → 10 manual review items (63 more journal articles detected).

### 15. Enhanced Webpage Scraping (NEW - Nov 28)
- [x] **JSON-LD Date Extraction**: Parse `datePublished` from `<script type="application/ld+json">` blocks.
  - **Example**: AAMC page now extracts `2021` from structured data (was `n.d.`).
- [x] **Author Filtering**: Filter out CMS usernames (e.g., `kpage_drupal_sso`) from author fields.
- [x] **Author + Organization**: When both author and site_name exist, include both in citation.
  - **Example**: `Beck M. The Future of AI in Healthcare. MediPro, Inc. 2025.`

### 16. Improved Organization Handling (NEW - Nov 28)
- [x] **Smart Abbreviations**: Common organizations mapped to standard acronyms:
  - `American Medical Association` → `AMA`
  - `American Hospital Association` → `AHA`
  - `Center on Budget and Policy Priorities` → `CBPP`
- [x] **Acronym Detection**: Short domain names (≤5 chars, few vowels) uppercased automatically:
  - `cbpp.org` → `CBPP` (not `Cbpp`)
- [x] **Full Names in Citations**: Abbreviation in tag, full name in citation text:
  - `[^AMA-...]: American Medical Association. Title...`

### 17. URL-Based Title Extraction (NEW - Nov 28)
- [x] **Issue**: Truncated titles with `...` from original documents.
- [x] **Solution**: When title contains ellipsis, extract full title from URL slug.
- [x] **Example**: `States Can Use Medicaid to Help Address Health-Related Social ...` → `States Can Use Medicaid to Help Address Health Related Social Needs`

### 18. Blocked Site Detection with Guidance (NEW - Nov 28)
- [x] **Issue**: Sites with Cloudflare/403 blocks couldn't be scraped, leaving incomplete citations.
- [x] **Solution**: Detect blocking type and flag for manual review with specific guidance.
- [x] **Guidance Provided**:
  - AUTHOR (look for byline or 'Written by')
  - PUBLICATION DATE (check article header or footer)
  - ORGANIZATION NAME (check page header/logo)
- [x] **Block Types Detected**: `blocked_cloudflare`, `blocked_403`, `blocked_javascript`, `timeout`

### 19. Improved URL Year Extraction (NEW - Nov 28)
- [x] **Issue**: Year in URLs like `/2019/article-title` wasn't being extracted.
- [x] **Solution**: Added pattern to match `/YYYY/` followed by content slug.
- [x] **Example**: Johns Hopkins URL now extracts 2019 from path.

### 20. Ellipsis Removal (NEW - Nov 28)
- [x] **Issue**: Titles with `...` from original documents looked incomplete.
- [x] **Solution**: Strip ellipses from titles when no better alternative found.
- [x] **Result**: Clean titles without trailing `...`

### 21. Social Media URL Handling (NEW - Nov 28)
- [x] **Issue**: LinkedIn/Twitter URL slugs produced garbage titles (e.g., `jake-pyles-8a7518_were-295800...`).
- [x] **Solution**: Skip URL-based title extraction for social media domains.
- [x] **Result**: LinkedIn posts now use scraped `og:title` which is clean.

### 22. Non-Padded Date Parsing (NEW - Nov 28)
- [x] **Issue**: JSON-LD dates like `2023-1-2` (no leading zeros) weren't being parsed.
- [x] **Solution**: Updated regex to match `\d{1,2}` for month/day, then pad with `zfill(2)`.
- [x] **Result**: Milliman article now extracts year 2023 from JSON-LD.

### 23. Custom Meta Tag Support (NEW - Nov 28)
- [x] **Issue**: Sites like Milliman use `m_authors` instead of standard `author` meta tag.
- [x] **Solution**: Added `m_authors`, `m_author` to GENERAL_PATTERNS.
- [x] **Result**: Milliman article now shows `Jensen B.` as author.

### 24. CrossRef Title Search Fallback (NEW - Nov 28)
- [x] **Issue**: Articles in CrossRef but not PubMed weren't being found (e.g., ScienceDirect).
- [x] **Solution**: Added `crossref_search_title()` method with direct CrossRef API call.
- [x] **Result**: "COVID-19 pandemic and artificial intelligence possibilities" now resolved via CrossRef.

### 25. URL Metadata Fallback for Blocked Sites (NEW - Nov 28)
- [x] **Issue**: Sites blocking scrapers (403, Cloudflare) returned no metadata.
- [x] **Solution**: Extract title, date, and organization from URL patterns when scraping fails.
- [x] **Features**:
  - Known domains mapped to organization names (Politico, NYT, Reuters, etc.)
  - Date extraction from URL paths (`/2025/04/09/`)
  - Title extraction from URL slugs
- [x] **Result**: Blocked Politico article now has title and date from URL.

### 26. Null Placeholder System (NEW - Nov 28)
- [x] **Issue**: Manual review section was cluttered with blocked sites.
- [x] **Solution**: Use searchable placeholders instead of manual review:
  - `Null_Date` in citation text (searchable with Cmd+F)
  - `ND` in citation tags (compact)
  - `Null_Author` when author is missing
- [x] **Result**: Manual review reduced to 0 items; search for `Null_` to find incomplete citations.

---

## 🔄 In Progress

*No items currently in progress.*

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
| `Right Ventricular Dilation...md` | V2 Extended + Multi-Section | ✅ PASS (10 manual review) |
| `Gene Therapy Approaches...md` | V3 Footnotes (DOI links) | ✅ PASS |
| `Arrhythmogenic Cardiomyopathies - Genetics.md` | V3 Footnotes (body after refs) | ✅ PASS |
| `Future Healthcare Delivery Models...md` | V6 Grouped Footnotes | ✅ PASS (9 blocked sites flagged) |
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
