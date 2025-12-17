#!/usr/bin/env python3
"""
CitationSculptor HTTP API Server v2.0

A comprehensive HTTP server exposing all CitationSculptor v2.0 functionality:
- Citation lookup (PMID, DOI, PMC, arXiv, ISBN, title)
- PDF metadata extraction
- BibTeX/RIS import/export
- Citation database management
- Duplicate detection
- Bibliography generation
- Multiple citation styles

Usage:
    python -m mcp_server.http_server [--port 3019]
    
Web UI:
    Open http://127.0.0.1:3019 in your browser
"""

import sys
import json
import argparse
import mimetypes
import base64
import tempfile
import os
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from typing import Optional, Dict, Any, List
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from citation_lookup import CitationLookup, LookupResult
from modules.formatter_factory import get_available_styles, get_style_info
from modules.pdf_extractor import PDFExtractor, PYMUPDF_AVAILABLE
from modules.bibtex_handler import BibTeXParser, BibTeXExporter
from modules.ris_handler import RISParser, RISExporter
from modules.citation_database import CitationDatabase
from modules.duplicate_detector import DuplicateDetector
from modules.bibliography_generator import BibliographyGenerator
from modules.arxiv_client import ArxivClient
from modules.preprint_client import PreprintClient
from modules.book_client import BookClient
from modules.wayback_client import WaybackClient
from modules.openalex_client import OpenAlexClient
from modules.semantic_scholar_client import SemanticScholarClient

# Static files directory
WEB_DIR = Path(__file__).parent.parent / 'web'
DATA_DIR = Path(__file__).parent.parent / '.data'


class CitationHTTPHandler(BaseHTTPRequestHandler):
    """HTTP request handler for all CitationSculptor v2.0 functionality."""
    
    # Class-level singletons
    lookup: CitationLookup = None
    pdf_extractor: PDFExtractor = None
    bibtex_parser: BibTeXParser = None
    bibtex_exporter: BibTeXExporter = None
    ris_parser: RISParser = None
    ris_exporter: RISExporter = None
    citation_db: CitationDatabase = None
    duplicate_detector: DuplicateDetector = None
    bibliography_gen: BibliographyGenerator = None
    arxiv_client: ArxivClient = None
    preprint_client: PreprintClient = None
    book_client: BookClient = None
    wayback_client: WaybackClient = None
    openalex_client: OpenAlexClient = None
    semantic_scholar_client: SemanticScholarClient = None
    
    def log_message(self, format: str, *args) -> None:
        """Suppress logging for cleaner output."""
        pass
    
    def _send_json(self, data: Dict[str, Any], status: int = 200):
        """Send JSON response."""
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
        self.wfile.write(json.dumps(data, default=str).encode('utf-8'))
    
    def _send_file(self, filepath: Path):
        """Send a static file."""
        if not filepath.exists():
            self.send_error(404, 'File not found')
            return
        
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
    
    def _send_text(self, text: str, content_type: str = 'text/plain', filename: str = None):
        """Send text response with optional download filename."""
        self.send_response(200)
        self.send_header('Content-Type', content_type)
        self.send_header('Access-Control-Allow-Origin', '*')
        if filename:
            self.send_header('Content-Disposition', f'attachment; filename="{filename}"')
        self.end_headers()
        self.wfile.write(text.encode('utf-8'))
    
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
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    
    def do_GET(self):
        """Handle GET requests."""
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        
        # === Web UI ===
        if path == '/' or path == '/index.html':
            self._send_file(WEB_DIR / 'index.html')
            return
        
        if path.startswith('/static/') or path.endswith(('.css', '.js', '.ico', '.png', '.svg')):
            file_path = WEB_DIR / path.lstrip('/')
            if file_path.exists() and file_path.is_file():
                self._send_file(file_path)
                return
        
        # === Health & Info ===
        if path == '/health':
            self._send_json({
                'status': 'ok',
                'version': '2.0.0',
                'features': {
                    'pdf_support': PYMUPDF_AVAILABLE,
                    'citation_styles': get_available_styles(),
                    'database_enabled': self.citation_db is not None,
                }
            })
            return
        
        if path == '/api/styles':
            self._send_json({
                'styles': get_available_styles(),
                'info': get_style_info(),
                'default': 'vancouver'
            })
            return
        
        if path == '/api/capabilities':
            self._send_json({
                'lookup': ['pmid', 'doi', 'pmcid', 'arxiv', 'isbn', 'title', 'url'],
                'search': ['pubmed', 'openalex', 'semantic_scholar'],
                'import': ['bibtex', 'ris'],
                'export': ['bibtex', 'ris'],
                'features': ['pdf_extraction', 'duplicate_detection', 'bibliography_generation', 'citation_database'],
                'pdf_support': PYMUPDF_AVAILABLE,
            })
            return
        
        # === Citation Lookup ===
        if path == '/api/lookup':
            identifier = query.get('id', [None])[0]
            style = query.get('style', ['vancouver'])[0]
            if not identifier:
                self._send_json({'error': 'Missing id parameter'}, 400)
                return
            
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
        
        if path == '/api/lookup/arxiv':
            arxiv_id = query.get('id', [None])[0]
            if not arxiv_id:
                self._send_json({'error': 'Missing id parameter'}, 400)
                return
            try:
                metadata = self.arxiv_client.get_paper(arxiv_id)
                if metadata:
                    citation = self.lookup.formatter.format_preprint(metadata, original_number=0)
                    self._send_json({
                        'success': True,
                        'identifier': arxiv_id,
                        'identifier_type': 'arxiv',
                        'inline_mark': citation.label,
                        'full_citation': citation.formatted_text,
                        'metadata': {
                            'title': metadata.title,
                            'authors': metadata.authors,
                            'year': metadata.year,
                            'abstract': metadata.abstract[:500] if metadata.abstract else None,
                        }
                    })
                else:
                    self._send_json({'success': False, 'error': 'arXiv paper not found'})
            except Exception as e:
                self._send_json({'success': False, 'error': str(e)})
            return
        
        if path == '/api/lookup/isbn':
            isbn = query.get('isbn', [None])[0]
            if not isbn:
                self._send_json({'error': 'Missing isbn parameter'}, 400)
                return
            try:
                metadata = self.book_client.lookup_isbn(isbn)
                if metadata:
                    citation = self.lookup.formatter.format_book(metadata, original_number=0)
                    self._send_json({
                        'success': True,
                        'identifier': isbn,
                        'identifier_type': 'isbn',
                        'inline_mark': citation.label,
                        'full_citation': citation.formatted_text,
                        'metadata': {
                            'title': metadata.title,
                            'authors': metadata.authors,
                            'year': metadata.year,
                            'publisher': metadata.publisher,
                        }
                    })
                else:
                    self._send_json({'success': False, 'error': 'Book not found'})
            except Exception as e:
                self._send_json({'success': False, 'error': str(e)})
            return
        
        # === Search ===
        if path == '/api/search':
            q = query.get('q', [None])[0]
            source = query.get('source', ['pubmed'])[0]
            max_results = int(query.get('max', ['10'])[0])
            
            if not q:
                self._send_json({'error': 'Missing q parameter'}, 400)
                return
            
            results = []
            
            if source == 'pubmed':
                articles = self.lookup.pubmed_client.search_by_title(q, max_results=min(max_results, 50))
                for article in articles:
                    results.append({
                        'pmid': str(article.pmid) if article.pmid else None,
                        'title': str(article.title) if article.title else None,
                        'authors': list(article.authors) if article.authors else [],
                        'journal': str(article.journal_abbreviation or article.journal) if (article.journal_abbreviation or article.journal) else None,
                        'year': str(article.year) if article.year else None,
                        'doi': str(article.doi) if article.doi else None,
                        'source': 'pubmed',
                    })
            
            elif source == 'openalex':
                try:
                    works = self.openalex_client.search(q, max_results=min(max_results, 50))
                    for work in works:
                        results.append({
                            'id': work.openalex_id,
                            'title': work.title,
                            'authors': work.authors,
                            'journal': work.journal,
                            'year': work.year,
                            'doi': work.doi,
                            'cited_by_count': work.cited_by_count,
                            'source': 'openalex',
                        })
                except Exception as e:
                    self._send_json({'error': f'OpenAlex search failed: {e}'}, 500)
                    return
            
            elif source == 'semantic_scholar':
                try:
                    papers = self.semantic_scholar_client.search(q, limit=min(max_results, 50))
                    for paper in papers:
                        results.append({
                            'id': paper.paper_id,
                            'title': paper.title,
                            'authors': paper.authors,
                            'journal': paper.venue,
                            'year': paper.year,
                            'doi': paper.doi,
                            'citation_count': paper.citation_count,
                            'source': 'semantic_scholar',
                        })
                except Exception as e:
                    self._send_json({'error': f'Semantic Scholar search failed: {e}'}, 500)
                    return
            
            self._send_json({'results': results, 'count': len(results), 'source': source})
            return
        
        # === Cache ===
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
        
        # === Citation Database ===
        if path == '/api/library':
            limit = int(query.get('limit', ['50'])[0])
            offset = int(query.get('offset', ['0'])[0])
            tag = query.get('tag', [None])[0]
            
            if self.citation_db:
                if tag:
                    citations = self.citation_db.get_by_tag(tag)
                else:
                    citations = self.citation_db.get_all(limit=limit, offset=offset)
                
                self._send_json({
                    'citations': [self._citation_to_dict(c) for c in citations],
                    'count': len(citations),
                    'total': self.citation_db.count(),
                })
            else:
                self._send_json({'citations': [], 'count': 0, 'total': 0})
            return
        
        if path == '/api/library/search':
            q = query.get('q', [None])[0]
            if not q:
                self._send_json({'error': 'Missing q parameter'}, 400)
                return
            
            if self.citation_db:
                citations = self.citation_db.search(q)
                self._send_json({
                    'citations': [self._citation_to_dict(c) for c in citations],
                    'count': len(citations),
                })
            else:
                self._send_json({'citations': [], 'count': 0})
            return
        
        if path == '/api/library/tags':
            if self.citation_db:
                tags = self.citation_db.get_all_tags()
                self._send_json({'tags': tags})
            else:
                self._send_json({'tags': []})
            return
        
        if path == '/api/library/collections':
            if self.citation_db:
                collections = self.citation_db.get_all_collections()
                self._send_json({'collections': collections})
            else:
                self._send_json({'collections': []})
            return
        
        # === Export ===
        if path == '/api/export/bibtex':
            ids = query.get('ids', [''])[0]
            if not ids:
                self._send_json({'error': 'Missing ids parameter'}, 400)
                return
            
            id_list = [int(i) for i in ids.split(',') if i.strip()]
            if self.citation_db and id_list:
                entries = []
                for cid in id_list:
                    citation = self.citation_db.get(cid)
                    if citation:
                        entry = self.bibtex_exporter.metadata_to_entry(citation.metadata_dict)
                        entries.append(entry.to_bibtex())
                
                bibtex_text = "\n\n".join(entries)
                self._send_text(bibtex_text, 'application/x-bibtex', 'citations.bib')
            else:
                self._send_json({'error': 'No citations found'}, 404)
            return
        
        if path == '/api/export/ris':
            ids = query.get('ids', [''])[0]
            if not ids:
                self._send_json({'error': 'Missing ids parameter'}, 400)
                return
            
            id_list = [int(i) for i in ids.split(',') if i.strip()]
            if self.citation_db and id_list:
                entries = []
                for cid in id_list:
                    citation = self.citation_db.get(cid)
                    if citation:
                        entry = self.ris_exporter.metadata_to_entry(citation.metadata_dict)
                        entries.append(entry.to_ris())
                
                ris_text = "\n".join(entries)
                self._send_text(ris_text, 'application/x-research-info-systems', 'citations.ris')
            else:
                self._send_json({'error': 'No citations found'}, 404)
            return
        
        # Default: 404
        self._send_json({'error': f'Unknown endpoint: {path}'}, 404)
    
    def do_POST(self):
        """Handle POST requests."""
        parsed = urlparse(self.path)
        path = parsed.path
        
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8') if content_length > 0 else '{}'
        
        try:
            data = json.loads(body) if body else {}
        except json.JSONDecodeError:
            self._send_json({'error': 'Invalid JSON'}, 400)
            return
        
        # === Lookup ===
        if path == '/api/lookup':
            identifier = data.get('identifier') or data.get('id')
            style = data.get('style', 'vancouver')
            if not identifier:
                self._send_json({'error': 'Missing identifier'}, 400)
                return
            
            if style != self.lookup.style:
                self.lookup.set_style(style)
            
            result = self.lookup.lookup_auto(identifier)
            self._send_json(self._format_result(result))
            return
        
        if path == '/api/batch':
            identifiers = data.get('identifiers', [])
            style = data.get('style', 'vancouver')
            if not identifiers:
                self._send_json({'error': 'Missing identifiers array'}, 400)
                return
            
            if style != self.lookup.style:
                self.lookup.set_style(style)
            
            results = self.lookup.batch_lookup(identifiers)
            self._send_json({
                'results': [self._format_result(r) for r in results],
                'count': len(results),
                'success_count': sum(1 for r in results if r.success),
            })
            return
        
        # === PDF Extraction ===
        if path == '/api/pdf/extract':
            if not PYMUPDF_AVAILABLE:
                self._send_json({'error': 'PDF support not available. Install PyMuPDF: pip install PyMuPDF'}, 503)
                return
            
            # Handle base64-encoded PDF
            pdf_data = data.get('pdf_base64')
            if not pdf_data:
                self._send_json({'error': 'Missing pdf_base64 field'}, 400)
                return
            
            try:
                pdf_bytes = base64.b64decode(pdf_data)
                
                with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
                    tmp.write(pdf_bytes)
                    tmp_path = tmp.name
                
                try:
                    metadata = self.pdf_extractor.extract(tmp_path)
                    
                    response = {
                        'success': True,
                        'metadata': {
                            'title': metadata.title,
                            'authors': metadata.authors,
                            'doi': metadata.doi,
                            'arxiv_id': metadata.arxiv_id,
                            'pmid': metadata.pmid,
                            'creation_date': metadata.creation_date,
                            'page_count': metadata.page_count,
                            'has_identifier': metadata.has_identifier,
                        }
                    }
                    
                    # If we found an identifier, look it up
                    if metadata.has_identifier:
                        id_type, id_value = metadata.best_identifier
                        result = self.lookup.lookup_auto(id_value)
                        if result.success:
                            response['citation'] = self._format_result(result)
                    
                    self._send_json(response)
                finally:
                    os.unlink(tmp_path)
                    
            except Exception as e:
                self._send_json({'success': False, 'error': str(e)}, 500)
            return
        
        # === Import ===
        if path == '/api/import/bibtex':
            bibtex_text = data.get('bibtex')
            if not bibtex_text:
                self._send_json({'error': 'Missing bibtex field'}, 400)
                return
            
            try:
                entries = self.bibtex_parser.parse_string(bibtex_text)
                results = []
                
                for entry in entries:
                    # Try to look up by DOI if available
                    if entry.doi:
                        result = self.lookup.lookup_doi(entry.doi)
                        if result.success:
                            results.append(self._format_result(result))
                            continue
                    
                    # Otherwise, return parsed entry info
                    results.append({
                        'success': True,
                        'identifier': entry.cite_key,
                        'identifier_type': 'bibtex',
                        'inline_mark': f'[^{entry.cite_key}]',
                        'full_citation': f"{', '.join(entry.authors)}. {entry.title}. {entry.year}.",
                        'metadata': entry.fields,
                    })
                
                self._send_json({
                    'imported': len(results),
                    'results': results,
                })
            except Exception as e:
                self._send_json({'error': str(e)}, 500)
            return
        
        if path == '/api/import/ris':
            ris_text = data.get('ris')
            if not ris_text:
                self._send_json({'error': 'Missing ris field'}, 400)
                return
            
            try:
                entries = self.ris_parser.parse_string(ris_text)
                results = []
                
                for entry in entries:
                    # Try to look up by DOI if available
                    if entry.doi:
                        result = self.lookup.lookup_doi(entry.doi)
                        if result.success:
                            results.append(self._format_result(result))
                            continue
                    
                    # Otherwise, return parsed entry info
                    results.append({
                        'success': True,
                        'identifier': entry.title[:30] if entry.title else 'Unknown',
                        'identifier_type': 'ris',
                        'inline_mark': '',
                        'full_citation': f"{', '.join(entry.authors)}. {entry.title}. {entry.year}.",
                        'metadata': entry.fields,
                    })
                
                self._send_json({
                    'imported': len(results),
                    'results': results,
                })
            except Exception as e:
                self._send_json({'error': str(e)}, 500)
            return
        
        # === Citation Database ===
        if path == '/api/library/save':
            if not self.citation_db:
                self._send_json({'error': 'Database not available'}, 503)
                return
            
            citation_data = data.get('citation')
            if not citation_data:
                self._send_json({'error': 'Missing citation field'}, 400)
                return
            
            try:
                citation_id = self.citation_db.save(
                    identifier_type=citation_data.get('identifier_type', 'unknown'),
                    identifier=citation_data.get('identifier', ''),
                    title=citation_data.get('title', ''),
                    authors=citation_data.get('authors', []),
                    year=citation_data.get('year', ''),
                    citation_style=citation_data.get('style', 'vancouver'),
                    inline_mark=citation_data.get('inline_mark', ''),
                    full_citation=citation_data.get('full_citation', ''),
                    metadata=citation_data.get('metadata', {}),
                    tags=citation_data.get('tags', []),
                )
                self._send_json({'success': True, 'id': citation_id})
            except Exception as e:
                self._send_json({'error': str(e)}, 500)
            return
        
        if path == '/api/library/update':
            if not self.citation_db:
                self._send_json({'error': 'Database not available'}, 503)
                return
            
            citation_id = data.get('id')
            updates = data.get('updates', {})
            if not citation_id:
                self._send_json({'error': 'Missing id field'}, 400)
                return
            
            try:
                self.citation_db.update(citation_id, **updates)
                self._send_json({'success': True})
            except Exception as e:
                self._send_json({'error': str(e)}, 500)
            return
        
        # === Duplicate Detection ===
        if path == '/api/duplicates/check':
            citations = data.get('citations', [])
            if not citations:
                self._send_json({'error': 'Missing citations array'}, 400)
                return
            
            try:
                groups = self.duplicate_detector.find_duplicates(citations)
                self._send_json({
                    'duplicate_groups': groups,
                    'total_duplicates': sum(len(g) - 1 for g in groups if len(g) > 1),
                })
            except Exception as e:
                self._send_json({'error': str(e)}, 500)
            return
        
        # === Bibliography Generation ===
        if path == '/api/bibliography/extract':
            text = data.get('text')
            if not text:
                self._send_json({'error': 'Missing text field'}, 400)
                return
            
            try:
                refs = self.bibliography_gen.extract_citations(text)
                self._send_json({
                    'references': [
                        {
                            'inline_mark': r.inline_mark,
                            'line_number': r.line_number,
                            'context': r.context,
                        }
                        for r in refs
                    ],
                    'count': len(refs),
                })
            except Exception as e:
                self._send_json({'error': str(e)}, 500)
            return
        
        if path == '/api/bibliography/generate':
            identifiers = data.get('identifiers', [])
            style = data.get('style', 'vancouver')
            sort_order = data.get('sort', 'alphabetical')
            
            if not identifiers:
                self._send_json({'error': 'Missing identifiers array'}, 400)
                return
            
            try:
                if style != self.lookup.style:
                    self.lookup.set_style(style)
                
                results = self.lookup.batch_lookup(identifiers)
                successful = [r for r in results if r.success]
                
                # Sort as requested
                if sort_order == 'alphabetical':
                    successful.sort(key=lambda r: r.full_citation.lower() if r.full_citation else '')
                elif sort_order == 'year':
                    successful.sort(key=lambda r: r.metadata.get('year', '0000'), reverse=True)
                
                bibliography = "\n\n".join([r.full_citation for r in successful if r.full_citation])
                
                self._send_json({
                    'bibliography': bibliography,
                    'entries': len(successful),
                    'failed': len(results) - len(successful),
                })
            except Exception as e:
                self._send_json({'error': str(e)}, 500)
            return
        
        # Default: 404
        self._send_json({'error': f'Unknown endpoint: {path}'}, 404)
    
    def do_DELETE(self):
        """Handle DELETE requests."""
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        
        if path == '/api/library/delete':
            citation_id = query.get('id', [None])[0]
            if not citation_id:
                self._send_json({'error': 'Missing id parameter'}, 400)
                return
            
            if self.citation_db:
                try:
                    self.citation_db.delete(int(citation_id))
                    self._send_json({'success': True})
                except Exception as e:
                    self._send_json({'error': str(e)}, 500)
            else:
                self._send_json({'error': 'Database not available'}, 503)
            return
        
        self._send_json({'error': f'Unknown endpoint: {path}'}, 404)
    
    def _citation_to_dict(self, citation) -> Dict[str, Any]:
        """Convert StoredCitation to dict."""
        return {
            'id': citation.id,
            'identifier_type': citation.identifier_type,
            'identifier': citation.identifier,
            'title': citation.title,
            'authors': citation.authors_list,
            'year': citation.year,
            'style': citation.citation_style,
            'inline_mark': citation.inline_mark,
            'full_citation': citation.full_citation,
            'tags': citation.tags_list,
            'notes': citation.notes,
            'created_at': citation.created_at,
        }


def run_server(port: int = 3019, host: str = '127.0.0.1'):
    """Start the HTTP server."""
    # Ensure data directory exists
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    # Initialize all handlers
    CitationHTTPHandler.lookup = CitationLookup()
    CitationHTTPHandler.pdf_extractor = PDFExtractor()
    CitationHTTPHandler.bibtex_parser = BibTeXParser()
    CitationHTTPHandler.bibtex_exporter = BibTeXExporter()
    CitationHTTPHandler.ris_parser = RISParser()
    CitationHTTPHandler.ris_exporter = RISExporter()
    CitationHTTPHandler.citation_db = CitationDatabase(str(DATA_DIR / 'citations.db'))
    CitationHTTPHandler.duplicate_detector = DuplicateDetector()
    CitationHTTPHandler.bibliography_gen = BibliographyGenerator()
    CitationHTTPHandler.arxiv_client = ArxivClient()
    CitationHTTPHandler.preprint_client = PreprintClient()
    CitationHTTPHandler.book_client = BookClient()
    CitationHTTPHandler.wayback_client = WaybackClient()
    CitationHTTPHandler.openalex_client = OpenAlexClient()
    CitationHTTPHandler.semantic_scholar_client = SemanticScholarClient()
    
    server = HTTPServer((host, port), CitationHTTPHandler)
    
    print(f"")
    print(f"  ╔═══════════════════════════════════════════════════════════════╗")
    print(f"  ║           📚 CitationSculptor HTTP Server v2.0.0              ║")
    print(f"  ╚═══════════════════════════════════════════════════════════════╝")
    print(f"")
    print(f"  🌐 Web UI:    http://{host}:{port}")
    print(f"  📡 API Base:  http://{host}:{port}/api")
    print(f"")
    print(f"  Features:")
    print(f"    ✓ Multi-source lookup (PubMed, arXiv, ISBN, DOI)")
    print(f"    ✓ Multiple citation styles (Vancouver, APA, MLA, etc.)")
    print(f"    {'✓' if PYMUPDF_AVAILABLE else '✗'} PDF metadata extraction")
    print(f"    ✓ BibTeX/RIS import & export")
    print(f"    ✓ Citation library with search")
    print(f"    ✓ Duplicate detection")
    print(f"    ✓ Bibliography generation")
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
