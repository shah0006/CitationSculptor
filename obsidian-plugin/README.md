# CitationSculptor Obsidian Plugin

An Obsidian plugin that integrates CitationSculptor for looking up and inserting Vancouver-style citations directly into your notes.

## Features

- **Quick Citation Lookup**: Look up citations by PMID, DOI, PMC ID, or article title
- **PubMed Search**: Search PubMed and select from multiple results
- **One-Click Insert**: Insert formatted citations at cursor position
- **Auto-Reference Section**: Automatically adds citations to a References section
- **Clipboard Integration**: Copies citations to clipboard automatically

## Installation

### Prerequisites

1. CitationSculptor must be installed and working:
   ```bash
   cd /Users/tusharshah/Developer/MCP-Servers/CitationSculptor
   .venv/bin/python citation_lookup.py --pmid 32089132
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

## Usage

### Commands (Cmd/Ctrl + P)

| Command | Description |
|---------|-------------|
| **Open Citation Lookup** | Opens the full citation lookup modal |
| **Quick Lookup** | Quick input for PMID/DOI/title |
| **Look Up Selected Text** | Look up the currently selected text |

### Ribbon Icon

Click the quote icon (") in the left ribbon to open the citation lookup modal.

### Keyboard Workflow

1. Press `Cmd+P` and type "Citation"
2. Select "Quick Lookup"
3. Enter a PMID (e.g., `37622666`)
4. Press Enter
5. Citation is inserted at cursor and copied to clipboard

### Search Workflow

1. Open Citation Lookup modal
2. Enter a search query (e.g., "ESC heart failure guidelines 2023")
3. Click "Search PubMed"
4. Click on a result to get the full citation
5. Click "Insert at Cursor" to add it to your note

## Settings

| Setting | Description | Default |
|---------|-------------|---------|
| CitationSculptor Path | Path to CitationSculptor directory | `/Users/tusharshah/Developer/MCP-Servers/CitationSculptor` |
| Python Path | Path to Python in venv | `.venv/bin/python` |
| Default Format | Citation format (full/inline/endnote) | `full` |
| Auto Copy to Clipboard | Copy citations automatically | `true` |
| Insert at Cursor | Insert citation at cursor | `true` |

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

## Development

```bash
cd /Users/tusharshah/Developer/MCP-Servers/CitationSculptor/obsidian-plugin
npm install
npm run dev  # Watch mode for development
npm run build  # Production build
```

## Troubleshooting

### "Cannot find citation_lookup.py"
- Verify CitationSculptor Path in settings points to the correct directory

### "Python not found"
- Verify Python Path points to the correct venv Python executable
- Test: `/path/to/.venv/bin/python --version`

### "Cannot connect to PubMed API"
- Check internet connection
- NCBI E-utilities may be rate-limiting requests

## License

MIT

