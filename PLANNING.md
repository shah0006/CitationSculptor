# CitationSculptor Planning

**Version:** 2.4.1 | **Updated:** Jan 13, 2026 | **Status:** ✅ v2.4.1 Complete

## Quick Links
- [CHANGELOG.md](./CHANGELOG.md) - Version history
- [docs/ARCHITECTURE.md](./docs/ARCHITECTURE.md) - Technical reference
- [docs/TESTING.md](./docs/TESTING.md) - Testing guide
- [docs/COMPLETED_FEATURES.md](./docs/COMPLETED_FEATURES.md) - Feature archive

---

## 🎯 Vision: Comprehensive Citation Management

CitationSculptor aims to be the most comprehensive citation tool for researchers, supporting all source types with intelligent detection, multiple citation formats, and seamless Obsidian integration.

---

## ✅ All Phases Complete - v2.3.0 Achieved!

### v2.3.0 - Citation Format Normalizer (Dec 2025) ✅
- **Citation Normalizer Module**: Auto-converts legacy LLM-generated citation formats to Obsidian footnotes
- **Format Support**: Single `[1]`, comma-separated `[1, 2]`, ranges `[6-10]`, mixed `[1, 3-5, 8]`
- **Range Delimiters**: Hyphen `-`, en-dash `–`, em-dash `—`, word `to`
- **Table Awareness**: Auto-escapes brackets `\[^N\]` when inside markdown tables
- **False Positive Protection**: Hybrid placeholder + context strategy preserves links, wikilinks, code, math, YAML
- **Preview Mode**: Dry-run output shows table of original vs converted citations
- **Integration**: Auto-runs as preprocessing step in `process_document`
- **New MCP Tool**: `citation_normalize_format` for standalone normalization
- **Tests**: 47 comprehensive tests covering all scenarios

### v2.2.0 - Complete Feature Parity (Dec 2025) ✅
- **Web UI**: Recent Lookups tab, Dry Run preview, Multi-Section mode, Corrections workflow
- **Obsidian Plugin**: Library save/search, BibTeX export, Link verification command
- **CLI**: Interactive mode (`--interactive`), Quick lookup (`--lookup`), Restore backup (`--restore-backup`)
- **API**: `/api/corrections/generate`, `/api/corrections/apply`, `dry_run` & `multi_section` params
- **Statistics**: 7 stat cards in Web UI (Processed, Review, Failed, Orphaned, Duplicates, Replacements)
- **Abbreviations**: Organization abbreviations (ACC, AHA, NIH) only in citation tags, full names in body

### v2.1.0 - Document Intelligence & Safety (Dec 2025) ✅
- **Link Verification**: Parallel URL checking with redirect/broken/archived detection
- **Citation Suggestions**: Pattern-based detection of uncited statistics, claims, findings
- **Citation Compliance**: Plagiarism-style checker for missing citations
- **LLM Metadata Extraction**: Ollama-powered metadata extraction for edge cases
- **HTTP API**: `/api/verify-links`, `/api/suggest-citations`, `/api/check-compliance`, `/api/analyze-document`
- **MCP Tools**: 5 new tools for AI agents
- **Auto-Save (HTTP API only)**: Save processed content directly to file with `save_to_file` parameter via HTTP API
  - ⚠️ **Note:** MCP tool `citation_process_document` does NOT currently save to file - this is a v2.4.0 fix
- **One-Click Restore**: "Restore Original" button in Web UI, `/api/restore-backup` endpoint
- **Real-Time Progress**: SSE streaming with live progress bar and statistics
- **Comprehensive Logging**: File-based logging with rotation in `.data/logs/`
- **Improved Errors**: Detailed error types and suggestions for failed references

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

## ✅ v2.4.1 - Enhanced Context Verification Algorithm (COMPLETE)

**Status:** COMPLETE  
**Released:** Jan 13, 2026

### Enhancements Based on IR Research
- **IDF-Weighted Inclusion**: Generic terms weighted less, specific terms more
- **Keyphrase Extraction**: Captures multi-word concepts ("cardiac amyloidosis")
- **Conservative Lemmatization**: Reduces variants, protects technical terms
- **Configurable Options**: Toggle lemmatization, keyphrases, IDF weighting

---

## ✅ v2.4.0 - Critical Improvements Sprint (COMPLETE)

**Status:** COMPLETE  
**Released:** Jan 12, 2026  
**See:** `docs/IMPROVEMENT_PLAN_v2.4.md` for analysis  

> ✅ **Domain-Agnostic Implementation Achieved**
>
> All v2.4.0 implementations use dynamic keyword extraction, NOT hardcoded topic lists.
> Solutions work universally across medical, legal, engineering, humanities, CS, and all domains.

### Issues Fixed ✅

| Issue | Status | Solution |
|-------|--------|----------|
| **File not saved after processing** | ✅ Fixed | Added `save_to_file` param, writes directly with backup |
| **No duplicate detection** | ✅ Fixed | New `citation_find_duplicates` tool + `citation_integrity_checker.py` |
| **No context verification** | ✅ Fixed | New `citation_verify_context` tool + `citation_context_verifier.py` |
| **No comprehensive audit** | ✅ Fixed | New `citation_audit_document` tool |
| **Security vulnerability** | ✅ Fixed | Path traversal protection in `/api/restore-backup` |

### New Tools Added ✅

| Tool | Purpose | Status |
|------|---------|--------|
| `citation_find_duplicates` | Detect `[^A][^A]`, orphans, missing defs | ✅ Complete |
| `citation_verify_context` | IDF-weighted keyword-based context matching | ✅ Complete |
| `citation_audit_document` | Comprehensive health check with score | ✅ Complete |

### New Modules Added ✅

- `modules/citation_integrity_checker.py` - Duplicate/orphan detection
- `modules/citation_context_verifier.py` - IDF-weighted context verification with lemmatization & keyphrases

### Feature Parity Achieved ✅

All tools accessible via:
- MCP Server (stdio)
- HTTP API
- CLI
- Web UI (Document Intelligence section)

---

## 🎯 Future Enhancements (Post v2.4)

| Feature | Priority | Notes |
|---------|----------|-------|
| **BM25 Scoring** | **High** | Better lexical matching for short query vs long document |
| **Corpus-Based IDF** | **High** | Use S2ORC or similar for more accurate term specificity |
| **PDF/Document Link Handling** | **High** | Better handling of URLs pointing to PDFs, presentations, spreadsheets |
| **Superscript Citations** | Medium | Handle `¹²` and `<sup>1,2</sup>` formats |
| Zotero sync integration | Medium | Bi-directional sync |
| Semantic embeddings | Medium | Catch synonyms like "heart" ↔ "cardiac" |
| CSL-JSON export | Medium | For Pandoc/Citation.js |
| Citation graph visualization | Low | D3.js or Obsidian Graph |
| Calibrated thresholds | Low | Learn optimal cutoffs from labeled data |
| SSRN support | Low | Niche academic |

> **Note:** LLM metadata extraction, link verification, citation format normalization, context verification, and integrity checking are now available

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

### v2.1.0 - Document Intelligence
- `modules/document_intelligence.py` - Link verification, citation suggestions, compliance checker
- `modules/llm_extractor.py` - LLM-powered metadata extraction (enhanced)

### v2.3.0 - Citation Format Normalizer
- `modules/citation_normalizer.py` - Legacy citation format preprocessing (`[1, 2]` → `[^1] [^2]`)

---

## 🐛 Known Issues

| Issue | Workaround | Priority |
|-------|------------|----------|
| Tkinter crash on macOS | Use CLI mode | Low |
| Some sites block scraping | Use Null placeholders | Low |

> **Note:** Duplicate citation detection is now available via `/api/duplicates` endpoint and `DuplicateDetector` module (v2.0).

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
- 30+ tools available (core lookup, search, batch, document processing, intelligence, import/export)

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
| test_document_intelligence.py | 30 | ✅ |
| test_document_intelligence_integration.py | 24 | ✅ |
| test_save_to_file_safety.py | 12 | ✅ |
| test_citation_normalizer.py | 47 | ✅ |
| test_citation_integrity_checker.py | 14 | ✅ |
| test_citation_context_verifier.py | 45 | ✅ |
| **Total** | **471+** | ✅ |
