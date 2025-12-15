# CitationSculptor

**Transform LLM-generated reference sections into properly formatted Vancouver-style citations for Obsidian markdown documents.**

## Overview

CitationSculptor is a Python toolkit that processes Obsidian markdown documents containing LLM-generated reference sections and reformats them according to Vancouver citation standards. It integrates with PubMed and CrossRef APIs (via MCP server) to fetch accurate metadata for journal articles, book chapters, books, and more.

### Two Tools, Two Workflows

| Tool | Purpose | Best For |
|:-----|:--------|:---------|
| **`citation_lookup.py`** | Generate single citations from identifiers | Creating atomic notes, looking up specific references |
| **`citation_sculptor.py`** | Batch process entire documents | Documents with many inline `[1]` or `[^1]` references |

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
- **Plain Text DOI Extraction**: Detects `doi:10.xxx` patterns in reference text
- **Unreferenced Citation Filter**: Skips citations not actually used in document body
- **PMC ID → PMID Conversion**: Uses NCBI ID Converter API
- **Webpage Metadata Scraping**: 
  - Extracts `citation_*` meta tags from academic webpages
  - Parses JSON-LD structured data for publication dates
  - Filters out CMS usernames from author fields
  - Combines author + organization when both available

### Multi-Section Document Support
- Handles documents with multiple independent reference sections
- Each section processed independently with its own numbering
- Supports mixed reference formats within the same document
- Detects footnote definitions (`[^N]:`) and numeric references (`[N]`)

### V6 Grouped Footnotes Format (NEW)
- Handles grouped references: `[^1] [^47] [^49] Title | Source`
- Multi-line parsing with URLs on separate lines: `<https://...>`
- Many-to-one deduplication (multiple IDs → single citation)
- Recognizes `**Sources:**` as reference section header

### Smart Title & Organization Handling
- **URL-based Title Recovery**: Extracts full title from URL slug when source has truncated title with `...`
- **Smart Abbreviations**: Common organizations mapped to standard acronyms (AMA, AHA, CDC, etc.)
- **Acronym Detection**: Short domain names automatically uppercased (CBPP, KFF, etc.)
- **Full Names in Citations**: Abbreviation in tag `[^AMA-...]`, full name in text `American Medical Association.`

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
- **Blocked Site Detection**: Identifies Cloudflare/403 blocks with specific guidance:
  - Tells you exactly what info to look up (author, date, organization)
  - Distinguishes between bot protection, 403 errors, and timeouts

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

### Citation Lookup (Single Citations) ⭐ NEW

Generate Vancouver-style citations from PMID, DOI, PMC ID, or article title:

```bash
# Look up by PMID
python citation_lookup.py --pmid 32089132

# Look up by DOI
python citation_lookup.py --doi "10.1186/s12968-020-00607-1"

# Search by title
python citation_lookup.py --title "Lake Louise Criteria myocarditis"

# Auto-detect identifier type
python citation_lookup.py --auto "32089132"

# Batch processing from file (one identifier per line)
python citation_lookup.py --batch identifiers.txt --output citations.md
```

**Output Formats:**
| Format | Description |
|:-------|:------------|
| `--format full` | Both inline mark and endnote (default) |
| `--format inline` | Just `[^KramerC-2020-32089132]` |
| `--format endnote` | Just the full endnote citation |
| `--format json` | Full metadata as JSON |

**Example Output:**
```
Inline: [^KramerC-2020-32089132]

[^KramerC-2020-32089132]: Kramer CM, Barkhausen J, Bucciarelli-Ducci C, et al. 
Standardized cardiovascular magnetic resonance imaging (CMR) protocols: 2020 update. 
J Cardiovasc Magn Reson. 2020 Feb;22(1):17. 
[DOI](https://doi.org/10.1186/s12968-020-00607-1). 
[PMID: 32089132](https://pubmed.ncbi.nlm.nih.gov/32089132/)
```

### Graphical Interface (For Batch Processing)

```bash
# Launch the web-based GUI
python gui.py

# Or directly with streamlit
streamlit run gui.py
```

The GUI provides:
- 📁 File browser for selecting markdown documents
- ⚙️ Easy access to all processing options
- 📊 Real-time processing statistics
- 🔧 Built-in corrections editor for fixing missing data
- 📥 Download buttons for processed files

### Command Line

```bash
# Basic usage
python citation_sculptor.py "path/to/document.md"

# With options
python citation_sculptor.py "path/to/document.md" --verbose --output custom_output.md

# Generate corrections template for incomplete citations
python citation_sculptor.py "path/to/document.md" --generate-corrections

# Apply corrections from a filled-in template
python citation_sculptor.py --apply-corrections "corrections.md" "formatted_document.md"
```

### CLI Options

| Option | Description |
|--------|-------------|
| `--output, -o` | Output file path (default: `filename_formatted.md`) |
| `--verbose, -v` | Enable detailed logging |
| `--dry-run, -n` | Preview changes without writing |
| `--no-backup` | Skip creating backup file |
| `--multi-section` | Process documents with multiple independent reference sections |
| `--generate-corrections` | Generate a template for fixing incomplete citations |
| `--apply-corrections FILE` | Apply corrections from a filled template |

### Output Files

| File | Description |
|------|-------------|
| `*_formatted.md` | Processed document with Vancouver citations |
| `*_corrections.md` | Template for fixing incomplete citations (if needed) |
| `*_formatted_mapping.json` | Reference mapping for audit/rollback |

### Corrections Workflow

When websites block automated scraping, citations may have `Null_Date` or `Null_Author` placeholders:

1. **Process document** → generates `_formatted.md` and `_corrections.md`
2. **Open URLs** listed in corrections file and find the missing info
3. **Fill in the template** with dates, authors, etc.
4. **Apply corrections** via GUI or `--apply-corrections`

Example corrections template:
```markdown
### 1. [^CBPP-StatesCan-ND]

**URL**: https://www.cbpp.org/research/health/...
**Current Citation**: CBPP. States Can Use Medicaid... Null_Date.
**Missing**: Date, Authors

**Corrections** (fill in below):
- Date: 2024-02-27
- Authors: Orris A, Bailey A, Sullivan J
- New Tag (optional): [^OrrisA-2024]
```

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

## Recent Updates (2025-11-29)

### v0.4.2
- **Evergreen Page Detection**: Landing pages, service pages, about pages no longer flagged with `Null_Date`
  - These pages legitimately don't have publication dates
  - Reduces noise in "Need Review" count
- **GUI Dark Mode Fix**: Metric cards now display properly in dark mode themes
- **Processing Summary**: After processing, GUI shows detailed statistics:
  - Citations formatted count
  - Inline refs updated
  - Undefined refs detected
  - Null placeholder counts with breakdown

### v0.4.1
- **DOI Path Date Extraction**: Extract dates from DOI-style URLs (e.g., `healthaffairs.org/do/10.1377/forefront.20201130` → 2020)
- **Blog Scraping**: Blogs now scraped for author/date metadata (previously only webpages)
- **Console Null Summary**: End-of-processing shows count of `Null_Date` and `Null_Author` citations
- **Published Date Fallback**: Extract year from `published_date` field when `year` is empty

### v0.4.0
- **V6 Grouped Footnotes**: Support for `[^1] [^47] Title` format with multi-line URLs
- **JSON-LD Date Extraction**: Parse publication dates from structured data (handles non-padded dates like `2023-1-2`)
- **DOI Text Extraction**: Detect `doi:10.xxx` patterns in plain text references
- **CrossRef Title Search**: Fallback to CrossRef when PubMed title search fails
- **Smart Organization Handling**: 
  - Automatic acronym detection for domain names (CBPP, AMA, etc.)
  - Full organization names in citations, abbreviations in tags
  - Custom meta tag support (`m_authors` for sites like Milliman)
- **URL Title Recovery**: Extract full titles from URL slugs when source has truncated `...` titles
- **URL Year Extraction**: Improved patterns to extract years from paths like `/2019/article-title`
- **URL Metadata Fallback**: Extract title, date, organization from URLs when sites block scraping
- **Ellipsis Removal**: Truncated titles cleaned up (no more `...` in citations)
- **Social Media Handling**: Skip garbage URL-based title extraction for LinkedIn, Twitter, Facebook
- **Author + Organization**: Include both when available in webpage citations
- **Author Filtering**: Filter out CMS usernames from author metadata
- **Null Placeholders**: Missing fields use searchable placeholders (`Null_Date`, `Null_Author`)
  - Tag uses short form: `[^Org-Title-ND]`
  - Citation text uses full form: `Org. Title. Null_Date. [Link](...)`
  - Search for `Null_` to find all incomplete citations

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
