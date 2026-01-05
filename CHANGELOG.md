# CitationSculptor Changelog

All notable changes to CitationSculptor are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [2.3.2] - 2026-01-04

### Improved - Metadata Extraction & Citation Quality
This release significantly improves the quality of citations generated from web sources, particularly for medical organization websites (AHA, ESC, Mayo Clinic, etc.).

- **Organization-as-Author Logic**: When no individual author is found, the system now automatically promotes the Organization Name to the author field.
  - Eliminated `Null_Author` placeholders for organizational content.
  - Citations now correctly format as: `British Heart Foundation (BHF). Title...`
- **Smart Citation Labels**: Reference labels for organizational content now use the organization abbreviation (e.g., `[^AHA-2025]`) instead of generic `[^Unknown-...]`.
- **Evergreen Content Detection**: Added support for identifying "evergreen" medical content (e.g., condition overviews, health topics).
  - Recognized paths like `/conditions/` and `/health-topics/`.
  - Suppresses `Null_Date` warnings for these timeless pages.
- **Expanded Medical Domain Knowledge**: Added 13 new medical domains to the scraper's knowledge base for better organization extraction, including:
  - European Society of Cardiology (`escardio.org`)
  - American Heart Association (`heart.org`)
  - British Heart Foundation (`bhf.org.uk`)
  - Mayo Clinic, Cleveland Clinic, Hopkins Medicine, and more.

### Fixed
- Fixed issue where scraped webpages with missing authors would default to "Null_Author" even when the site name was known.

---

## [2.3.0] - 2025-12-18

### Added - Citation Format Normalizer (Preprocessing)

This release adds a robust preprocessing step that automatically converts legacy LLM-generated citation formats to Obsidian footnote style before document processing.

#### Citation Normalizer Features
- **Automatic Preprocessing**: Runs automatically before `process_document` operations
- **Single Citations**: `[1]` → `[^1]`
- **Comma-Separated Lists**: `[1, 2]` → `[^1] [^2]`
- **Range Expansion**: `[6-10]` → `[^6] [^7] [^8] [^9] [^10]`
- **Mixed Formats**: `[1, 3-5, 8]` → `[^1] [^3] [^4] [^5] [^8]`
- **Multiple Range Delimiters**: Supports hyphen `-`, en-dash `–`, em-dash `—`, and word `to`
- **Table Context Awareness**: Auto-escapes brackets `\[^N\]` when inside markdown tables
- **Dry Run/Preview Mode**: Preview changes before applying with table or diff-style output

#### False Positive Protection
Uses hybrid placeholder+context strategy to avoid converting non-citations:
- **Markdown links**: `[text](url)` preserved
- **Wikilinks**: `[[Note]]` preserved
- **Images**: `![alt](url)` and `![[image]]` preserved
- **Existing footnotes**: `[^existing]` not re-converted
- **Code blocks**: Fenced and inline code excluded
- **YAML frontmatter**: Document metadata excluded
- **Math blocks**: `$...$` and `$$...$$` excluded
- **Consecutive citations**: `[1][2][3]` all converted correctly

#### New MCP Tool
- `citation_normalize_format`: Standalone tool for manual normalization with dry_run option

#### Integration
- Normalization statistics included in document processing results
- SSE streaming shows normalization phase with progress
- Statistics show how many legacy citations were converted

---

## [2.2.0] - 2025-12-17

### Added - Complete Feature Parity Across All Interfaces

This release achieves **full feature parity** across Web UI, Obsidian Plugin, and CLI. All major features are now available in all three interfaces.

#### Web UI Enhancements
- **Recent Lookups Tab**: View and reuse previous citation lookups (localStorage-backed)
- **Dry Run Preview**: New checkbox to preview document processing without saving changes
- **Multi-Section Mode**: Option to process documents with multiple reference sections independently
- **Corrections Workflow**: New dedicated page to find and fix citations with Null placeholders
  - Detects `Null_Date`, `Null_Author`, `Null_Organization` placeholders
  - Interactive editor for filling in missing information
  - Download corrections template as Markdown
- **Comprehensive Statistics**: Results now show 7 stat cards (Processed, Needs Review, Failed, Orphaned, Duplicates Merged, Replacements)

#### Obsidian Plugin Enhancements
- **Save to Library** command: Save last lookup to server citation library
- **Search Library** modal: Search and insert citations from library with one click
- **Export BibTeX** command: Export selected identifiers as BibTeX (copies to clipboard)
- **Verify Links** command: Check all links in current note for accessibility
- **Link Verification Modal**: Shows broken/valid link status with details

#### CLI Enhancements
- **Interactive Mode** (`--interactive` / `-i`): REPL for lookups and PubMed searches
  - Commands: `lookup`, `search`, `batch`, `help`, `quit`
  - Direct identifier input auto-detects and looks up
- **Quick Lookup** (`--lookup <ID>`): Single lookup without entering interactive mode
- **Restore from Backup** (`--restore-backup <FILE>`): Restore original file from backup

#### API Enhancements
- `/api/corrections/generate`: Generate corrections template for incomplete citations
- `/api/corrections/apply`: Apply corrections to document content
- `dry_run` and `multi_section` parameters in `/api/process-document`

### Fixed
- Abbreviation now only used in citation tags (e.g., `[^ACC-Impact-2023]`), full organization names in citation body

---

## [2.1.1] - 2025-12-17

### Fixed - Web Scraping and DOI Extraction
- **Playwright Browser Fallback**: Added Playwright-based scraping for sites that block HTTP requests (Cloudflare, 403 errors, JavaScript requirements)
- **DOI Extraction**: Fixed regex patterns to exclude query parameters (`?utm_source=...`) from DOIs
- **URL Cleaning**: Query parameters are now stripped from citation URLs
- **BeautifulSoup Integration**: Meta tag extraction now uses BeautifulSoup for more robust HTML parsing
- **DOI URL Patterns**: Added support for `/doi/abs/` and `/doi/full/` URL formats (AHA Journals, etc.)

### Added
- `playwright>=1.40.0` as optional dependency for browser-based scraping
- Fallback chain: HTTP request → Playwright browser → URL-based extraction

### Technical Details
- New `_scrape_with_playwright()` method in `WebpageScraper` class
- Updated `_extract_meta_tags()` to use BeautifulSoup with regex fallback
- Fixed DOI patterns in `type_detector.py` and `reference_parser.py`

---

## [2.0.1] - 2025-12-17

### Added - Document Processing Across All Interfaces
- **HTTP Server** (`/api/process-document`):
  - Process full markdown documents via REST API
  - Accepts content directly or file path
  - Returns processed content with statistics
  - Support for all citation styles

- **Web UI** (Process Document tab):
  - New tab for document processing
  - Paste content or enter file path
  - Live statistics (total, processed, failed, replacements)
  - Download processed document

- **MCP Server** (`citation_process_document` tool):
  - Process markdown files from AI assistants
  - Accepts file_path or content parameter
  - Detailed output with statistics

- **Obsidian Plugin** (Process Current Note command):
  - One-click processing of the active note
  - Confirmation dialog before processing
  - Progress notifications
  - Automatic document replacement

---

## [2.0.0] - 2025-06-17

### Added - Smart Features
- **Citation Database** (`modules/citation_database.py`):
  - SQLite-backed persistent storage for all citations
  - Full-text search (FTS5) across titles, authors, notes
  - Tag and collection support for organization
  - Citation relationship tracking (cites, cited_by, related)
  - Database statistics and export
  
- **Duplicate Detection** (`modules/duplicate_detector.py`):
  - Multi-strategy duplicate finding:
    - Exact DOI/PMID matching (100% confidence)
    - Fuzzy title matching (configurable threshold)
    - Author/year heuristics
  - Fingerprint generation for quick lookups
  - Merge suggestions for duplicate pairs
  
- **Auto-Bibliography Generator** (`modules/bibliography_generator.py`):
  - Extract citations from document text
  - Multiple citation patterns (footnote, numeric, author-year)
  - Generate formatted bibliographies
  - Find undefined/unused citations
  - Update document bibliography sections
  - Support for appearance/alphabetical/year sorting

### Changed
- All formatters now inherit from `BaseFormatter`
- Comprehensive source type detection

---

## [1.10.0] - 2025-06-17

### Added - Import/Export
- **BibTeX Handler** (`modules/bibtex_handler.py`):
  - Full BibTeX file parsing
  - Export articles, books, preprints to BibTeX
  - Auto-generate cite keys
  - Handle special characters and LaTeX escaping
  
- **RIS Handler** (`modules/ris_handler.py`):
  - Complete RIS format parsing
  - Export to RIS format
  - Support all standard RIS tags
  - Multi-value field handling (authors, keywords)

---

## [1.9.0] - 2025-06-17

### Added - PDF Support
- **PDF Metadata Extractor** (`modules/pdf_extractor.py`):
  - Extract document metadata (title, authors, date)
  - DOI extraction from PDF text content
  - arXiv ID and PMID detection
  - First-page title extraction (font-size heuristic)
  - Batch extraction from directories
  - Optional PyMuPDF dependency for full functionality

---

## [1.8.0] - 2025-06-17

### Added - Enhanced Sources
- **Wayback Machine Integration** (`modules/wayback_client.py`):
  - Check if URLs are archived
  - Get closest snapshot to any timestamp
  - List all snapshots for a URL
  - Format citations with archived URLs
  - Request new page archival
  
- **OpenAlex API Client** (`modules/openalex_client.py`):
  - Lookup by DOI, PMID, or OpenAlex ID
  - Full-text search with type filtering
  - Citation and reference retrieval
  - Open access URL detection
  - Polite pool support (100k requests/day)
  
- **Semantic Scholar API Client** (`modules/semantic_scholar_client.py`):
  - Lookup by DOI, arXiv ID, PMID
  - AI-powered search and recommendations
  - Citation and reference networks
  - TLDR summaries (AI-generated abstracts)
  - Influential citation counts

---

## [1.7.0] - 2025-06-17

### Added
- **arXiv Integration**: Full support for arXiv preprint lookup
  - Auto-detect arXiv IDs (e.g., `2301.04104`, `arxiv:2301.04104`)
  - New `modules/arxiv_client.py` with search and metadata fetching
  - Proper preprint citation formatting with category and URL
- **bioRxiv/medRxiv Support**: Preprint server integration
  - New `modules/preprint_client.py` for bioRxiv/medRxiv API
  - Auto-detect preprint DOIs (10.1101/...)
  - Notes if preprint has been published in a journal
- **ISBN Lookup**: Book citation support via Google Books and OpenLibrary
  - New `modules/book_client.py` with dual-API fallback
  - Validates ISBN-10 and ISBN-13 checksums
  - Rich book metadata including publisher, page count, edition
- **Enhanced Auto-Detection**: `lookup_auto()` now handles:
  - arXiv IDs (new and old format)
  - ISBNs (with or without hyphens)
  - bioRxiv/medRxiv preprint DOIs
  - Standard PubMed identifiers (PMID, DOI, PMC ID, title)

---

## [1.6.0] - 2025-06-17

### Added
- **Multiple Citation Styles**: Support for 6 major citation formats
  - Vancouver (medical/scientific) - default
  - APA 7th Edition (social sciences)
  - MLA 9th Edition (humanities)
  - Chicago/Turabian (notes-bibliography)
  - Harvard (author-date)
  - IEEE (engineering/computer science)
- **Base Formatter Architecture**: New `modules/base_formatter.py` with shared functionality
  - Common author formatting methods for each style
  - Shared utilities for DOI formatting, label generation, organization extraction
  - Style-specific formatters inherit from base class
- **CLI Style Support**: New `--style` / `-s` flag to select citation format
  - `--list-styles` to show available styles and descriptions
  - Style persists in cache per-style (same article, different styles cached separately)
- **Interactive Mode Style Command**: `/style` to view/change style during session
- **Web UI Style Selector**: Dropdown to choose citation style before lookup
- **Obsidian Plugin Style Settings**: New dropdown in plugin settings
  - Style selector in Quick Lookup tab for on-the-fly changes
  - Persistent style preference saved to settings

### Changed
- Cache now includes style in key (different style = separate cache entry)
- HTTP API `/api/lookup` accepts `?style=` query parameter
- New endpoint `/api/styles` returns available styles and descriptions
- VancouverFormatter now inherits from BaseFormatter

---

## [1.5.2] - 2025-06-17

### Added
- **Beautiful Web UI**: Modern, dark-themed browser interface (`web/index.html`)
  - 🔍 Quick Lookup - Enter any identifier (PMID, DOI, PMC ID, title)
  - 📚 PubMed Search - Search and select from results
  - 📋 Batch Lookup - Process multiple identifiers at once
  - 🕐 Recent History - Access past lookups (persisted in localStorage)
  - Live server status indicator
  - One-click copy to clipboard
  - Responsive design with beautiful gradient accents
- **HTTP Server Web UI Serving**: Server now serves web UI at root (`/`)
- **Enhanced Obsidian Plugin Styles**:
  - Refined CSS with improved visual hierarchy
  - Pill-style tabs with accent colors
  - Better dark/light mode support
  - Collapsible metadata sections
  - Gradient accent bar in header

### Changed
- Default HTTP server port changed to 3019 (was 3018)

---

## [1.5.1] - 2025-06-17

### Added
- **HTTP Server for Obsidian Integration**: New `mcp_server/http_server.py`
  - Lightweight HTTP server exposing all CitationSculptor features
  - CORS-enabled for browser access
  - Endpoints: `/api/lookup`, `/api/search`, `/api/batch`, `/api/cache/stats`
  - Health check endpoint for connection testing
  - Eliminates process spawning overhead from Obsidian plugin
- **macOS LaunchAgent**: Auto-start HTTP server on login
  - `scripts/com.citationsculptor.httpserver.plist`
- **Improved Obsidian Plugin**:
  - HTTP API integration (primary) with CLI fallback
  - Connection test button in settings
  - Settings for HTTP API URL configuration
  - 4-tab UI: Quick Lookup, PubMed Search, Batch Lookup, Recent
  - 8 commands for all plugin features
- **HTTP Server Tests**: 11 new tests for HTTP endpoints
  - Total test count: 185 tests across 6 test files

### Documentation
- Updated README with HTTP server documentation
- Updated Obsidian plugin README with HTTP API usage
- Architecture diagram showing HTTP/CLI fallback flow

---

## [1.5.0] - 2025-06-17

### Added
- **Interactive Mode**: `--interactive` / `-i` flag runs REPL-style continuous lookups
  - Commands: `/search <query>`, `/format <type>`, `/cache clear|stats`, `/help`, `/quit`
  - Auto-copy to clipboard on each lookup
- **Obsidian Plugin**: Native Obsidian plugin for citation lookup
  - Command palette integration: "Open Citation Lookup", "Quick Lookup", "Look Up Selected Text"
  - Ribbon icon for quick access
  - Search modal with PubMed search results
  - One-click insert at cursor
  - Auto-creates References section if needed
  - Configurable settings (paths, format, auto-copy)

---

## [1.4.0] - 2025-06-17

### Added
- **Clipboard Integration**: `--copy` / `-c` flag copies citation to clipboard via pbcopy (macOS)
- **Result Caching**: Persistent JSON cache (`.cache/citation_cache.json`) with 30-day expiry
- **Search Multiple**: `--search-multi QUERY` shows interactive table of up to 5 PubMed results

---

## [1.3.1] - 2025-05-27

### Fixed
- **PubMed Client Integration**: 
    - Fixed `TypeError` in `convert_ids` where integer IDs caused string concatenation failures.
    - Fixed `AttributeError` in `crossref_lookup_doi` by removing call to non-existent `_send_request`.
- **API Reliability**:
    - Refactored `PubMedClient` to communicate directly with NCBI E-utilities and CrossRef APIs using `requests`.
    - Removed legacy dependency logic that assumed a separate running PubMed MCP server.
    - Added robust error handling and type conversion for ID operations.

## [1.3.0] - 2024-12-15

### Changed
- **MCP Server: HTTP → stdio Transport** - Complete rewrite for Abacus Desktop compatibility
  - Replaced aiohttp HTTP server with official MCP SDK (`mcp>=1.0.0`)
  - Uses stdio transport (stdin/stdout) instead of HTTP port
  - Simplified server code from 504 lines to 195 lines
  - Removed Ollama integration tools (can be re-added if needed)
  - Python 3.10+ now required (MCP SDK requirement)

### Added
- Uses `uv` for faster dependency management (recommended)

### Migration
- Previous HTTP server tagged as `v1.2.0-http` for rollback if needed
- New server configured in Abacus Desktop MCP settings instead of HTTP URL

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

