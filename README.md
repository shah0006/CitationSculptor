# CitationSculptor

**The comprehensive citation management toolkit for researchers and Obsidian users.**

Transform identifiers (PMID, DOI, ISBN, URLs) into properly formatted citations, process entire documents with LLM-generated references, and manage your citations directly in Obsidian.

[![Version](https://img.shields.io/badge/version-2.1.0-blue.svg)](CHANGELOG.md)
[![Python](https://img.shields.io/badge/python-3.10+-green.svg)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-yellow.svg)](LICENSE)

---

## ✨ Features

### 🔍 Citation Lookup
- **PubMed**: PMID, DOI, PMC ID, title search
- **CrossRef**: Journal articles, book chapters, books not in PubMed
- **Webpages**: Smart metadata extraction with fallbacks
- **News/Blogs**: Publication date and author extraction

### 🎨 Citation Styles
- **Vancouver** - Medical/scientific standard
- **APA 7th** - Psychology, social sciences
- **MLA 9th** - Humanities, literature
- **Chicago** - History, arts
- **Harvard** - General academic
- **IEEE** - Engineering, computer science

### 🖥️ Multiple Interfaces
| Interface | Use Case |
|-----------|----------|
| **CLI** | Quick lookups, scripting, batch processing |
| **Interactive Mode** | Continuous lookups with REPL |
| **Web UI** | Beautiful browser-based interface with document processing |
| **Obsidian Plugin** | Native integration with process current note |
| **MCP Server** | AI assistant integration (Cursor, etc.) |
| **Streamlit GUI** | Document batch processing |

### 📚 Document Processing
- Batch process entire markdown documents
- Multi-section support (multiple reference lists)
- 8 reference format variants (V1-V8)
- Inline reference transformation (`[1]` → `[^Author-2024-PMID]`)

### 🧠 Document Intelligence (v2.1)
- **Link Verification**: Check for broken links with Wayback Machine fallback
- **Citation Suggestions**: Find passages that may need citations
- **Compliance Checker**: Detect uncited quotes, claims, and statistics
- **LLM Extraction**: AI-powered metadata extraction for edge cases

### 🛡️ Safety & Reliability
- **Automatic Backups**: Creates timestamped backup before any file modification
- **One-Click Restore**: Instantly restore original file from Web UI
- **Detailed Error Messages**: Clear explanations when references fail to resolve
- **Real-Time Progress**: Live progress bar and statistics during processing
- **Comprehensive Logging**: Persistent log files for troubleshooting

### 📊 Real-Time Progress (Web UI)
- Live progress bar with percentage
- Running statistics (processed/failed/total)
- Current reference being looked up
- Streaming updates via Server-Sent Events

---

## 🚀 Quick Start

### Installation

```bash
cd /path/to/CitationSculptor

# Using uv (recommended)
uv venv --python 3.12
uv pip install -r requirements.txt

# Or standard venv
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Basic Usage

```bash
# Single citation lookup
python citation_lookup.py --pmid 37622666

# Interactive mode (REPL)
python citation_lookup.py --interactive --copy

# Search PubMed
python citation_lookup.py --search-multi "ESC heart failure guidelines"

# Process a document
python citation_sculptor.py "document.md" --multi-section
```

---

## 📖 Tools Overview

### `citation_lookup.py` - Single Citation Lookup

Generate Vancouver-style citations from any identifier:

```bash
# By PMID
python citation_lookup.py --pmid 32089132

# By DOI  
python citation_lookup.py --doi "10.1093/eurheartj/ehad195"

# By PMC ID
python citation_lookup.py --pmcid PMC7039045

# By title
python citation_lookup.py --title "Lake Louise Criteria myocarditis"

# Auto-detect type
python citation_lookup.py --auto "32089132"
```

**Options:**
| Flag | Description |
|------|-------------|
| `--format, -f` | Output format: `full`, `inline`, `endnote`, `json` |
| `--copy, -c` | Copy to clipboard (macOS) |
| `--no-cache` | Bypass the 30-day cache |
| `--interactive, -i` | Run in REPL mode |
| `--search-multi QUERY` | Search PubMed, select from results |
| `--batch FILE` | Process multiple identifiers |

**Example Output:**
```
Inline: [^McDonaghT-2023-37622666]

[^McDonaghT-2023-37622666]: McDonagh TA, Metra M, Adamo M, et al. 
2023 Focused Update of the 2021 ESC Guidelines for the diagnosis 
and treatment of acute and chronic heart failure. Eur Heart J. 
2023 Oct;44(37):3627-3639. 
[DOI](https://doi.org/10.1093/eurheartj/ehad195). 
[PMID: 37622666](https://pubmed.ncbi.nlm.nih.gov/37622666/)
```

### Interactive Mode

```bash
python citation_lookup.py --interactive --copy
```

```
CitationSculptor Interactive Mode
Commands: /search <query>, /format <type>, /help, /quit

> 37622666
[^McDonaghT-2023-37622666]: McDonagh TA, Metra M, et al...
✓ Copied to clipboard

> /search ESC heart failure
Found 10 results:
1. 2023 Focused Update of the 2021 ESC Guidelines...
Select: 1

> /format inline
Output format set to: inline

> /quit
```

### `citation_sculptor.py` - Document Processing

Process entire markdown documents with reference sections:

```bash
# Basic processing
python citation_sculptor.py "document.md"

# Multi-section documents
python citation_sculptor.py "document.md" --multi-section

# Generate corrections template
python citation_sculptor.py "document.md" --generate-corrections
```

---

## 🔌 Obsidian Plugin

Native Obsidian integration with a comprehensive UI that connects to the CitationSculptor MCP server for efficient lookups.

### Installation

1. Build the plugin:
   ```bash
   cd obsidian-plugin
   npm install && npm run build
   ```
2. Copy `manifest.json`, `main.js`, `styles.css` to `.obsidian/plugins/citation-sculptor/`
3. Enable in Settings → Community Plugins

### Start the HTTP Server (Recommended)

The plugin works best with the HTTP server running:

```bash
# Start the server
.venv/bin/python -m mcp_server.http_server --port 3019

# Or install as a macOS service (auto-start on login)
cp scripts/com.citationsculptor.httpserver.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.citationsculptor.httpserver.plist
```

### Commands (Cmd+P)

| Command | Description |
|---------|-------------|
| **Open Citation Lookup** | Full modal with all features |
| **Quick Lookup** | Simple identifier input |
| **Look Up Selected Text** | Look up highlighted text |
| **Quick Lookup (Inline Only)** | Insert just the reference mark |
| **Search PubMed** | Browse search results |
| **Batch Citation Lookup** | Process multiple identifiers |
| **Recent Citation Lookups** | Access lookup history |

### Features

- **4-tab interface**: Lookup, Search, Batch, Recent
- **Process Current Note**: One-click processing of all citations in the active note
- **HTTP API Integration**: Uses MCP server for fast lookups (no process spawning)
- **CLI Fallback**: Automatically falls back to CLI if server unavailable
- **One-click insert**: At cursor with auto References section
- **Format options**: Inline only, full citation, or both
- **Auto-copy**: Clipboard integration
- **Recent history**: Quick access to past lookups

---

## 🤖 MCP Server Integration

Use CitationSculptor with AI assistants (Cursor, Claude, etc.) or via HTTP API.

### stdio Server (for AI assistants)

Add to your MCP settings (`.cursor/mcp.json`):

```json
{
  "mcpServers": {
    "citation-lookup-mcp": {
      "command": "/path/to/CitationSculptor/.venv/bin/python",
      "args": ["-m", "mcp_server.server"],
      "cwd": "/path/to/CitationSculptor"
    }
  }
}
```

### HTTP Server with Web UI

Start the HTTP server to access the beautiful web UI and API:

```bash
# Start the HTTP server
.venv/bin/python -m mcp_server.http_server --port 3019

# Open in browser
open http://127.0.0.1:3019
```

**Web UI Features:**
- 🔍 Quick Lookup - Enter any identifier
- 📚 PubMed Search - Search and select from results
- 📋 Batch Lookup - Process multiple identifiers
- 📝 Process Document - Process entire markdown files with file path or content
- 🕐 Recent History - Access past lookups

```bash
# API access
curl http://127.0.0.1:3019/health
curl "http://127.0.0.1:3019/api/lookup?id=37622666"
curl "http://127.0.0.1:3019/api/search?q=heart+failure"
```

### HTTP API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/api/lookup?id=X` | GET | Auto-detect and lookup |
| `/api/lookup/pmid?pmid=X` | GET | Lookup by PMID |
| `/api/lookup/doi?doi=X` | GET | Lookup by DOI |
| `/api/search?q=X&max=10` | GET | Search PubMed |
| `/api/lookup` | POST | Lookup with JSON body |
| `/api/batch` | POST | Batch lookup |
| `/api/process-document` | POST | Process full markdown document |
| `/api/cache/stats` | GET | Cache statistics |

### MCP Tools (for AI assistants)

| Tool | Description |
|------|-------------|
| `citation_lookup_pmid` | Look up by PubMed ID |
| `citation_lookup_doi` | Look up by DOI |
| `citation_lookup_pmcid` | Look up by PMC ID |
| `citation_lookup_title` | Search by title |
| `citation_lookup_auto` | Auto-detect identifier |
| `citation_get_inline_only` | Get just `[^Author-Year-PMID]` |
| `citation_get_endnote_only` | Get just the endnote |
| `citation_get_metadata` | Get JSON metadata |
| `citation_get_abstract` | Get article abstract |
| `citation_search_pubmed` | Search with multiple results |
| `citation_batch_lookup` | Multiple identifiers |
| `citation_process_document` | Process full markdown document |
| `citation_test_connection` | Test API connection |

---

## 📊 Source Type Support

**Legend:** ✅ Fully supported | ⚠️ Partial support

| Source | Detection | Lookup | Format | Status |
|--------|-----------|--------|--------|--------|
| PubMed Articles | ✅ Supported | ✅ Supported | ✅ Supported | Complete |
| CrossRef Articles | ✅ Supported | ✅ Supported | ✅ Supported | Complete |
| Book Chapters | ✅ Supported | ✅ Supported | ✅ Supported | Complete |
| Books (ISBN) | ✅ Supported | ✅ Supported | ✅ Supported | Complete |
| Webpages | ✅ Supported | ✅ Supported | ✅ Supported | Complete |
| News Articles | ✅ Supported | ✅ Supported | ✅ Supported | Complete |
| Blogs | ✅ Supported | ✅ Supported | ✅ Supported | Complete |
| PDFs | ✅ Supported | ✅ Supported | ✅ Supported | Complete |
| arXiv | ✅ Supported | ✅ Supported | ✅ Supported | Complete |
| bioRxiv/medRxiv | ✅ Supported | ⚠️ Partial | ✅ Supported | Complete |
| OpenAlex | ✅ Supported | ✅ Supported | ✅ Supported | Complete |
| Semantic Scholar | ✅ Supported | ✅ Supported | ✅ Supported | Complete |

---

## 🗺️ Version History

### ✅ v2.1.0 - Document Intelligence (Complete)
- [x] Link verification & broken link detection
- [x] Automatic citation suggestions based on content
- [x] Plagiarism-style citation compliance checker
- [x] LLM-powered metadata extraction for edge cases
- [x] HTTP API: `/api/verify-links`, `/api/suggest-citations`, `/api/check-compliance`, `/api/analyze-document`
- [x] MCP tools for AI agents

### ✅ v2.0.0 - Smart Features (Complete)
- [x] Citation database (SQLite) with full-text search
- [x] Duplicate detection with fuzzy matching
- [x] Bibliography auto-generation
- [x] Document processing across all interfaces

### ✅ v1.9.0 - Import/Export (Complete)
- [x] BibTeX import & export
- [x] RIS import & export

### ✅ v1.8.0 - Additional Sources (Complete)
- [x] Wayback Machine integration
- [x] OpenAlex API
- [x] Semantic Scholar API
- [x] PDF metadata extraction

### ✅ v1.7.0 - Enhanced Sources (Complete)
- [x] arXiv API integration
- [x] bioRxiv/medRxiv support
- [x] ISBN → Google Books/OpenLibrary lookup

### ✅ v1.6.0 - Multi-Format Support (Complete)
- [x] APA 7th Edition
- [x] MLA 9th Edition
- [x] Chicago/Turabian
- [x] Harvard
- [x] IEEE
- [x] Format selector in CLI, Web UI & plugin

---

## 🔮 Future Roadmap

We're always looking to improve CitationSculptor. Here's what's planned:

### v2.2.0 - Reference Manager Integration
- [ ] Zotero library sync (two-way)
- [ ] Mendeley integration
- [ ] EndNote support
- [ ] Papers app integration

### v2.3.0 - Visualization & Analytics
- [ ] Citation network graph visualization
- [ ] Co-author network mapping
- [ ] Research trend analysis
- [ ] Journal impact metrics display

### v2.4.0 - Collaboration Features
- [ ] Shared citation libraries
- [ ] Team workspaces
- [ ] Citation annotation & notes sharing
- [ ] Export to collaborative writing platforms (Overleaf, Google Docs)

### Continuous Improvements
- Performance optimizations
- Additional citation styles on request
- More source integrations (JSTOR, Google Scholar, etc.)
- Mobile-friendly web interface

**Have a feature request?** Open an issue on [GitHub](https://github.com/shah0006/CitationSculptor/issues).

See [PLANNING.md](PLANNING.md) and [CHANGELOG.md](CHANGELOG.md) for details.

---

## 🏗️ Architecture

```
CitationSculptor/
├── citation_lookup.py       # Single citation CLI (--interactive mode)
├── citation_sculptor.py     # Document processing CLI
├── gui.py                   # Streamlit web interface
├── mcp_server/
│   ├── server.py            # MCP server (stdio transport)
│   └── http_server.py       # HTTP API server (for Obsidian)
├── obsidian-plugin/         # Native Obsidian plugin
│   ├── main.ts              # Plugin code (uses HTTP API)
│   ├── manifest.json
│   └── styles.css
├── modules/
│   ├── pubmed_client.py     # PubMed/CrossRef/scraper
│   ├── vancouver_formatter.py
│   ├── reference_parser.py
│   ├── inline_replacer.py
│   └── ...
├── scripts/
│   └── com.citationsculptor.httpserver.plist  # macOS launchd service
└── tests/                   # 185 tests
```

---

## 🧪 Testing

```bash
# Run all tests
python -m pytest tests/ -v

# Run specific module
python -m pytest tests/test_pubmed_client.py -v

# With coverage
python -m pytest tests/ --cov=modules
```

**Test Coverage:** 292+ tests across all modules

---

## ⚙️ Configuration

Settings can be configured via environment variables or `.env` file:

### Logging Settings
| Setting | Default | Description |
|---------|---------|-------------|
| `ENABLE_FILE_LOGGING` | `true` | Enable persistent log files |
| `LOG_LEVEL` | `INFO` | Console log level (DEBUG, INFO, WARNING, ERROR) |
| `LOG_ROTATION_SIZE_MB` | `10` | Rotate logs at this size |
| `LOG_RETENTION_COUNT` | `5` | Number of log files to keep |

### Log Files Location
```
.data/logs/
├── citationsculptor.log      # Main application log
├── errors.log                 # Critical errors only
└── document_processing.log    # Backup/restore/save operations
```

### Viewing Logs via API
```bash
# Get log file information
curl http://127.0.0.1:3019/api/logs/info

# View recent logs (last 100 lines)
curl "http://127.0.0.1:3019/api/logs?type=main&lines=100"

# View errors only
curl "http://127.0.0.1:3019/api/logs?type=errors"

# View document operations
curl "http://127.0.0.1:3019/api/logs?type=processing"
```

### Other Settings
| Setting | Default | Description |
|---------|---------|-------------|
| `OBSIDIAN_VAULT_PATH` | *(empty)* | Path to Obsidian vault for relative path resolution |
| `CREATE_BACKUP` | `true` | Auto-backup before processing |
| `MAX_AUTHORS` | `3` | Authors before "et al." |

---

## 📝 Citation Format Examples

### Journal Article (PubMed)
```
[^KramerC-2020-32089132]: Kramer CM, Barkhausen J, et al. 
Standardized cardiovascular magnetic resonance imaging (CMR) 
protocols: 2020 update. J Cardiovasc Magn Reson. 2020 Feb;22(1):17. 
[DOI](https://doi.org/10.1186/s12968-020-00607-1). 
[PMID: 32089132](https://pubmed.ncbi.nlm.nih.gov/32089132/)
```

### Book Chapter (CrossRef)
```
[^SmithJ-2023-p145]: Smith J, Jones M. Chapter Title. In: Editor A, 
Editor B, editors. Book Title. 3rd ed. New York: Publisher; 2023. 
p. 145-167. [DOI](https://doi.org/10.1007/...)
```

### Webpage
```
[^AHA-HeartFailure-2024]: American Heart Association. Heart Failure 
Guidelines 2024. AHA. 2024 Mar 15. Available from: https://...
```

---

## 🏷️ Why Unique Reference Tags?

CitationSculptor uses **semantic reference tags** like `[^AuthorY-Year-PMID]` instead of traditional numbered references (`[1]`, `[2]`, etc.) for important reasons:

### The Problem with Numbered References

When working with long documents, especially those assembled from multiple sources (LLM outputs, literature searches, copied content), numbered references create serious issues:

1. **Duplicate Numbers**: Content pasted from different sources often reuses the same reference numbers (`[1]`, `[2]`), causing conflicts and broken links.

2. **Renumbering Nightmare**: Adding a reference early in a document requires renumbering all subsequent citations—error-prone and tedious.

3. **Context Loss**: Seeing `[1]` in text tells you nothing about what it references without scrolling to the reference section.

4. **Merge Conflicts**: Combining sections from different documents with numbered references is nearly impossible without manual renumbering.

### The Unique Tag Solution

Our format `[^AuthorY-Year-Identifier]` solves all of these:

| Tag Component | Example | Purpose |
|---------------|---------|---------|
| `Author` | `McDonaghT` | First author's surname + first initial |
| `Year` | `2023` | Publication year |
| `Identifier` | `37622666` | PMID, DOI hash, or unique string |

**Benefits:**

- ✅ **Globally Unique**: Each citation has a distinct tag that won't collide with others
- ✅ **Self-Describing**: Glancing at `[^McDonaghT-2023-37622666]` tells you it's a 2023 paper by McDonagh
- ✅ **Merge-Friendly**: Combine documents freely without renumbering
- ✅ **LLM-Compatible**: Paste AI-generated content without citation conflicts
- ✅ **Obsidian-Native**: Works with Obsidian's footnote syntax for clickable links

### Example Comparison

**Traditional (problematic):**
```markdown
Heart failure affects 6.2 million Americans[1]. The 2023 ESC guidelines[2]...

## References
[1]: CDC statistics...
[2]: McDonagh TA, et al. 2023 ESC Guidelines...
```

**CitationSculptor (robust):**
```markdown
Heart failure affects 6.2 million Americans[^CDC-HeartStats-2024]. 
The 2023 ESC guidelines[^McDonaghT-2023-37622666]...

## References
[^CDC-HeartStats-2024]: Centers for Disease Control...
[^McDonaghT-2023-37622666]: McDonagh TA, et al. 2023 ESC Guidelines...
```

The second format can be freely combined with any other document without conflicts.

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Run tests: `python -m pytest tests/ -v`
4. Submit a pull request

---

## 📄 License

MIT License - See [LICENSE](LICENSE)

---

## 🙏 Acknowledgments

- NCBI E-utilities API
- CrossRef API
- PubMed MCP Server
- Obsidian community
