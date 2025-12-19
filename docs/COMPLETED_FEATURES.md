# Completed Features Archive

This document archives all completed features and implementation details. For version history, see [CHANGELOG.md](../CHANGELOG.md).

---

## v2.3.0 (Dec 2025) - Citation Format Normalizer

### Citation Normalizer Module
A robust preprocessing step that automatically converts legacy LLM-generated citation formats to Obsidian footnote style before document processing.

#### Supported Formats
| Input | Output |
|-------|--------|
| `[1]` | `[^1]` |
| `[1, 2]` | `[^1] [^2]` |
| `[6-10]` | `[^6] [^7] [^8] [^9] [^10]` |
| `[6–10]` (en-dash) | `[^6] [^7] [^8] [^9] [^10]` |
| `[6—10]` (em-dash) | `[^6] [^7] [^8] [^9] [^10]` |
| `[6 to 10]` | `[^6] [^7] [^8] [^9] [^10]` |
| `[1, 3-5, 8]` | `[^1] [^3] [^4] [^5] [^8]` |

#### Table Context Awareness
- Auto-detects markdown table rows
- Escapes brackets: `[^N]` → `\[^N\]` inside tables
- Works with `InlineReplacer` which also applies table escaping

#### False Positive Protection
Uses hybrid placeholder + context strategy:
- **Markdown links**: `[text](url)` preserved
- **Wikilinks**: `[[Note]]` preserved  
- **Images**: `![alt](url)` and `![[image]]` preserved
- **Existing footnotes**: `[^existing]` not re-converted
- **Code blocks**: Fenced (```) and inline (`code`) excluded
- **YAML frontmatter**: Document metadata excluded
- **Math blocks**: `$...$` and `$$...$$` excluded
- **Alphanumeric content**: `[Figure 1]`, `[2024]` ignored

#### Integration
- Auto-runs as preprocessing step in `process_document`
- Statistics included in processing results
- SSE streaming shows normalization phase

#### New MCP Tool
- `citation_normalize_format`: Standalone normalization with `dry_run` option

#### Preview Mode
- Dry-run shows table of original vs converted citations
- Displays line numbers and change types
- Useful for validating before applying changes

#### Files Added/Modified
- `modules/citation_normalizer.py` - New module
- `tests/test_citation_normalizer.py` - 47 comprehensive tests
- `mcp_server/server.py` - Integration + new tool
- `mcp_server/http_server.py` - Integration in sync and streaming modes

---

## v2.2.0 (Dec 2025) - Complete Feature Parity

### Full Feature Parity Across All Interfaces

| Feature | Web UI | Obsidian | CLI |
|---------|:------:|:--------:|:---:|
| Single lookup | ✅ | ✅ | ✅ |
| Batch lookup | ✅ | ✅ | ✅ |
| PubMed search | ✅ | ✅ | ✅ |
| Recent lookups | ✅ | ✅ | ✅ |
| Process document | ✅ | ✅ | ✅ |
| Dry run preview | ✅ | - | ✅ |
| Multi-section | ✅ | - | ✅ |
| Create backup | ✅ | ✅ | ✅ |
| Restore backup | ✅ | ✅ | ✅ |
| Library save/search | ✅ | ✅ | - |
| BibTeX export | ✅ | ✅ | - |
| Link verification | ✅ | ✅ | - |
| Corrections workflow | ✅ | - | ✅ |

### Web UI Enhancements
- Recent Lookups tab (localStorage)
- Dry Run preview checkbox
- Multi-Section mode option
- Corrections workflow page
- 7-stat comprehensive results

### Obsidian Plugin Enhancements
- `save-to-library` command
- `search-library` command with modal
- `export-bibtex` command
- `verify-links` command with modal
- `LibrarySearchModal` class
- `LinkVerificationModal` class

### CLI Enhancements
- `--interactive` / `-i` flag for REPL mode
- `--lookup <ID>` for quick single lookup
- `--restore-backup <FILE>` for file restoration
- `run_interactive_mode()` function with commands

### API Enhancements
- `/api/corrections/generate` endpoint
- `/api/corrections/apply` endpoint
- `dry_run` parameter in process-document
- `multi_section` parameter in process-document

---

## v0.5.1 (Dec 2025) - Code Quality

### Test Coverage Expansion
- `test_pubmed_client.py` - 55+ tests for API client, caching, rate limiting
- `test_vancouver_formatter.py` - 50+ tests for all citation formats
- `test_reference_parser.py` - 45+ tests for V1-V8 formats, multi-section
- **166 tests total, all passing**

### Error Handling
- Replaced all bare `except:` blocks with specific exception handling
- Files updated: `mcp_server/server.py`, `modules/vancouver_formatter.py`

### Type Hints
- Added return type hints to public methods
- Files updated: `pubmed_client.py`, `progress_dialog.py`, `output_generator.py`

### Configuration Module
- Created `modules/config.py` with centralized settings
- Environment variable support with `.env` file loading

---

## v0.5.0 (Nov 29, 2025) - Citation Lookup Tool

### citation_lookup.py
- Single-citation lookup for atomic note workflows
- Supports: PMID, DOI, PMC ID, title search
- Output formats: inline, endnote, full, json
- Batch processing from file
- Auto-detection of identifier type

```bash
python citation_lookup.py --pmid 32089132
python citation_lookup.py --doi "10.1186/s12968-020-00607-1"
python citation_lookup.py --title "Lake Louise Criteria myocarditis"
python citation_lookup.py --batch identifiers.txt --output citations.md
```

---

## v0.4.0 (Nov 29, 2025) - GUI & Detection

### Evergreen Page Detection
- `is_evergreen` field in `WebpageMetadata`
- URL patterns: `/about`, `/services`, `/products`, `/contact`, `/careers`
- Evergreen pages skip `Null_Date` flagging

### Processing Summary
- GUI shows: Citations Formatted, Inline Refs Updated, Undefined Refs, Need Review
- Missing Data Breakdown with expandable details

### GUI Dark Mode
- Fixed metric cards for dark mode compatibility

---

## v0.3.0 (Nov 28, 2025) - Format Support

### V6 Grouped Footnotes
- Format: `[^1] [^47] [^49] Title | Source` with URL on separate line
- `**Sources:**` recognized as reference header
- Many-to-one deduplication

### Webpage Scraping Enhancements
- JSON-LD date extraction (`datePublished`)
- Author filtering (CMS usernames removed)
- Author + Organization combined citations
- Custom meta tags: `m_authors`, `m_author`

### Organization Handling
- Smart abbreviations: AMA, AHA, CDC, NIH, etc.
- Acronym detection for short domains
- Full names in citations, abbreviations in tags

### URL-Based Extraction
- Title from URL slug (when truncated)
- Year from URL paths (`/2024/05/12/`)
- Metadata fallback for blocked sites

### Null Placeholder System
- `Null_Date`, `Null_Author` in citation text (searchable)
- `ND` in tags (compact)
- Replaces manual review sections

---

## v0.2.0 (Nov 27, 2025) - Scraping & Detection

### Webpage Metadata Scraping
- `WebpageScraper` class extracts `citation_*` meta tags
- Academic pages get proper Vancouver citations

### Detection Features
- Undefined reference detection
- PDF document processing via PubMed title search
- Long title search fix (truncate to ~100 chars)

### Improvements
- PMC ID fallback to CrossRef (when PMID missing)
- Full metadata fetch after title match
- Alphabetical reference sorting

---

## v0.1.0 (Nov 27, 2025) - Initial Release

### Core Functionality
- ID Conversion: PMC ID → PMID
- DOI Extraction: Complex URLs (Wiley, Springer, OUP)
- Metadata Parsing: Nested `journalInfo`, books, chapters via CrossRef
- Rate Limiting: Exponential backoff for NCBI limits

### Document Processing
- Multi-section document support
- Footnote definitions (`[^N]: Citation...`)
- Text-only citations
- Unreferenced filtering

### Output
- Mapping file generation (`_mapping.json`)
- Inline reference replacement

