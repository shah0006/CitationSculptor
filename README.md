# CitationSculptor

**The comprehensive citation management toolkit for researchers and Obsidian users.**

Transform identifiers (PMID, DOI, ISBN, URLs) into properly formatted citations, process entire documents with LLM-generated references, and manage your citations directly in Obsidian.

[![Version](https://img.shields.io/badge/version-1.5.0-blue.svg)](CHANGELOG.md)
[![Python](https://img.shields.io/badge/python-3.10+-green.svg)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-yellow.svg)](LICENSE)

---

## ✨ Features

### 🔍 Citation Lookup
- **PubMed**: PMID, DOI, PMC ID, title search
- **CrossRef**: Journal articles, book chapters, books not in PubMed
- **Webpages**: Smart metadata extraction with fallbacks
- **News/Blogs**: Publication date and author extraction

### 🎨 Output Formats
- **Vancouver Style** (medical/scientific standard)
- *Coming soon: APA, MLA, Chicago, Harvard, IEEE*

### 🖥️ Multiple Interfaces
| Interface | Use Case |
|-----------|----------|
| **CLI** | Quick lookups, scripting, batch processing |
| **Interactive Mode** | Continuous lookups with REPL |
| **Obsidian Plugin** | Native integration with full UI |
| **MCP Server** | AI assistant integration (Cursor, etc.) |
| **Web GUI** | Browser-based batch processing |

### 📚 Document Processing
- Batch process entire markdown documents
- Multi-section support (multiple reference lists)
- 8 reference format variants (V1-V8)
- Inline reference transformation (`[1]` → `[^Author-2024-PMID]`)

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

Native Obsidian integration with a comprehensive UI.

### Installation

1. Copy plugin files to `.obsidian/plugins/citation-sculptor/`
2. Enable in Settings → Community Plugins
3. Configure paths in plugin settings

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
- **One-click insert**: At cursor with auto References section
- **Format options**: Inline only, full citation, or both
- **Auto-copy**: Clipboard integration
- **Recent history**: Quick access to past lookups

---

## 🤖 MCP Server Integration

Use CitationSculptor with AI assistants (Cursor, Claude, etc.).

### Configuration

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

### Available Tools

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
| `citation_test_connection` | Test API connection |

---

## 📊 Source Type Support

| Source | Detection | Lookup | Format | Status |
|--------|-----------|--------|--------|--------|
| PubMed Articles | ✅ | ✅ | ✅ | Complete |
| CrossRef Articles | ✅ | ✅ | ✅ | Complete |
| Book Chapters | ✅ | ✅ | ✅ | Complete |
| Books (ISBN) | ⚠️ | 📋 | ✅ | v1.7 |
| Webpages | ✅ | ✅ | ✅ | Complete |
| News Articles | ✅ | ✅ | ✅ | Complete |
| Blogs | ✅ | ✅ | ✅ | Complete |
| PDFs | ⚠️ | 📋 | ✅ | v1.8 |
| arXiv | 📋 | 📋 | 📋 | v1.7 |
| bioRxiv/medRxiv | 📋 | 📋 | 📋 | v1.7 |

---

## 🗺️ Roadmap

### v1.6.0 - Multi-Format Support
- [ ] APA 7th Edition
- [ ] MLA 9th Edition
- [ ] Chicago/Turabian
- [ ] Format selector in CLI & plugin

### v1.7.0 - Enhanced Sources
- [ ] arXiv API integration
- [ ] bioRxiv/medRxiv support
- [ ] ISBN → Google Books lookup
- [ ] Wayback Machine for archived URLs
- [ ] OpenAlex API

### v1.8.0 - PDF Support
- [ ] PDF metadata extraction
- [ ] DOI extraction from PDF content
- [ ] PDF drag & drop in Obsidian

### v1.9.0 - Import/Export
- [ ] BibTeX export
- [ ] RIS export
- [ ] BibTeX import
- [ ] Zotero integration

### v2.0.0 - Smart Features
- [ ] LLM-powered metadata extraction
- [ ] Citation database (SQLite)
- [ ] Duplicate detection
- [ ] Link verification
- [ ] Citation graph visualization

See [PLANNING.md](PLANNING.md) for detailed roadmap.

---

## 🏗️ Architecture

```
CitationSculptor/
├── citation_lookup.py       # Single citation CLI
├── citation_sculptor.py     # Document processing CLI
├── gui.py                   # Streamlit web interface
├── mcp_server/
│   └── server.py            # MCP server (stdio)
├── obsidian-plugin/         # Native Obsidian plugin
│   ├── main.ts
│   ├── manifest.json
│   └── styles.css
├── modules/
│   ├── pubmed_client.py     # PubMed/CrossRef/scraper
│   ├── vancouver_formatter.py
│   ├── reference_parser.py
│   ├── inline_replacer.py
│   └── ...
└── tests/                   # 174 tests
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

**Test Coverage:** 174 tests across 5 test files

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
