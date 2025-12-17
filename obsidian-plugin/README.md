# CitationSculptor Obsidian Plugin

An Obsidian plugin that integrates CitationSculptor for looking up and inserting Vancouver-style citations directly into your notes.

## Features

- **Quick Citation Lookup**: Look up citations by PMID, DOI, PMC ID, or article title
- **PubMed Search**: Search PubMed and select from multiple results
- **Batch Lookup**: Process multiple identifiers at once
- **Recent Lookups**: Access your lookup history for quick re-use
- **One-Click Insert**: Insert formatted citations at cursor position
- **Auto-Reference Section**: Automatically adds citations to a References section
- **Clipboard Integration**: Copies citations to clipboard automatically
- **MCP Server Integration**: Uses CitationSculptor's HTTP API for efficient lookups (no process spawning)

## Installation

### Prerequisites

1. CitationSculptor must be installed:
   ```bash
   cd /Users/tusharshah/Developer/MCP-Servers/CitationSculptor
   .venv/bin/python citation_lookup.py --pmid 32089132
   ```

2. **Recommended**: Start the HTTP server for efficient lookups:
   ```bash
   cd /Users/tusharshah/Developer/MCP-Servers/CitationSculptor
   .venv/bin/python -m mcp_server.http_server --port 3018
   ```

### Manual Installation

1. Navigate to your vault's plugins folder:
   ```bash
   cd /path/to/your/vault/.obsidian/plugins
   ```

2. Create the plugin folder and copy files:
   ```bash
   mkdir citation-sculptor
   cd citation-sculptor
   # Copy manifest.json, main.js, and styles.css here
   ```

3. Build the plugin (if you have the source):
   ```bash
   cd /Users/tusharshah/Developer/MCP-Servers/CitationSculptor/obsidian-plugin
   npm install
   npm run build
   ```

4. Enable the plugin in Obsidian Settings → Community Plugins

### Auto-Starting the HTTP Server (macOS)

For automatic startup on login, install the launchd service:

```bash
# Copy the plist file
cp /Users/tusharshah/Developer/MCP-Servers/CitationSculptor/scripts/com.citationsculptor.httpserver.plist ~/Library/LaunchAgents/

# Load and start the service
launchctl load ~/Library/LaunchAgents/com.citationsculptor.httpserver.plist

# Check status
launchctl list | grep citationsculptor
```

To stop and unload:
```bash
launchctl unload ~/Library/LaunchAgents/com.citationsculptor.httpserver.plist
```

## Usage

### Commands (Cmd/Ctrl + P)

| Command | Description |
|---------|-------------|
| **Open Citation Lookup** | Opens the full citation lookup modal with tabs |
| **Quick Lookup** | Quick input for PMID/DOI/title |
| **Look Up Selected Text** | Look up the currently selected text |
| **Quick Lookup (Insert Inline Only)** | Look up and insert only the inline reference |
| **Search PubMed** | Opens the search tab directly |
| **Batch Citation Lookup** | Opens the batch lookup tab |
| **Recent Citation Lookups** | Opens recent lookups tab |

### Ribbon Icon

Click the quote icon (❝) in the left ribbon to open the citation lookup modal.

### Modal Tabs

The main modal has 4 tabs:

1. **Quick Lookup**: Enter any identifier (PMID, DOI, PMC ID, or title)
2. **PubMed Search**: Search PubMed and browse results
3. **Batch Lookup**: Process multiple identifiers at once
4. **Recent**: Access your lookup history

### Keyboard Workflow

1. Press `Cmd+P` and type "Citation"
2. Select "Quick Lookup"
3. Enter a PMID (e.g., `37622666`)
4. Press Enter
5. Citation is inserted at cursor and copied to clipboard

### Search Workflow

1. Open Citation Lookup modal
2. Click "PubMed Search" tab
3. Enter a search query (e.g., "ESC heart failure guidelines 2023")
4. Click "Search PubMed"
5. Click "Get Citation" on a result
6. Click "Insert Both" to add inline reference and endnote

### Batch Workflow

1. Open Citation Lookup modal
2. Click "Batch Lookup" tab
3. Enter identifiers, one per line:
   ```
   37622666
   10.1093/eurheartj/ehad195
   PMC7039045
   ```
4. Click "Process Batch"
5. Copy all or insert into your note

## Settings

### MCP Server (Recommended)

| Setting | Description | Default |
|---------|-------------|---------|
| Use HTTP API | Use the CitationSculptor HTTP server | `true` |
| HTTP API URL | URL of the HTTP server | `http://127.0.0.1:3018` |

### CLI Fallback

| Setting | Description | Default |
|---------|-------------|---------|
| CitationSculptor Path | Path to CitationSculptor directory | `/Users/tusharshah/Developer/MCP-Servers/CitationSculptor` |
| Python Path | Path to Python in venv | `.venv/bin/python` |

### Behavior

| Setting | Description | Default |
|---------|-------------|---------|
| Default Format | Citation format (full/inline/endnote) | `full` |
| Auto Copy to Clipboard | Copy citations automatically | `true` |
| Insert at Cursor | Insert citation at cursor | `true` |
| Show Abstracts in Search | Display abstracts in search results | `false` |
| Max Search Results | Number of PubMed results to show | `10` |

## Citation Format

Citations are formatted in Vancouver style with mnemonic labels:

**Inline Reference:**
```
[^McDonaghT-2023-37622666]
```

**Full Citation:**
```
[^McDonaghT-2023-37622666]: McDonagh TA, Metra M, Adamo M, et al. 2023 Focused Update of the 2021 ESC Guidelines for the diagnosis and treatment of acute and chronic heart failure. Eur Heart J. 2023 Oct;44(37):3627-3639. [DOI](https://doi.org/10.1093/eurheartj/ehad195). [PMID: 37622666](https://pubmed.ncbi.nlm.nih.gov/37622666/)
```

## HTTP API Endpoints

When the HTTP server is running, you can access these endpoints directly:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/api/lookup?id=X` | GET | Auto-detect and lookup identifier |
| `/api/lookup/pmid?pmid=X` | GET | Lookup by PMID |
| `/api/lookup/doi?doi=X` | GET | Lookup by DOI |
| `/api/search?q=X&max=10` | GET | Search PubMed |
| `/api/lookup` | POST | Lookup with JSON body |
| `/api/batch` | POST | Batch lookup with JSON body |
| `/api/cache/stats` | GET | Cache statistics |

## Development

```bash
cd /Users/tusharshah/Developer/MCP-Servers/CitationSculptor/obsidian-plugin
npm install
npm run dev  # Watch mode for development
npm run build  # Production build
```

## Troubleshooting

### "HTTP API unavailable" notice
1. Start the HTTP server:
   ```bash
   cd /Users/tusharshah/Developer/MCP-Servers/CitationSculptor
   .venv/bin/python -m mcp_server.http_server
   ```
2. Check the URL in settings (default: `http://127.0.0.1:3018`)
3. Test with: `curl http://127.0.0.1:3018/health`

### "Cannot find citation_lookup.py"
- Verify CitationSculptor Path in settings points to the correct directory

### "Python not found"
- Verify Python Path points to the correct venv Python executable
- Test: `/path/to/.venv/bin/python --version`

### "Cannot connect to PubMed API"
- Check internet connection
- NCBI E-utilities may be rate-limiting requests

## Architecture

The plugin uses a two-tier approach for efficiency:

1. **HTTP API (Primary)**: When the CitationSculptor HTTP server is running, the plugin makes HTTP requests to `localhost:3018`. This is fast and avoids spawning new processes.

2. **CLI Fallback**: If the HTTP server is unavailable, the plugin falls back to spawning Python processes for each lookup. This works but is slower.

```
┌─────────────────────────┐
│   Obsidian Plugin       │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐     ┌─────────────────────────┐
│  HTTP API (Primary)     │────▶│  CitationSculptor       │
│  localhost:3018         │     │  HTTP Server            │
└─────────────────────────┘     └───────────┬─────────────┘
            │                               │
            │ (fallback)                    ▼
            ▼                   ┌─────────────────────────┐
┌─────────────────────────┐     │  PubMed/CrossRef APIs   │
│  CLI Process Spawn      │────▶│                         │
│  citation_lookup.py     │     └─────────────────────────┘
└─────────────────────────┘
```

## License

MIT
