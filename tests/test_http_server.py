"""
Tests for the HTTP server module.

Tests cover:
- Health endpoint
- Lookup endpoints (auto, pmid, doi, pmcid, title)
- Search endpoint
- Batch endpoint
- Cache endpoints
- Error handling
"""

import pytest
import json
import threading
import time
from unittest.mock import Mock, patch, MagicMock
from http.client import HTTPConnection

# Import the HTTP server module
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp_server.http_server import CitationHTTPHandler, run_server
from citation_lookup import LookupResult


class MockLookup:
    """Mock CitationLookup for testing."""
    
    def __init__(self):
        self.style = "vancouver"
    
    def set_style(self, style):
        self.style = style
    
    def lookup_auto(self, identifier):
        if identifier == "32089132":
            return LookupResult(
                success=True,
                identifier="32089132",
                identifier_type="pmid",
                inline_mark="[^KramerCM-2020-32089132]",
                endnote_citation="[^KramerCM-2020-32089132]: Kramer CM...",
                full_citation="[^KramerCM-2020-32089132]: Kramer CM...",
                metadata={"pmid": "32089132", "title": "Test Article"},
                error=None
            )
        return LookupResult(
            success=False,
            identifier=identifier,
            identifier_type="unknown",
            error="Not found"
        )
    
    def lookup_pmid(self, pmid):
        return self.lookup_auto(pmid)
    
    def lookup_doi(self, doi):
        if doi == "10.1234/test":
            return LookupResult(
                success=True,
                identifier="10.1234/test",
                identifier_type="doi",
                inline_mark="[^TestDOI-2024]",
                endnote_citation="[^TestDOI-2024]: Test...",
                full_citation="[^TestDOI-2024]: Test...",
                metadata={"doi": doi},
                error=None
            )
        return LookupResult(success=False, identifier=doi, error="Not found")
    
    def lookup_pmcid(self, pmcid):
        return LookupResult(success=False, identifier=pmcid, error="Not found")
    
    def lookup_title(self, title):
        return LookupResult(success=False, identifier=title, error="Not found")
    
    def batch_lookup(self, identifiers):
        return [self.lookup_auto(i) for i in identifiers]
    
    @property
    def pubmed_client(self):
        mock_client = Mock()
        # Create a proper article-like object with actual values
        mock_article = MagicMock()
        mock_article.pmid = "12345"
        mock_article.title = "Test Article"
        mock_article.authors = ["Smith J"]
        mock_article.journal = "Test Journal"
        mock_article.journal_abbreviation = "Test J"
        mock_article.year = "2024"
        mock_article.doi = "10.1234/test"
        mock_article.abstract = None
        
        mock_client.search_by_title.return_value = [mock_article]
        mock_client.get_cache_stats.return_value = {
            'pmid_cache_size': 5,
            'conversion_cache_size': 2,
            'crossref_cache_size': 1,
        }
        mock_client._pmid_cache = Mock()
        mock_client._conversion_cache = Mock()
        mock_client._crossref_cache = Mock()
        return mock_client


class TestCitationHTTPHandler:
    """Test cases for the HTTP handler."""

    def setup_method(self):
        """Set up test fixtures."""
        CitationHTTPHandler.lookup = MockLookup()

    def test_format_result_success(self):
        """Test formatting a successful result."""
        handler = CitationHTTPHandler.__new__(CitationHTTPHandler)
        result = LookupResult(
            success=True,
            identifier="32089132",
            identifier_type="pmid",
            inline_mark="[^Test-2024]",
            endnote_citation="[^Test-2024]: Citation",
            full_citation="[^Test-2024]: Citation",
            metadata={"title": "Test"},
            error=None
        )
        
        formatted = handler._format_result(result)
        
        assert formatted['success'] is True
        assert formatted['identifier'] == "32089132"
        assert formatted['inline_mark'] == "[^Test-2024]"
        assert formatted['metadata']['title'] == "Test"
        assert formatted['error'] is None

    def test_format_result_failure(self):
        """Test formatting a failed result."""
        handler = CitationHTTPHandler.__new__(CitationHTTPHandler)
        result = LookupResult(
            success=False,
            identifier="invalid",
            identifier_type="unknown",
            error="Not found"
        )
        
        formatted = handler._format_result(result)
        
        assert formatted['success'] is False
        assert formatted['error'] == "Not found"
        assert formatted['inline_mark'] == ""


class TestHTTPEndpointsIntegration:
    """Integration tests for HTTP endpoints using actual server."""
    
    @pytest.fixture(scope="class")
    def server_thread(self):
        """Start server in background for testing."""
        import socket
        
        # Find an available port
        sock = socket.socket()
        sock.bind(('', 0))
        port = sock.getsockname()[1]
        sock.close()
        
        CitationHTTPHandler.lookup = MockLookup()
        
        from http.server import HTTPServer
        server = HTTPServer(('127.0.0.1', port), CitationHTTPHandler)
        
        thread = threading.Thread(target=server.serve_forever)
        thread.daemon = True
        thread.start()
        
        time.sleep(0.1)  # Give server time to start
        
        yield port
        
        server.shutdown()
    
    def test_health_endpoint(self, server_thread):
        """Test health check endpoint."""
        port = server_thread
        conn = HTTPConnection('127.0.0.1', port)
        conn.request('GET', '/health')
        response = conn.getresponse()
        
        assert response.status == 200
        data = json.loads(response.read())
        assert data['status'] == 'ok'
        assert 'version' in data
    
    def test_lookup_endpoint_success(self, server_thread):
        """Test successful auto lookup."""
        port = server_thread
        conn = HTTPConnection('127.0.0.1', port)
        conn.request('GET', '/api/lookup?id=32089132')
        response = conn.getresponse()
        
        assert response.status == 200
        data = json.loads(response.read())
        assert data['success'] is True
        assert data['identifier'] == "32089132"
        assert '[^KramerCM-2020-32089132]' in data['inline_mark']
    
    def test_lookup_endpoint_missing_param(self, server_thread):
        """Test lookup with missing parameter."""
        port = server_thread
        conn = HTTPConnection('127.0.0.1', port)
        conn.request('GET', '/api/lookup')
        response = conn.getresponse()
        
        assert response.status == 400
        data = json.loads(response.read())
        assert 'error' in data
    
    def test_search_endpoint(self, server_thread):
        """Test PubMed search endpoint."""
        port = server_thread
        conn = HTTPConnection('127.0.0.1', port)
        conn.request('GET', '/api/search?q=heart+failure')
        response = conn.getresponse()
        
        assert response.status == 200
        data = json.loads(response.read())
        assert 'results' in data
        assert 'count' in data
    
    def test_cache_stats_endpoint(self, server_thread):
        """Test cache stats endpoint."""
        port = server_thread
        conn = HTTPConnection('127.0.0.1', port)
        conn.request('GET', '/api/cache/stats')
        response = conn.getresponse()
        
        assert response.status == 200
        data = json.loads(response.read())
        assert 'pmid_cache_size' in data
    
    def test_post_lookup_endpoint(self, server_thread):
        """Test POST lookup endpoint."""
        port = server_thread
        conn = HTTPConnection('127.0.0.1', port)
        body = json.dumps({'identifier': '32089132'})
        headers = {'Content-Type': 'application/json'}
        conn.request('POST', '/api/lookup', body, headers)
        response = conn.getresponse()
        
        assert response.status == 200
        data = json.loads(response.read())
        assert data['success'] is True
    
    def test_post_batch_endpoint(self, server_thread):
        """Test POST batch endpoint."""
        port = server_thread
        conn = HTTPConnection('127.0.0.1', port)
        body = json.dumps({'identifiers': ['32089132', 'invalid']})
        headers = {'Content-Type': 'application/json'}
        conn.request('POST', '/api/batch', body, headers)
        response = conn.getresponse()
        
        assert response.status == 200
        data = json.loads(response.read())
        assert 'results' in data
        assert data['count'] == 2
        assert data['success_count'] == 1
    
    def test_cors_headers(self, server_thread):
        """Test CORS headers are present."""
        port = server_thread
        conn = HTTPConnection('127.0.0.1', port)
        conn.request('OPTIONS', '/api/lookup')
        response = conn.getresponse()
        
        assert response.status == 200
        assert response.getheader('Access-Control-Allow-Origin') == '*'
    
    def test_unknown_endpoint(self, server_thread):
        """Test 404 for unknown endpoint."""
        port = server_thread
        conn = HTTPConnection('127.0.0.1', port)
        conn.request('GET', '/api/unknown')
        response = conn.getresponse()
        
        assert response.status == 404
        data = json.loads(response.read())
        assert 'error' in data

