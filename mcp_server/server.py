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
from modules.document_intelligence import (
    DocumentIntelligence,
    verify_document_links,
    suggest_document_citations,
    check_citation_compliance,
)




# Initialize server and components
server = Server("citation-lookup-mcp")
lookup = CitationLookup()
type_detector = CitationTypeDetector()
doc_intelligence = DocumentIntelligence(pubmed_client=lookup.pubmed_client, use_llm=True)


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
        # === Document Intelligence Tools (v2.3.0) ===
        Tool(
            name="citation_verify_links",
            description="Verify all URLs in a document to check for broken links, redirects, and archived versions. Returns status for each URL found.",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to the markdown file to analyze"
                    },
                    "content": {
                        "type": "string",
                        "description": "Markdown content to analyze (alternative to file_path)"
                    },
                    "urls": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of specific URLs to verify (alternative to file/content)"
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="citation_suggest_citations",
            description="Analyze document content to identify passages that may need citations (statistics, claims, research findings without sources). Optionally searches PubMed for suggested citations.",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to the markdown file to analyze"
                    },
                    "content": {
                        "type": "string",
                        "description": "Markdown content to analyze (alternative to file_path)"
                    },
                    "search_pubmed": {
                        "type": "boolean",
                        "description": "Search PubMed for suggested citations (slower but more helpful)",
                        "default": False
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="citation_check_compliance",
            description="Check document for citation compliance issues: uncited quotes, claims presented as fact without evidence, academic phrases that need sources. Returns a compliance score and list of issues.",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to the markdown file to check"
                    },
                    "content": {
                        "type": "string",
                        "description": "Markdown content to check (alternative to file_path)"
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="citation_analyze_document",
            description="Comprehensive document analysis: verify all links, suggest missing citations, and check citation compliance. Returns overall document health score.",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to the markdown file to analyze"
                    },
                    "content": {
                        "type": "string",
                        "description": "Markdown content to analyze (alternative to file_path)"
                    },
                    "verify_links": {
                        "type": "boolean",
                        "description": "Verify all URLs (default: true)",
                        "default": True
                    },
                    "suggest_citations": {
                        "type": "boolean",
                        "description": "Suggest missing citations (default: true)",
                        "default": True
                    },
                    "check_compliance": {
                        "type": "boolean",
                        "description": "Check citation compliance (default: true)",
                        "default": True
                    },
                    "search_pubmed": {
                        "type": "boolean",
                        "description": "Search PubMed for citation suggestions (slower)",
                        "default": False
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="citation_extract_metadata_llm",
            description="Use LLM to extract citation metadata from a webpage that doesn't have standard metadata. Requires Ollama to be running locally.",
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "URL of the webpage"
                    },
                    "html_content": {
                        "type": "string",
                        "description": "HTML content of the webpage"
                    }
                },
                "required": ["url", "html_content"]
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

        # === Document Intelligence Tools ===
        elif name == "citation_verify_links":
            result = await loop.run_in_executor(
                None,
                handle_verify_links,
                arguments.get('file_path'),
                arguments.get('content'),
                arguments.get('urls')
            )
            return [TextContent(type="text", text=result)]
        
        elif name == "citation_suggest_citations":
            result = await loop.run_in_executor(
                None,
                handle_suggest_citations,
                arguments.get('file_path'),
                arguments.get('content'),
                arguments.get('search_pubmed', False)
            )
            return [TextContent(type="text", text=result)]
        
        elif name == "citation_check_compliance":
            result = await loop.run_in_executor(
                None,
                handle_check_compliance,
                arguments.get('file_path'),
                arguments.get('content')
            )
            return [TextContent(type="text", text=result)]
        
        elif name == "citation_analyze_document":
            result = await loop.run_in_executor(
                None,
                handle_analyze_document,
                arguments.get('file_path'),
                arguments.get('content'),
                arguments.get('verify_links', True),
                arguments.get('suggest_citations', True),
                arguments.get('check_compliance', True),
                arguments.get('search_pubmed', False)
            )
            return [TextContent(type="text", text=result)]
        
        elif name == "citation_extract_metadata_llm":
            result = await loop.run_in_executor(
                None,
                handle_extract_metadata_llm,
                arguments.get('url'),
                arguments.get('html_content')
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


def get_content(file_path: Optional[str], content: Optional[str]) -> tuple:
    """Helper to get content from file or direct input."""
    if file_path:
        file_path = os.path.expanduser(file_path)
        if not os.path.exists(file_path):
            return None, f"Error: File not found: {file_path}"
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            return content, None
        except Exception as e:
            return None, f"Error reading file: {e}"
    elif content:
        return content, None
    else:
        return None, "Error: No content provided. Specify either file_path or content."


def handle_verify_links(file_path: Optional[str], content: Optional[str], urls: Optional[list]) -> str:
    """Handle link verification."""
    if urls:
        # Verify provided URLs directly
        results = doc_intelligence.verify_links_batch(urls)
        output_lines = ["# Link Verification Results", "", f"**URLs checked:** {len(results)}", ""]
        
        ok_count = sum(1 for r in results if r.get('status') == 'ok')
        broken_count = sum(1 for r in results if r.get('status') in ('broken', 'error'))
        
        output_lines.append(f"✅ OK: {ok_count}")
        output_lines.append(f"❌ Broken/Error: {broken_count}")
        output_lines.append("")
        
        for r in results:
            status_emoji = {
                'ok': '✅', 'redirect': '↪️', 'broken': '❌', 
                'error': '❌', 'timeout': '⏱️', 'paywall': '🔒', 
                'archived': '📦', 'skipped': '⏭️'
            }.get(r.get('status'), '❓')
            
            output_lines.append(f"{status_emoji} **{r.get('status', 'unknown').upper()}**: {r.get('url', 'N/A')}")
            if r.get('archived_url'):
                output_lines.append(f"   📦 Archive: {r.get('archived_url')}")
            if r.get('error_message'):
                output_lines.append(f"   ⚠️ {r.get('error_message')}")
            output_lines.append("")
        
        return "\n".join(output_lines)
    
    # Get content from file or direct input
    text_content, error = get_content(file_path, content)
    if error:
        return error
    
    result = verify_document_links(text_content)
    
    output_lines = ["# Link Verification Results", ""]
    output_lines.append(f"**Total URLs found:** {result.get('total_urls', 0)}")
    
    status = result.get('status_summary', {})
    output_lines.append("")
    output_lines.append("## Summary")
    for status_type, count in status.items():
        emoji = {'ok': '✅', 'redirect': '↪️', 'broken': '❌', 'error': '❌', 
                 'timeout': '⏱️', 'paywall': '🔒', 'archived': '📦'}.get(status_type, '❓')
        output_lines.append(f"- {emoji} {status_type}: {count}")
    
    broken = result.get('broken_links', [])
    if broken:
        output_lines.extend(["", "## ❌ Broken Links"])
        for link in broken:
            output_lines.append(f"- **{link.get('url', 'N/A')}**")
            if link.get('error_message'):
                output_lines.append(f"  - Error: {link.get('error_message')}")
            if link.get('archived_url'):
                output_lines.append(f"  - 📦 Archive available: {link.get('archived_url')}")
    
    redirects = result.get('redirected_links', [])
    if redirects:
        output_lines.extend(["", "## ↪️ Redirected Links"])
        for link in redirects:
            output_lines.append(f"- {link.get('url', 'N/A')}")
            output_lines.append(f"  → {link.get('final_url', 'N/A')}")
    
    return "\n".join(output_lines)


def handle_suggest_citations(file_path: Optional[str], content: Optional[str], search_pubmed: bool = False) -> str:
    """Handle citation suggestions."""
    text_content, error = get_content(file_path, content)
    if error:
        return error
    
    from modules.document_intelligence import CitationSuggestor
    suggestor = CitationSuggestor(pubmed_client=lookup.pubmed_client if search_pubmed else None)
    suggestions = suggestor.analyze_document(text_content, search_suggestions=search_pubmed)
    
    output_lines = ["# Citation Suggestions", ""]
    output_lines.append(f"**Potential citations needed:** {len(suggestions)}")
    output_lines.append("")
    
    if not suggestions:
        output_lines.append("✅ No obvious missing citations detected.")
        return "\n".join(output_lines)
    
    # Group by category
    categories = {}
    for s in suggestions:
        cat = s.category
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(s)
    
    for category, items in categories.items():
        emoji = {'statistic': '📊', 'claim': '💬', 'definition': '📖', 'finding': '🔬'}.get(category, '📝')
        output_lines.append(f"## {emoji} {category.title()}s ({len(items)})")
        output_lines.append("")
        
        for item in items:
            output_lines.append(f"**Line {item.line_number}** (confidence: {item.confidence:.0%})")
            output_lines.append(f"> {item.text_excerpt}")
            output_lines.append(f"*{item.reason}*")
            
            if item.suggested_search_terms:
                output_lines.append(f"Search: `{' '.join(item.suggested_search_terms)}`")
            
            if item.pubmed_results:
                output_lines.append("**Suggested citations:**")
                for r in item.pubmed_results[:3]:
                    authors = ', '.join(r.get('authors', [])[:2])
                    if len(r.get('authors', [])) > 2:
                        authors += ' et al.'
                    output_lines.append(f"  - {r.get('title', 'N/A')} ({authors}, {r.get('year', 'N/A')}) [PMID: {r.get('pmid', 'N/A')}]")
            
            output_lines.append("")
    
    return "\n".join(output_lines)


def handle_check_compliance(file_path: Optional[str], content: Optional[str]) -> str:
    """Handle citation compliance check."""
    text_content, error = get_content(file_path, content)
    if error:
        return error
    
    result = check_citation_compliance(text_content)
    
    output_lines = ["# Citation Compliance Check", ""]
    
    score = result.get('compliance_score', 100)
    score_emoji = "🟢" if score >= 80 else "🟡" if score >= 60 else "🔴"
    output_lines.append(f"## {score_emoji} Compliance Score: {score}/100")
    output_lines.append("")
    
    output_lines.append("### Summary")
    output_lines.append(f"- Total issues: {result.get('total_issues', 0)}")
    output_lines.append(f"- 🔴 High severity: {result.get('high_severity_count', 0)}")
    output_lines.append(f"- 🟡 Medium severity: {result.get('medium_severity_count', 0)}")
    output_lines.append(f"- 🟢 Low severity: {result.get('low_severity_count', 0)}")
    output_lines.append("")
    
    recommendations = result.get('recommendations', [])
    if recommendations:
        output_lines.append("### Recommendations")
        for rec in recommendations:
            output_lines.append(f"- {rec}")
        output_lines.append("")
    
    issues = result.get('issues', [])
    if issues:
        output_lines.append("### Issues Found")
        output_lines.append("")
        
        for issue in issues:
            severity_emoji = {'high': '🔴', 'medium': '🟡', 'low': '🟢'}.get(issue.get('severity'), '⚪')
            output_lines.append(f"**Line {issue.get('line_number', 'N/A')}** {severity_emoji}")
            output_lines.append(f"> {issue.get('text', 'N/A')[:100]}...")
            output_lines.append(f"*{issue.get('explanation', 'N/A')}*")
            if issue.get('suggested_action'):
                output_lines.append(f"💡 {issue.get('suggested_action')}")
            output_lines.append("")
    
    return "\n".join(output_lines)


def handle_analyze_document(file_path: Optional[str], content: Optional[str], 
                           verify_links: bool = True, suggest_citations: bool = True,
                           check_compliance: bool = True, search_pubmed: bool = False) -> str:
    """Handle comprehensive document analysis."""
    text_content, error = get_content(file_path, content)
    if error:
        return error
    
    result = doc_intelligence.analyze_document(
        text_content,
        verify_links=verify_links,
        suggest_citations=suggest_citations,
        check_plagiarism=check_compliance,
        search_suggestions=search_pubmed
    )
    
    output_lines = ["# 📊 Document Analysis Report", ""]
    
    # Overall health score
    health = result.get('overall_health_score', 100)
    health_emoji = "🟢" if health >= 80 else "🟡" if health >= 60 else "🔴"
    output_lines.append(f"## {health_emoji} Overall Health Score: {health}/100")
    output_lines.append("")
    output_lines.append(f"*Analysis timestamp: {result.get('timestamp', 'N/A')}*")
    output_lines.append(f"*Document: {result.get('line_count', 0)} lines*")
    output_lines.append("")
    
    # Link verification
    if 'link_verification' in result:
        lv = result['link_verification']
        broken = len(lv.get('broken_links', []))
        total = lv.get('total_urls', 0)
        ok = total - broken
        output_lines.append(f"### 🔗 Link Verification")
        output_lines.append(f"- {ok}/{total} links OK")
        if broken > 0:
            output_lines.append(f"- ❌ {broken} broken links found")
        output_lines.append("")
    
    # Citation suggestions
    if 'citation_suggestions' in result:
        cs = result['citation_suggestions']
        count = cs.get('count', 0)
        output_lines.append(f"### 📝 Citation Suggestions")
        output_lines.append(f"- {count} passages may need citations")
        output_lines.append("")
    
    # Compliance check
    if 'citation_compliance' in result:
        cc = result['citation_compliance']
        score = cc.get('compliance_score', 100)
        output_lines.append(f"### ✅ Citation Compliance")
        output_lines.append(f"- Compliance score: {score}/100")
        output_lines.append(f"- Issues: {cc.get('total_issues', 0)}")
        output_lines.append("")
    
    output_lines.append("---")
    output_lines.append("*Use individual tools for detailed results:*")
    output_lines.append("- `citation_verify_links` for link details")
    output_lines.append("- `citation_suggest_citations` for suggested citations")
    output_lines.append("- `citation_check_compliance` for compliance issues")
    
    return "\n".join(output_lines)


def handle_extract_metadata_llm(url: str, html_content: str) -> str:
    """Handle LLM metadata extraction."""
    if not url or not html_content:
        return "Error: Both url and html_content are required."
    
    result = doc_intelligence.extract_metadata_llm(url, html_content)
    
    if result:
        output_lines = ["# LLM Metadata Extraction", "", "**Success!**", ""]
        output_lines.append(f"**Title:** {result.get('title', 'N/A')}")
        
        authors = result.get('authors', [])
        if authors:
            output_lines.append(f"**Authors:** {', '.join(authors)}")
        
        if result.get('date'):
            output_lines.append(f"**Date:** {result.get('date')}")
        elif result.get('year'):
            output_lines.append(f"**Year:** {result.get('year')}")
        
        if result.get('organization'):
            output_lines.append(f"**Organization:** {result.get('organization')}")
        
        if result.get('publication_name'):
            output_lines.append(f"**Publication:** {result.get('publication_name')}")
        
        output_lines.append("")
        output_lines.append("**Raw metadata:**")
        output_lines.append(f"```json\n{json.dumps(result, indent=2)}\n```")
        
        return "\n".join(output_lines)
    else:
        return "**Error:** LLM extraction failed. Make sure Ollama is running locally with llama3:8b model."


async def main():
    """Run the MCP server with stdio transport."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())