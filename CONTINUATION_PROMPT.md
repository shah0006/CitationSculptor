# CitationSculptor Continuation Prompt

## Current State: v2.1.0 (Complete)

CitationSculptor is a comprehensive citation management toolkit that has been fully developed through v2.1. All major features are implemented and working, including the new Document Intelligence features.

## What's Been Completed

### Core Features (v1.0-v1.5)
- ✅ Citation lookup via PMID, DOI, PMC ID, title, URL
- ✅ Vancouver-style citation formatting
- ✅ Interactive CLI mode with REPL
- ✅ Clipboard integration
- ✅ Result caching (30-day)
- ✅ Batch processing
- ✅ Document processing (`citation_sculptor.py`)

### v1.6.0 - Multi-Format Citation Styles
- ✅ Vancouver, APA 7th, MLA 9th, Chicago, Harvard, IEEE
- ✅ `modules/base_formatter.py`, `apa_formatter.py`, `mla_formatter.py`, etc.
- ✅ `modules/formatter_factory.py` for style selection

### v1.7.0 - Enhanced Sources
- ✅ arXiv API (`modules/arxiv_client.py`)
- ✅ bioRxiv/medRxiv (`modules/preprint_client.py`)
- ✅ ISBN lookup via Google Books/OpenLibrary (`modules/book_client.py`)

### v1.8.0 - Additional Sources
- ✅ Wayback Machine (`modules/wayback_client.py`)
- ✅ OpenAlex API (`modules/openalex_client.py`)
- ✅ Semantic Scholar API (`modules/semantic_scholar_client.py`)
- ✅ PDF metadata extraction (`modules/pdf_extractor.py`)

### v1.9.0 - Import/Export
- ✅ BibTeX handler (`modules/bibtex_handler.py`)
- ✅ RIS handler (`modules/ris_handler.py`)

### v2.0.0 - Smart Features
- ✅ SQLite citation database (`modules/citation_database.py`)
- ✅ Duplicate detection (`modules/duplicate_detector.py`)
- ✅ Bibliography generation (`modules/bibliography_generator.py`)
- ✅ Document processing across all interfaces

### v2.1.0 - Document Intelligence (Dec 2025)
- ✅ Link verification & broken link detection (`modules/document_intelligence.py`)
- ✅ Automatic citation suggestions based on content
- ✅ Plagiarism-style citation compliance checker
- ✅ LLM-powered metadata extraction for edge cases
- ✅ HTTP API endpoints: `/api/verify-links`, `/api/suggest-citations`, `/api/check-compliance`, `/api/analyze-document`
- ✅ MCP tools: `citation_verify_links`, `citation_suggest_citations`, `citation_check_compliance`, `citation_analyze_document`, `citation_extract_metadata_llm`

### Interfaces
- ✅ CLI: `citation_lookup.py` (single lookups, interactive mode)
- ✅ CLI: `citation_sculptor.py` (document processing)
- ✅ Web UI: `web/index.html` (served by HTTP server)
- ✅ Obsidian Plugin: `obsidian-plugin/` (uses HTTP API)
- ✅ MCP Server: `mcp_server/server.py` (stdio for AI assistants)
- ✅ HTTP Server: `mcp_server/http_server.py` (port 3019, serves Web UI + API)
- ✅ Streamlit GUI: `gui.py`

## Key Files

| File | Purpose |
|------|---------|
| `citation_lookup.py` | Single citation CLI with --interactive mode |
| `citation_sculptor.py` | Document processing CLI |
| `mcp_server/server.py` | MCP server (stdio transport) |
| `mcp_server/http_server.py` | HTTP API server (port 3019) |
| `web/index.html` | Web UI (served by HTTP server) |
| `obsidian-plugin/main.ts` | Obsidian plugin source |
| `README.md` | Full documentation |
| `PLANNING.md` | Project roadmap |
| `CHANGELOG.md` | Version history |

## Running the Project

```bash
cd /Users/tusharshah/Developer/MCP-Servers/CitationSculptor

# Activate venv
source .venv/bin/activate

# Start HTTP server (for Web UI and Obsidian plugin)
python -m mcp_server.http_server --port 3019

# Web UI available at: http://127.0.0.1:3019

# Run tests
python -m pytest tests/ -v
```

## MCP Configuration

The MCP server is configured in `~/.cursor/mcp.json`:
```json
{
  "mcpServers": {
    "citation-lookup-mcp": {
      "command": "/Users/tusharshah/Developer/MCP-Servers/CitationSculptor/.venv/bin/python",
      "args": ["-m", "mcp_server.server"],
      "cwd": "/Users/tusharshah/Developer/MCP-Servers/CitationSculptor"
    }
  }
}
```

## Recent Updates (Just Completed)

### Dec 17, 2025 - Document Intelligence (v2.1.0)
1. **Link Verification & Broken Link Detection:**
   - Parallel URL checking with configurable workers
   - Detects: OK, broken, redirect, timeout, paywall, archived
   - Wayback Machine fallback for broken links
   - Document scanning extracts all URLs automatically

2. **Citation Suggestions:**
   - Pattern-based detection of uncited content
   - Categories: statistics, claims, definitions, findings
   - Optional PubMed search for suggested citations
   - Confidence scoring and search term extraction

3. **Citation Compliance Checker:**
   - Detects uncited quotes, academic phrases, medical claims
   - Severity levels: high, medium, low
   - Compliance score (0-100) and recommendations
   - Skips headers, code blocks, and already-cited content

4. **Comprehensive Document Analysis:**
   - `/api/analyze-document` endpoint for full analysis
   - Overall health score combining all checks
   - MCP tool `citation_analyze_document` for AI agents

5. **LLM Metadata Extraction:**
   - Uses local Ollama (llama3:8b) for edge case extraction
   - Site rules database for domain-specific hints
   - Learning capability for new domains

### Dec 17, 2025 - Safety Features & Backup System
1. **Obsidian Plugin Safety Features:**
   - Added automatic backup before processing notes (creates timestamped `filename_backup_YYYYMMDD_HHMMSS.md`)
   - Added "Restore from Last Backup" command
   - Added safety toggle in settings (enabled by default)
   - Confirmation dialogs now show backup status

2. **HTTP Server Safety Features:**
   - Added automatic backup when processing files via `/api/process-document` with `file_path`
   - Backup path included in response
   - New `create_backup` parameter (default: true)

3. **MCP Server Safety Features:**
   - Added backup creation for `citation_process_document` tool
   - Backup path shown in output
   - New `create_backup` parameter (default: true)

### Dec 17, 2025 - Auto-Save & One-Click Restore
1. **Auto-Save Feature:**
   - New `save_to_file` parameter in `/api/process-document`
   - When enabled, writes processed content directly back to original file
   - Backup ALWAYS created first (enforced when saving)
   - Web UI checkbox "💾 Save to original file" in File Path mode

2. **One-Click Restore:**
   - "🔄 Restore Original" button in Web UI after saving
   - `/api/restore-backup` endpoint for programmatic restore
   - Confirmation dialog prevents accidental restores
   - Success message shows restored file path

3. **Improved Error Messages:**
   - Detailed error types: `pubmed_not_found`, `invalid_doi_url`, `url_not_recognized`, etc.
   - Actionable suggestions for each error type
   - Shows URL and title for failed references
   - Expandable error panel with full details

### Dec 17, 2025 - Real-Time Progress & Streaming
1. **Server-Sent Events (SSE) Streaming:**
   - New `/api/process-document-stream` endpoint
   - Events: `status`, `progress`, `ref_processed`, `complete`, `error`
   - Real-time statistics as each reference is processed

2. **Web UI Progress Display:**
   - Live progress bar with percentage
   - Running statistics (Total/Processed/Failed)
   - Current reference being looked up
   - Smooth fallback to regular endpoint if streaming fails

### Dec 17, 2025 - Comprehensive File Logging
1. **Logging System:**
   - New `modules/logging_setup.py` module
   - Loguru-based with file rotation
   - Three log files in `.data/logs/`:
     - `citationsculptor.log` - Main application log (DEBUG level)
     - `errors.log` - Critical errors only
     - `document_processing.log` - Backup/restore/save operations

2. **Log Configuration:**
   - `ENABLE_FILE_LOGGING` (default: true)
   - `LOG_ROTATION_SIZE_MB` (default: 10)
   - `LOG_RETENTION_COUNT` (default: 5)

3. **Log API Endpoints:**
   - `/api/logs/info` - List log files with sizes
   - `/api/logs?type=main&lines=100` - View recent logs

### Dec 17, 2025 - Maintenance & Testing
1. Fixed asyncio deprecation warning in `tests/test_mcp_server.py`
   - Updated `run_async()` helper to use `asyncio.new_event_loop()` instead of deprecated `asyncio.get_event_loop()`
2. Verified duplicate detection is implemented (DuplicateDetector module + `/api/duplicates` endpoint)
   - Updated PLANNING.md to remove outdated "duplicate citations" known issue
3. Updated documentation test counts (166 → 226 tests)
4. Ran full test suite: **226 tests passing, 0 warnings**
5. Verified HTTP server and Web UI functionality

### Previous Updates
1. Updated README.md:
   - Changed "Roadmap" section to "Version History" showing all v1.6-v2.0 as complete
   - Added expanded "Future Roadmap" section (v2.1-v2.4 planned features)
   - Updated Source Type Support table - all sources now show ✅ Supported
   - Added OpenAlex and Semantic Scholar to source table
   - Fixed "Output Formats" to show all 6 citation styles as available

2. Web UI About Page:
   - Added `/api/about` endpoint to serve README.md
   - Added client-side markdown renderer
   - Compact CSS for documentation display

## Future Roadmap (Planned)

### v2.4.0 - Reference Manager Integration
- Zotero library sync (two-way)
- Mendeley integration
- EndNote support

### v2.5.0 - Visualization & Analytics
- Citation network graph visualization
- Co-author network mapping

### v2.6.0 - Collaboration Features
- Shared citation libraries
- Team workspaces

> **v2.1.0 Document Intelligence - COMPLETED!**

## Pending Tasks

- Push v2.1.0 changes to GitHub
- Run full test suite to verify all new features
- User may need to hard-refresh browser (Cmd+Shift+R) to see updated features

## Notes

- HTTP server runs on port 3019 (localhost only, secure)
- All tests pass (292+ tests including document intelligence, safety, and integration tests)
- bioRxiv/medRxiv API can be finicky (marked as ⚠️ Partial for Lookup)
- Obsidian plugin requires HTTP server to be running for best performance
- LLM metadata extraction requires Ollama running locally with llama3:8b model
- Link verification makes actual HTTP requests (may be slow for many URLs)
- Logs are stored in `.data/logs/` with automatic rotation
- Backups are created in the same directory as the original file

