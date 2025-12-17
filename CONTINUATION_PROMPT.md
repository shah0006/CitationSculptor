# CitationSculptor Continuation Prompt

## Current State: v2.0.1 (Complete)

CitationSculptor is a comprehensive citation management toolkit that has been fully developed through v2.0. All major features are implemented and working.

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

### v2.1.0 - Reference Manager Integration
- Zotero library sync (two-way)
- Mendeley integration
- EndNote support

### v2.2.0 - Visualization & Analytics
- Citation network graph visualization
- Co-author network mapping

### v2.3.0 - Document Intelligence
- LLM-powered metadata extraction for edge cases
- Link verification & broken link detection

### v2.4.0 - Collaboration Features
- Shared citation libraries
- Team workspaces

## Pending Tasks

- Push latest README changes to GitHub
- User may need to hard-refresh browser (Cmd+Shift+R) to see updated About page

## Notes

- HTTP server runs on port 3019 (localhost only, secure)
- All tests pass (226 tests, 0 warnings)
- bioRxiv/medRxiv API can be finicky (marked as ⚠️ Partial for Lookup)
- Obsidian plugin requires HTTP server to be running for best performance

