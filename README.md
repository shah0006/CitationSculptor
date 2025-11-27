# CitationSculptor

**Transform LLM-generated reference sections into properly formatted Vancouver-style citations for Obsidian markdown documents.**

## Overview

CitationSculptor is a Python tool that processes Obsidian markdown documents containing LLM-generated reference sections and reformats them according to Vancouver citation standards. It integrates with the PubMed API (via MCP server) to fetch accurate journal article metadata.

## Features

- **Journal Article Processing**: Fetches metadata from PubMed and generates complete Vancouver citations
- **Smart Citation Detection**: Identifies citation types (journal articles, books, webpages, etc.)
- **Inline Reference Transformation**: Converts numbered references `[1]` to mnemonic labels `[^AuthorYear-PMID]`
- **Hallucination Detection**: Verifies citations against PubMed
- **Manual Review Flagging**: Problematic citations are flagged for human review

## Installation

```bash
cd C:\Users\tusharshah\Projects\CitationSculptor

# Create virtual environment
python -m venv venv

# Activate (Windows)
.\venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## Usage

```bash
python citation_sculptor.py "path/to/document.md"
```

### Options

| Option | Description |
|--------|-------------|
| `--output, -o` | Output file path (default: `filename_formatted.md`) |
| `--verbose, -v` | Enable detailed logging |
| `--dry-run, -n` | Preview changes without writing |
| `--no-backup` | Skip creating backup file |

## Requirements

- Python 3.9+
- PubMed MCP Server running at `http://127.0.0.1:3017/mcp`

## Project Phases

| Phase | Scope | Status |
|-------|-------|--------|
| Phase 1 | Journal articles via PubMed | In Progress |
| Phase 2 | Book chapters, books | Planned |
| Phase 3 | Newspaper articles | Planned |
| Phase 4 | Webpages, web articles, blogs | Planned |
| Phase 5 | Batch processing | Planned |
| Phase 6 | Obsidian plugin | Planned |

## License

MIT License

