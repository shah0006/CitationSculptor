# CitationSculptor Planning

**Version:** 1.5.2 | **Updated:** Jun 2025 | **Status:** Active Development

## Quick Links
- [CHANGELOG.md](./CHANGELOG.md) - Version history
- [docs/ARCHITECTURE.md](./docs/ARCHITECTURE.md) - Technical reference
- [docs/TESTING.md](./docs/TESTING.md) - Testing guide
- [docs/COMPLETED_FEATURES.md](./docs/COMPLETED_FEATURES.md) - Feature archive

---

## 🎯 Vision: Comprehensive Citation Management

CitationSculptor aims to be the most comprehensive citation tool for researchers, supporting all source types with intelligent detection, multiple citation formats, and seamless Obsidian integration.

---

## ✅ Recently Completed

### v1.5.2 - Web UI & Enhanced Styles (Jun 2025)
- **Beautiful Web UI**: Modern browser interface at `http://127.0.0.1:3019`
  - Quick Lookup, PubMed Search, Batch Lookup, Recent History tabs
  - Dark theme with gradient accents, responsive design
  - One-click copy, live server status indicator
- **Enhanced Obsidian Plugin Styles**: Polished CSS with better visual hierarchy
- **Documentation**: Added "Why Unique Reference Tags?" section explaining semantic tag benefits

### v1.5.1 - HTTP Server & Obsidian Integration (Jun 2025)
- **HTTP Server**: Lightweight API server for Obsidian plugin
  - Eliminates CLI process spawning overhead
  - CORS-enabled, all endpoints exposed
- **macOS LaunchAgent**: Auto-start HTTP server on login
- **Improved Obsidian Plugin**: HTTP API integration with CLI fallback

### v1.5.0 - Interactive Mode & Obsidian Plugin (Jun 2025)
- **Interactive Mode**: `--interactive` / `-i` flag for REPL-style continuous lookups
  - Commands: `/search`, `/format`, `/cache`, `/help`, `/quit`
  - Auto-copy to clipboard on each lookup
- **Obsidian Plugin**: Native plugin with comprehensive UI
  - 4 tabs: Quick Lookup, PubMed Search, Batch, Recent
  - 8 command palette commands
  - Insert options: inline only, full citation, or both
  - Recent lookups history
  - Configurable settings

### v1.4.0 - CLI Enhancements (Jun 2025)
- **Clipboard Integration**: `--copy` / `-c` flag (macOS pbcopy)
- **Result Caching**: 30-day JSON cache, `--no-cache` to bypass
- **Search Multiple**: `--search-multi QUERY` with interactive table

### v1.3.x - API Refactor (May 2025)
- Direct E-utilities/CrossRef API integration
- Bug fixes for ID conversion and CrossRef lookup
- MCP server stdio transport

---

## 🚀 Roadmap to v2.0

### Phase 1: v1.6.0 - Multi-Format Support
**Goal**: Support multiple citation styles beyond Vancouver

| Feature | Status | Priority |
|---------|--------|----------|
| APA 7th Edition formatter | 📋 Planned | High |
| MLA 9th Edition formatter | 📋 Planned | Medium |
| Chicago/Turabian formatter | 📋 Planned | Medium |
| Harvard formatter | 📋 Planned | Low |
| IEEE formatter | 📋 Planned | Low |
| Custom format templates | 📋 Planned | Medium |
| Format selector in CLI | 📋 Planned | High |
| Format selector in Obsidian plugin | 📋 Planned | High |

### Phase 2: v1.7.0 - Enhanced Source Detection
**Goal**: Comprehensive support for all academic source types

| Feature | Status | Priority |
|---------|--------|----------|
| **Preprint Servers** | | |
| arXiv API integration | 📋 Planned | High |
| bioRxiv/medRxiv API | 📋 Planned | High |
| SSRN support | 📋 Planned | Medium |
| **Books** | | |
| ISBN lookup (Google Books) | 📋 Planned | High |
| OpenLibrary API | 📋 Planned | Medium |
| WorldCat integration | 📋 Planned | Low |
| **Academic Databases** | | |
| OpenAlex API | 📋 Planned | High |
| Semantic Scholar API | 📋 Planned | Medium |
| Unpaywall (open access) | 📋 Planned | Medium |
| **Web Sources** | | |
| Wayback Machine integration | 📋 Planned | High |
| News site domain detection | 📋 Planned | Medium |
| Improved blog detection | 📋 Planned | Medium |

### Phase 3: v1.8.0 - PDF & Document Support
**Goal**: Extract citations from PDF documents

| Feature | Status | Priority |
|---------|--------|----------|
| PDF metadata extraction | 📋 Planned | High |
| DOI extraction from PDF content | 📋 Planned | High |
| Title extraction from first page | 📋 Planned | Medium |
| PDF drag & drop in Obsidian | 📋 Planned | High |
| Google Scholar PDF matching | 📋 Planned | Low |
| Local PDF library indexing | 📋 Planned | Low |

### Phase 4: v1.9.0 - Import/Export
**Goal**: Interoperability with other citation tools

| Feature | Status | Priority |
|---------|--------|----------|
| **Export** | | |
| BibTeX export | 📋 Planned | High |
| RIS export | 📋 Planned | High |
| CSL-JSON export | 📋 Planned | Medium |
| EndNote XML | 📋 Planned | Low |
| **Import** | | |
| BibTeX import/parse | 📋 Planned | High |
| RIS import | 📋 Planned | Medium |
| **Integrations** | | |
| Zotero sync | 📋 Planned | High |
| Mendeley import | 📋 Planned | Low |

### Phase 5: v2.0.0 - Smart Features
**Goal**: AI-powered intelligence and vault-wide management

| Feature | Status | Priority |
|---------|--------|----------|
| **AI Features** | | |
| LLM-powered metadata extraction | 📋 Planned | High |
| Smart author name parsing | 📋 Planned | Medium |
| Automatic source type detection | 📋 Planned | High |
| Citation suggestions | 📋 Planned | Low |
| **Citation Management** | | |
| Citation database (SQLite) | 📋 Planned | High |
| Duplicate detection | 📋 Planned | High |
| Link verification | 📋 Planned | Medium |
| Link rot detection | 📋 Planned | Medium |
| **Obsidian Features** | | |
| Backlinks to citations | 📋 Planned | High |
| Citation graph visualization | 📋 Planned | Medium |
| Auto-bibliography generation | 📋 Planned | High |
| Templater integration | 📋 Planned | Medium |

---

## 📋 Implementation Priority Queue

### Immediate (v1.6.0)
1. APA 7th Edition formatter
2. Format selector in CLI and plugin
3. arXiv API integration

### Short-term (v1.7.0)
1. bioRxiv/medRxiv support
2. ISBN → Google Books lookup
3. Wayback Machine for archived URLs
4. OpenAlex API integration

### Medium-term (v1.8.0-1.9.0)
1. PDF content analysis
2. BibTeX export/import
3. Zotero integration

### Long-term (v2.0.0)
1. LLM-powered extraction
2. Citation database
3. Duplicate detection
4. Citation graph

---

## 🐛 Known Issues

| Issue | Workaround | Priority |
|-------|------------|----------|
| Tkinter crash on macOS | Use CLI mode | Low |
| Duplicate citations in output | Manual dedup | Medium |
| Some sites block scraping | Use Null placeholders | Low |

---

## 📝 Source Type Support Matrix

| Source Type | Detection | Lookup | Formatting | Status |
|-------------|-----------|--------|------------|--------|
| PubMed Articles | ✅ | ✅ | ✅ Vancouver | Complete |
| CrossRef Articles | ✅ | ✅ | ✅ Vancouver | Complete |
| Book Chapters | ✅ | ✅ | ✅ Vancouver | Complete |
| Books | ⚠️ ISBN only | ❌ | ✅ Vancouver | Partial |
| Webpages | ✅ | ✅ Scrape | ✅ Vancouver | Complete |
| News Articles | ✅ | ✅ Scrape | ✅ Vancouver | Complete |
| Blogs | ✅ | ✅ Scrape | ✅ Vancouver | Complete |
| PDFs | ⚠️ By title | ❌ | ✅ Vancouver | Partial |
| arXiv | ❌ | ❌ | ❌ | Planned v1.7 |
| bioRxiv/medRxiv | ❌ | ❌ | ❌ | Planned v1.7 |
| Google Books | ❌ | ❌ | ❌ | Planned v1.7 |

---

## 🔧 Technical Notes

### API Rate Limits
| API | Limit | Notes |
|-----|-------|-------|
| NCBI E-utilities | 3/sec (10 with key) | Using 2.5/sec |
| CrossRef | 50/sec polite | Using User-Agent |
| Google Books | 1000/day | Need API key |
| arXiv | No limit | Polite delay |
| OpenAlex | 100,000/day | Free tier |

### MCP Server
- Transport: stdio (stdin/stdout)
- Python 3.10+ required
- 12 tools available

### Key Commands
```bash
# Activate venv
source .venv/bin/activate

# Run tests
python -m pytest tests/ -v

# Interactive mode
python citation_lookup.py --interactive --copy

# Process document
python citation_sculptor.py "document.md" --multi-section
```

---

## 📊 Test Coverage

| Module | Tests | Coverage |
|--------|-------|----------|
| test_inline_replacer.py | 15 | ✅ |
| test_pubmed_client.py | 49 | ✅ |
| test_reference_parser.py | 48 | ✅ |
| test_type_detector.py | 10 | ✅ |
| test_vancouver_formatter.py | 52 | ✅ |
| test_citation_lookup.py | 20 | ✅ |
| test_mcp_server.py | 21 | ✅ |
| test_http_server.py | 11 | ✅ |
| **Total** | **226** | ✅ |
