# CitationSculptor Planning

**Version:** 0.6.0 | **Updated:** Dec 2025 | **Status:** Active Development

## Quick Links
- [CHANGELOG.md](./CHANGELOG.md) - Version history
- [docs/ARCHITECTURE.md](./docs/ARCHITECTURE.md) - Technical reference
- [docs/TESTING.md](./docs/TESTING.md) - Testing guide
- [docs/COMPLETED_FEATURES.md](./docs/COMPLETED_FEATURES.md) - Feature archive

---

## 🎯 Current Focus

**Completed: LLM-Based Webpage Metadata Extraction**

Added intelligent LLM-based extraction for webpages with non-standard metadata formats.

---

## ✅ Recently Completed (Dec 2025)

### Markdown Table Bracket Escaping
- **Module:** `modules/inline_replacer.py` - Now auto-escapes brackets in table rows
- **Rule:** In Obsidian markdown tables, `[^ref]` must be written with a single backslash: `\[^ref]`
- **Detection:** Lines starting with `|` are identified as table rows
- **Automatic:** CitationSculptor now handles this automatically during processing
- **Tests:** 8 new tests in `tests/test_inline_replacer.py`

### LLM Metadata Extractor
- **New Module:** `modules/llm_extractor.py` - Uses Ollama LLM for intelligent extraction
- **Site Rules Database:** `data/site_rules.yaml` - Stores learned patterns for domains
- **Self-Learning:** Automatically saves successful extraction patterns for reuse
- **WebpageScraper Integration:** Falls back to LLM when standard meta tags fail
- **Author Section Prioritization:** Extracts "Article By:" sections for LLM analysis

**Example Use Case:** LipidSpin articles (lipid.org) now correctly extract:
- 6 authors from "Article By:" section
- Seasonal dates from URL (spring-2024 → March 2024)
- Organization name (National Lipid Association)

---

## 📋 Next Steps (Priority Order)

### High Priority - citation_lookup.py Enhancements
1. **Interactive Mode** - Run continuously, entering identifiers one at a time
2. **Clipboard Integration** - Copy result directly to clipboard (macOS `pbcopy`)
3. **Obsidian Integration** - Output format optimized for pasting into Obsidian
4. **Search Multiple** - Search multiple titles, pick best match
5. **Cache Results** - Persistent cache to avoid repeated API calls

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

### Server Requirements
- PubMed MCP server must run on port 3017
- Start: `cd pubmed-mcp-server && npm start`

### Key Commands
```bash
# Activate venv
source venv/bin/activate

# Run tests
python -m pytest tests/ -v

# Process document
python citation_sculptor.py "document.md" --multi-section

# Single lookup
python citation_lookup.py --pmid 32089132
```

### Important Design Notes
- `WebpageScraper` is in `pubmed_client.py` (Obsidian Sync issue)
- Rate limit: 2.5 req/sec (no NCBI API key)
- Null placeholders: `Null_Date`, `Null_Author` (searchable)
- **Table Escaping:** Inline refs in markdown tables need single backslash: `\[^ref]` (auto-handled)
