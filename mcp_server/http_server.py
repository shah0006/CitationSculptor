#!/usr/bin/env python3
"""
CitationSculptor HTTP API Server

A lightweight HTTP server that exposes CitationSculptor functionality
for Obsidian plugin integration and provides a beautiful web UI.

Usage:
    python -m mcp_server.http_server [--port 3019]
    
Or configure in systemd/launchd for automatic startup.

Web UI:
    Open http://127.0.0.1:3019 in your browser
"""

import sys
import json
import argparse
import mimetypes
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from typing import Optional, Dict, Any

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from citation_lookup import CitationLookup, LookupResult
from modules.formatter_factory import get_available_styles, get_style_info

# Static files directory
WEB_DIR = Path(__file__).parent.parent / 'web'


class CitationHTTPHandler(BaseHTTPRequestHandler):
    """HTTP request handler for citation lookups and web UI."""
    
    lookup: CitationLookup = None  # Class-level singleton
    
    def log_message(self, format: str, *args) -> None:
        """Suppress logging for cleaner output."""
        pass
    
    def _send_json(self, data: Dict[str, Any], status: int = 200):
        """Send JSON response."""
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))
    
    def _send_file(self, filepath: Path):
        """Send a static file."""
        if not filepath.exists():
            self.send_error(404, 'File not found')
            return
        
        # Determine content type
        content_type, _ = mimetypes.guess_type(str(filepath))
        if content_type is None:
            content_type = 'application/octet-stream'
        
        try:
            with open(filepath, 'rb') as f:
                content = f.read()
            
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', len(content))
            self.send_header('Cache-Control', 'no-cache')
            self.end_headers()
            self.wfile.write(content)
        except Exception as e:
            self.send_error(500, str(e))
    
    def _format_result(self, result: LookupResult) -> Dict[str, Any]:
        """Convert LookupResult to JSON-serializable dict."""
        return {
            'success': result.success,
            'identifier': result.identifier,
            'identifier_type': result.identifier_type,
            'inline_mark': result.inline_mark or '',
            'endnote_citation': result.endnote_citation or '',
            'full_citation': result.full_citation or '',
            'metadata': result.metadata,
            'error': result.error,
        }
    
    def do_OPTIONS(self):
        """Handle CORS preflight."""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    
    def do_GET(self):
        """Handle GET requests."""
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        
        # Serve Web UI (root or /index.html)
        if path == '/' or path == '/index.html':
            self._send_file(WEB_DIR / 'index.html')
            return
        
        # Serve static files from /web/
        if path.startswith('/static/') or path.endswith(('.css', '.js', '.ico', '.png', '.svg')):
            # Remove leading slash and serve from web directory
            file_path = WEB_DIR / path.lstrip('/')
            if file_path.exists() and file_path.is_file():
                self._send_file(file_path)
                return
        
        # API Endpoints
        if path == '/health':
            self._send_json({'status': 'ok', 'version': '2.0.0'})
            return
        
        if path == '/api/styles':
            self._send_json({
                'styles': get_available_styles(),
                'info': get_style_info(),
                'default': 'vancouver'
            })
            return
        
        if path == '/api/lookup':
            identifier = query.get('id', [None])[0]
            style = query.get('style', ['vancouver'])[0]
            if not identifier:
                self._send_json({'error': 'Missing id parameter'}, 400)
                return
            
            # Set style if different from current
            if style != self.lookup.style:
                self.lookup.set_style(style)
            
            result = self.lookup.lookup_auto(identifier)
            self._send_json(self._format_result(result))
            return
        
        if path == '/api/lookup/pmid':
            pmid = query.get('pmid', [None])[0]
            if not pmid:
                self._send_json({'error': 'Missing pmid parameter'}, 400)
                return
            
            result = self.lookup.lookup_pmid(pmid)
            self._send_json(self._format_result(result))
            return
        
        if path == '/api/lookup/doi':
            doi = query.get('doi', [None])[0]
            if not doi:
                self._send_json({'error': 'Missing doi parameter'}, 400)
                return
            
            result = self.lookup.lookup_doi(doi)
            self._send_json(self._format_result(result))
            return
        
        if path == '/api/lookup/pmcid':
            pmcid = query.get('pmcid', [None])[0]
            if not pmcid:
                self._send_json({'error': 'Missing pmcid parameter'}, 400)
                return
            
            result = self.lookup.lookup_pmcid(pmcid)
            self._send_json(self._format_result(result))
            return
        
        if path == '/api/lookup/title':
            title = query.get('title', [None])[0]
            if not title:
                self._send_json({'error': 'Missing title parameter'}, 400)
                return
            
            result = self.lookup.lookup_title(title)
            self._send_json(self._format_result(result))
            return
        
        if path == '/api/search':
            q = query.get('q', [None])[0]
            max_results = int(query.get('max', ['10'])[0])
            if not q:
                self._send_json({'error': 'Missing q parameter'}, 400)
                return
            
            articles = self.lookup.pubmed_client.search_by_title(q, max_results=min(max_results, 50))
            results = []
            for article in articles:
                # Safely extract attributes ensuring they're JSON-serializable
                abstract = getattr(article, 'abstract', None)
                if abstract and not isinstance(abstract, str):
                    abstract = None
                results.append({
                    'pmid': str(article.pmid) if article.pmid else None,
                    'title': str(article.title) if article.title else None,
                    'authors': list(article.authors) if article.authors else [],
                    'journal': str(article.journal_abbreviation or article.journal) if (article.journal_abbreviation or article.journal) else None,
                    'year': str(article.year) if article.year else None,
                    'doi': str(article.doi) if article.doi else None,
                    'abstract': abstract,
                })
            self._send_json({'results': results, 'count': len(results)})
            return
        
        if path == '/api/cache/stats':
            stats = self.lookup.pubmed_client.get_cache_stats()
            self._send_json(stats)
            return
        
        if path == '/api/cache/clear':
            self.lookup.pubmed_client._pmid_cache.clear()
            self.lookup.pubmed_client._conversion_cache.clear()
            self.lookup.pubmed_client._crossref_cache.clear()
            self._send_json({'status': 'cleared'})
            return
        
        # Default: 404
        self._send_json({'error': f'Unknown endpoint: {path}'}, 404)
    
    def do_POST(self):
        """Handle POST requests."""
        parsed = urlparse(self.path)
        path = parsed.path
        
        # Read body
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8') if content_length > 0 else '{}'
        
        try:
            data = json.loads(body) if body else {}
        except json.JSONDecodeError:
            self._send_json({'error': 'Invalid JSON'}, 400)
            return
        
        if path == '/api/lookup':
            identifier = data.get('identifier') or data.get('id')
            if not identifier:
                self._send_json({'error': 'Missing identifier'}, 400)
                return
            
            result = self.lookup.lookup_auto(identifier)
            self._send_json(self._format_result(result))
            return
        
        if path == '/api/batch':
            identifiers = data.get('identifiers', [])
            if not identifiers:
                self._send_json({'error': 'Missing identifiers array'}, 400)
                return
            
            results = self.lookup.batch_lookup(identifiers)
            self._send_json({
                'results': [self._format_result(r) for r in results],
                'count': len(results),
                'success_count': sum(1 for r in results if r.success),
            })
            return
        
        if path == '/api/search':
            query = data.get('query') or data.get('q')
            max_results = data.get('max_results', 10)
            if not query:
                self._send_json({'error': 'Missing query'}, 400)
                return
            
            articles = self.lookup.pubmed_client.search_by_title(query, max_results=min(max_results, 50))
            results = []
            for article in articles:
                results.append({
                    'pmid': str(article.pmid) if article.pmid else None,
                    'title': str(article.title) if article.title else None,
                    'authors': list(article.authors) if article.authors else [],
                    'journal': str(article.journal_abbreviation or article.journal) if (article.journal_abbreviation or article.journal) else None,
                    'year': str(article.year) if article.year else None,
                    'doi': str(article.doi) if article.doi else None,
                })
            self._send_json({'results': results, 'count': len(results)})
            return
        
        # Default: 404
        self._send_json({'error': f'Unknown endpoint: {path}'}, 404)


def run_server(port: int = 3019, host: str = '127.0.0.1'):
    """Start the HTTP server."""
    # Initialize singleton lookup instance
    CitationHTTPHandler.lookup = CitationLookup()
    
    server = HTTPServer((host, port), CitationHTTPHandler)
    print(f"")
    print(f"  ╔═══════════════════════════════════════════════════════════╗")
    print(f"  ║          📚 CitationSculptor HTTP Server v2.0.0            ║")
    print(f"  ╚═══════════════════════════════════════════════════════════╝")
    print(f"")
    print(f"  🌐 Web UI:    http://{host}:{port}")
    print(f"  📡 API Base:  http://{host}:{port}/api")
    print(f"")
    print(f"  API Endpoints:")
    print(f"    GET  /health              Health check")
    print(f"    GET  /api/lookup?id=X     Auto-detect and lookup identifier")
    print(f"    GET  /api/search?q=X      Search PubMed")
    print(f"    POST /api/batch           Batch lookup (JSON body)")
    print(f"    GET  /api/cache/stats     Cache statistics")
    print(f"")
    print(f"  Press Ctrl+C to stop")
    print(f"")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Shutting down...")
        server.shutdown()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='CitationSculptor HTTP Server')
    parser.add_argument('--port', '-p', type=int, default=3019, help='Port to listen on (default: 3019)')
    parser.add_argument('--host', '-H', type=str, default='127.0.0.1', help='Host to bind to (default: 127.0.0.1)')
    args = parser.parse_args()
    
    run_server(port=args.port, host=args.host)
