# CitationSculptor Changelog

All notable changes to CitationSculptor are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.6.0] - 2025-12

### Added
- **Markdown Table Bracket Escaping**: Inline references in table rows are now automatically escaped
  - In Obsidian markdown tables, `[^ref]` must be written as `\[^ref]` (single backslash)
  - `InlineReplacer` now detects table rows (lines starting with `|`) and escapes automatically
  - 8 new tests in `tests/test_inline_replacer.py` for table escaping
- **LLM-Based Webpage Metadata Extraction**: New `modules/llm_extractor.py`
  - Uses Ollama LLM for intelligent extraction from non-standard webpages
  - Site rules database: `data/site_rules.yaml` stores learned patterns
  - Self-learning: automatically saves successful extraction patterns for reuse
  - Falls back to LLM when standard meta tags fail

---

## [0.5.1] - 2025-12

### Added
- **Test Suite Expansion**: Comprehensive test coverage for core modules
  - `test_pubmed_client.py` - 500+ lines covering API client, caching, rate limiting
  - `test_vancouver_formatter.py` - 400+ lines covering all citation formats
  - `test_reference_parser.py` - 400+ lines covering V1-V8 formats and multi-section
  - **166 tests total, all passing**
- **Unified Config Module**: New `modules/config.py` centralizing all settings
  - Environment variable support for all configuration options
  - Automatic `.env` file loading
  - Organized settings by category (API, formatting, scraping, caching)
- **Type Hints**: Added missing return type hints throughout codebase

### Fixed
- Replaced all bare `except:` blocks with specific exception handling
  - `mcp_server/server.py`: Ollama connection and model errors
  - `modules/vancouver_formatter.py`: URL parsing and title extraction errors

### Documentation - Major Restructure
Reorganized documentation for AI coding agent efficiency (limited context windows):

- **PLANNING.md** - Streamlined to ~70 lines, active work only
- **docs/ARCHITECTURE.md** - Technical reference, module overview, design decisions
- **docs/TESTING.md** - Test running guide, regression test info
- **docs/COMPLETED_FEATURES.md** - Archive of all completed features
- **CHANGELOG.md** - Version history (unchanged)

---

## [0.5.0] - 2025-11-29

### Added
- **New Tool: `citation_lookup.py`** - Single-citation lookup for atomic note workflows
  - Accepts PMID, DOI, PMC ID, or article title
  - Multiple output formats: `inline`, `endnote`, `full`, `json`
  - Batch processing from file
  - Auto-detection of identifier type

### Changed
- PubMed MCP Integration confirmed working in HTTP mode on port 3017

---

## [0.4.0] - 2025-11-29

### Added
- **Evergreen Page Detection**: Added `is_evergreen` field to `WebpageMetadata`
  - Landing pages, service pages, about pages marked as evergreen
  - Evergreen pages skip `Null_Date` flagging (no date expected)
- **Processing Summary**: GUI now shows detailed statistics after processing
  - Total formatted citations
  - Inline refs updated
  - Undefined refs detected
  - Null placeholder counts with breakdown

### Fixed
- **GUI Dark Mode**: Metric cards now use transparent blue backgrounds readable in dark mode

---

## [0.3.0] - 2025-11-28

### Added
- **V6 Grouped Footnotes Format**: Support for `[^1] [^47] [^49] Title | Source` format
  - Multi-line parsing for angle-bracket URLs
  - Many-to-one deduplication (all grouped IDs → same output label)
  - `**Sources:**` recognized as reference header
- **JSON-LD Date Extraction**: Parse `datePublished` from structured data
- **DOI Text Extraction**: Extract DOIs from plain text references
- **CrossRef Title Search Fallback**: Find articles not in PubMed
- **URL-Based Title Extraction**: Extract full title from URL when truncated
- **URL Year Extraction**: Extract year from paths like `/2019/article-title`
- **URL Metadata Fallback**: Extract title, date, org from URL for blocked sites
- **Null Placeholder System**: Searchable placeholders for missing data
  - `Null_Date`, `Null_Author` in citation text
  - `ND` in tags (compact)
- **Smart Organization Abbreviations**: Common orgs mapped to standard acronyms
- **Custom Meta Tag Support**: `m_authors`, `m_author` for Milliman, etc.

### Fixed
- Non-padded date parsing (e.g., `2023-1-2`)
- Ellipsis removal from truncated titles
- Social media URL handling (skip garbage from LinkedIn/Twitter URLs)
- Blog scraping for author/date metadata

---

## [0.2.0] - 2025-11-27

### Added
- **Webpage Metadata Scraping**: Extract `citation_*` meta tags from HTML
  - Supports academic webpages with proper metadata
  - Falls back gracefully for sites without citation tags
- **Undefined Reference Detection**: Flags citations used but not defined
- **PDF Document Processing**: PDFs treated as potential journal articles
- **Long Title Search Fix**: Truncate queries to ~100 chars at word boundaries
- **Full Metadata Fetch After Title Match**: Complete Vancouver citations for title searches
- **PMC ID Fallback to CrossRef**: Fetch metadata via DOI when PMID missing
- **Alphabetical Reference Sorting**: Output sorted by citation label

### Fixed
- Citation 14 Resolution (PMC10206993) - DOI fallback working
- Body content after references now processed correctly
- Incomplete metadata from title search fixed

---

## [0.1.0] - 2025-11-27

### Added
- Initial release with core functionality
- **ID Conversion**: PMC ID → PMID conversion via `pubmed_convert_ids`
- **DOI Extraction**: Handle complex URLs (Wiley, Springer, OUP)
- **Metadata Parsing**: Support for nested `journalInfo`, books, chapters
- **Unreferenced Filtering**: Skip citations not used in body text
- **Mapping File**: JSON file for audit trails and rollback
- **Rate Limiting**: Exponential backoff for NCBI API limits
- **Multi-Section Documents**: Independent reference section processing
- **Text-Only Citations**: Parse `1. Title. Authors. Journal.` format
- **Footnote Definitions**: Support `[^N]: Citation...` syntax

---

## Development History

### Session Notes: November 2025

#### Nov 29 - Evening
- Created `citation_lookup.py` for atomic note workflows
- Tested with SCMR 2020 Protocols paper
- Documented in CMR Knowledge Base Conversion Plan

#### Nov 29 - Morning
- Fixed GUI dark mode compatibility
- Implemented evergreen page detection
- Added processing summary statistics

#### Nov 28 - Part 2
- DOI path date extraction
- Blog scraping enhancements
- Console summary with Null counts
- Manual citation editing workflow

#### Nov 28 - Part 1
- V6 grouped footnotes support
- JSON-LD date extraction
- CrossRef title search fallback
- URL-based metadata extraction

#### Nov 27
- Environment migration (Windows → Mac)
- Rate limiting implementation
- Webpage metadata scraping
- Multi-section document support
- PDF processing via PubMed

