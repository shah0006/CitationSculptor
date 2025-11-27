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

