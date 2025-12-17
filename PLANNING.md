# CitationSculptor Planning

**Version:** 1.4.0 | **Updated:** Jun 2025 | **Status:** Active Development

## Quick Links
- [CHANGELOG.md](./CHANGELOG.md) - Version history
- [docs/ARCHITECTURE.md](./docs/ARCHITECTURE.md) - Technical reference
- [docs/TESTING.md](./docs/TESTING.md) - Testing guide
- [docs/COMPLETED_FEATURES.md](./docs/COMPLETED_FEATURES.md) - Feature archive

---

## 🎯 Current Focus

**Completed: MCP Server - Abacus Desktop Integration**

Converted MCP server from HTTP to stdio transport for compatibility with Abacus Desktop.

---

## ✅ Recently Completed (Jun 2025)

### citation_lookup.py Enhancements (v1.4.0)
- **Clipboard Integration**: `--copy` / `-c` flag copies citation to clipboard via `pbcopy` (macOS)
- **Result Caching**: Persistent JSON cache (`.cache/citation_cache.json`) with 30-day expiry, `--no-cache` to bypass
- **Search Multiple**: `--search-multi QUERY` shows interactive Rich table of up to 5 PubMed results

### API Client Refactor (v1.3.1) - May 2025
- **Direct API Integration**: Restored direct E-utilities/CrossRef access in `PubMedClient` to fix server dependency issues.
- **Bug Fixes**: Resolved valid-but-crashing type errors in ID conversion and missing methods in CrossRef lookup.
- **Cleanup**: Removed unused legacy code and temporary methods (`_parse_conversion_result`, etc.).

### MCP Server Conversion (v1.3.0) - Dec 2024
- **Transport:** HTTP (aiohttp port 3018) → stdio (stdin/stdout)
- **SDK:** Now uses official `mcp` Python SDK
- **Python:** Requires 3.10+ (MCP SDK requirement)
- **Tools:** 7 citation lookup tools available via MCP protocol
- **Rollback:** Previous HTTP version tagged as `v1.2.0-http`

### Abacus Desktop Configuration
```json
{
  "citation-lookup": {
    "command": "/path/to/CitationSculptor/.venv/bin/python",
    "args": ["-m", "mcp_server.server"],
    "cwd": "/path/to/CitationSculptor"
  }
}
```

---

## 📋 Next Steps (Priority Order)

### High Priority - citation_lookup.py Enhancements
1. **Interactive Mode** - Run continuously, entering identifiers one at a time
2. ~~**Clipboard Integration**~~ ✅ Completed in v1.4.0
3. **Obsidian Integration** - Output format optimized for pasting into Obsidian
4. ~~**Search Multiple**~~ ✅ Completed in v1.4.0
5. ~~**Cache Results**~~ ✅ Completed in v1.4.0

### Medium Priority - citation_sculptor.py
1. **Duplicate Detection** - Detect/merge same PMID with different ref numbers
2. **Better Error Recovery** - Cache successful lookups, resume from failures
3. **V7/V8 Format Testing** - Real-world testing of new formats

### Low Priority
- Configurable output path
- Performance optimization (parallel API calls)
- Batch folder processing
- Obsidian plugin

---

## 🐛 Known Issues

| Issue | Workaround |
|-------|------------|
| Tkinter crash on macOS | Use CLI mode (default) |
| Duplicate citations in output | Manual dedup needed |

---

## 📝 Quick Reference

### MCP Server Setup
```bash
# Create venv with Python 3.10+
uv venv --python 3.12
uv pip install -r requirements.txt

# Test server imports
source .venv/bin/activate
python -c "from mcp_server.server import server; print('OK')"
```

### Key Commands
```bash
# Activate venv
source .venv/bin/activate

# Run tests
python -m pytest tests/ -v

# Process document
python citation_sculptor.py "document.md" --multi-section

# Single lookup
python citation_lookup.py --pmid 32089132
```

### Important Design Notes
- MCP server uses stdio transport (not HTTP)
- Rate limit: 2.5 req/sec (no NCBI API key)
- Null placeholders: `Null_Date`, `Null_Author` (searchable)
- **Table Escaping:** Inline refs in markdown tables need single backslash: `\[^ref]` (auto-handled)
