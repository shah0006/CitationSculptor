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
from modules.reference_parser import ReferenceParser, ParsedReference
from modules.type_detector import CitationTypeDetector, CitationType
from modules.inline_replacer import InlineReplacer
from modules.arxiv_client import ArxivClient
from modules.preprint_client import PreprintClient
from modules.book_client import BookClient
from modules.wayback_client import WaybackClient
from modules.openalex_client import OpenAlexClient
from modules.semantic_scholar_client import SemanticScholarClient
from modules.pubmed_client import WebpageScraper
from modules.learning_engine import get_learning_engine, LearningEngine
from modules.document_intelligence import (
    DocumentIntelligence,
    LinkVerifier,
    CitationSuggestor,
    PlagiarismChecker,
    verify_document_links,
    suggest_document_citations,
    check_citation_compliance,
)
from modules.config import config, resolve_vault_path
from modules.settings_manager import settings_manager, get_settings, update_settings

from loguru import logger
from modules.logging_setup import setup_logging, log_document_operation, init_from_config, get_recent_logs, get_log_directory
from modules.config import VERSION

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
    type_detector: CitationTypeDetector = None
    arxiv_client: ArxivClient = None
    preprint_client: PreprintClient = None
    book_client: BookClient = None
    wayback_client: WaybackClient = None
    openalex_client: OpenAlexClient = None
    semantic_scholar_client: SemanticScholarClient = None
    document_intelligence: DocumentIntelligence = None
    
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
    
    def _list_directories(self, path: str) -> list:
        """List subdirectories in a path (for folder browser)."""
        import os
        try:
            entries = []
            for entry in sorted(os.listdir(path)):
                # Skip hidden files/folders
                if entry.startswith('.'):
                    continue
                full_path = os.path.join(path, entry)
                if os.path.isdir(full_path):
                    try:
                        # Check if we can access it
                        os.listdir(full_path)
                        entries.append({
                            'name': entry,
                            'path': full_path,
                            'is_obsidian_vault': self._is_obsidian_vault(full_path),
                        })
                    except PermissionError:
                        # Skip inaccessible directories
                        pass
            return entries
        except Exception:
            return []
    
    def _is_obsidian_vault(self, path: str) -> bool:
        """Check if a directory is an Obsidian vault (contains .obsidian folder)."""
        import os
        obsidian_dir = os.path.join(path, '.obsidian')
        return os.path.isdir(obsidian_dir)
    
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
        if path == '/api/about' or path == '/api/readme':
            readme_path = Path(__file__).parent.parent / 'README.md'
            if readme_path.exists():
                with open(readme_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                self._send_json({
                    'content': content,
                    'version': '2.1.0',
                })
            else:
                self._send_json({'error': 'README not found'}, 404)
            return
        
        if path == '/health':
            self._send_json({
                'status': 'ok',
                'version': '2.1.0',
                'features': {
                    'pdf_support': PYMUPDF_AVAILABLE,
                    'citation_styles': get_available_styles(),
                    'database_enabled': self.citation_db is not None,
                    'document_intelligence': True,
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
                'features': [
                    'document_processing', 'pdf_extraction', 'duplicate_detection', 
                    'bibliography_generation', 'citation_database',
                    'link_verification', 'citation_suggestions', 'citation_compliance',
                ],
                'pdf_support': PYMUPDF_AVAILABLE,
                'document_intelligence': {
                    'link_verification': True,
                    'citation_suggestions': True,
                    'plagiarism_check': True,
                    'llm_extraction': True,
                },
                'obsidian_vault_path': config.OBSIDIAN_VAULT_PATH or None,
            })
            return
        
        # === Vault Configuration (legacy - use /api/settings instead) ===
        if path == '/api/config/vault':
            vault_path = settings_manager.get_obsidian_vault_path()
            self._send_json({
                'configured': bool(vault_path),
                'path': vault_path or None,
                'hint': 'Configure via Settings page or set OBSIDIAN_VAULT_PATH in .env',
            })
            return
        
        # === Native Folder Picker (macOS) ===
        if path == '/api/pick-folder':
            import subprocess
            import platform
            
            if platform.system() != 'Darwin':
                self._send_json({'error': 'Native folder picker only available on macOS'}, 400)
                return
            
            try:
                # Use AppleScript to show native macOS folder picker
                script = '''
                    tell application "System Events"
                        activate
                    end tell
                    set chosenFolder to choose folder with prompt "Select your Obsidian Vault folder:"
                    return POSIX path of chosenFolder
                '''
                result = subprocess.run(
                    ['osascript', '-e', script],
                    capture_output=True,
                    text=True,
                    timeout=120  # 2 minute timeout for user to select
                )
                
                if result.returncode == 0 and result.stdout.strip():
                    folder_path = result.stdout.strip().rstrip('/')
                    self._send_json({
                        'success': True,
                        'path': folder_path,
                        'is_obsidian_vault': self._is_obsidian_vault(folder_path),
                    })
                else:
                    # User cancelled
                    self._send_json({
                        'success': False,
                        'cancelled': True,
                    })
            except subprocess.TimeoutExpired:
                self._send_json({'error': 'Folder picker timed out'}, 408)
            except Exception as e:
                self._send_json({'error': str(e)}, 500)
            return
        
        # === Directory Browser (fallback for non-macOS or manual browsing) ===
        if path == '/api/browse-directories':
            browse_path = query.get('path', [None])[0]
            
            # Default starting locations
            if not browse_path:
                import os
                home = os.path.expanduser('~')
                self._send_json({
                    'current': home,
                    'parent': os.path.dirname(home) if home != '/' else None,
                    'directories': self._list_directories(home),
                    'is_obsidian_vault': self._is_obsidian_vault(home),
                })
                return
            
            import os
            # Validate and resolve path
            try:
                resolved = os.path.abspath(os.path.expanduser(browse_path))
                if not os.path.isdir(resolved):
                    self._send_json({'error': 'Not a valid directory'}, 400)
                    return
                
                parent = os.path.dirname(resolved) if resolved != '/' else None
                
                self._send_json({
                    'current': resolved,
                    'parent': parent,
                    'directories': self._list_directories(resolved),
                    'is_obsidian_vault': self._is_obsidian_vault(resolved),
                })
            except Exception as e:
                self._send_json({'error': str(e)}, 400)
            return
        
        # === Settings API ===
        if path == '/api/settings':
            settings = get_settings()
            self._send_json({
                'settings': settings.to_dict(),
                'available_styles': get_available_styles(),
            })
            return
        
        # Lightweight endpoint - returns only the timestamp (for efficient polling)
        if path == '/api/settings/modified':
            settings = get_settings()
            self._send_json({
                'last_modified': settings.last_modified,
            })
            return
        
        # === Logging API ===
        if path == '/api/logs':
            max_lines = int(query.get('lines', ['100'])[0])
            log_type = query.get('type', ['main'])[0]  # main, errors, processing
            
            log_dir = get_log_directory()
            
            log_files = {
                'main': log_dir / 'citationsculptor.log',
                'errors': log_dir / 'errors.log',
                'processing': log_dir / 'document_processing.log',
            }
            
            log_file = log_files.get(log_type, log_files['main'])
            
            if log_file.exists():
                try:
                    with open(log_file, 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                        recent = lines[-max_lines:] if len(lines) > max_lines else lines
                    
                    self._send_json({
                        'success': True,
                        'log_type': log_type,
                        'log_file': str(log_file),
                        'total_lines': len(lines),
                        'returned_lines': len(recent),
                        'content': ''.join(recent),
                    })
                except Exception as e:
                    self._send_json({'error': f'Failed to read log: {e}'}, 500)
            else:
                self._send_json({
                    'success': True,
                    'log_type': log_type,
                    'log_file': str(log_file),
                    'total_lines': 0,
                    'returned_lines': 0,
                    'content': 'Log file not found. Logging may not be enabled.',
                })
            return
        
        if path == '/api/logs/info':
            log_dir = get_log_directory()
            
            log_files = []
            if log_dir.exists():
                for f in log_dir.iterdir():
                    if f.is_file():
                        log_files.append({
                            'name': f.name,
                            'path': str(f),
                            'size_bytes': f.stat().st_size,
                            'modified': f.stat().st_mtime,
                        })
            
            self._send_json({
                'log_directory': str(log_dir),
                'files': sorted(log_files, key=lambda x: x['modified'], reverse=True),
            })
            return
        
        # === Learning Engine API ===
        if path == '/api/learning/stats':
            learning = get_learning_engine()
            stats = learning.get_failure_stats()
            self._send_json({
                'success': True,
                'stats': stats,
            })
            return
        
        if path == '/api/learning/export':
            learning = get_learning_engine()
            data = learning.export_learnings()
            self._send_json({
                'success': True,
                'data': data,
            })
            return
        
        # === Document Intelligence - Link Verification ===
        if path == '/api/verify-link':
            url = query.get('url', [None])[0]
            if not url:
                self._send_json({'error': 'Missing url parameter'}, 400)
                return
            
            result = self.document_intelligence.verify_single_link(url)
            self._send_json(result)
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
        
        # === Settings API ===
        if path == '/api/settings':
            try:
                success = update_settings(data)
                if success:
                    # Reload the settings manager to reflect changes
                    settings_manager.load()
                    self._send_json({
                        'success': True,
                        'message': 'Settings updated successfully',
                        'settings': get_settings().to_dict(),
                    })
                else:
                    self._send_json({'error': 'Failed to save settings'}, 500)
            except Exception as e:
                self._send_json({'error': str(e)}, 500)
            return
        
        # === Learning Engine API - Add Correction ===
        if path == '/api/learning/correction':
            url = data.get('url')
            title = data.get('title')
            identifier = data.get('identifier')
            identifier_type = data.get('identifier_type')  # 'pmid', 'doi', 'pmcid'
            
            if not identifier or not identifier_type:
                self._send_json({'error': 'Missing identifier or identifier_type'}, 400)
                return
            
            if identifier_type not in ['pmid', 'doi', 'pmcid']:
                self._send_json({'error': 'Invalid identifier_type. Must be pmid, doi, or pmcid'}, 400)
                return
            
            learning = get_learning_engine()
            learning.add_user_correction(
                original_url=url,
                original_title=title,
                correct_identifier=identifier,
                identifier_type=identifier_type,
                source='api'
            )
            
            self._send_json({
                'success': True,
                'message': f'Correction recorded: {identifier_type}={identifier}',
            })
            return
        
        # === Learning Engine API - Import Learnings ===
        if path == '/api/learning/import':
            learning = get_learning_engine()
            try:
                learning.import_learnings(data)
                self._send_json({
                    'success': True,
                    'message': 'Learnings imported successfully',
                })
            except Exception as e:
                self._send_json({'error': f'Import failed: {e}'}, 500)
            return
        
        # === Restore from Backup API ===
        if path == '/api/restore-backup':
            backup_path = data.get('backup_path')
            target_path = data.get('target_path')
            
            logger.info(f"Restore request - backup: {backup_path}, target: {target_path}")
            
            if not backup_path:
                self._send_json({'error': 'Missing backup_path'}, 400)
                return
            
            # Resolve backup path (might be relative to vault)
            resolved_backup = Path(backup_path)
            if not resolved_backup.is_absolute() and config.OBSIDIAN_VAULT_PATH:
                resolved_backup = Path(config.OBSIDIAN_VAULT_PATH) / backup_path
            backup_path = str(resolved_backup)
            
            # If target_path not provided, infer it from backup_path
            # Backup format: filename_backup_YYYYMMDD_HHMMSS.ext
            if not target_path:
                import re
                # Try to extract original filename from backup
                match = re.search(r'^(.+)_backup_\d{8}_\d{6}(\.[^.]+)$', backup_path)
                if match:
                    target_path = match.group(1) + match.group(2)
                    logger.info(f"Inferred target path from backup: {target_path}")
                else:
                    logger.error(f"Could not parse backup filename: {backup_path}")
                    self._send_json({'error': f'Could not determine target path from backup filename: {backup_path}'}, 400)
                    return
            else:
                # Resolve target path if relative
                resolved_target = Path(target_path)
                if not resolved_target.is_absolute() and config.OBSIDIAN_VAULT_PATH:
                    target_path = str(Path(config.OBSIDIAN_VAULT_PATH) / target_path)
            
            try:
                # Verify backup exists
                logger.info(f"Checking backup exists: {backup_path}")
                if not os.path.exists(backup_path):
                    self._send_json({'error': f'Backup file not found: {backup_path}'}, 404)
                    return
                
                # Read backup content
                with open(backup_path, 'r', encoding='utf-8') as f:
                    backup_content = f.read()
                
                # Write to target
                with open(target_path, 'w', encoding='utf-8') as f:
                    f.write(backup_content)
                
                logger.info(f"Restored {target_path} from backup {backup_path}")
                log_document_operation("restore", target_path, {
                    "backup_used": backup_path,
                    "success": True
                })
                
                self._send_json({
                    'success': True,
                    'message': f'Successfully restored from backup',
                    'restored_path': target_path,
                    'backup_used': backup_path,
                })
            except Exception as e:
                logger.error(f"Restore failed: {e}")
                self._send_json({'error': f'Restore failed: {str(e)}'}, 500)
            return
        
        if path == '/api/settings/reset':
            try:
                success = settings_manager.reset_to_defaults()
                if success:
                    self._send_json({
                        'success': True,
                        'message': 'Settings reset to defaults',
                        'settings': get_settings().to_dict(),
                    })
                else:
                    self._send_json({'error': 'Failed to reset settings'}, 500)
            except Exception as e:
                self._send_json({'error': str(e)}, 500)
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
        
        # === Document Processing ===
        # === Streaming Document Processing with Progress ===
        if path == '/api/process-document-stream':
            content = data.get('content')
            file_path = data.get('file_path')
            style = data.get('style', 'vancouver')
            create_backup = data.get('create_backup', True)
            save_to_file = data.get('save_to_file', False)
            
            backup_path = None
            resolved_file_path = None
            
            # Get content from file or direct input
            if file_path:
                try:
                    resolved_file_path = resolve_vault_path(file_path)
                    with open(resolved_file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    if create_backup or save_to_file:
                        backup_path = self._create_backup(resolved_file_path, content)
                        
                except FileNotFoundError:
                    self._send_sse_error(f'File not found: {file_path}')
                    return
                except Exception as e:
                    self._send_sse_error(f'Error reading file: {e}')
                    return
            
            if not content:
                self._send_sse_error('Missing content or file_path')
                return
            
            # Process with streaming progress
            try:
                self._process_document_with_progress(
                    content, style, backup_path, resolved_file_path, save_to_file
                )
            except Exception as e:
                self._send_sse_error(str(e), backup_path)
            return
        
        if path == '/api/process-document':
            content = data.get('content')
            file_path = data.get('file_path')
            style = data.get('style', 'vancouver')
            create_backup = data.get('create_backup', True)  # Default: create backup when file_path provided
            save_to_file = data.get('save_to_file', False)  # Option to save processed content back to file
            
            backup_path = None
            resolved_file_path = None
            
            # Get content from file or direct input
            if file_path:
                try:
                    resolved_file_path = resolve_vault_path(file_path)
                    with open(resolved_file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # Create backup before processing (safety feature)
                    # Always create backup when save_to_file is True
                    if create_backup or save_to_file:
                        backup_path = self._create_backup(resolved_file_path, content)
                        
                except FileNotFoundError:
                    self._send_json({'error': f'File not found: {file_path}'}, 404)
                    return
                except Exception as e:
                    self._send_json({'error': f'Error reading file: {e}'}, 500)
                    return
            
            if not content:
                self._send_json({'error': 'Missing content or file_path'}, 400)
                return
            
            try:
                result = self._process_document_content(content, style)
                
                # Include backup path in response
                if backup_path:
                    result['backup_path'] = backup_path
                
                # Save processed content back to original file if requested
                if save_to_file and resolved_file_path and result.get('success'):
                    try:
                        with open(resolved_file_path, 'w', encoding='utf-8') as f:
                            f.write(result['processed_content'])
                        result['saved_to_file'] = True
                        result['saved_path'] = str(resolved_file_path)
                        result['message'] = f'Processed document saved to: {resolved_file_path}'
                        logger.info(f"Saved processed document to: {resolved_file_path}")
                        log_document_operation("save", str(resolved_file_path), {
                            "backup_path": backup_path,
                            "refs_processed": result.get('statistics', {}).get('processed', 0),
                            "refs_failed": result.get('statistics', {}).get('failed', 0)
                        })
                    except Exception as e:
                        result['saved_to_file'] = False
                        result['save_error'] = str(e)
                        result['message'] = f'Processing succeeded but failed to save: {e}. Backup available at: {backup_path}'
                        logger.error(f"Failed to save processed document: {e}")
                
                self._send_json(result)
            except Exception as e:
                error_response = {'error': str(e)}
                if backup_path:
                    error_response['backup_path'] = backup_path
                    error_response['message'] = f'Processing failed, but backup is available at: {backup_path}'
                self._send_json(error_response, 500)
            return
        
        # === Document Intelligence - Full Analysis ===
        if path == '/api/analyze-document':
            content = data.get('content')
            file_path = data.get('file_path')
            verify_links = data.get('verify_links', True)
            suggest_citations = data.get('suggest_citations', True)
            check_plagiarism = data.get('check_plagiarism', True)
            search_suggestions = data.get('search_suggestions', False)
            
            # Get content from file or direct input
            if file_path:
                try:
                    file_path = resolve_vault_path(file_path)
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                except FileNotFoundError:
                    self._send_json({'error': f'File not found: {file_path}'}, 404)
                    return
                except Exception as e:
                    self._send_json({'error': f'Error reading file: {e}'}, 500)
                    return
            
            if not content:
                self._send_json({'error': 'Missing content or file_path'}, 400)
                return
            
            try:
                result = self.document_intelligence.analyze_document(
                    content,
                    verify_links=verify_links,
                    suggest_citations=suggest_citations,
                    check_plagiarism=check_plagiarism,
                    search_suggestions=search_suggestions,
                )
                self._send_json(result)
            except Exception as e:
                self._send_json({'error': str(e)}, 500)
            return
        
        # === Document Intelligence - Link Verification ===
        if path == '/api/verify-links':
            content = data.get('content')
            file_path = data.get('file_path')
            urls = data.get('urls')  # Can also pass URLs directly
            
            # Get content from file or direct input
            if file_path:
                try:
                    file_path = resolve_vault_path(file_path)
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                except Exception as e:
                    self._send_json({'error': f'Error reading file: {e}'}, 500)
                    return
            
            if urls:
                # Verify provided URLs directly
                try:
                    results = self.document_intelligence.verify_links_batch(urls)
                    self._send_json({
                        'verified': len(results),
                        'results': results,
                    })
                except Exception as e:
                    self._send_json({'error': str(e)}, 500)
                return
            
            if not content:
                self._send_json({'error': 'Missing content, file_path, or urls'}, 400)
                return
            
            try:
                result = verify_document_links(content)
                self._send_json(result)
            except Exception as e:
                self._send_json({'error': str(e)}, 500)
            return
        
        # === Document Intelligence - Citation Suggestions ===
        if path == '/api/suggest-citations':
            content = data.get('content')
            file_path = data.get('file_path')
            search_pubmed = data.get('search_pubmed', False)
            
            # Get content from file or direct input
            if file_path:
                try:
                    file_path = resolve_vault_path(file_path)
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                except Exception as e:
                    self._send_json({'error': f'Error reading file: {e}'}, 500)
                    return
            
            if not content:
                self._send_json({'error': 'Missing content or file_path'}, 400)
                return
            
            try:
                suggestor = CitationSuggestor(
                    pubmed_client=self.lookup.pubmed_client if search_pubmed else None
                )
                suggestions = suggestor.analyze_document(content, search_suggestions=search_pubmed)
                self._send_json({
                    'count': len(suggestions),
                    'suggestions': [s.to_dict() for s in suggestions],
                })
            except Exception as e:
                self._send_json({'error': str(e)}, 500)
            return
        
        # === Document Intelligence - Citation Compliance (Plagiarism Check) ===
        if path == '/api/check-compliance':
            content = data.get('content')
            file_path = data.get('file_path')
            
            # Get content from file or direct input
            if file_path:
                try:
                    file_path = resolve_vault_path(file_path)
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                except Exception as e:
                    self._send_json({'error': f'Error reading file: {e}'}, 500)
                    return
            
            if not content:
                self._send_json({'error': 'Missing content or file_path'}, 400)
                return
            
            try:
                result = check_citation_compliance(content)
                self._send_json(result)
            except Exception as e:
                self._send_json({'error': str(e)}, 500)
            return
        
        # === Document Intelligence - LLM Metadata Extraction ===
        if path == '/api/extract-metadata-llm':
            url = data.get('url')
            html_content = data.get('html_content')
            
            if not url or not html_content:
                self._send_json({'error': 'Missing url or html_content'}, 400)
                return
            
            try:
                result = self.document_intelligence.extract_metadata_llm(url, html_content)
                if result:
                    self._send_json({'success': True, 'metadata': result})
                else:
                    self._send_json({
                        'success': False, 
                        'error': 'LLM extraction failed or not available'
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
    
    def _send_sse_event(self, event_type: str, data: dict):
        """Send a Server-Sent Event."""
        import json
        event_data = json.dumps(data)
        self.wfile.write(f"event: {event_type}\n".encode('utf-8'))
        self.wfile.write(f"data: {event_data}\n\n".encode('utf-8'))
        self.wfile.flush()
    
    def _send_sse_error(self, error: str, backup_path: str = None):
        """Send an SSE error and close the stream."""
        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream')
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('Connection', 'keep-alive')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        
        error_data = {'error': error}
        if backup_path:
            error_data['backup_path'] = backup_path
        self._send_sse_event('error', error_data)
    
    def _process_document_with_progress(self, content: str, style: str, 
                                         backup_path: str = None, 
                                         resolved_file_path: str = None,
                                         save_to_file: bool = False):
        """Process document with streaming progress updates via SSE."""
        # Send SSE headers
        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream')
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('Connection', 'keep-alive')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        
        # Send initial status
        self._send_sse_event('status', {
            'phase': 'analyzing',
            'message': 'Analyzing document structure...',
        })
        
        # Analyze document statistics
        doc_stats = self._analyze_document_statistics(content)
        self._send_sse_event('analysis', {
            'document_stats': doc_stats,
            'message': 'Document analysis complete',
        })
        
        # Set citation style
        if style != self.lookup.style:
            self.lookup.set_style(style)
        
        # Parse references
        self._send_sse_event('status', {
            'phase': 'parsing',
            'message': 'Finding references in document...',
        })
        
        parser = ReferenceParser(content)
        parser.find_reference_section()
        parser.parse_references()
        
        total_refs = len(parser.references) if parser.references else 0
        
        self._send_sse_event('refs_found', {
            'total': total_refs,
            'message': f'Found {total_refs} references to process',
        })
        
        if not parser.references:
            # No references to process
            result = {
                'success': True,
                'message': 'No processable references found in document',
                'processed_content': content,
                'citations': [],
                'statistics': {
                    'total_references': 0,
                    'processed': 0,
                    'failed': 0,
                    'inline_replacements': 0,
                    'document_analysis': doc_stats,
                },
            }
            if backup_path:
                result['backup_path'] = backup_path
            self._send_sse_event('complete', result)
            return
        
        # Categorize references
        categorized = self.type_detector.categorize_references(parser.references)
        
        # Get body content
        body = parser.get_body_content()
        inline_style = parser._detect_inline_style(body)
        
        # Track results
        processed_citations = []
        number_to_label_map = {}
        failed_refs = []
        
        # Process each reference with progress updates
        for idx, ref in enumerate(parser.references):
            # Send progress update
            self._send_sse_event('progress', {
                'current': idx + 1,
                'total': total_refs,
                'percent': round((idx + 1) / total_refs * 100),
                'processing': ref.title[:60] + '...' if ref.title and len(ref.title) > 60 else (ref.title or f'Reference #{ref.original_number}'),
                'stats': {
                    'processed': len(processed_citations),
                    'failed': len(failed_refs),
                },
            })
            
            # Process the reference
            result = self._process_single_reference(ref)
            
            if result and result.get('success'):
                # Keep the full inline mark format for proper replacement
                inline_mark = result.get('inline_mark', '')
                number_to_label_map[ref.original_number] = inline_mark
                processed_citations.append({
                    'original_number': ref.original_number,
                    'title': ref.title,
                    'inline_mark': inline_mark,
                    'full_citation': result.get('full_citation', ''),
                    'identifier': result.get('identifier', ''),
                    'identifier_type': result.get('identifier_type', ''),
                })
                
                # Send success event for this reference
                self._send_sse_event('ref_processed', {
                    'number': ref.original_number,
                    'success': True,
                    'title': ref.title[:50] if ref.title else 'Unknown',
                })
            else:
                # Provide detailed error information
                error_detail = self._get_detailed_error(ref, result)
                failed_refs.append({
                    'original_number': ref.original_number,
                    'title': ref.title[:100] if ref.title else 'Unknown',
                    'url': ref.url if hasattr(ref, 'url') else None,
                    'error': error_detail['message'],
                    'error_type': error_detail['type'],
                    'suggestion': error_detail['suggestion'],
                })
                
                # Send failure event for this reference with detailed info
                self._send_sse_event('ref_processed', {
                    'number': ref.original_number,
                    'success': False,
                    'error': error_detail['message'],
                    'error_type': error_detail['type'],
                    'suggestion': error_detail['suggestion'],
                })
        
        # Update status
        self._send_sse_event('status', {
            'phase': 'finalizing',
            'message': 'Updating inline references...',
        })
        
        # Update inline references in body
        if number_to_label_map:
            replacer = InlineReplacer(number_to_label_map, style=inline_style)
            replace_result = replacer.replace_all(body)
            updated_body = replace_result.modified_text
            replacements_made = replace_result.replacements_made
        else:
            updated_body = body
            replacements_made = 0
        
        # Generate new reference section
        reference_section = "\n## References\n\n"
        
        # Add successfully processed citations (sorted alphabetically)
        sorted_citations = sorted(processed_citations, key=lambda c: c.get('inline_mark', '').lower())
        for citation in sorted_citations:
            reference_section += f"{citation['full_citation']}\n\n"
        
        # Add failed references section if any failed
        # This keeps the original numbers so users can track them down
        if failed_refs:
            reference_section += "\n---\n\n### ⚠️ Unresolved References\n\n"
            reference_section += "_The following references could not be automatically resolved. Original numbers are preserved for tracking._\n\n"
            
            # Sort by original number for easy lookup
            sorted_failed = sorted(failed_refs, key=lambda r: r.get('original_number', 0))
            for ref in sorted_failed:
                num = ref.get('original_number', '?')
                title = ref.get('title', 'Unknown')[:80]
                if len(ref.get('title', '')) > 80:
                    title += '...'
                url = ref.get('url', '')
                error_type = ref.get('error_type', 'unknown')
                suggestion = ref.get('suggestion', '')
                
                reference_section += f"**[{num}]** {title}\n"
                if url:
                    reference_section += f"- URL: {url}\n"
                reference_section += f"- Issue: {error_type}\n"
                if suggestion:
                    reference_section += f"- Suggestion: {suggestion}\n"
                reference_section += "\n"
        
        # Combine updated body with new references
        processed_content = updated_body + "\n\n" + reference_section.strip()
        
        # Build final result
        final_result = {
            'success': True,
            'processed_content': processed_content,
            'citations': processed_citations,
            'failed_references': failed_refs,
            'statistics': {
                'total_references': len(parser.references),
                'processed': len(processed_citations),
                'failed': len(failed_refs),
                'inline_replacements': replacements_made,
                'document_analysis': doc_stats,
            },
        }
        
        if backup_path:
            final_result['backup_path'] = backup_path
        
        # Save to file if requested
        if save_to_file and resolved_file_path:
            self._send_sse_event('status', {
                'phase': 'saving',
                'message': f'Saving to {resolved_file_path}...',
            })
            
            try:
                with open(resolved_file_path, 'w', encoding='utf-8') as f:
                    f.write(processed_content)
                final_result['saved_to_file'] = True
                final_result['saved_path'] = str(resolved_file_path)
                final_result['message'] = f'Processed document saved to: {resolved_file_path}'
                logger.info(f"Saved processed document to: {resolved_file_path}")
            except Exception as e:
                final_result['saved_to_file'] = False
                final_result['save_error'] = str(e)
                final_result['message'] = f'Processing succeeded but failed to save: {e}'
                logger.error(f"Failed to save processed document: {e}")
        
        # Send completion event
        self._send_sse_event('complete', final_result)
    
    def _create_backup(self, file_path: str, content: str) -> str:
        """
        Create a timestamped backup of a file before processing.
        
        Args:
            file_path: Original file path
            content: Original file content
            
        Returns:
            Path to the backup file
        """
        from datetime import datetime
        
        path = Path(file_path)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{path.stem}_backup_{timestamp}{path.suffix}"
        backup_path = path.parent / backup_name
        
        with open(backup_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        logger.info(f"Created backup: {backup_path}")
        log_document_operation("backup", str(file_path), {
            "backup_path": str(backup_path),
            "content_length": len(content)
        })
        return str(backup_path)
    
    def _analyze_document_statistics(self, content: str) -> Dict[str, Any]:
        """
        Analyze a document to provide comprehensive citation/reference statistics.
        
        Counts various types of inline references and citations in the document.
        """
        import re
        
        stats = {
            # Inline reference marks (in body text)
            'inline_numeric': 0,       # [1], [2], etc.
            'inline_footnote': 0,      # [^name], [^PMID-123], etc.
            'inline_author_year': 0,   # (Smith 2020), (Smith et al., 2020)
            
            # Reference section
            'reference_section_items': 0,  # Items in ## References section
            'footnote_definitions': 0,     # [^name]: definition lines
            
            # Identifiers found
            'pubmed_urls': 0,          # pubmed.ncbi.nlm.nih.gov URLs
            'doi_links': 0,            # DOI URLs or patterns
            'pmid_mentions': 0,        # PMID: 12345 patterns
            'pmcid_mentions': 0,       # PMC12345 patterns
            
            # URLs
            'total_urls': 0,           # All URLs
            'markdown_links': 0,       # [text](url) links
        }
        
        lines = content.split('\n')
        in_reference_section = False
        
        for line in lines:
            # Check for reference section start (supports #, ##, ###, ####)
            if re.match(r'^#{1,4}\s*(References|Bibliography|Citations|Works\s+[Cc]ited|Sources)', line, re.IGNORECASE):
                in_reference_section = True
                continue
            
            # Check for next section (end of references)
            if in_reference_section and re.match(r'^#{1,4}\s+\w', line) and not re.match(r'^#{1,4}\s*(References|Bibliography)', line, re.IGNORECASE):
                in_reference_section = False
            
            # Count footnote definitions [^name]: ...
            if re.match(r'^\[\^[^\]]+\]:\s*', line):
                stats['footnote_definitions'] += 1
                if in_reference_section:
                    stats['reference_section_items'] += 1
                continue
            
            # Count numbered references in reference section (1. Author... or [1] Author...)
            if in_reference_section and re.match(r'^(\d+\.|\[\d+\])\s*\w', line):
                stats['reference_section_items'] += 1
            
            # Count inline numeric references [1], [2], [1,2], [1-3]
            numeric_refs = re.findall(r'\[(\d+(?:[,\-–]\d+)*)\](?!\()', line)
            for ref in numeric_refs:
                # Count individual numbers in ranges like [1-3] or [1,2,3]
                if '-' in ref or '–' in ref:
                    parts = re.split(r'[-–]', ref)
                    if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
                        stats['inline_numeric'] += int(parts[1]) - int(parts[0]) + 1
                    else:
                        stats['inline_numeric'] += 1
                elif ',' in ref:
                    stats['inline_numeric'] += len(ref.split(','))
                else:
                    stats['inline_numeric'] += 1
            
            # Count footnote-style references [^name]
            footnote_refs = re.findall(r'\[\^[^\]]+\](?!:)', line)
            stats['inline_footnote'] += len(footnote_refs)
            
            # Count author-year citations (Smith 2020), (Smith et al., 2020)
            author_year = re.findall(r'\([A-Z][a-z]+(?:\s+et\s+al\.?)?,?\s*\d{4}[a-z]?\)', line)
            stats['inline_author_year'] += len(author_year)
            
            # Count PubMed URLs
            pubmed_urls = re.findall(r'pubmed\.ncbi\.nlm\.nih\.gov/\d+', line)
            stats['pubmed_urls'] += len(pubmed_urls)
            
            # Count DOI patterns
            dois = re.findall(r'(?:doi\.org/|DOI:\s*)(10\.\d{4,}/[^\s\)]+)', line, re.IGNORECASE)
            stats['doi_links'] += len(dois)
            
            # Count PMID mentions
            pmids = re.findall(r'PMID:\s*\d+', line, re.IGNORECASE)
            stats['pmid_mentions'] += len(pmids)
            
            # Count PMC IDs
            pmcids = re.findall(r'PMC\d+', line)
            stats['pmcid_mentions'] += len(pmcids)
            
            # Count markdown links [text](url)
            md_links = re.findall(r'\[[^\]]+\]\([^)]+\)', line)
            stats['markdown_links'] += len(md_links)
            
            # Count all URLs
            all_urls = re.findall(r'https?://[^\s\)<>]+', line)
            stats['total_urls'] += len(all_urls)
        
        # Calculate totals
        stats['total_inline_references'] = (
            stats['inline_numeric'] + 
            stats['inline_footnote'] + 
            stats['inline_author_year']
        )
        
        stats['total_citations'] = max(
            stats['reference_section_items'],
            stats['footnote_definitions']
        )
        
        stats['total_identifiers'] = (
            stats['pubmed_urls'] + 
            stats['doi_links'] + 
            stats['pmid_mentions'] + 
            stats['pmcid_mentions']
        )
        
        return stats
    
    def _process_document_content(self, content: str, style: str = 'vancouver') -> Dict[str, Any]:
        """
        Process a markdown document, looking up all citations and replacing inline references.
        
        Returns a dict with:
        - processed_content: The document with updated inline references
        - citations: List of processed citations
        - statistics: Processing stats
        """
        # First, analyze the document for comprehensive statistics
        doc_stats = self._analyze_document_statistics(content)
        
        # Set citation style
        if style != self.lookup.style:
            self.lookup.set_style(style)
        
        # Parse references
        parser = ReferenceParser(content)
        parser.find_reference_section()
        parser.parse_references()
        
        if not parser.references:
            return {
                'success': True,
                'message': 'No processable references found in document',
                'processed_content': content,
                'citations': [],
                'statistics': {
                    'total_references': 0,
                    'processed': 0,
                    'failed': 0,
                    'inline_replacements': 0,
                    # Include document analysis stats
                    'document_analysis': doc_stats,
                },
            }
        
        # Categorize references by type
        categorized = self.type_detector.categorize_references(parser.references)
        
        # Get body content
        body = parser.get_body_content()
        inline_style = parser._detect_inline_style(body)
        
        # Track results
        processed_citations = []
        number_to_label_map = {}
        failed_refs = []
        
        # Deduplication tracking - prevent same citation from appearing multiple times
        seen_identifiers = {}  # identifier -> inline_mark
        seen_full_citations = {}  # full_citation hash -> inline_mark
        
        # Process each reference
        for ref in parser.references:
            result = self._process_single_reference(ref)
            
            if result and result.get('success'):
                # Create a FormattedCitation-like structure for inline replacement
                # Keep the full inline mark format for proper replacement (e.g., [^SmithJA-2024-12345])
                inline_mark = result.get('inline_mark', '')
                full_citation = result.get('full_citation', '')
                identifier = result.get('identifier', '')
                
                # Check for duplicates by identifier (DOI, PMID, etc.)
                if identifier and identifier in seen_identifiers:
                    # Reuse existing citation's inline mark
                    inline_mark = seen_identifiers[identifier]
                    logger.debug(f"Dedup: Reusing {inline_mark} for duplicate identifier {identifier}")
                else:
                    # Check for duplicates by full citation text (for fallback citations)
                    citation_key = full_citation[:100].lower().strip()
                    if citation_key in seen_full_citations:
                        inline_mark = seen_full_citations[citation_key]
                        logger.debug(f"Dedup: Reusing {inline_mark} for duplicate citation")
                    else:
                        # New unique citation - track it
                        if identifier:
                            seen_identifiers[identifier] = inline_mark
                        seen_full_citations[citation_key] = inline_mark
                        
                        # Only add to processed_citations if it's new
                        processed_citations.append({
                            'original_number': ref.original_number,
                            'title': ref.title,
                            'inline_mark': inline_mark,
                            'full_citation': full_citation,
                            'identifier': identifier,
                            'identifier_type': result.get('identifier_type', ''),
                        })
                
                # Always map the original number to the (possibly reused) inline mark
                number_to_label_map[ref.original_number] = inline_mark
            else:
                # Provide detailed error information
                error_detail = self._get_detailed_error(ref, result)
                failed_refs.append({
                    'original_number': ref.original_number,
                    'title': ref.title[:100] if ref.title else 'Unknown',
                    'url': ref.url if hasattr(ref, 'url') else None,
                    'error': error_detail['message'],
                    'error_type': error_detail['type'],
                    'suggestion': error_detail['suggestion'],
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
        
        # Add successfully processed citations (sorted alphabetically)
        sorted_citations = sorted(processed_citations, key=lambda c: c.get('inline_mark', '').lower())
        for citation in sorted_citations:
            reference_section += f"{citation['full_citation']}\n\n"
        
        # Add failed references section if any failed
        # This keeps the original numbers so users can track them down
        if failed_refs:
            reference_section += "\n---\n\n### ⚠️ Unresolved References\n\n"
            reference_section += "_The following references could not be automatically resolved. Original numbers are preserved for tracking._\n\n"
            
            # Sort by original number for easy lookup
            sorted_failed = sorted(failed_refs, key=lambda r: r.get('original_number', 0))
            for ref in sorted_failed:
                num = ref.get('original_number', '?')
                title = ref.get('title', 'Unknown')[:80]
                if len(ref.get('title', '')) > 80:
                    title += '...'
                url = ref.get('url', '')
                error_type = ref.get('error_type', 'unknown')
                suggestion = ref.get('suggestion', '')
                
                reference_section += f"**[{num}]** {title}\n"
                if url:
                    reference_section += f"- URL: {url}\n"
                reference_section += f"- Issue: {error_type}\n"
                if suggestion:
                    reference_section += f"- Suggestion: {suggestion}\n"
                reference_section += "\n"
        
        # Combine updated body with new references
        processed_content = updated_body + "\n\n" + reference_section.strip()
        
        return {
            'success': True,
            'processed_content': processed_content,
            'citations': processed_citations,
            'failed_references': failed_refs,
            'statistics': {
                'total_references': len(parser.references),
                'processed': len(processed_citations),
                'failed': len(failed_refs),
                'inline_replacements': replacements_made,
                # Include comprehensive document analysis stats
                'document_analysis': doc_stats,
            },
        }
    
    def _create_fallback_citation(self, ref: ParsedReference, attempted_strategies: List[str]) -> Optional[Dict[str, Any]]:
        """
        Create a fallback webpage/organizational citation when database lookups fail.
        
        This ensures we always produce a valid citation, even for:
        - Company websites (Novo Nordisk, Ventyx, etc.)
        - Press releases (PR Newswire, etc.)
        - Wikipedia
        - ClinicalTrials.gov
        - News sites
        - Any other URL-based reference
        """
        from urllib.parse import urlparse
        from datetime import datetime
        
        url = ref.url or ''
        # Always have a title - use URL-derived title or reference number if needed
        title = ref.title or ''
        if not title and url:
            # Extract title from URL path
            try:
                parsed = urlparse(url)
                path_parts = [p for p in parsed.path.split('/') if p]
                if path_parts:
                    # Use last meaningful path segment
                    title = path_parts[-1].replace('-', ' ').replace('_', ' ').title()
            except:
                pass
        if not title:
            title = f'Reference {ref.original_number}' if hasattr(ref, 'original_number') else 'Untitled'
        
        # Parse URL for domain info
        domain = ''
        org_name = ''
        if url:
            try:
                parsed = urlparse(url)
                domain = parsed.netloc.lower().replace('www.', '')
            except:
                pass
        
        # Determine citation type and organization based on domain
        citation_type = 'webpage'
        year = datetime.now().strftime('%Y')
        
        # Comprehensive domain-specific handling
        domain_orgs = {
            # === Pharmaceutical Companies ===
            'novonordisk.com': ('Novo Nordisk', 'pharmaceutical'),
            'ventyxbio.com': ('Ventyx Biosciences', 'pharmaceutical'),
            'ir.ventyxbio.com': ('Ventyx Biosciences', 'pharmaceutical'),
            'olatec.com': ('Olatec Therapeutics', 'pharmaceutical'),
            'pfizer.com': ('Pfizer', 'pharmaceutical'),
            'merck.com': ('Merck', 'pharmaceutical'),
            'lilly.com': ('Eli Lilly', 'pharmaceutical'),
            'abbvie.com': ('AbbVie', 'pharmaceutical'),
            'gsk.com': ('GlaxoSmithKline', 'pharmaceutical'),
            'astrazeneca.com': ('AstraZeneca', 'pharmaceutical'),
            'sanofi.com': ('Sanofi', 'pharmaceutical'),
            'bms.com': ('Bristol-Myers Squibb', 'pharmaceutical'),
            'jnj.com': ('Johnson & Johnson', 'pharmaceutical'),
            'roche.com': ('Roche', 'pharmaceutical'),
            'boehringer-ingelheim.com': ('Boehringer Ingelheim', 'pharmaceutical'),
            
            # === Press Releases ===
            'prnewswire.com': ('PR Newswire', 'press_release'),
            'businesswire.com': ('Business Wire', 'press_release'),
            'globenewswire.com': ('GlobeNewswire', 'press_release'),
            'accesswire.com': ('AccessWire', 'press_release'),
            
            # === News/Media ===
            'firstwordpharma.com': ('FirstWord Pharma', 'news'),
            'clinicaltrialsarena.com': ('Clinical Trials Arena', 'news'),
            'barchart.com': ('Barchart', 'news'),
            'fiercepharma.com': ('Fierce Pharma', 'news'),
            'statnews.com': ('STAT News', 'news'),
            'medscape.com': ('Medscape', 'news'),
            'healio.com': ('Healio', 'news'),
            'medpagetoday.com': ('MedPage Today', 'news'),
            'reuters.com': ('Reuters', 'news'),
            'nytimes.com': ('The New York Times', 'news'),
            'washingtonpost.com': ('The Washington Post', 'news'),
            
            # === Encyclopedia/Reference ===
            'wikipedia.org': ('Wikipedia', 'encyclopedia'),
            'en.wikipedia.org': ('Wikipedia', 'encyclopedia'),
            
            # === Clinical Trials ===
            'clinicaltrials.gov': ('ClinicalTrials.gov', 'clinical_trial'),
            
            # === Medical Organizations ===
            'acc.org': ('American College of Cardiology', 'organization'),
            'aha.org': ('American Heart Association', 'organization'),
            'heart.org': ('American Heart Association', 'organization'),
            'escardio.org': ('European Society of Cardiology', 'organization'),
            'who.int': ('World Health Organization', 'organization'),
            'cdc.gov': ('Centers for Disease Control', 'organization'),
            'nih.gov': ('National Institutes of Health', 'organization'),
            'fda.gov': ('U.S. Food and Drug Administration', 'organization'),
            'ema.europa.eu': ('European Medicines Agency', 'organization'),
            
            # === Academic/Research Networks ===
            'researchgate.net': ('ResearchGate', 'preprint'),
            'academia.edu': ('Academia.edu', 'preprint'),
            'ssrn.com': ('SSRN', 'preprint'),
            
            # === Academic Publishers (fallback if DOI extraction fails) ===
            'jstage.jst.go.jp': ('J-STAGE', 'journal'),
            'imrpress.com': ('IMR Press', 'journal'),
            'aging-us.com': ('Aging', 'journal'),
            'frontiersin.org': ('Frontiers', 'journal'),
            'mdpi.com': ('MDPI', 'journal'),
            'nature.com': ('Nature', 'journal'),
            'sciencedirect.com': ('ScienceDirect', 'journal'),
            'springer.com': ('Springer', 'journal'),
            'wiley.com': ('Wiley', 'journal'),
            'plos.org': ('PLOS', 'journal'),
            'bmj.com': ('BMJ', 'journal'),
            'nejm.org': ('NEJM', 'journal'),
            'jamanetwork.com': ('JAMA Network', 'journal'),
            'thelancet.com': ('The Lancet', 'journal'),
            'ahajournals.org': ('AHA Journals', 'journal'),
            'dovepress.com': ('Dove Medical Press', 'journal'),
            'karger.com': ('Karger', 'journal'),
            'ecrjournal.com': ('European Cardiology Review', 'journal'),
            'diabetesjournals.org': ('Diabetes Journals', 'journal'),
        }
        
        # Find matching domain
        for dom, (org, ctype) in domain_orgs.items():
            if dom in domain:
                org_name = org
                citation_type = ctype
                break
        
        # If no match, try to extract organization from domain
        if not org_name and domain:
            # Convert domain to organization name
            parts = domain.split('.')
            if len(parts) >= 2:
                # Use the main domain part (before .com, .org, etc.)
                main_part = parts[0] if parts[0] not in ['www', 'ir', 'investor', 'news'] else (parts[1] if len(parts) > 1 else parts[0])
                org_name = main_part.replace('-', ' ').replace('_', ' ').title()
                
                # Handle common abbreviations
                abbrev_map = {
                    'Nih': 'NIH', 'Fda': 'FDA', 'Cdc': 'CDC', 'Who': 'WHO',
                    'Aha': 'AHA', 'Acc': 'ACC', 'Esc': 'ESC', 'Jama': 'JAMA',
                    'Nejm': 'NEJM', 'Bmj': 'BMJ', 'Plos': 'PLOS', 'Mdpi': 'MDPI',
                }
                for abbrev, correct in abbrev_map.items():
                    if org_name == abbrev:
                        org_name = correct
                        break
        
        # Try to scrape for more metadata
        scraped_metadata = None
        if url:
            try:
                scraper = WebpageScraper(timeout=8)
                scraped_metadata = scraper.extract_metadata(url)
            except:
                pass
        
        # Use scraped data if available (with defensive error handling)
        # Filter out bad metadata values
        BAD_ORG_NAMES = [
            'authors not specified', '(authors not specified)', 'author not specified',
            'unknown', 'n/a', 'none', 'null', 'undefined', ''
        ]
        
        if scraped_metadata:
            try:
                if getattr(scraped_metadata, 'title', None) and len(scraped_metadata.title) > len(title):
                    scraped_title = scraped_metadata.title.strip()
                    # Don't use generic titles
                    if scraped_title.lower() not in ['home', 'welcome', 'error', '404', 'page not found']:
                        title = scraped_title
                if getattr(scraped_metadata, 'site_name', None):
                    site = scraped_metadata.site_name.strip()
                    # Only use site_name if it's a real organization name
                    if site.lower() not in BAD_ORG_NAMES and len(site) > 2:
                        org_name = site
                if getattr(scraped_metadata, 'year', None):
                    year = scraped_metadata.year
                elif getattr(scraped_metadata, 'published_date', None):
                    import re
                    year_match = re.search(r'(\d{4})', scraped_metadata.published_date)
                    if year_match:
                        year = year_match.group(1)
            except Exception as e:
                logger.debug(f"Error extracting scraped metadata: {e}")
        
        # Extract year from URL if available
        if url and year == datetime.now().strftime('%Y'):
            import re
            year_match = re.search(r'/(\d{4})/', url)
            if year_match:
                year = year_match.group(1)
        
        # Clean up title
        title = title.strip()
        if title.endswith('.'):
            title = title[:-1]
        
        # Truncate very long titles
        if len(title) > 150:
            title = title[:147] + '...'
        
        # Create inline label based on organization and year
        # Format: [^OrgName-TitlePart-Year] - must be unique and meaningful
        
        # Clean org_name - remove spaces and bad characters, take first meaningful word
        if org_name and org_name.lower() not in BAD_ORG_NAMES:
            # Take first meaningful word from org name
            org_words = [w for w in org_name.split() if len(w) > 2 and w.lower() not in ['the', 'and', 'of', 'for']]
            label_org = ''.join(c for c in (org_words[0] if org_words else org_name) if c.isalnum())[:12]
        else:
            # Use domain name instead
            if domain:
                label_org = domain.split('.')[0].title()[:12]
            else:
                label_org = 'Web'
        
        # Create title part from actual title (not "Authors not specified")
        title_words = [w for w in title.split() if len(w) > 3 and w.lower() not in ['the', 'and', 'for', 'with', 'from', 'authors', 'not', 'specified']]
        if title_words:
            title_part = ''.join(c for c in title_words[0] if c.isalnum())[:10]
        else:
            title_part = ''.join(c for c in title[:15] if c.isalnum())[:10]
        
        # Ensure we have meaningful parts
        if not label_org or label_org.lower() in ['web', 'unknown', 'authors']:
            label_org = domain.split('.')[0].title()[:12] if domain else 'Ref'
        
        # CRITICAL: Include reference number for uniqueness
        # This prevents duplicate labels for different references from the same source
        ref_num = getattr(ref, 'original_number', None)
        if ref_num:
            inline_label = f"[^{label_org}-{title_part[:6]}-{year}-ref{ref_num}]"
        else:
            # Use URL hash for uniqueness if no ref number
            import hashlib
            url_hash = hashlib.md5(url.encode()).hexdigest()[:6] if url else 'x'
            inline_label = f"[^{label_org}-{title_part[:6]}-{year}-{url_hash}]"
        
        # Format the full citation based on type
        if citation_type == 'clinical_trial':
            # Extract NCT number if present
            import re
            nct_match = re.search(r'NCT\d{8}', url, re.IGNORECASE)
            nct = nct_match.group(0) if nct_match else ''
            if nct:
                full_citation = f"{inline_label}: {title}. ClinicalTrials.gov Identifier: {nct}. [{nct}]({url})"
            else:
                full_citation = f"{inline_label}: {title}. ClinicalTrials.gov. [Link]({url})"
        
        elif citation_type == 'press_release':
            full_citation = f"{inline_label}: {org_name}. {title}. {year}. [Press Release]({url})"
        
        elif citation_type == 'encyclopedia':
            full_citation = f"{inline_label}: {title}. Wikipedia. Accessed {year}. [Link]({url})"
        
        elif citation_type in ('pharmaceutical', 'organization'):
            full_citation = f"{inline_label}: {org_name}. {title}. {year}. [Link]({url})"
        
        elif citation_type == 'news':
            full_citation = f"{inline_label}: {title}. {org_name}. {year}. [Link]({url})"
        
        else:
            # Generic webpage format
            if url:
                if org_name:
                    full_citation = f"{inline_label}: {title}. {org_name}. {year}. [Link]({url})"
                else:
                    full_citation = f"{inline_label}: {title}. {year}. [Link]({url})"
            else:
                # No URL - just title-based citation
                if org_name:
                    full_citation = f"{inline_label}: {title}. {org_name}. {year}."
                else:
                    full_citation = f"{inline_label}: {title}. {year}."
        
        # Final safety check - ensure we have a valid citation
        if not full_citation or len(full_citation) < 10:
            full_citation = f"{inline_label}: {title}. {year}."
        
        # Final validation and return
        try:
            # Ensure inline_label is valid
            if not inline_label or '[^' not in inline_label:
                inline_label = f"[^Web-{ref.original_number if hasattr(ref, 'original_number') else 'ref'}-{year}]"
            
            logger.info(f"Created fallback {citation_type} citation for: {domain or title[:30]}")
            
            return {
                'success': True,
                'inline_mark': inline_label,
                'full_citation': full_citation,
                'citation_type': citation_type,
                'is_fallback': True,
                'fallback_reason': f'No database record found; formatted as {citation_type}',
            }
        except Exception as e:
            # Absolute last resort - NEVER fail
            logger.warning(f"Fallback citation exception: {e}, creating minimal citation")
            minimal_label = f"[^Ref{ref.original_number if hasattr(ref, 'original_number') else 'Unknown'}]"
            minimal_citation = f"{minimal_label}: Reference. Accessed {year}."
            return {
                'success': True,
                'inline_mark': minimal_label,
                'full_citation': minimal_citation,
                'citation_type': 'minimal',
                'is_fallback': True,
                'fallback_reason': 'Minimal citation due to processing error',
            }
    
    def _get_detailed_error(self, ref, result: Optional[Dict]) -> Dict[str, str]:
        """Generate detailed error information for a failed reference lookup."""
        url = ref.url if hasattr(ref, 'url') else None
        title = ref.title if hasattr(ref, 'title') else None
        
        # Determine error type and provide helpful suggestions
        if result is None:
            return {
                'type': 'lookup_failed',
                'message': 'Citation lookup returned no result',
                'suggestion': 'The source may be unavailable or the identifier format is not recognized.',
            }
        
        error_msg = result.get('error', 'Unknown error')
        
        # Check for specific error patterns
        if url:
            # Check if URL format is problematic
            if 'pubmed' in url.lower():
                pmid = self.type_detector.extract_pmid(url)
                if not pmid:
                    return {
                        'type': 'invalid_pubmed_url',
                        'message': f'Could not extract PMID from URL: {url[:50]}...',
                        'suggestion': 'Ensure the PubMed URL contains a valid PMID (e.g., https://pubmed.ncbi.nlm.nih.gov/12345678/)',
                    }
                else:
                    return {
                        'type': 'pubmed_not_found',
                        'message': f'PMID {pmid} not found in PubMed database',
                        'suggestion': 'The article may have been retracted, or the PMID may be incorrect. Verify the PMID at pubmed.ncbi.nlm.nih.gov',
                    }
            elif 'doi.org' in url.lower():
                doi = self.type_detector.extract_doi(url)
                if not doi:
                    return {
                        'type': 'invalid_doi_url',
                        'message': f'Could not extract DOI from URL: {url[:50]}...',
                        'suggestion': 'Ensure the DOI URL is properly formatted (e.g., https://doi.org/10.1234/example)',
                    }
                else:
                    return {
                        'type': 'doi_not_found',
                        'message': f'DOI {doi} not found in CrossRef database',
                        'suggestion': 'The DOI may be incorrect or the article is not indexed in CrossRef.',
                    }
            elif 'pmc' in url.lower():
                pmcid = self.type_detector.extract_pmcid(url)
                return {
                    'type': 'pmc_not_found',
                    'message': f'PMC ID {pmcid or "unknown"} could not be resolved',
                    'suggestion': 'Try using the PubMed URL instead, or verify the PMC ID at ncbi.nlm.nih.gov/pmc/',
                }
            else:
                return {
                    'type': 'url_not_recognized',
                    'message': f'URL format not recognized: {url[:50]}...',
                    'suggestion': 'Supported sources: PubMed, DOI, PMC, arXiv, bioRxiv/medRxiv. Use direct links to these databases.',
                }
        
        if title and not url:
            return {
                'type': 'title_search_failed',
                'message': f'Could not find article by title: "{title[:40]}..."',
                'suggestion': 'Title searches are less reliable. Add a PubMed URL, DOI, or PMID for better results.',
            }
        
        return {
            'type': 'unknown',
            'message': error_msg,
            'suggestion': 'Check the reference format and ensure it contains a valid identifier (PMID, DOI, or URL).',
        }
    
    def _process_single_reference(self, ref: ParsedReference) -> Optional[Dict[str, Any]]:
        """Process a single reference, attempting to look it up.
        
        Lookup priority:
        1. Check learning engine for user corrections
        2. Check learning engine for learned patterns
        3. Extract identifiers from URL (PMID, PMCID, DOI)
        4. Check metadata for DOI (extracted from reference text)
        5. Scrape webpage for DOI/metadata (if URL available)
        6. Title search as last resort
        7. Record failure for future learning
        """
        learning = get_learning_engine()
        attempted_strategies = []
        
        # 1. Check learning engine for user corrections or learned patterns
        if ref.url or ref.title:
            suggestions = learning.suggest_resolution(ref.url, ref.title)
            for suggestion in suggestions:
                attempted_strategies.append(f"learning:{suggestion['type']}")
                
                if suggestion['type'] == 'user_correction':
                    # User already told us the correct identifier
                    identifier = suggestion['identifier']
                    id_type = suggestion['identifier_type']
                    logger.info(f"Using user correction: {id_type}={identifier}")
                    
                    if id_type == 'pmid':
                        result = self.lookup.lookup_pmid(identifier)
                    elif id_type == 'doi':
                        result = self.lookup.lookup_doi(identifier)
                    elif id_type == 'pmcid':
                        result = self.lookup.lookup_pmcid(identifier)
                    else:
                        continue
                    
                    if result.success:
                        learning.record_success(ref.url, identifier, id_type, 'user_correction')
                        return self._format_result(result)
                
                elif suggestion['type'] == 'url_pattern' and suggestion.get('identifier'):
                    # Learning engine found identifier via URL pattern
                    identifier = suggestion['identifier']
                    id_type = suggestion['identifier_type']
                    logger.info(f"Using learned pattern: {id_type}={identifier}")
                    
                    if id_type == 'doi':
                        result = self.lookup.lookup_doi(identifier)
                        if result.success:
                            learning.record_success(ref.url, identifier, id_type, 'url_pattern')
                            return self._format_result(result)
        
        # 2. Try to extract identifiers from URL
        attempted_strategies.append('url_extraction')
        pmid = self.type_detector.extract_pmid(ref.url) if ref.url else None
        pmcid = self.type_detector.extract_pmcid(ref.url) if ref.url else None
        doi = self.type_detector.extract_doi(ref.url) if ref.url else None
        
        # 3. Also check ref.metadata for DOI extracted from reference text
        if not doi and ref.metadata:
            doi = ref.metadata.get('doi')
            if doi:
                logger.debug(f"Found DOI in metadata: {doi}")
                attempted_strategies.append('metadata_doi')
        
        # 4. Attempt lookup by identifier priority
        if pmid:
            attempted_strategies.append('pmid_lookup')
            result = self.lookup.lookup_pmid(pmid)
            if result.success:
                learning.record_success(ref.url, pmid, 'pmid', 'url_extraction')
                return self._format_result(result)
        
        if pmcid:
            attempted_strategies.append('pmcid_lookup')
            result = self.lookup.lookup_pmcid(pmcid)
            if result.success:
                learning.record_success(ref.url, pmcid, 'pmcid', 'url_extraction')
                return self._format_result(result)
        
        if doi:
            attempted_strategies.append('doi_lookup')
            result = self.lookup.lookup_doi(doi)
            if result.success:
                learning.record_success(ref.url, doi, 'doi', 'metadata_or_url')
                # Learn from this success if DOI was in URL
                if ref.url and doi in ref.url:
                    learning.learn_from_url(ref.url, doi, 'doi')
                return self._format_result(result)
        
        # 5. If no identifier found but we have a URL, try scraping the webpage for DOI
        if ref.url and not (pmid or pmcid or doi):
            attempted_strategies.append('webpage_scraping')
            try:
                scraper = WebpageScraper(timeout=10)
                scraped_metadata = scraper.extract_metadata(ref.url)
                if scraped_metadata:
                    # Check if scraping found a DOI
                    if scraped_metadata.doi:
                        logger.info(f"Found DOI via webpage scraping: {scraped_metadata.doi}")
                        result = self.lookup.lookup_doi(scraped_metadata.doi)
                        if result.success:
                            learning.record_success(ref.url, scraped_metadata.doi, 'doi', 'webpage_scraping')
                            return self._format_result(result)
                    
                    # Check if scraping found a PMID
                    if scraped_metadata.pmid:
                        logger.info(f"Found PMID via webpage scraping: {scraped_metadata.pmid}")
                        result = self.lookup.lookup_pmid(scraped_metadata.pmid)
                        if result.success:
                            learning.record_success(ref.url, scraped_metadata.pmid, 'pmid', 'webpage_scraping')
                            return self._format_result(result)
            except Exception as e:
                logger.debug(f"Webpage scraping failed for {ref.url}: {e}")
        
        # 6. Try title search as last resort (but only for academic sources)
        # Skip title search for non-academic domains that would return wrong CrossRef results
        NON_ACADEMIC_DOMAINS = {
            'wikipedia.org', 'en.wikipedia.org',  # Encyclopedia
            'novonordisk.com', 'pfizer.com', 'merck.com', 'lilly.com', 'abbvie.com',
            'gsk.com', 'astrazeneca.com', 'sanofi.com', 'bms.com', 'jnj.com',
            'roche.com', 'boehringer-ingelheim.com', 'ventyxbio.com', 'olatec.com',  # Pharma
            'prnewswire.com', 'businesswire.com', 'globenewswire.com',  # Press releases
            'firstwordpharma.com', 'clinicaltrialsarena.com', 'barchart.com',
            'fiercepharma.com', 'statnews.com', 'medpagetoday.com',  # News
            'reuters.com', 'nytimes.com', 'washingtonpost.com',
            'acc.org', 'aha.org', 'heart.org', 'escardio.org',  # Organizations (non-journal)
            'cdc.gov', 'nih.gov', 'fda.gov', 'who.int', 'ema.europa.eu',  # Government
            'researchgate.net', 'academia.edu',  # Social academic (often wrong matches)
        }
        
        should_skip_title_search = False
        if ref.url:
            from urllib.parse import urlparse
            try:
                domain = urlparse(ref.url).netloc.lower().replace('www.', '')
                if any(nd in domain for nd in NON_ACADEMIC_DOMAINS):
                    should_skip_title_search = True
                    logger.debug(f"Skipping title search for non-academic domain: {domain}")
            except:
                pass
        
        # Also skip title search if title looks like a company/organization name (not an article title)
        COMPANY_NAME_PATTERNS = {
            'novo nordisk', 'pfizer', 'merck', 'eli lilly', 'lilly', 'abbvie',
            'gsk', 'glaxosmithkline', 'astrazeneca', 'sanofi', 'bristol-myers', 'bms',
            'johnson & johnson', 'j&j', 'roche', 'boehringer', 'ventyx', 'olatec',
            'wikipedia', 'pubmed', 'google', 'microsoft', 'apple', 'amazon',
        }
        if ref.title and ref.title.lower().strip() in COMPANY_NAME_PATTERNS:
            should_skip_title_search = True
            logger.debug(f"Skipping title search for company/organization name: {ref.title}")
        
        if ref.title and not should_skip_title_search:
            attempted_strategies.append('title_search')
            result = self.lookup.lookup_auto(ref.title)
            if result.success:
                # Record success with the identifier found
                if result.identifier:
                    learning.record_success(ref.url, result.identifier, result.identifier_type or 'unknown', 'title_search')
                return self._format_result(result)
        
        # 7. FALLBACK: Create a webpage/organizational citation instead of failing
        # This ensures we ALWAYS produce a valid citation, even for non-academic sources
        attempted_strategies.append('fallback_citation')
        try:
            fallback_result = self._create_fallback_citation(ref, attempted_strategies)
            if fallback_result and fallback_result.get('success'):
                learning.record_success(ref.url, 'fallback', 'webpage', 'fallback_citation')
                return fallback_result
        except Exception as e:
            logger.warning(f"Fallback citation creation failed: {e}")
        
        # 8. ABSOLUTE LAST RESORT: Create a minimal citation rather than fail
        # This should basically never happen, but we guarantee no failures
        logger.warning(f"All strategies exhausted for reference {ref.original_number}, creating minimal citation")
        year = datetime.now().strftime('%Y')
        ref_num = ref.original_number if hasattr(ref, 'original_number') else 'Unknown'
        minimal_label = f"[^Ref{ref_num}]"
        minimal_title = ref.title[:50] if ref.title else f"Reference {ref_num}"
        
        # Include URL if available
        if ref.url:
            minimal_citation = f"{minimal_label}: {minimal_title}. [Link]({ref.url})"
        else:
            minimal_citation = f"{minimal_label}: {minimal_title}. {year}."
        
        return {
            'success': True,
            'inline_mark': minimal_label,
            'full_citation': minimal_citation,
            'citation_type': 'minimal',
            'is_fallback': True,
            'fallback_reason': 'All lookup methods exhausted; minimal citation created',
        }


def run_server(port: int = 3019, host: str = '127.0.0.1'):
    """Start the HTTP server."""
    # Initialize logging from config
    init_from_config()
    logger.info(f"Starting CitationSculptor HTTP Server v{VERSION}")
    
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
    CitationHTTPHandler.type_detector = CitationTypeDetector()
    CitationHTTPHandler.arxiv_client = ArxivClient()
    CitationHTTPHandler.preprint_client = PreprintClient()
    CitationHTTPHandler.book_client = BookClient()
    CitationHTTPHandler.wayback_client = WaybackClient()
    CitationHTTPHandler.openalex_client = OpenAlexClient()
    CitationHTTPHandler.semantic_scholar_client = SemanticScholarClient()
    CitationHTTPHandler.document_intelligence = DocumentIntelligence(
        pubmed_client=CitationHTTPHandler.lookup.pubmed_client,
        use_llm=True,
    )
    
    server = HTTPServer((host, port), CitationHTTPHandler)
    
    print(f"")
    print(f"  ╔═══════════════════════════════════════════════════════════════╗")
    print(f"  ║           📚 CitationSculptor HTTP Server v2.1.0              ║")
    print(f"  ╚═══════════════════════════════════════════════════════════════╝")
    print(f"")
    print(f"  🌐 Web UI:    http://{host}:{port}")
    print(f"  📡 API Base:  http://{host}:{port}/api")
    print(f"")
    print(f"  Core Features:")
    print(f"    ✓ Multi-source lookup (PubMed, arXiv, ISBN, DOI)")
    print(f"    ✓ Multiple citation styles (Vancouver, APA, MLA, etc.)")
    print(f"    ✓ Document processing (Markdown files)")
    print(f"    {'✓' if PYMUPDF_AVAILABLE else '✗'} PDF metadata extraction")
    print(f"    ✓ BibTeX/RIS import & export")
    print(f"    ✓ Citation library with search")
    print(f"")
    print(f"  Document Intelligence (v2.1):")
    print(f"    ✓ Link verification & broken link detection")
    print(f"    ✓ Automatic citation suggestions")
    print(f"    ✓ Citation compliance checker")
    print(f"    ✓ LLM-powered metadata extraction")
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
