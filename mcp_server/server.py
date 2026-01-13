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
from modules.citation_normalizer import (
    CitationNormalizer,
    normalize_citation_format,
    preview_citation_normalization,
)
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
            description="Process a markdown document, looking up all citations and replacing inline references with proper formatted citations. Accepts either a file path or document content directly. SAFETY: Creates an automatic backup when file_path is provided, then saves processed content back to file.",
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
                    },
                    "save_to_file": {
                        "type": "boolean",
                        "description": "Save processed content back to original file (default: true when file_path is provided). Backup is always created first.",
                        "default": True
                    },
                    "skip_verification": {
                        "type": "boolean",
                        "description": "Skip duplicate detection and context verification for faster processing (default: false)",
                        "default": False
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
        Tool(
            name="citation_normalize_format",
            description="Normalize legacy LLM-generated citation formats to Obsidian footnote style. Converts [1], [1, 2], [6-10] to [^1], [^1] [^2], [^6] [^7]... Automatically handles ranges, comma-separated lists, and mixed formats. Protects markdown links, wikilinks, images, code blocks, and math from false positive conversion.",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to the markdown file to normalize"
                    },
                    "content": {
                        "type": "string",
                        "description": "Markdown content to normalize (alternative to file_path)"
                    },
                    "dry_run": {
                        "type": "boolean",
                        "description": "If true, preview changes without modifying content (default: false)",
                        "default": False
                    }
                },
                "required": []
            }
        ),
        # === Additional Lookup Tools ===
        Tool(
            name="citation_lookup_arxiv",
            description="Look up an arXiv preprint by ID and return a formatted citation.",
            inputSchema={
                "type": "object",
                "properties": {
                    "arxiv_id": {"type": "string", "description": "arXiv ID (e.g., '2301.07041' or 'cs.AI/0304001')"}
                },
                "required": ["arxiv_id"]
            }
        ),
        Tool(
            name="citation_lookup_isbn",
            description="Look up a book by ISBN and return a formatted citation.",
            inputSchema={
                "type": "object",
                "properties": {
                    "isbn": {"type": "string", "description": "ISBN-10 or ISBN-13 (e.g., '978-0-13-468599-1')"}
                },
                "required": ["isbn"]
            }
        ),
        # === Search Tools ===
        Tool(
            name="citation_search_openalex",
            description="Search OpenAlex for academic works. Returns articles, books, datasets, etc.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "max_results": {"type": "integer", "description": "Max results (default 5, max 20)", "default": 5}
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="citation_search_semantic_scholar",
            description="Search Semantic Scholar for academic papers. Good for computer science and AI papers.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "max_results": {"type": "integer", "description": "Max results (default 5, max 20)", "default": 5}
                },
                "required": ["query"]
            }
        ),
        # === Import/Export Tools ===
        Tool(
            name="citation_export_bibtex",
            description="Export citations to BibTeX format.",
            inputSchema={
                "type": "object",
                "properties": {
                    "identifiers": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Array of identifiers (PMIDs, DOIs, etc.) to export"
                    }
                },
                "required": ["identifiers"]
            }
        ),
        Tool(
            name="citation_export_ris",
            description="Export citations to RIS format (compatible with EndNote, Zotero, Mendeley).",
            inputSchema={
                "type": "object",
                "properties": {
                    "identifiers": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Array of identifiers (PMIDs, DOIs, etc.) to export"
                    }
                },
                "required": ["identifiers"]
            }
        ),
        Tool(
            name="citation_import_bibtex",
            description="Import and parse a BibTeX file or string. Returns structured citation data.",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Path to BibTeX file"},
                    "content": {"type": "string", "description": "BibTeX content string (alternative to file_path)"}
                },
                "required": []
            }
        ),
        Tool(
            name="citation_import_ris",
            description="Import and parse a RIS file or string. Returns structured citation data.",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Path to RIS file"},
                    "content": {"type": "string", "description": "RIS content string (alternative to file_path)"}
                },
                "required": []
            }
        ),
        # === PDF and Bibliography Tools ===
        Tool(
            name="citation_extract_pdf",
            description="Extract citation metadata (DOI, arXiv ID, PMID, title, authors) from a PDF file.",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Path to PDF file"}
                },
                "required": ["file_path"]
            }
        ),
        Tool(
            name="citation_check_article_duplicates",
            description="Check for duplicate articles in a list of citations using DOI/PMID matching and fuzzy title matching.",
            inputSchema={
                "type": "object",
                "properties": {
                    "citations": {
                        "type": "array",
                        "items": {"type": "object"},
                        "description": "Array of citation objects with id, title, authors, year, doi, pmid fields"
                    }
                },
                "required": ["citations"]
            }
        ),
        Tool(
            name="citation_generate_bibliography",
            description="Generate a formatted bibliography from a list of identifiers.",
            inputSchema={
                "type": "object",
                "properties": {
                    "identifiers": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Array of identifiers (PMIDs, DOIs, titles, etc.)"
                    },
                    "style": {
                        "type": "string",
                        "description": "Citation style (vancouver, apa, mla, chicago, harvard, ieee)",
                        "default": "vancouver"
                    },
                    "sort_order": {
                        "type": "string",
                        "description": "Sort order: alphabetical, year, appearance",
                        "default": "alphabetical"
                    }
                },
                "required": ["identifiers"]
            }
        ),
        # === Citation Integrity Tools (v2.4.0) ===
        Tool(
            name="citation_find_duplicates",
            description="Find and optionally fix citation integrity issues: consecutive same citations [^A][^A], orphaned definitions (defined but unused), missing definitions (used but undefined). Works on any document type.",
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
                    "auto_fix": {
                        "type": "boolean",
                        "description": "Automatically fix consecutive duplicate citations",
                        "default": False
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="citation_verify_context",
            description="Verify each citation's keywords match its surrounding text context using dynamic keyword extraction. Works on ANY document type (medical, legal, engineering, humanities, etc.). Flags citations with low keyword overlap. Optionally uses LLM for deep verification.",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to the markdown file to verify"
                    },
                    "content": {
                        "type": "string",
                        "description": "Markdown content to verify (alternative to file_path)"
                    },
                    "threshold": {
                        "type": "number",
                        "description": "Minimum overlap score (0-1). Below this = potential mismatch. Default: 0.15",
                        "default": 0.15
                    },
                    "deep_verify": {
                        "type": "boolean",
                        "description": "Use LLM (local Ollama or Groq) for deep verification of flagged items",
                        "default": False
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="citation_audit_document",
            description="Comprehensive citation audit for ANY document type: check for duplicates, orphans, missing definitions, and context mismatches. Returns health score and actionable fixes.",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to the markdown file to audit"
                    },
                    "content": {
                        "type": "string",
                        "description": "Markdown content to audit (alternative to file_path)"
                    },
                    "auto_fix_duplicates": {
                        "type": "boolean",
                        "description": "Automatically fix consecutive duplicate citations",
                        "default": False
                    },
                    "deep_verify": {
                        "type": "boolean",
                        "description": "Use LLM for deep context verification",
                        "default": False
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
                arguments.get('create_backup', True),
                arguments.get('save_to_file', True),
                arguments.get('skip_verification', False)
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
        
        elif name == "citation_normalize_format":
            result = await loop.run_in_executor(
                None,
                handle_normalize_format,
                arguments.get('file_path'),
                arguments.get('content'),
                arguments.get('dry_run', False)
            )
            return [TextContent(type="text", text=result)]

        # === Additional Lookup Tools ===
        elif name == "citation_lookup_arxiv":
            result = await loop.run_in_executor(None, lookup.lookup_arxiv, arguments["arxiv_id"])
            return [TextContent(type="text", text=format_result(result))]
        
        elif name == "citation_lookup_isbn":
            result = await loop.run_in_executor(None, lookup.lookup_isbn, arguments["isbn"])
            return [TextContent(type="text", text=format_result(result))]
        
        # === Search Tools ===
        elif name == "citation_search_openalex":
            result = await loop.run_in_executor(
                None,
                handle_search_openalex,
                arguments["query"],
                arguments.get("max_results", 5)
            )
            return [TextContent(type="text", text=result)]
        
        elif name == "citation_search_semantic_scholar":
            result = await loop.run_in_executor(
                None,
                handle_search_semantic_scholar,
                arguments["query"],
                arguments.get("max_results", 5)
            )
            return [TextContent(type="text", text=result)]
        
        # === Import/Export Tools ===
        elif name == "citation_export_bibtex":
            result = await loop.run_in_executor(
                None,
                handle_export_bibtex,
                arguments["identifiers"]
            )
            return [TextContent(type="text", text=result)]
        
        elif name == "citation_export_ris":
            result = await loop.run_in_executor(
                None,
                handle_export_ris,
                arguments["identifiers"]
            )
            return [TextContent(type="text", text=result)]
        
        elif name == "citation_import_bibtex":
            result = await loop.run_in_executor(
                None,
                handle_import_bibtex,
                arguments.get("file_path"),
                arguments.get("content")
            )
            return [TextContent(type="text", text=result)]
        
        elif name == "citation_import_ris":
            result = await loop.run_in_executor(
                None,
                handle_import_ris,
                arguments.get("file_path"),
                arguments.get("content")
            )
            return [TextContent(type="text", text=result)]
        
        # === PDF and Bibliography Tools ===
        elif name == "citation_extract_pdf":
            result = await loop.run_in_executor(
                None,
                handle_extract_pdf,
                arguments["file_path"]
            )
            return [TextContent(type="text", text=result)]
        
        elif name == "citation_check_article_duplicates":
            result = await loop.run_in_executor(
                None,
                handle_check_article_duplicates,
                arguments["citations"]
            )
            return [TextContent(type="text", text=result)]
        
        elif name == "citation_generate_bibliography":
            result = await loop.run_in_executor(
                None,
                handle_generate_bibliography,
                arguments["identifiers"],
                arguments.get("style", "vancouver"),
                arguments.get("sort_order", "alphabetical")
            )
            return [TextContent(type="text", text=result)]

        # === Citation Integrity Tools (v2.4.0) ===
        elif name == "citation_find_duplicates":
            result = await loop.run_in_executor(
                None,
                handle_find_duplicates,
                arguments.get('file_path'),
                arguments.get('content'),
                arguments.get('auto_fix', False)
            )
            return [TextContent(type="text", text=result)]
        
        elif name == "citation_verify_context":
            result = await loop.run_in_executor(
                None,
                handle_verify_context,
                arguments.get('file_path'),
                arguments.get('content'),
                arguments.get('threshold', 0.15),
                arguments.get('deep_verify', False)
            )
            return [TextContent(type="text", text=result)]
        
        elif name == "citation_audit_document":
            result = await loop.run_in_executor(
                None,
                handle_audit_document,
                arguments.get('file_path'),
                arguments.get('content'),
                arguments.get('auto_fix_duplicates', False),
                arguments.get('deep_verify', False)
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


def process_document_content(file_path: Optional[str], content: Optional[str], style: str = 'vancouver', create_backup_file: bool = True, save_to_file: bool = True, skip_verification: bool = False) -> str:
    """
    Process a markdown document, looking up all citations and replacing inline references.
    
    Args:
        file_path: Path to the markdown file to process
        content: Markdown content to process (alternative to file_path)
        style: Citation style (vancouver, apa, mla, chicago, harvard, ieee)
        create_backup_file: Create a timestamped backup before processing (default: True when file_path provided)
        save_to_file: Write processed content back to file (default: True when file_path provided)
        skip_verification: Skip duplicate detection and context verification (default: False)
    
    Returns:
        Formatted result string with processed content and statistics
    """
    backup_path = None
    saved_to_path = None
    integrity_stats = {'duplicates_fixed': 0}
    context_mismatches = []
    
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
    
    # PREPROCESSING: Normalize legacy citation formats to Obsidian footnote style
    # This converts [1], [1, 2], [6-10] → [^1], [^1] [^2], [^6] [^7]... etc.
    normalizer = CitationNormalizer()
    normalization_result = normalizer.normalize(content)
    
    normalization_stats = {
        'changes_made': normalization_result.changes_made,
        'change_log': normalization_result.change_log,
    }
    
    # Use normalized content for further processing
    content = normalization_result.normalized_content
    
    # INTEGRITY CHECK: Fix consecutive duplicate citations [^A][^A] → [^A]
    if not skip_verification:
        from modules.citation_integrity_checker import CitationIntegrityChecker
        integrity_checker = CitationIntegrityChecker()
        content, duplicates_fixed = integrity_checker.fix_duplicates(content)
        integrity_stats['duplicates_fixed'] = duplicates_fixed
    
    # Set citation style
    # Note: This mutates the global lookup instance. Safe for single-threaded HTTP server,
    # but if converting to multi-threaded, consider creating per-request lookup instances.
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
    
    # CONTEXT VERIFICATION: Check if citations match their surrounding text
    if not skip_verification:
        from modules.citation_context_verifier import CitationContextVerifier
        context_verifier = CitationContextVerifier()
        # Only flag HIGH and MODERATE concern (threshold 0.15)
        context_mismatches = context_verifier.verify_citations(processed_content, deep_verify=False)
    
    # Save processed content back to file if requested
    if file_path and save_to_file:
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(processed_content)
            saved_to_path = file_path
        except Exception as e:
            # Log error but don't fail - content is still available in output
            saved_to_path = None
            # Will report the error in output
    
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
    
    # Add file save confirmation
    if saved_to_path:
        output_lines.extend([
            "## ✅ File Saved",
            f"- **Processed content saved to:** `{saved_to_path}`",
            "",
        ])
    elif file_path and save_to_file:
        # save_to_file was True but save failed
        output_lines.extend([
            "## ⚠️ File Save Failed",
            f"- Could not save to: `{file_path}`",
            "- Processed content is available below.",
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
    
    # Add normalization statistics if any changes were made
    if normalization_stats['changes_made'] > 0:
        output_lines.extend([
            "## 🔄 Citation Format Normalization",
            f"- **Legacy citations converted:** {normalization_stats['changes_made']}",
            "",
        ])
        # Show up to 10 examples
        examples = normalization_stats['change_log'][:10]
        for orig, replacement, line_num, change_type in examples:
            output_lines.append(f"  - Line {line_num}: `{orig}` → `{replacement}`")
        if len(normalization_stats['change_log']) > 10:
            output_lines.append(f"  - ... and {len(normalization_stats['change_log']) - 10} more")
        output_lines.append("")
    
    # Add integrity check results (duplicate fixes)
    if integrity_stats.get('duplicates_fixed', 0) > 0:
        output_lines.extend([
            "## 🔧 Citation Integrity Fixes",
            f"- **Consecutive duplicate citations removed:** {integrity_stats['duplicates_fixed']}",
            "",
        ])
    
    # Add context verification warnings
    if context_mismatches:
        from modules.citation_context_verifier import ConcernLevel
        high_concern = [m for m in context_mismatches if m.concern_level == ConcernLevel.HIGH]
        moderate_concern = [m for m in context_mismatches if m.concern_level == ConcernLevel.MODERATE]
        
        output_lines.extend([
            "## ⚠️ Context Verification Warnings",
            "",
            f"**{len(context_mismatches)} potential context mismatches found.**",
            "These citations have low keyword overlap with their surrounding text.",
            "Review manually to confirm they are appropriate.",
            "",
        ])
        
        if high_concern:
            output_lines.append("### 🔴 High Concern")
            for m in high_concern[:5]:
                output_lines.append(f"- Line {m.line_number}: `{m.citation_tag}` (overlap: {m.overlap_score:.0%})")
            if len(high_concern) > 5:
                output_lines.append(f"- ... and {len(high_concern) - 5} more")
            output_lines.append("")
        
        if moderate_concern:
            output_lines.append("### 🟡 Moderate Concern")
            for m in moderate_concern[:5]:
                output_lines.append(f"- Line {m.line_number}: `{m.citation_tag}` (overlap: {m.overlap_score:.0%})")
            if len(moderate_concern) > 5:
                output_lines.append(f"- ... and {len(moderate_concern) - 5} more")
            output_lines.append("")
        
        output_lines.append("*Use `citation_audit_document` with `deep_verify=true` for detailed LLM analysis.*")
        output_lines.append("")
    
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


def handle_normalize_format(file_path: Optional[str], content: Optional[str], dry_run: bool = False) -> str:
    """
    Handle citation format normalization.
    
    Converts legacy citation formats to Obsidian footnote style:
    - [1] → [^1]
    - [1, 2] → [^1] [^2]
    - [6-10] → [^6] [^7] [^8] [^9] [^10]
    - [1, 3-5, 8] → [^1] [^3] [^4] [^5] [^8]
    """
    # Get content from file or direct input
    if file_path:
        file_path = os.path.expanduser(file_path)
        if not os.path.exists(file_path):
            return f"Error: File not found: {file_path}"
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            return f"Error reading file: {e}"
    
    if not content:
        return "Error: No content provided. Specify either file_path or content."
    
    # Normalize citation formats
    normalizer = CitationNormalizer()
    
    if dry_run:
        # Preview mode - show what would change
        preview = normalizer.preview(content)
        return preview
    else:
        # Apply normalization
        result = normalizer.normalize(content)
        
        if not result.has_changes:
            return "# Citation Format Normalization\n\nNo legacy citation formats found. Document is already using Obsidian footnote style."
        
        output_lines = [
            "# Citation Format Normalization Complete",
            "",
            "## Statistics",
            f"- **Legacy citations converted:** {result.changes_made}",
            "",
        ]
        
        # Group changes by type
        by_type = {}
        for orig, replacement, line_num, change_type in result.change_log:
            if change_type not in by_type:
                by_type[change_type] = []
            by_type[change_type].append((orig, replacement, line_num))
        
        type_names = {
            "single": "Single Citations [N] → [^N]",
            "comma_list": "Comma Lists [1, 2] → [^1] [^2]",
            "range": "Ranges [1-5] → [^1] [^2] [^3] [^4] [^5]",
            "mixed": "Mixed Formats [1, 3-5] → [^1] [^3] [^4] [^5]",
        }
        
        output_lines.append("## Changes by Type")
        for change_type, changes in by_type.items():
            output_lines.append(f"\n### {type_names.get(change_type, change_type)} ({len(changes)})")
            for orig, replacement, line_num in changes[:10]:
                output_lines.append(f"- Line {line_num}: `{orig}` → `{replacement}`")
            if len(changes) > 10:
                output_lines.append(f"- ... and {len(changes) - 10} more")
        
        output_lines.extend([
            "",
            "---",
            "",
            "## Normalized Document",
            "",
            result.normalized_content,
        ])
        
        return "\n".join(output_lines)


# === Search Handlers ===

def handle_search_openalex(query: str, max_results: int = 5) -> str:
    """Handle OpenAlex search."""
    try:
        from modules.openalex_client import OpenAlexClient
        client = OpenAlexClient()
        results = client.search(query, max_results=min(max_results, 20))
        
        if not results:
            return "No results found in OpenAlex."
        
        output = ["# OpenAlex Search Results", "", f"**Query:** {query}", f"**Results:** {len(results)}", ""]
        
        for i, work in enumerate(results, 1):
            output.append(f"## {i}. {work.get('title', 'No title')}")
            
            authors = work.get('authors', [])
            if authors:
                author_str = ', '.join(authors[:3])
                if len(authors) > 3:
                    author_str += ' et al.'
                output.append(f"**Authors:** {author_str}")
            
            if work.get('year'):
                output.append(f"**Year:** {work.get('year')}")
            
            if work.get('venue'):
                output.append(f"**Venue:** {work.get('venue')}")
            
            if work.get('doi'):
                output.append(f"**DOI:** {work.get('doi')}")
            
            if work.get('cited_by_count'):
                output.append(f"**Citations:** {work.get('cited_by_count')}")
            
            output.append("")
        
        return "\n".join(output)
    except ImportError:
        return "Error: OpenAlex client not available."
    except Exception as e:
        return f"Error searching OpenAlex: {e}"


def handle_search_semantic_scholar(query: str, max_results: int = 5) -> str:
    """Handle Semantic Scholar search."""
    try:
        from modules.semantic_scholar_client import SemanticScholarClient
        client = SemanticScholarClient()
        results = client.search(query, limit=min(max_results, 20))
        
        if not results:
            return "No results found in Semantic Scholar."
        
        output = ["# Semantic Scholar Search Results", "", f"**Query:** {query}", f"**Results:** {len(results)}", ""]
        
        for i, paper in enumerate(results, 1):
            output.append(f"## {i}. {paper.get('title', 'No title')}")
            
            authors = paper.get('authors', [])
            if authors:
                author_names = [a.get('name', '') for a in authors[:3]]
                author_str = ', '.join(author_names)
                if len(authors) > 3:
                    author_str += ' et al.'
                output.append(f"**Authors:** {author_str}")
            
            if paper.get('year'):
                output.append(f"**Year:** {paper.get('year')}")
            
            if paper.get('venue'):
                output.append(f"**Venue:** {paper.get('venue')}")
            
            if paper.get('paperId'):
                output.append(f"**Paper ID:** {paper.get('paperId')}")
            
            if paper.get('citationCount'):
                output.append(f"**Citations:** {paper.get('citationCount')}")
            
            if paper.get('externalIds', {}).get('DOI'):
                output.append(f"**DOI:** {paper.get('externalIds', {}).get('DOI')}")
            
            output.append("")
        
        return "\n".join(output)
    except ImportError:
        return "Error: Semantic Scholar client not available."
    except Exception as e:
        return f"Error searching Semantic Scholar: {e}"


# === Import/Export Handlers ===

def handle_export_bibtex(identifiers: list) -> str:
    """Export citations to BibTeX format."""
    try:
        from modules.bibtex_handler import BibTeXExporter
        
        exporter = BibTeXExporter()
        results = lookup.batch_lookup(identifiers)
        
        bibtex_entries = []
        failed = []
        
        for result in results:
            if result.success and result.metadata:
                entry = exporter.metadata_to_bibtex(result.metadata)
                bibtex_entries.append(entry)
            else:
                failed.append(result.identifier)
        
        if not bibtex_entries:
            return "No citations could be exported. All lookups failed."
        
        output = ["# BibTeX Export", "", f"**Exported:** {len(bibtex_entries)}", f"**Failed:** {len(failed)}", ""]
        
        if failed:
            output.append("## Failed Lookups")
            for f in failed:
                output.append(f"- {f}")
            output.append("")
        
        output.append("## BibTeX Output")
        output.append("")
        output.append("```bibtex")
        output.append("\n\n".join(bibtex_entries))
        output.append("```")
        
        return "\n".join(output)
    except Exception as e:
        return f"Error exporting BibTeX: {e}"


def handle_export_ris(identifiers: list) -> str:
    """Export citations to RIS format."""
    try:
        from modules.ris_handler import RISExporter
        
        exporter = RISExporter()
        results = lookup.batch_lookup(identifiers)
        
        ris_entries = []
        failed = []
        
        for result in results:
            if result.success and result.metadata:
                entry = exporter.metadata_to_ris(result.metadata)
                ris_entries.append(entry)
            else:
                failed.append(result.identifier)
        
        if not ris_entries:
            return "No citations could be exported. All lookups failed."
        
        output = ["# RIS Export", "", f"**Exported:** {len(ris_entries)}", f"**Failed:** {len(failed)}", ""]
        
        if failed:
            output.append("## Failed Lookups")
            for f in failed:
                output.append(f"- {f}")
            output.append("")
        
        output.append("## RIS Output")
        output.append("")
        output.append("```")
        output.append("\n".join(ris_entries))
        output.append("```")
        
        return "\n".join(output)
    except Exception as e:
        return f"Error exporting RIS: {e}"


def handle_import_bibtex(file_path: Optional[str], content: Optional[str]) -> str:
    """Import and parse BibTeX."""
    try:
        from modules.bibtex_handler import BibTeXParser
        
        parser = BibTeXParser()
        
        if file_path:
            file_path = os.path.expanduser(file_path)
            entries = parser.parse_file(file_path)
        elif content:
            entries = parser.parse_string(content)
        else:
            return "Error: Provide either file_path or content."
        
        if not entries:
            return "No BibTeX entries found."
        
        output = ["# BibTeX Import", "", f"**Entries found:** {len(entries)}", ""]
        
        for i, entry in enumerate(entries, 1):
            output.append(f"## {i}. {entry.cite_key} ({entry.entry_type})")
            output.append(f"**Title:** {entry.title}")
            if entry.authors:
                output.append(f"**Authors:** {', '.join(entry.authors)}")
            if entry.year:
                output.append(f"**Year:** {entry.year}")
            if entry.doi:
                output.append(f"**DOI:** {entry.doi}")
            output.append("")
        
        return "\n".join(output)
    except Exception as e:
        return f"Error importing BibTeX: {e}"


def handle_import_ris(file_path: Optional[str], content: Optional[str]) -> str:
    """Import and parse RIS."""
    try:
        from modules.ris_handler import RISParser
        
        parser = RISParser()
        
        if file_path:
            file_path = os.path.expanduser(file_path)
            entries = parser.parse_file(file_path)
        elif content:
            entries = parser.parse_string(content)
        else:
            return "Error: Provide either file_path or content."
        
        if not entries:
            return "No RIS entries found."
        
        output = ["# RIS Import", "", f"**Entries found:** {len(entries)}", ""]
        
        for i, entry in enumerate(entries, 1):
            output.append(f"## {i}. ({entry.entry_type})")
            output.append(f"**Title:** {entry.title}")
            if entry.authors:
                output.append(f"**Authors:** {', '.join(entry.authors)}")
            if entry.year:
                output.append(f"**Year:** {entry.year}")
            if entry.doi:
                output.append(f"**DOI:** {entry.doi}")
            output.append("")
        
        return "\n".join(output)
    except Exception as e:
        return f"Error importing RIS: {e}"


# === PDF and Bibliography Handlers ===

def handle_extract_pdf(file_path: str) -> str:
    """Extract citation metadata from PDF."""
    try:
        from modules.pdf_extractor import PDFExtractor, PYMUPDF_AVAILABLE
        
        if not PYMUPDF_AVAILABLE:
            return "Error: PyMuPDF not installed. Run: pip install PyMuPDF"
        
        extractor = PDFExtractor()
        file_path = os.path.expanduser(file_path)
        
        if not os.path.exists(file_path):
            return f"Error: File not found: {file_path}"
        
        metadata = extractor.extract(file_path)
        
        if not metadata:
            return "Error: Could not extract metadata from PDF."
        
        output = ["# PDF Metadata Extraction", "", f"**File:** {file_path}", ""]
        
        if metadata.title:
            output.append(f"**Title:** {metadata.title}")
        
        if metadata.authors:
            output.append(f"**Authors:** {', '.join(metadata.authors)}")
        
        if metadata.doi:
            output.append(f"**DOI:** {metadata.doi}")
        
        if metadata.pmid:
            output.append(f"**PMID:** {metadata.pmid}")
        
        if metadata.arxiv_id:
            output.append(f"**arXiv ID:** {metadata.arxiv_id}")
        
        if metadata.creation_date:
            output.append(f"**Creation Date:** {metadata.creation_date}")
        
        output.append(f"**Pages:** {metadata.page_count}")
        output.append(f"**File Size:** {metadata.file_size:,} bytes")
        
        if metadata.has_identifier:
            id_type, id_value = metadata.best_identifier
            output.append("")
            output.append(f"**Best Identifier:** {id_type.upper()} = {id_value}")
            output.append("")
            output.append("*Use this identifier to look up the full citation.*")
        
        return "\n".join(output)
    except Exception as e:
        return f"Error extracting PDF metadata: {e}"


def handle_check_article_duplicates(citations: list) -> str:
    """Check for duplicate articles in citations list."""
    try:
        from modules.duplicate_detector import DuplicateDetector
        
        detector = DuplicateDetector()
        duplicates = detector.find_duplicates(citations)
        
        if not duplicates:
            return "# Duplicate Check\n\n✅ **No duplicate articles found.**"
        
        output = ["# Duplicate Check", "", f"**Duplicates found:** {len(duplicates)}", ""]
        
        for dup in duplicates:
            emoji = "🔴" if dup.confidence >= 0.95 else "🟡" if dup.confidence >= 0.8 else "🟢"
            output.append(f"## {emoji} Duplicate Pair")
            output.append(f"**Match type:** {dup.match_type}")
            output.append(f"**Confidence:** {dup.confidence:.0%}")
            output.append(f"**Original ID:** {dup.original_id}")
            output.append(f"**Duplicate ID:** {dup.duplicate_id}")
            output.append(f"**Reason:** {dup.reason}")
            output.append(f"**Title:** {dup.original_title[:80]}...")
            output.append("")
        
        return "\n".join(output)
    except Exception as e:
        return f"Error checking duplicates: {e}"


def handle_generate_bibliography(identifiers: list, style: str = "vancouver", sort_order: str = "alphabetical") -> str:
    """Generate formatted bibliography from identifiers."""
    try:
        # Set style (mutates global - safe for single-threaded server)
        if style != lookup.style:
            lookup.set_style(style)
        
        results = lookup.batch_lookup(identifiers)
        successful = [r for r in results if r.success]
        failed = [r for r in results if not r.success]
        
        if not successful:
            return "Error: No citations could be looked up."
        
        # Sort as requested
        if sort_order == 'alphabetical':
            successful.sort(key=lambda r: r.full_citation.lower() if r.full_citation else '')
        elif sort_order == 'year':
            successful.sort(key=lambda r: r.metadata.get('year', '0000') if r.metadata else '0000', reverse=True)
        
        output = ["# Generated Bibliography", "", f"**Style:** {style}", f"**Entries:** {len(successful)}", ""]
        
        if failed:
            output.append(f"**Failed lookups:** {len(failed)}")
            output.append("")
        
        output.append("---")
        output.append("")
        
        for r in successful:
            output.append(r.full_citation)
            output.append("")
        
        if failed:
            output.append("---")
            output.append("")
            output.append("## Failed Lookups")
            for r in failed:
                output.append(f"- **{r.identifier}:** {r.error}")
        
        return "\n".join(output)
    except Exception as e:
        return f"Error generating bibliography: {e}"


# === Citation Integrity Handlers (v2.4.0) ===

def handle_find_duplicates(
    file_path: Optional[str], 
    content: Optional[str], 
    auto_fix: bool = False
) -> str:
    """Handle citation_find_duplicates MCP tool calls."""
    text_content, error = get_content(file_path, content)
    if error:
        return error
    
    from modules.citation_integrity_checker import CitationIntegrityChecker
    checker = CitationIntegrityChecker()
    
    # Always analyze first
    report = checker.analyze(text_content)
    
    output = ["# Citation Integrity Report", ""]
    
    if report.is_clean:
        output.append("✅ **No integrity issues found.** Document citations are clean.")
        return "\n".join(output)
    
    # Report issues
    if report.same_citation_duplicates:
        output.append(f"## ❌ Same-Citation Duplicates ({len(report.same_citation_duplicates)})")
        output.append("")
        output.append("Consecutive identical citations that should be deduplicated:")
        output.append("")
        for line, orig, fix in report.same_citation_duplicates:
            output.append(f"- **Line {line}:** `{orig}` → `{fix}`")
        output.append("")
    
    if report.orphaned_definitions:
        output.append(f"## ⚠️ Orphaned Definitions ({len(report.orphaned_definitions)})")
        output.append("")
        output.append("Defined but never used in document body:")
        output.append("")
        for orphan in report.orphaned_definitions[:15]:
            output.append(f"- `{orphan}`")
        if len(report.orphaned_definitions) > 15:
            output.append(f"- ... and {len(report.orphaned_definitions) - 15} more")
        output.append("")
    
    if report.missing_definitions:
        output.append(f"## ❌ Missing Definitions ({len(report.missing_definitions)})")
        output.append("")
        output.append("Used inline but never defined:")
        output.append("")
        for missing in report.missing_definitions[:15]:
            output.append(f"- `{missing}`")
        if len(report.missing_definitions) > 15:
            output.append(f"- ... and {len(report.missing_definitions) - 15} more")
        output.append("")
    
    # Auto-fix if requested (fixes same-citation duplicates only)
    if auto_fix and report.same_citation_duplicates:
        fixed_content, fixes_applied = checker.fix_duplicates(text_content)
        output.append(f"## ✅ Auto-Fixed: {fixes_applied} duplicates removed")
        output.append("")
        
        # Save back to file if file_path provided
        if file_path:
            try:
                file_path = os.path.expanduser(file_path)
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(fixed_content)
                output.append(f"- **Saved to:** `{file_path}`")
            except Exception as e:
                output.append(f"- ⚠️ Could not save: {e}")
    
    return "\n".join(output)


def handle_verify_context(
    file_path: Optional[str],
    content: Optional[str],
    threshold: float = 0.15,
    deep_verify: bool = False
) -> str:
    """Handle citation_verify_context MCP tool calls."""
    text_content, error = get_content(file_path, content)
    if error:
        return error
    
    from modules.citation_context_verifier import CitationContextVerifier
    
    # Get Groq API key from environment if available
    groq_api_key = os.environ.get('GROQ_API_KEY')
    
    verifier = CitationContextVerifier(groq_api_key=groq_api_key)
    mismatches = verifier.verify_citations(
        text_content, 
        deep_verify=deep_verify,
        flag_threshold=threshold
    )
    
    output = ["# Citation Context Verification Report", ""]
    
    if not mismatches:
        output.append("✅ **All citations appear to match their context.**")
        output.append("")
        output.append(f"*Verified {verifier.stats.total_citations_verified} citations with threshold {threshold:.0%}*")
        return "\n".join(output)
    
    output.append(f"**{len(mismatches)} potential context mismatches found**")
    output.append(f"*Threshold: {threshold:.0%} keyword overlap*")
    output.append("")
    
    # Format the mismatch report
    output.append(verifier.format_mismatch_report(mismatches))
    
    return "\n".join(output)


def handle_audit_document(
    file_path: Optional[str],
    content: Optional[str],
    auto_fix_duplicates: bool = False,
    deep_verify: bool = False
) -> str:
    """Handle citation_audit_document MCP tool calls."""
    text_content, error = get_content(file_path, content)
    if error:
        return error
    
    from modules.citation_integrity_checker import CitationIntegrityChecker
    from modules.citation_context_verifier import CitationContextVerifier
    
    # Get Groq API key from environment if available
    groq_api_key = os.environ.get('GROQ_API_KEY')
    
    integrity_checker = CitationIntegrityChecker()
    context_verifier = CitationContextVerifier(groq_api_key=groq_api_key)
    
    # Run integrity analysis
    integrity_report = integrity_checker.analyze(text_content)
    
    # Run context verification
    mismatches = context_verifier.verify_citations(text_content, deep_verify=deep_verify)
    
    # Calculate health score
    total_issues = integrity_report.total_issues + len(mismatches)
    health_score = max(0, 100 - (total_issues * 5))
    
    # Auto-fix duplicates if requested
    fixed_content = text_content
    fixes_applied = 0
    if auto_fix_duplicates and integrity_report.same_citation_duplicates:
        fixed_content, fixes_applied = integrity_checker.fix_duplicates(text_content)
    
    # Build output
    output = [
        "# 📊 Citation Audit Report",
        "",
    ]
    
    # Health score with emoji
    if health_score >= 80:
        score_emoji = "🟢"
    elif health_score >= 60:
        score_emoji = "🟡"
    else:
        score_emoji = "🔴"
    
    output.extend([
        f"## {score_emoji} Health Score: {health_score}/100",
        "",
        "## Summary",
        f"- **Same-citation duplicates:** {len(integrity_report.same_citation_duplicates)}",
        f"- **Orphaned definitions:** {len(integrity_report.orphaned_definitions)}",
        f"- **Missing definitions:** {len(integrity_report.missing_definitions)}",
        f"- **Context mismatches:** {len(mismatches)}",
        "",
    ])
    
    # Details for each issue type
    if integrity_report.same_citation_duplicates:
        output.append("## ❌ Same-Citation Duplicates")
        output.append("")
        for line, orig, fix in integrity_report.same_citation_duplicates[:10]:
            output.append(f"- Line {line}: `{orig}` → `{fix}`")
        if len(integrity_report.same_citation_duplicates) > 10:
            output.append(f"- ... and {len(integrity_report.same_citation_duplicates) - 10} more")
        output.append("")
    
    if integrity_report.orphaned_definitions:
        output.append("## ⚠️ Orphaned Definitions")
        output.append("")
        output.append("Defined but never used in document body:")
        output.append("")
        for orphan in integrity_report.orphaned_definitions[:10]:
            output.append(f"- `{orphan}`")
        if len(integrity_report.orphaned_definitions) > 10:
            output.append(f"- ... and {len(integrity_report.orphaned_definitions) - 10} more")
        output.append("")
    
    if integrity_report.missing_definitions:
        output.append("## ❌ Missing Definitions")
        output.append("")
        output.append("Used inline but never defined:")
        output.append("")
        for missing in integrity_report.missing_definitions[:10]:
            output.append(f"- `{missing}`")
        if len(integrity_report.missing_definitions) > 10:
            output.append(f"- ... and {len(integrity_report.missing_definitions) - 10} more")
        output.append("")
    
    if mismatches:
        output.append(context_verifier.format_mismatch_report(mismatches))
    
    if fixes_applied > 0:
        output.extend([
            f"## ✅ Auto-Fixes Applied: {fixes_applied}",
            "",
        ])
        
        # Save back to file if file_path provided
        if file_path:
            try:
                file_path = os.path.expanduser(file_path)
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(fixed_content)
                output.append(f"- **Saved to:** `{file_path}`")
            except Exception as e:
                output.append(f"- ⚠️ Could not save: {e}")
    
    return "\n".join(output)


async def main():
    """Run the MCP server with stdio transport."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())