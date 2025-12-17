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
import os
import json
import asyncio
from pathlib import Path
from typing import Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from citation_lookup import CitationLookup, LookupResult
from modules.reference_parser import ReferenceParser
from modules.type_detector import CitationTypeDetector
from modules.inline_replacer import InlineReplacer




# Initialize server and lookup
server = Server("citation-lookup-mcp")
lookup = CitationLookup()
type_detector = CitationTypeDetector()


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
        Tool(
            name="citation_process_document",
            description="Process a markdown document, looking up all citations and replacing inline references with proper formatted citations. Accepts either a file path or document content directly. SAFETY: Creates an automatic backup when file_path is provided (backup_path included in response).",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to the markdown file to process (absolute or relative path)"
                    },
                    "content": {
                        "type": "string",
                        "description": "Markdown content to process (alternative to file_path)"
                    },
                    "style": {
                        "type": "string",
                        "description": "Citation style: vancouver (default), apa, mla, chicago, harvard, ieee",
                        "default": "vancouver"
                    },
                    "create_backup": {
                        "type": "boolean",
                        "description": "Create a timestamped backup before processing (default: true when file_path is provided)",
                        "default": True
                    }
                },
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
            if arguments.get("query") == "CRASH_NOW":
                import sys
                sys.exit(1)
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
            import modules.pubmed_client
            import inspect
            api_ok = await loop.run_in_executor(None, lookup.test_connection)
            
            src = inspect.getsource(modules.pubmed_client.PubMedClient.convert_ids)
            has_fix = "id_list = [str(x) for x in ids]" in src
            
            lines = [
                f"**PubMed API Connection:** {'OK' if api_ok else 'FAILED'}",
                "**Transport:** Direct E-utilities (Python)",
                "",
                "**Debug Info:**",
                f"Client File: `{modules.pubmed_client.__file__}`",
                f"Has _send_request: `{hasattr(modules.pubmed_client.PubMedClient, '_send_request')}`",
                f"Has Fix: `{has_fix}`",
                f"Server Version: v3 (Test 5)",
            ]

            if api_ok:
                lines.insert(0, "**Status: OK**\n")
            else:
                lines.insert(0, "**Status: FAILED**\n")
                lines.append("\n*Check your internet connection or NCBI API availability*")

            return [TextContent(type="text", text="\n".join(lines))]

        elif name == "citation_process_document":
            result = await loop.run_in_executor(
                None,
                process_document_content,
                arguments.get('file_path'),
                arguments.get('content'),
                arguments.get('style', 'vancouver'),
                arguments.get('create_backup', True)
            )
            return [TextContent(type="text", text=result)]

        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]

    except Exception as e:
        return [TextContent(type="text", text=f"Error: {str(e)}")]


def create_backup(file_path: str, content: str) -> str:
    """
    Create a timestamped backup of a file before processing.
    
    Args:
        file_path: Original file path
        content: Original file content
        
    Returns:
        Path to the backup file
    """
    from datetime import datetime
    from pathlib import Path
    
    path = Path(file_path)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"{path.stem}_backup_{timestamp}{path.suffix}"
    backup_path = path.parent / backup_name
    
    with open(backup_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    return str(backup_path)


def process_document_content(file_path: Optional[str], content: Optional[str], style: str = 'vancouver', create_backup_file: bool = True) -> str:
    """
    Process a markdown document, looking up all citations and replacing inline references.
    
    Args:
        file_path: Path to the markdown file to process
        content: Markdown content to process (alternative to file_path)
        style: Citation style (vancouver, apa, mla, chicago, harvard, ieee)
        create_backup_file: Create a timestamped backup before processing (default: True when file_path provided)
    
    Returns:
        Formatted result string with processed content and statistics
    """
    backup_path = None
    
    # Get content from file or direct input
    if file_path:
        file_path = os.path.expanduser(file_path)
        if not os.path.exists(file_path):
            return f"Error: File not found: {file_path}"
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Create backup before processing (safety feature)
            if create_backup_file:
                backup_path = create_backup(file_path, content)
                
        except Exception as e:
            return f"Error reading file: {e}"
    
    if not content:
        return "Error: No content provided. Specify either file_path or content."
    
    # Set citation style
    if style != lookup.style:
        lookup.set_style(style)
    
    # Parse references
    parser = ReferenceParser(content)
    parser.find_reference_section()
    parser.parse_references()
    
    if not parser.references:
        return "**No references found in document.**\n\nThe document does not contain a recognizable reference section."
    
    # Get body content
    body = parser.get_body_content()
    inline_style = parser._detect_inline_style(body)
    
    # Track results
    processed_citations = []
    number_to_label_map = {}
    failed_refs = []
    
    # Process each reference
    for ref in parser.references:
        # Try to extract identifiers from URL
        pmid = type_detector.extract_pmid(ref.url) if ref.url else None
        pmcid = type_detector.extract_pmcid(ref.url) if ref.url else None
        doi = type_detector.extract_doi(ref.url) if ref.url else None
        
        result = None
        
        # Attempt lookup by identifier priority
        if pmid:
            result = lookup.lookup_pmid(pmid)
        elif pmcid:
            result = lookup.lookup_pmcid(pmcid)
        elif doi:
            result = lookup.lookup_doi(doi)
        elif ref.title:
            result = lookup.lookup_auto(ref.title)
        
        if result and result.success:
            label = result.inline_mark.strip('[]^') if result.inline_mark else ''
            number_to_label_map[ref.original_number] = label
            processed_citations.append({
                'original_number': ref.original_number,
                'inline_mark': result.inline_mark,
                'full_citation': result.full_citation,
            })
        else:
            failed_refs.append({
                'original_number': ref.original_number,
                'title': ref.title[:80] if ref.title else 'Unknown',
                'error': result.error if result else 'Lookup returned None',
            })
    
    # Update inline references in body
    if number_to_label_map:
        replacer = InlineReplacer(number_to_label_map, style=inline_style)
        result = replacer.replace_all(body)
        updated_body = result.modified_text
        replacements_made = result.replacements_made
    else:
        updated_body = body
        replacements_made = 0
    
    # Generate new reference section
    reference_section = "\n## References\n\n"
    sorted_citations = sorted(processed_citations, key=lambda c: c.get('inline_mark', '').lower())
    for citation in sorted_citations:
        reference_section += f"{citation['full_citation']}\n\n"
    
    # Combine updated body with new references
    processed_content = updated_body + "\n\n" + reference_section.strip()
    
    # Build output
    output_lines = [
        "# Document Processing Complete",
        "",
    ]
    
    # Add backup information (safety feature)
    if backup_path:
        output_lines.extend([
            "## 💾 Backup Created",
            f"- **Backup saved to:** `{backup_path}`",
            "- *If anything goes wrong, your original document is safe.*",
            "",
        ])
    
    output_lines.extend([
        "## Statistics",
        f"- **Total references found:** {len(parser.references)}",
        f"- **Successfully processed:** {len(processed_citations)}",
        f"- **Failed:** {len(failed_refs)}",
        f"- **Inline replacements:** {replacements_made}",
        "",
    ])
    
    if failed_refs:
        output_lines.extend([
            "## ⚠️ Failed References",
            "",
        ])
        for ref in failed_refs:
            output_lines.append(f"- **#{ref['original_number']}:** {ref['title']} - {ref['error']}")
        output_lines.append("")
    
    output_lines.extend([
        "---",
        "",
        "## Processed Document",
        "",
        "```markdown",
        processed_content,
        "```",
    ])
    
    return "\n".join(output_lines)


async def main():
    """Run the MCP server with stdio transport."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())