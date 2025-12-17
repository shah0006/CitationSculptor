# Continuation Prompt: CitationSculptor MCP Server Fix

## Background
The user has an Obsidian vault with MCP (Model Context Protocol) servers configured in Abacus Desktop. Two custom MCP servers were not working: `citation-lookup` (CitationSculptor) and `vault-organizer`.

## Problems Identified

1. **Transport Mismatch**: CitationSculptor's `pubmed_client.py` was designed to communicate with a separate `pubmed-mcp-server` via JSON-RPC HTTP (`http://127.0.0.1:3017/mcp`), but that server uses SSE transport, making them incompatible.

2. **File Editing Tool Failures**: The native Abacus Desktop `edit` tool repeatedly truncated files when making partial edits, even with `# ... existing code ...` markers. This caused `pubmed_client.py` to be corrupted multiple times (reduced from 1999 lines to 19-53 lines).

## Solutions Implemented

1. **Added Developer directory to MCP filesystem server**: Modified `/Users/tusharshah/Library/Application Support/AbacusAI/User/mcp.json` to include `/Users/tusharshah/Developer` in the `dropbox-local` server args. This enabled use of the reliable `mcp_edit_file` tool.

2. **Refactored pubmed_client.py**: Using `mcp_edit_file`, successfully modified `/Users/tusharshah/Developer/MCP-Servers/CitationSculptor/modules/pubmed_client.py` to use direct NCBI E-utilities API instead of the problematic `pubmed-mcp-server`:
   - Changed class constants to E-utilities URLs
   - Replaced `_send_request()` (JSON-RPC) with `_eutils_request()` (direct HTTP to NCBI)
   - Updated `test_connection()` to test E-utilities
   - Updated `convert_ids()` to call NCBI ID Converter directly

3. **Verified changes work**: 
   - File has 1967 lines (intact)
   - Python syntax check passes
   - Direct test of `PubMedClient.test_connection()` returns `True`
   - Direct test of `convert_ids(['32089132'])` successfully returns PMID/PMCID/DOI

## Current Problem
The MCP citation tools (`mcp_citation_lookup_pmid`, etc.) are still being cancelled when called. The CitationSculptor MCP server process is not running (verified via `ps aux | grep citation`).

## What Needs To Be Done

1. **Debug MCP server startup**: Run the server manually to see errors:
   ```bash
   cd /Users/tusharshah/Developer/MCP-Servers/CitationSculptor
   .venv/bin/python -m mcp_server.server
   ```

2. **Check server.py for issues**: The server at `/Users/tusharshah/Developer/MCP-Servers/CitationSculptor/mcp_server/server.py` may have code that still references the old `pubmed-mcp-server` or `_send_request`. Search for and update any remaining references.

3. **Verify MCP configuration**: Ensure `/Users/tusharshah/Library/Application Support/AbacusAI/User/mcp.json` has correct paths for `citation-lookup`.

4. **Test the MCP tools**: After fixes, test:
   ```
   mcp_citation_test_connection
   mcp_citation_lookup_pmid with PMID 32089132
   ```

## Key Files

- **MCP Config**: `/Users/tusharshah/Library/Application Support/AbacusAI/User/mcp.json`
- **PubMed Client** (already fixed): `/Users/tusharshah/Developer/MCP-Servers/CitationSculptor/modules/pubmed_client.py`
- **MCP Server** (needs checking): `/Users/tusharshah/Developer/MCP-Servers/CitationSculptor/mcp_server/server.py`

## Critical Instructions for Next Agent

1. **Use `mcp_edit_file` for edits** - NOT the native `edit` tool, which truncates files.
2. **Always verify file line count** after edits with `wc -l`.
3. **Test syntax** with `python3 -m py_compile <file>`.
4. **Test functionality** before declaring success.
5. **Do not use heredocs** in terminal - they don't work reliably; write Python scripts to files instead.
