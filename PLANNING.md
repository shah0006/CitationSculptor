# CitationSculptor Planning

**Version:** 1.7.0 | **Updated:** Jun 2025 | **Status:** Active Development

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

### v1.7.0 - Enhanced Source Detection (Jun 2025)
- **arXiv Integration**: Full support for arXiv preprint lookup
  - Auto-detect arXiv IDs (e.g., `2301.04104`, `arxiv:2301.04104`)
  - New `modules/arxiv_client.py` with search and metadata fetching
  - Proper preprint citation formatting with category and URL
- **bioRxiv/medRxiv Support**: Preprint server integration (API limitations noted)
  - New `modules/preprint_client.py` for bioRxiv/medRxiv API
  - Auto-detect preprint DOIs (10.1101/...)
- **ISBN Lookup**: Book citation support via Google Books and OpenLibrary
  - New `modules/book_client.py` with dual-API fallback
  - Validates ISBN-10 and ISBN-13 checksums
  - Rich book metadata including publisher, page count, edition
- **Enhanced Auto-Detection**: `lookup_auto()` handles all identifier types

### v1.6.0 - Multi-Format Support (Jun 2025)
- **6 Citation Styles**: Vancouver, APA 7th, MLA 9th, Chicago, Harvard, IEEE
- **Base Formatter Architecture**: `modules/base_formatter.py` with inheritance
- **CLI Style Support**: `--style` flag, `--list-styles`, `/style` in interactive mode
- **Web UI & Obsidian Plugin**: Style selector dropdowns

### v1.5.2 - Web UI & Enhanced Styles (Jun 2025)
- **Beautiful Web UI**: Modern browser interface at `http://127.0.0.1:3019`
  - Quick Lookup, PubMed Search, Batch Lookup, Recent History tabs
  - Dark theme with gradient accents, responsive design
  - One-click copy, live server status indicator
- **Enhanced Obsidian Plugin Styles**: Polished CSS with better visual hierarchy
- **Documentation**: Added "Why Unique Reference Tags?" section

### v1.5.0-1.5.1 - Interactive Mode & HTTP Server (Jun 2025)
- **Interactive Mode**: `--interactive` / `-i` flag for REPL-style lookups
- **HTTP Server**: Lightweight API for Obsidian plugin (eliminates CLI overhead)
- **Obsidian Plugin**: 4-tab UI, 8 commands, HTTP API integration

### v1.4.0 - CLI Enhancements (Jun 2025)
- **Clipboard**: `--copy` flag | **Caching**: 30-day JSON cache | **Multi-search**: Interactive table

---

## 🚀 Roadmap to v2.0

### ✅ Phase 1: v1.6.0 - Multi-Format Support (COMPLETED)
All planned formatters implemented, style selection in CLI/Web UI/Obsidian plugin.

### ✅ Phase 2: v1.7.0 - Enhanced Source Detection (COMPLETED)
arXiv, bioRxiv/medRxiv, ISBN lookup all implemented with auto-detection.

### Phase 3: v1.8.0 - Additional Sources & Wayback Machine
**Goal**: More academic databases and web source handling

| Feature | Status | Priority |
|---------|--------|----------|
| Wayback Machine integration | 📋 Planned | High |
| OpenAlex API | 📋 Planned | High |
| Semantic Scholar API | 📋 Planned | Medium |
| Unpaywall (open access links) | 📋 Planned | Medium |
| SSRN support | 📋 Planned | Low |
| WorldCat integration | 📋 Planned | Low |

### Phase 4: v1.9.0 - PDF & Document Support
**Goal**: Extract citations from PDF documents

| Feature | Status | Priority |
|---------|--------|----------|
| PDF metadata extraction | 📋 Planned | High |
| DOI extraction from PDF content | 📋 Planned | High |
| Title extraction from first page | 📋 Planned | Medium |
| PDF drag & drop in Obsidian | 📋 Planned | High |
| Google Scholar PDF matching | 📋 Planned | Low |
| Local PDF library indexing | 📋 Planned | Low |

### Phase 5: v1.10.0 - Import/Export
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

### Phase 6: v2.0.0 - Smart Features
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

### Immediate (v1.8.0)
1. Wayback Machine for archived URLs
2. OpenAlex API integration
3. Semantic Scholar API

### Short-term (v1.9.0)
1. PDF content analysis
2. PDF metadata extraction
3. Obsidian drag & drop

### Medium-term (v1.10.0)
1. BibTeX export/import
2. RIS export/import
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
| PubMed Articles | ✅ | ✅ | ✅ 6 styles | Complete |
| CrossRef Articles | ✅ | ✅ | ✅ 6 styles | Complete |
| Book Chapters | ✅ | ✅ | ✅ 6 styles | Complete |
| **Books (ISBN)** | ✅ | ✅ Google/OpenLib | ✅ 6 styles | **v1.7** |
| **arXiv** | ✅ | ✅ | ✅ preprint | **v1.7** |
| **bioRxiv/medRxiv** | ✅ | ⚠️ API limits | ✅ preprint | **v1.7** |
| Webpages | ✅ | ✅ Scrape | ✅ 6 styles | Complete |
| News Articles | ✅ | ✅ Scrape | ✅ 6 styles | Complete |
| Blogs | ✅ | ✅ Scrape | ✅ 6 styles | Complete |
| PDFs | ⚠️ By title | ❌ | ✅ 6 styles | Partial |
| OpenAlex | ❌ | ❌ | ❌ | Planned v1.8 |
| Semantic Scholar | ❌ | ❌ | ❌ | Planned v1.8 |

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
