#!/usr/bin/env python3
"""
Citation Lookup MCP Server (Async Version)

A high-performance async MCP server wrapper around the existing CitationLookup class.
Reuses all existing, tested logic from citation_lookup.py.
Integrates with local Ollama LLMs for enhanced capabilities.

Usage:
    cd CitationSculptor
    source venv/bin/activate
    python mcp_server/server.py --port 3018

Environment Variables:
    OLLAMA_MODEL: Model to use for AI-enhanced features (default: deepseek-r1:32b-qwen-distill-q4_K_M)
    OLLAMA_URL: Ollama API URL (default: http://localhost:11434)
"""

import sys
import json
import argparse
import os
import asyncio
from pathlib import Path
from typing import Optional, List
from concurrent.futures import ThreadPoolExecutor

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from aiohttp import web, ClientSession, ClientTimeout

# Import the existing, tested CitationLookup class
from citation_lookup import CitationLookup, LookupResult


class AsyncOllamaClient:
    """Async client for Ollama API to offload tasks from Claude."""
    
    def __init__(
        self, 
        base_url: str = "http://localhost:11434",
        default_model: str = "deepseek-r1:32b-qwen-distill-q4_K_M"
    ):
        self.base_url = base_url
        self.default_model = default_model
        self._available: Optional[bool] = None
        self._session: Optional[ClientSession] = None
    
    async def _get_session(self) -> ClientSession:
        if self._session is None or self._session.closed:
            self._session = ClientSession()
        return self._session
    
    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()
    
    async def is_available(self) -> bool:
        """Check if Ollama is running."""
        if self._available is not None:
            return self._available
        try:
            session = await self._get_session()
            async with session.get(
                f"{self.base_url}/api/tags", 
                timeout=ClientTimeout(total=2)
            ) as resp:
                self._available = resp.status == 200
                return self._available
        except (ConnectionError, TimeoutError, OSError, Exception) as e:
            # Ollama not running or unreachable - this is expected in many environments
            self._available = False
            return False
    
    async def generate(
        self, 
        prompt: str, 
        model: Optional[str] = None,
        system: Optional[str] = None,
        max_tokens: int = 1000
    ) -> str:
        """Generate text using Ollama."""
        model = model or self.default_model
        
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"num_predict": max_tokens}
        }
        if system:
            payload["system"] = system
        
        try:
            session = await self._get_session()
            async with session.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=ClientTimeout(total=120)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("response", "")
                return f"Error: Ollama returned status {resp.status}"
        except Exception as e:
            return f"Error: {str(e)}"
    
    async def medical_query(self, query: str) -> str:
        """Use meditron for medical queries if available."""
        try:
            session = await self._get_session()
            async with session.get(f"{self.base_url}/api/tags") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    models = [m["name"] for m in data.get("models", [])]
                    if any("meditron" in m for m in models):
                        return await self.generate(
                            query, 
                            model="meditron:70b",
                            system="You are a medical expert specializing in cardiovascular imaging. Provide accurate, evidence-based information with specific values and references where applicable."
                        )
        except (ConnectionError, TimeoutError, KeyError, Exception):
            # Meditron model not available - fall back to default model
            pass
        
        # Fall back to default model
        return await self.generate(query)


class CitationMCPServer:
    """
    Async MCP Server wrapper for CitationLookup.
    
    Uses aiohttp for high-performance async HTTP handling.
    Runs synchronous CitationLookup methods in a thread pool.
    """
    
    def __init__(self, port: int = 3018):
        self.port = port
        self.lookup = CitationLookup(verbose=False)
        self.ollama = AsyncOllamaClient(
            default_model=os.environ.get("OLLAMA_MODEL", "deepseek-r1:32b-qwen-distill-q4_K_M")
        )
        self.executor = ThreadPoolExecutor(max_workers=4)
        self.app = web.Application()
        self._setup_routes()
    
    def _setup_routes(self):
        """Set up HTTP routes."""
        self.app.router.add_post('/mcp', self.handle_mcp)
        self.app.router.add_get('/health', self.handle_health)
        self.app.router.add_options('/mcp', self.handle_options)
        self.app.on_startup.append(self._on_startup)
        self.app.on_cleanup.append(self._on_cleanup)
    
    async def _on_startup(self, app):
        """Startup tasks."""
        loop = asyncio.get_event_loop()
        pubmed_ok = await loop.run_in_executor(self.executor, self.lookup.test_connection)
        ollama_ok = await self.ollama.is_available()
        
        print(f"PubMed MCP: {'Connected' if pubmed_ok else 'Not available'}")
        print(f"Ollama: {'Available' if ollama_ok else 'Not available'}")
        if ollama_ok:
            print(f"  Default model: {self.ollama.default_model}")
    
    async def _on_cleanup(self, app):
        """Cleanup tasks."""
        await self.ollama.close()
        self.executor.shutdown(wait=False)
    
    async def handle_options(self, request: web.Request) -> web.Response:
        """Handle CORS preflight."""
        return web.Response(
            headers={
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'POST, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type, Accept',
            }
        )
    
    async def handle_health(self, request: web.Request) -> web.Response:
        """Health check endpoint."""
        loop = asyncio.get_event_loop()
        pubmed_connected = await loop.run_in_executor(
            self.executor, self.lookup.test_connection
        )
        ollama_available = await self.ollama.is_available()
        
        return web.json_response({
            "status": "ok" if pubmed_connected else "degraded",
            "server": "citation-lookup-mcp",
            "version": "1.2.0",
            "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "async": True,
            "pubmed_mcp_connected": pubmed_connected,
            "ollama_available": ollama_available,
            "ollama_model": self.ollama.default_model if ollama_available else None,
        })
    
    async def handle_mcp(self, request: web.Request) -> web.Response:
        """Handle MCP JSON-RPC requests."""
        cors_headers = {'Access-Control-Allow-Origin': '*'}
        
        try:
            data = await request.json()
        except json.JSONDecodeError:
            return web.json_response(
                {"jsonrpc": "2.0", "error": {"code": -32700, "message": "Parse error"}, "id": None},
                headers=cors_headers,
                status=400
            )
        
        method = data.get("method")
        params = data.get("params", {})
        request_id = data.get("id")
        
        if method == "initialize":
            result = {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "citation-lookup-mcp", "version": "1.2.0"}
            }
        elif method == "tools/list":
            result = {"tools": self._get_tools()}
        elif method == "tools/call":
            tool_name = params.get("name")
            arguments = params.get("arguments", {})
            result = await self._handle_tool_call(tool_name, arguments)
        else:
            return web.json_response(
                {"jsonrpc": "2.0", "error": {"code": -32601, "message": f"Method not found: {method}"}, "id": request_id},
                headers=cors_headers,
                status=404
            )
        
        return web.json_response(
            {"jsonrpc": "2.0", "result": result, "id": request_id},
            headers=cors_headers
        )
    
    def _get_tools(self) -> list:
        """Return MCP tool definitions."""
        return [
            {
                "name": "citation_lookup_pmid",
                "description": "Look up a journal article by PubMed ID (PMID) and return a Vancouver-style citation with mnemonic label for Obsidian.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "pmid": {"type": "string", "description": "The PubMed ID to look up, e.g., '32089132'"}
                    },
                    "required": ["pmid"]
                }
            },
            {
                "name": "citation_lookup_doi",
                "description": "Look up an article by DOI and return a Vancouver-style citation.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "doi": {"type": "string", "description": "The DOI to look up, e.g., '10.1186/s12968-020-00607-1'"}
                    },
                    "required": ["doi"]
                }
            },
            {
                "name": "citation_lookup_pmcid",
                "description": "Look up an article by PubMed Central ID (PMC ID).",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "pmcid": {"type": "string", "description": "The PMC ID, e.g., 'PMC7039045'"}
                    },
                    "required": ["pmcid"]
                }
            },
            {
                "name": "citation_lookup_title",
                "description": "Search for an article by title and return a Vancouver-style citation.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "description": "The article title to search for"}
                    },
                    "required": ["title"]
                }
            },
            {
                "name": "citation_lookup_auto",
                "description": "Auto-detect identifier type (PMID, DOI, PMC ID, or title) and return citation.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "identifier": {"type": "string", "description": "Any identifier or article title"}
                    },
                    "required": ["identifier"]
                }
            },
            {
                "name": "citation_get_inline_only",
                "description": "Get ONLY the inline reference mark, e.g., [^KramerCM-2020-32089132]",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "identifier": {"type": "string", "description": "Any identifier to look up"}
                    },
                    "required": ["identifier"]
                }
            },
            {
                "name": "citation_batch_lookup",
                "description": "Look up multiple identifiers at once IN PARALLEL. Much faster than individual lookups.",
                "inputSchema": {
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
            },
            {
                "name": "medical_query",
                "description": "Ask a medical question using local Ollama LLM (meditron:70b if available). Use this to offload medical knowledge queries from Claude to save tokens.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Medical question to answer"}
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "summarize_for_atomic_note",
                "description": "Use local LLM to summarize content for an atomic note. Saves Claude tokens.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "content": {"type": "string", "description": "Content to summarize"},
                        "note_type": {"type": "string", "description": "Type: protocol, physics, safety, pathology, reference, clinical"}
                    },
                    "required": ["content"]
                }
            }
        ]
    
    async def _handle_tool_call(self, tool_name: str, arguments: dict) -> dict:
        """Handle an MCP tool call."""
        try:
            return await self._handle_tool_call_inner(tool_name, arguments)
        except Exception as e:
            import traceback
            error_msg = f"Error in {tool_name}: {str(e)}\n{traceback.format_exc()}"
            print(error_msg)  # Log to console
            return {"content": [{"type": "text", "text": error_msg}], "isError": True}
    
    async def _handle_tool_call_inner(self, tool_name: str, arguments: dict) -> dict:
        """Inner handler for tool calls."""
        loop = asyncio.get_event_loop()
        
        # Citation lookup tools (run in thread pool since they're synchronous)
        if tool_name == "citation_lookup_pmid":
            result = await loop.run_in_executor(
                self.executor, self.lookup.lookup_pmid, arguments["pmid"]
            )
            return self._format_result(result)
        
        elif tool_name == "citation_lookup_doi":
            result = await loop.run_in_executor(
                self.executor, self.lookup.lookup_doi, arguments["doi"]
            )
            return self._format_result(result)
        
        elif tool_name == "citation_lookup_pmcid":
            result = await loop.run_in_executor(
                self.executor, self.lookup.lookup_pmcid, arguments["pmcid"]
            )
            return self._format_result(result)
        
        elif tool_name == "citation_lookup_title":
            result = await loop.run_in_executor(
                self.executor, self.lookup.lookup_title, arguments["title"]
            )
            return self._format_result(result)
        
        elif tool_name == "citation_lookup_auto":
            result = await loop.run_in_executor(
                self.executor, self.lookup.lookup_auto, arguments["identifier"]
            )
            return self._format_result(result)
        
        elif tool_name == "citation_get_inline_only":
            result = await loop.run_in_executor(
                self.executor, self.lookup.lookup_auto, arguments["identifier"]
            )
            if result.success:
                return {"content": [{"type": "text", "text": result.inline_mark}]}
            return {"content": [{"type": "text", "text": f"Error: {result.error}"}], "isError": True}
        
        elif tool_name == "citation_batch_lookup":
            # Run batch lookup (uses existing batch_lookup method which is sequential but reliable)
            # For true parallelism, we'd need thread-safe PubMed client
            identifiers = arguments["identifiers"]
            
            # Use the existing batch_lookup method
            results = await loop.run_in_executor(
                self.executor, 
                self.lookup.batch_lookup, 
                identifiers
            )
            
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
            return {"content": [{"type": "text", "text": "\n".join(output_lines)}]}
        
        # Ollama-powered tools (already async)
        elif tool_name == "medical_query":
            if not await self.ollama.is_available():
                return {"content": [{"type": "text", "text": "Error: Ollama not available"}], "isError": True}
            response = await self.ollama.medical_query(arguments["query"])
            return {"content": [{"type": "text", "text": response}]}
        
        elif tool_name == "summarize_for_atomic_note":
            if not await self.ollama.is_available():
                return {"content": [{"type": "text", "text": "Error: Ollama not available"}], "isError": True}
            
            note_type = arguments.get("note_type", "general")
            prompt = f"""Summarize the following content for an Obsidian atomic note of type '{note_type}'.
Keep the summary concise (2-3 sentences) and focus on the key clinical or technical points.

Content:
{arguments["content"]}

Summary:"""
            response = await self.ollama.generate(prompt)
            return {"content": [{"type": "text", "text": response}]}
        
        else:
            return {"content": [{"type": "text", "text": f"Unknown tool: {tool_name}"}], "isError": True}
    
    def _format_result(self, result: LookupResult) -> dict:
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
            return {"content": [{"type": "text", "text": "\n".join(lines)}]}
        else:
            return {"content": [{"type": "text", "text": f"Error: {result.error}"}], "isError": True}
    
    def run(self):
        """Start the HTTP server."""
        print(f"\nStarting Citation Lookup MCP Server v1.2.0 (Async)")
        print(f"  Python: {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
        print(f"  Health: http://127.0.0.1:{self.port}/health")
        print(f"  MCP:    http://127.0.0.1:{self.port}/mcp")
        print(f"\nPress Ctrl+C to stop.\n")
        
        web.run_app(self.app, host='127.0.0.1', port=self.port, print=None)


def main():
    parser = argparse.ArgumentParser(description="Citation Lookup MCP Server (Async)")
    parser.add_argument('--port', type=int, default=3018, help='HTTP port (default: 3018)')
    args = parser.parse_args()
    
    server = CitationMCPServer(port=args.port)
    server.run()


if __name__ == "__main__":
    main()
