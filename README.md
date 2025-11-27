# CitationSculptor

**Transform LLM-generated reference sections into properly formatted Vancouver-style citations for Obsidian markdown documents.**

## Overview

CitationSculptor is a Python tool that processes Obsidian markdown documents containing LLM-generated reference sections and reformats them according to Vancouver citation standards. It integrates with PubMed and CrossRef APIs (via MCP server) to fetch accurate metadata for journal articles, book chapters, books, and more.

## Features

### Citation Processing
- **Journal Articles**: Fetches metadata from PubMed with DOI, volume, issue, and pages
- **Book Chapters**: Retrieves from CrossRef with proper Vancouver formatting
- **Books**: CrossRef integration for complete book citations
- **Newspaper Articles**: Extracts publication info from URLs
- **Webpages & Blogs**: Generates labels from organization/source names

### Smart Detection & Filtering
- **Citation Type Detection**: Automatically identifies journals, books, webpages, blogs, newspapers
- **DOI Extraction**: Handles multiple publisher URL patterns (Springer, Wiley, OUP, BMC, etc.)
- **Unreferenced Citation Filter**: Skips citations not actually used in document body
- **PMC ID → PMID Conversion**: Uses NCBI ID Converter API
- **Webpage Metadata Scraping**: Extracts `citation_*` meta tags from academic webpages

### Multi-Section Document Support
- Handles documents with multiple independent reference sections
- Each section processed independently with its own numbering
- Supports mixed reference formats within the same document
- Detects footnote definitions (`[^N]:`) and numeric references (`[N]`)

### Inline Reference Transformation
- Converts numbered references `[1]` to mnemonic labels
- Journal articles: `[^AuthorAB-2024-12345678]` (with PMID)
- Book chapters: `[^AuthorAB-2024-p123]` (with starting page)
- Webpages/blogs: `[^OrgName-BriefTitle-Year]`

### Reliability Features
- **Rate Limiting**: 2.5 requests/second with exponential backoff
- **Retry Logic**: Automatic retry on 429 errors (5s, 10s, 20s, 40s)
- **Mapping File**: JSON audit trail for rollback/debugging
- **Progress Indicators**: Real-time progress bars with counts

## Installation

```bash
# Navigate to project (Mac)
cd "/path/to/CitationSculptor"

# Create virtual environment
python -m venv venv

# Activate (Mac/Linux)
source venv/bin/activate

# Activate (Windows)
.\venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## Configuration

Create a `.env` file:

```env
PUBMED_MCP_URL=http://127.0.0.1:3017/mcp
LOG_LEVEL=INFO
MAX_AUTHORS=3
```

## Usage

```bash
# Basic usage
python citation_sculptor.py "path/to/document.md"

# With options
python citation_sculptor.py "path/to/document.md" --verbose --output custom_output.md
```

### Options

| Option | Description |
|--------|-------------|
| `--output, -o` | Output file path (default: `filename_formatted.md`) |
| `--verbose, -v` | Enable detailed logging |
| `--dry-run, -n` | Preview changes without writing |
| `--no-backup` | Skip creating backup file |
| `--multi-section` | Process documents with multiple independent reference sections |
| `--gui` | Show progress in popup dialog (requires compatible tkinter) |

### Output Files

| File | Description |
|------|-------------|
| `*_formatted.md` | Processed document with Vancouver citations |
| `*_formatted_report.md` | Processing summary statistics |
| `*_formatted_mapping.json` | Reference mapping for audit/rollback |

## Requirements

- Python 3.9+
- PubMed MCP Server running at `http://127.0.0.1:3017/mcp`
  - Required tools: `pubmed_search_articles`, `pubmed_fetch_contents`, `pubmed_convert_ids`, `crossref_lookup_doi`

## Project Phases

| Phase | Scope | Status |
|-------|-------|--------|
| Phase 1 | Journal articles via PubMed | ✅ Complete |
| Phase 2 | Book chapters, books (CrossRef) | ✅ Complete |
| Phase 3 | Newspaper articles | ✅ Complete |
| Phase 4 | Webpages, web articles, blogs | ✅ Complete |
| Phase 5 | Batch processing | 📋 Planned |
| Phase 6 | Obsidian plugin | 📋 Planned |

## Test Results (Sample Document)

| Metric | Value |
|--------|-------|
| Total references | 211 |
| Used in document | 130 |
| Journal articles | 11 |
| Book chapters | 1 |
| Webpages | 106 |
| Blogs | 7 |
| Newspaper articles | 4 |
| **Inline replacements** | **257** |
| **Manual review needed** | **0** |

## Architecture

```
CitationSculptor/
├── citation_sculptor.py      # Main CLI entry point
├── modules/
│   ├── file_handler.py       # File I/O and backup
│   ├── reference_parser.py   # Parse reference sections (multi-section support)
│   ├── type_detector.py      # Detect citation types, extract DOIs
│   ├── pubmed_client.py      # PubMed, CrossRef MCP client + webpage scraper
│   ├── vancouver_formatter.py # Format citations
│   ├── inline_replacer.py    # Replace inline references
│   ├── output_generator.py   # Generate output files
│   └── progress_dialog.py    # GUI progress (optional)
├── config/
│   └── journal_domains.json  # Journal domain patterns
├── samples/                  # Active test documents
├── test_samples/             # Regression test originals
│   └── TEST_MANIFEST.md      # Test specifications
└── tests/
    ├── fixtures/             # Format examples (V1-V5)
    └── test_*.py             # Unit tests
```

## Recent Updates (2025-11-27)

### v0.3.0
- **Webpage Metadata Scraping**: Extract `citation_*` meta tags for proper Vancouver formatting
- **Regression Testing**: Added `test_samples/` folder with TEST_MANIFEST.md
- **PDF Document Handling**: PDFs now searched on PubMed by title
- **PMC Fallback**: PMC articles without PMID now use CrossRef for metadata
- **Alphabetical Sorting**: Reference sections sorted by citation label
- **Undefined Reference Detection**: Flags citations used in text but not defined

### v0.2.0
- **Multi-Section Support**: Process documents with multiple reference sections
- **Footnote Definitions**: Support for `[^N]:` syntax
- **Text-Only Citations**: Title-based PubMed search for citations without URLs
- **Body After References**: Handle documents with content after reference sections

### v0.1.0
- CrossRef integration for non-PubMed items
- Unreferenced citation filtering
- DOI extraction for OUP, Springer chapter URLs
- Mapping file for audit trail
- Rate limiting with exponential backoff
- Progress indicators with counts

## License

MIT License
