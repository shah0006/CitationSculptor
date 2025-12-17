# CitationSculptor Architecture

Technical reference for the CitationSculptor codebase.

## Module Overview

```
CitationSculptor/
├── citation_sculptor.py    # Main CLI - batch document processing
├── citation_lookup.py      # Single citation lookup tool
├── gui.py                  # Streamlit web interface
├── modules/
│   ├── config.py           # Centralized configuration
│   ├── pubmed_client.py    # PubMed/CrossRef API client + WebpageScraper
│   ├── vancouver_formatter.py  # Citation formatting (Vancouver style)
│   ├── reference_parser.py     # Document parsing (V1-V8 formats)
│   ├── inline_replacer.py      # [1] → [^AuthorY-2024-PMID] replacement
│   ├── type_detector.py        # Citation type detection
│   ├── output_generator.py     # Output file generation
│   ├── file_handler.py         # File I/O operations
│   └── progress_dialog.py      # GUI progress indicators
├── mcp_server/
│   └── server.py           # MCP server for AI agent access
└── tests/
    └── *.py                # Unit tests (226 tests)
```

## Key Classes

### PubMedClient (`modules/pubmed_client.py`)
- Communicates with PubMed MCP server (port 3017)
- Handles CrossRef API for non-PubMed articles
- Includes `WebpageScraper` for webpage metadata extraction
- Features: caching, rate limiting (2.5 req/sec), retry with backoff

### VancouverFormatter (`modules/vancouver_formatter.py`)
- Formats metadata into Vancouver-style citations
- Supports: journal articles, books, chapters, webpages, blogs, newspapers
- Generates mnemonic labels: `[^AuthorY-Year-PMID]`

### ReferenceParser (`modules/reference_parser.py`)
- Parses reference sections from markdown documents
- Supports formats V1-V8 (see Reference Formats below)
- Multi-section mode for documents with multiple reference lists

## Reference Formats Supported

| Format | Description | Example |
|--------|-------------|---------|
| V1 | Simple numbered | `1. [Title - Source](URL)` |
| V2 | Extended with metadata | `1. [Title](URL). Authors. Journal...` |
| V3 | Footnote definitions | `[^1]: Citation text...` |
| V4 | Text-only | `1. Title. Authors. Journal.` |
| V6 | Grouped footnotes | `[^1] [^47] Title \| Source` |
| V7 | Numbered with link | `1. [Title](URL). Extra info...` |
| V8 | Works cited | `1. Title, accessed date, <URL>` |

## Key Design Decisions

1. **WebpageScraper in pubmed_client.py**: Originally separate file, moved to avoid Obsidian Sync deletion issues

2. **Null Placeholders**: Use searchable `Null_Date`, `Null_Author` instead of manual review sections

3. **Rate Limiting**: 2.5 req/sec (conservative for NCBI without API key)

4. **Multi-Section Mode**: Each reference section processed independently with scoped inline replacements

5. **Evergreen Pages**: Landing/about pages skip `Null_Date` flagging

## Configuration

All settings in `modules/config.py` with environment variable support:

```python
# Key settings
PUBMED_MCP_URL = "http://127.0.0.1:3017/mcp"
REQUESTS_PER_SECOND = 2.5
MAX_AUTHORS = 3
SCRAPING_TIMEOUT = 10
```

Override via `.env` file or environment variables.

## API Dependencies

- **PubMed MCP Server**: Must be running on port 3017
- **CrossRef API**: Public API, no key required
- **Ollama** (optional): For MCP server medical queries

