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
import asyncio
from pathlib import Path
from typing import Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from citation_lookup import CitationLookup, LookupResult


# Initialize server and lookup
server = Server("citation-lookup-mcp")
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
        
        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]
    
    except Exception as e:
        return [TextContent(type="text", text=f"Error: {str(e)}")]


async def main():
    """Run the MCP server with stdio transport."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
