# CitationSculptor Planning Document

## Project Status Overview
**Current Version:** 0.1.0
**Last Updated:** 2025-11-27
**Status:** Active Development (Mac Migration Complete)

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
- [x] **Processing Logic**: 
    - Updated `CitationSculptor` to process each section independently.
    - Ensures inline reference replacements (`[^1]`) are scoped to their specific section.

### 4. Text-Only / Unknown Citation Handling
- [x] **Parser Update**:
    - Added support for text-only citations (e.g., "1. Title. Authors. Journal.").
    - Improved title extraction to handle "Title – Author" separators.
- [x] **Processing Logic**:
    - Configured system to attempt PubMed/CrossRef lookup for `CitationType.UNKNOWN` items instead of skipping them.

## 🔄 In Progress / Pending Verification

- [ ] **Verification of Text-Only Lookup**: 
    - Need to confirm that the improved title extraction successfully resolves the ~39 text-only citations in the sample document.
    - *Next Step:* Run full processing on sample document to verify "Manual Review" count drops.

## 📋 Backlog / Future Tasks

### High Priority
- [ ] **Better Title Search Fallback**: 
    - If exact title match fails, try fuzzy matching or searching by author + year.
- [ ] **GUI Improvements**:
    - Fix `tkinter` crash on macOS (requires newer Tcl/Tk or switching to a web-based/CLI-only UI).
    - Currently using Rich CLI progress bars (working well).

### Medium Priority
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

## 🐛 Known Issues
- **Tkinter Crash**: The `--gui` flag causes a crash on macOS due to system Python version mismatch. *Workaround: Use CLI progress bars (default).*
- **Unresolved Text-Only Refs**: Some text-only citations may still fail lookup if the title extraction isn't perfect.

## 📝 Notes
- **Server**: PubMed MCP server must be running on port 3017.
- **Rate Limits**: NCBI rate limits are stricter without an API key. Current delay is set to 200ms/request.

---

## 📜 Development Log & Retrospective (Nov 27, 2025)

### 1. Environment Migration (Windows → Mac)
- **Challenge**: The project was originally set up on Windows. The `venv` contained `.exe` files incompatible with macOS.
- **Solution**: Deleted the old `venv`, created a fresh Python 3.9.6 environment, and reinstalled dependencies from `requirements.txt`. Created a new `.env` file for local configuration.

### 2. Rate Limiting & API Stability
- **Challenge**: The PubMed MCP server frequently returned HTTP 429 (Too Many Requests) errors, causing the pipeline to fail mid-process.
- **Solution**: 
  - Implemented a robust `RateLimiter` class in `pubmed_client.py` (2.5 requests/sec).
  - Added exponential backoff retry logic (up to 4 attempts with increasing delays).
  - Restarted the MCP server with a higher internal delay (200ms) to be safe.

### 3. Metadata Quality & Parsing
- **Challenge**: Some citations were missing DOIs or had incomplete metadata (missing volume/issue).
- **Solution**: 
  - Updated `pubmed_client.py` to correctly parse nested `journalInfo` from the API response.
  - Added a new `crossref_lookup_doi` tool usage to handle non-PubMed items (books, chapters).
  - Fixed DOI extraction regex to handle complex publisher URLs (e.g., Springer `/chapter/`, OUP `/article/`) and strip query parameters.

### 4. Handling "Text-Only" Citations
- **Challenge**: The sample document contained citations like `1. Recommendations... – Baggish et al., 2020.` without URLs. These were initially categorized as `UNKNOWN` and skipped.
- **Solution**: 
  - Updated `CitationSculptor` to attempt title-based lookup for `UNKNOWN` citations instead of ignoring them.
  - Improved `ReferenceParser` to intelligently split titles from authors using dash separators (` – `), significantly improving lookup success.

### 5. Multi-Section Document Architecture
- **Challenge**: The user provided a complex document with **two independent reference sections** (likely from merged LLM outputs). The original parser only found the last one, ignoring the first.
- **Solution**: 
  - Rewrote `ReferenceParser` to detect multiple `# References` headers.
  - Created a `Multi-Section Mode` in `CitationSculptor` that processes each section independently.
  - Ensured inline citation replacements (`[^1]`) are scoped strictly to their containing section, preserving document integrity.

### 6. Validation & Cleanup
- **Verified**: Validated backward compatibility with a simple single-section test file.
- **Cleanup**: Removed temporary test files (`test_old_format.md`, etc.) to keep the workspace clean.
- **Commit**: Pushed all changes to GitHub with detailed commit messages.
