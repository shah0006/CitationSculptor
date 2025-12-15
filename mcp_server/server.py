#!/usr/bin/env python3
"""
Citation Lookup MCP Server (stdio transport)

A stdio-based MCP server for Abacus Desktop integration.
Reuses all existing, tested logic from citation_lookup.py.

Usage:
    python -m mcp_server.server
    
Or configure in Abacus Desktop MCP settings.
"""

import sys
import json
import asyncio
import subprocess
import socket
import os
import time
from pathlib import Path
from typing import Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from citation_lookup import CitationLookup, LookupResult

# Configuration
PUBMED_MCP_PORT = 3017
PUBMED_MCP_SERVER_PATH = Path(__file__).parent.parent.parent / "PubMed Integration MCP" / "pubmed-mcp-server"


def is_port_open(port: int, host: str = "127.0.0.1", timeout: float = 1.0) -> bool:
    """Check if a port is open (server is running)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout)
            return sock.connect_ex((host, port)) == 0
    except:
        return False


def start_pubmed_server() -> Optional[subprocess.Popen]:
    """Start the pubmed-mcp-server in HTTP mode if not already running."""
    if is_port_open(PUBMED_MCP_PORT):
        return None  # Already running

    if not PUBMED_MCP_SERVER_PATH.exists():
        print(f"Warning: pubmed-mcp-server not found at {PUBMED_MCP_SERVER_PATH}", file=sys.stderr)
        return None

    # Start the server in background
    env = os.environ.copy()
    env["MCP_TRANSPORT_TYPE"] = "http"
    env["MCP_LOG_LEVEL"] = "warn"

    try:
        proc = subprocess.Popen(
            ["node", "dist/index.js"],
            cwd=PUBMED_MCP_SERVER_PATH,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        # Wait for server to start
        for _ in range(10):
            time.sleep(0.5)
            if is_port_open(PUBMED_MCP_PORT):
                print(f"Started pubmed-mcp-server on port {PUBMED_MCP_PORT}", file=sys.stderr)
                return proc
        print("Warning: pubmed-mcp-server started but port not responding", file=sys.stderr)
        return proc
    except Exception as e:
        print(f"Warning: Failed to start pubmed-mcp-server: {e}", file=sys.stderr)
        return None


# Initialize server and lookup
server = Server("citation-lookup-mcp")
pubmed_proc = start_pubmed_server()  # Auto-start if needed
lookup = CitationLookup()


def format_result(result: LookupResult) -> str:
    """Format a LookupResult for MCP response."""
    if result.success:
        lines = [
            f"**Inline Mark:** `{result.inline_mark}`",
            "",
            "**Full Citation:**",
            result.full_citation,
        ]
        if result.metadata:
            authors = result.metadata.get('authors', [])
            author_str = ', '.join(authors[:3])
            if len(authors) > 3:
                author_str += '...'
            lines.extend([
                "",
                "**Metadata:**",
                f"- Title: {result.metadata.get('title', 'N/A')}",
                f"- Authors: {author_str}",
                f"- Journal: {result.metadata.get('journal_abbreviation') or result.metadata.get('journal') or result.metadata.get('container_title', 'N/A')}",
                f"- Year: {result.metadata.get('year', 'N/A')}",
                f"- PMID: {result.metadata.get('pmid', 'N/A')}",
                f"- DOI: {result.metadata.get('doi', 'N/A')}",
            ])
        return "\n".join(lines)
    else:
        return f"Error: {result.error}"


@server.list_tools()
async def list_tools():
    """Return list of available tools."""
    return [
        Tool(
            name="citation_lookup_pmid",
            description="Look up a journal article by PubMed ID (PMID) and return a Vancouver-style citation with mnemonic label for Obsidian.",
            inputSchema={
                "type": "object",
                "properties": {
                    "pmid": {"type": "string", "description": "The PubMed ID to look up, e.g., '32089132'"}
                },
                "required": ["pmid"]
            }
        ),
        Tool(
            name="citation_lookup_doi",
            description="Look up an article by DOI and return a Vancouver-style citation.",
            inputSchema={
                "type": "object",
                "properties": {
                    "doi": {"type": "string", "description": "The DOI to look up, e.g., '10.1186/s12968-020-00607-1'"}
                },
                "required": ["doi"]
            }
        ),
        Tool(
            name="citation_lookup_pmcid",
            description="Look up an article by PubMed Central ID (PMC ID).",
            inputSchema={
                "type": "object",
                "properties": {
                    "pmcid": {"type": "string", "description": "The PMC ID, e.g., 'PMC7039045'"}
                },
                "required": ["pmcid"]
            }
        ),
        Tool(
            name="citation_lookup_title",
            description="Search for an article by title and return a Vancouver-style citation.",
            inputSchema={
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "The article title to search for"}
                },
                "required": ["title"]
            }
        ),
        Tool(
            name="citation_lookup_auto",
            description="Auto-detect identifier type (PMID, DOI, PMC ID, or title) and return citation.",
            inputSchema={
                "type": "object",
                "properties": {
                    "identifier": {"type": "string", "description": "Any identifier or article title"}
                },
                "required": ["identifier"]
            }
        ),
        Tool(
            name="citation_get_inline_only",
            description="Get ONLY the inline reference mark, e.g., [^KramerCM-2020-32089132]",
            inputSchema={
                "type": "object",
                "properties": {
                    "identifier": {"type": "string", "description": "Any identifier to look up"}
                },
                "required": ["identifier"]
            }
        ),
        Tool(
            name="citation_get_endnote_only",
            description="Get ONLY the formatted endnote citation (no inline mark).",
            inputSchema={
                "type": "object",
                "properties": {
                    "identifier": {"type": "string", "description": "Any identifier to look up"}
                },
                "required": ["identifier"]
            }
        ),
        Tool(
            name="citation_get_metadata",
            description="Get structured JSON metadata for an article (title, authors, journal, year, DOI, PMID, abstract).",
            inputSchema={
                "type": "object",
                "properties": {
                    "identifier": {"type": "string", "description": "Any identifier to look up"}
                },
                "required": ["identifier"]
            }
        ),
        Tool(
            name="citation_get_abstract",
            description="Get the abstract of an article.",
            inputSchema={
                "type": "object",
                "properties": {
                    "identifier": {"type": "string", "description": "Any identifier to look up"}
                },
                "required": ["identifier"]
            }
        ),
        Tool(
            name="citation_search_pubmed",
            description="Search PubMed and return multiple matching articles (up to 5). Use this when you want to browse results rather than get a single best match.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query (title, keywords, etc.)"},
                    "max_results": {"type": "integer", "description": "Max results to return (1-10, default 5)", "default": 5}
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="citation_batch_lookup",
            description="Look up multiple identifiers at once. Returns all citations together.",
            inputSchema={
                "type": "object",
                "properties": {
                    "identifiers": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Array of identifiers (PMIDs, DOIs, titles, etc.)"
                    }
                },
                "required": ["identifiers"]
            }
        ),
        Tool(
            name="citation_test_connection",
            description="Test connection to the PubMed API. Use this to diagnose issues.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict):
    """Handle tool calls."""
    loop = asyncio.get_event_loop()
    
    try:
        if name == "citation_lookup_pmid":
            result = await loop.run_in_executor(None, lookup.lookup_pmid, arguments["pmid"])
            return [TextContent(type="text", text=format_result(result))]
        
        elif name == "citation_lookup_doi":
            result = await loop.run_in_executor(None, lookup.lookup_doi, arguments["doi"])
            return [TextContent(type="text", text=format_result(result))]
        
        elif name == "citation_lookup_pmcid":
            result = await loop.run_in_executor(None, lookup.lookup_pmcid, arguments["pmcid"])
            return [TextContent(type="text", text=format_result(result))]
        
        elif name == "citation_lookup_title":
            result = await loop.run_in_executor(None, lookup.lookup_title, arguments["title"])
            return [TextContent(type="text", text=format_result(result))]
        
        elif name == "citation_lookup_auto":
            result = await loop.run_in_executor(None, lookup.lookup_auto, arguments["identifier"])
            return [TextContent(type="text", text=format_result(result))]
        
        elif name == "citation_get_inline_only":
            result = await loop.run_in_executor(None, lookup.lookup_auto, arguments["identifier"])
            if result.success:
                return [TextContent(type="text", text=result.inline_mark)]
            return [TextContent(type="text", text=f"Error: {result.error}")]

        elif name == "citation_get_endnote_only":
            result = await loop.run_in_executor(None, lookup.lookup_auto, arguments["identifier"])
            if result.success:
                return [TextContent(type="text", text=result.endnote_citation)]
            return [TextContent(type="text", text=f"Error: {result.error}")]

        elif name == "citation_get_metadata":
            result = await loop.run_in_executor(None, lookup.lookup_auto, arguments["identifier"])
            if result.success and result.metadata:
                return [TextContent(type="text", text=json.dumps(result.metadata, indent=2))]
            elif result.success:
                return [TextContent(type="text", text="No metadata available")]
            return [TextContent(type="text", text=f"Error: {result.error}")]

        elif name == "citation_get_abstract":
            result = await loop.run_in_executor(None, lookup.lookup_auto, arguments["identifier"])
            if result.success and result.metadata:
                abstract = result.metadata.get('abstract', '')
                if abstract:
                    return [TextContent(type="text", text=abstract)]
                return [TextContent(type="text", text="No abstract available for this article.")]
            return [TextContent(type="text", text=f"Error: {result.error}")]

        elif name == "citation_search_pubmed":
            max_results = min(arguments.get("max_results", 5), 10)
            articles = await loop.run_in_executor(
                None,
                lookup.pubmed_client.search_by_title,
                arguments["query"],
                max_results
            )
            if not articles:
                return [TextContent(type="text", text="No articles found.")]

            lines = [f"Found {len(articles)} result(s):\n"]
            for i, article in enumerate(articles, 1):
                lines.append(f"**{i}. {article.title}**")
                authors = ', '.join(article.authors[:3])
                if len(article.authors) > 3:
                    authors += ' et al.'
                lines.append(f"   Authors: {authors}")
                lines.append(f"   Journal: {article.journal_abbreviation or article.journal} ({article.year})")
                lines.append(f"   PMID: {article.pmid}")
                if article.doi:
                    lines.append(f"   DOI: {article.doi}")
                lines.append("")
            return [TextContent(type="text", text="\n".join(lines))]

        elif name == "citation_batch_lookup":
            identifiers = arguments["identifiers"]
            results = await loop.run_in_executor(None, lookup.batch_lookup, identifiers)

            output_lines = []
            for r in results:
                if r.success:
                    output_lines.append(f"**{r.identifier}**")
                    output_lines.append(f"Inline: `{r.inline_mark}`")
                    output_lines.append(r.full_citation)
                    output_lines.append("")
                else:
                    output_lines.append(f"**{r.identifier}**: Error - {r.error}")
                    output_lines.append("")
            return [TextContent(type="text", text="\n".join(output_lines))]

        elif name == "citation_test_connection":
            port_open = is_port_open(PUBMED_MCP_PORT)
            api_ok = await loop.run_in_executor(None, lookup.test_connection) if port_open else False

            lines = [
                f"**Port {PUBMED_MCP_PORT}:** {'Open' if port_open else 'CLOSED'}",
                f"**PubMed API:** {'OK' if api_ok else 'FAILED'}",
                f"**Server path:** {PUBMED_MCP_SERVER_PATH}",
                f"**Server exists:** {PUBMED_MCP_SERVER_PATH.exists()}",
            ]
            if pubmed_proc:
                lines.append(f"**Auto-started:** Yes (PID {pubmed_proc.pid})")

            if api_ok:
                lines.insert(0, "**Status: OK**\n")
            else:
                lines.insert(0, "**Status: FAILED**\n")
                if not port_open:
                    lines.append("\n*Try restarting CitationSculptor MCP or manually start pubmed-mcp-server*")

            return [TextContent(type="text", text="\n".join(lines))]

        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]

    except Exception as e:
        return [TextContent(type="text", text=f"Error: {str(e)}")]


async def main():
    """Run the MCP server with stdio transport."""
    try:
        async with stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream, server.create_initialization_options())
    finally:
        # Cleanup: terminate pubmed-mcp-server if we started it
        if pubmed_proc and pubmed_proc.poll() is None:
            pubmed_proc.terminate()
            pubmed_proc.wait(timeout=5)


if __name__ == "__main__":
    asyncio.run(main())