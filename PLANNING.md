# CitationSculptor Planning

**Version:** 2.0.0 | **Updated:** Jun 2025 | **Status:** ✅ v2.0 Complete!

## Quick Links
- [CHANGELOG.md](./CHANGELOG.md) - Version history
- [docs/ARCHITECTURE.md](./docs/ARCHITECTURE.md) - Technical reference
- [docs/TESTING.md](./docs/TESTING.md) - Testing guide
- [docs/COMPLETED_FEATURES.md](./docs/COMPLETED_FEATURES.md) - Feature archive

---

## 🎯 Vision: Comprehensive Citation Management

CitationSculptor aims to be the most comprehensive citation tool for researchers, supporting all source types with intelligent detection, multiple citation formats, and seamless Obsidian integration.

---

## ✅ All Phases Complete - v2.0.0 Achieved!

### v2.0.0 - Smart Features (Jun 2025) ✅
- **Citation Database**: SQLite-backed storage with FTS5 search, tags, collections
- **Duplicate Detection**: Multi-strategy matching (DOI, title fuzzy, author/year)
- **Auto-Bibliography**: Extract citations, generate bibliographies, find undefined refs

### v1.10.0 - Import/Export (Jun 2025) ✅
- **BibTeX Handler**: Full parse/export with auto cite keys
- **RIS Handler**: Complete RIS format support

### v1.9.0 - PDF Support (Jun 2025) ✅
- **PDF Extractor**: Extract DOIs, arXiv IDs, PMIDs from PDFs
- **Metadata Extraction**: Title, authors, dates from PDF metadata

### v1.8.0 - Enhanced Sources (Jun 2025) ✅
- **Wayback Machine**: Archive URL lookup and citation formatting
- **OpenAlex API**: 100k requests/day, citations/references
- **Semantic Scholar**: AI-powered search, TLDR summaries, recommendations

### v1.7.0 - Enhanced Source Detection (Jun 2025) ✅
- **arXiv Integration**: Full preprint support with categories
- **bioRxiv/medRxiv**: Preprint server APIs
- **ISBN Lookup**: Google Books + OpenLibrary

### v1.6.0 - Multi-Format Support (Jun 2025) ✅
- **6 Citation Styles**: Vancouver, APA, MLA, Chicago, Harvard, IEEE
- **Style Selection**: CLI, Web UI, Obsidian plugin

### v1.5.x - User Interfaces (Jun 2025) ✅
- **Web UI**: Beautiful dark-themed browser interface
- **Obsidian Plugin**: 4-tab comprehensive plugin
- **HTTP Server**: Efficient API for integrations
- **Interactive Mode**: REPL with commands

### v1.4.0 - CLI Enhancements (Jun 2025) ✅
- Clipboard integration, caching, multi-search

---

## 🚀 Roadmap Summary - ALL COMPLETE!

### ✅ Phase 1: v1.6.0 - Multi-Format Support
### ✅ Phase 2: v1.7.0 - Enhanced Source Detection
### ✅ Phase 3: v1.8.0 - Additional Sources & Wayback
### ✅ Phase 4: v1.9.0 - PDF & Document Support
### ✅ Phase 5: v1.10.0 - Import/Export
### ✅ Phase 6: v2.0.0 - Smart Features

## 🎯 Future Enhancements (Post v2.0)

| Feature | Priority | Notes |
|---------|----------|-------|
| Zotero sync integration | Medium | Bi-directional sync |
| CSL-JSON export | Medium | For Pandoc/Citation.js |
| Citation graph visualization | Low | D3.js or Obsidian Graph |
| LLM-powered metadata extraction | Low | Use local LLMs |
| Link rot detection | Low | Periodic URL checking |
| SSRN support | Low | Niche academic |
| WorldCat integration | Low | Library catalog |

---

## 📋 New Modules Added (v1.8.0-v2.0.0)

### v1.8.0 - Additional Sources
- `modules/wayback_client.py` - Internet Archive integration
- `modules/openalex_client.py` - OpenAlex scholarly API
- `modules/semantic_scholar_client.py` - AI-powered search

### v1.9.0 - PDF Support
- `modules/pdf_extractor.py` - PDF metadata & DOI extraction

### v1.10.0 - Import/Export
- `modules/bibtex_handler.py` - BibTeX parse/export
- `modules/ris_handler.py` - RIS parse/export

### v2.0.0 - Smart Features
- `modules/citation_database.py` - SQLite citation storage
- `modules/duplicate_detector.py` - Duplicate finding
- `modules/bibliography_generator.py` - Auto-bibliography

---

## 🐛 Known Issues

| Issue | Workaround | Priority |
|-------|------------|----------|
| Tkinter crash on macOS | Use CLI mode | Low |
| Duplicate citations in output | Manual dedup | Medium |
| Some sites block scraping | Use Null placeholders | Low |

---

## 📝 Source Type Support Matrix (v2.0)

| Source Type | Detection | Lookup | Formatting | Status |
|-------------|-----------|--------|------------|--------|
| PubMed Articles | ✅ | ✅ | ✅ 6 styles | Complete |
| CrossRef Articles | ✅ | ✅ | ✅ 6 styles | Complete |
| Book Chapters | ✅ | ✅ | ✅ 6 styles | Complete |
| **Books (ISBN)** | ✅ | ✅ Google/OpenLib | ✅ 6 styles | **v1.7** ✅ |
| **arXiv** | ✅ | ✅ arXiv API | ✅ 6 styles | **v1.7** ✅ |
| **bioRxiv/medRxiv** | ✅ | ✅ | ✅ 6 styles | **v1.7** ✅ |
| Webpages | ✅ | ✅ Scrape | ✅ 6 styles | Complete |
| **+ Wayback** | ✅ | ✅ Archive.org | ✅ archived URL | **v1.8** ✅ |
| **OpenAlex** | ✅ | ✅ | ✅ 6 styles | **v1.8** ✅ |
| **Semantic Scholar** | ✅ | ✅ + TLDR | ✅ 6 styles | **v1.8** ✅ |
| **PDFs** | ✅ DOI/arXiv/PMID | ✅ extract | ✅ 6 styles | **v1.9** ✅ |
| **BibTeX** | ✅ import | ✅ parse | ✅ export | **v1.10** ✅ |
| **RIS** | ✅ import | ✅ parse | ✅ export | **v1.10** ✅ |

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
