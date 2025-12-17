"""
Integration tests for Document Intelligence HTTP and MCP endpoints.

Tests cover:
- HTTP API endpoints for document intelligence
- MCP tools for document intelligence
- Backup functionality
"""

import pytest
import json
import threading
import time
import tempfile
import os
from unittest.mock import Mock, patch, MagicMock
from http.client import HTTPConnection
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp_server.http_server import CitationHTTPHandler
from mcp_server.server import (
    call_tool,
    handle_verify_links,
    handle_suggest_citations,
    handle_check_compliance,
    handle_analyze_document,
    handle_extract_metadata_llm,
    get_content,
    create_backup,
)
from modules.document_intelligence import DocumentIntelligence
import asyncio


def run_async(coro):
    """Helper to run async functions in sync tests."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class TestBackupFunctionality:
    """Tests for backup creation functionality."""
    
    def test_create_backup_creates_file(self):
        """Test that backup creates a timestamped file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create original file
            original_path = os.path.join(tmpdir, "test_document.md")
            original_content = "# Test Document\n\nThis is test content."
            with open(original_path, 'w') as f:
                f.write(original_content)
            
            # Create backup
            backup_path = create_backup(original_path, original_content)
            
            # Verify backup exists
            assert os.path.exists(backup_path)
            assert "test_document_backup_" in backup_path
            assert backup_path.endswith(".md")
            
            # Verify backup content matches original
            with open(backup_path, 'r') as f:
                backup_content = f.read()
            assert backup_content == original_content
    
    def test_create_backup_timestamp_format(self):
        """Test that backup filename has correct timestamp format."""
        with tempfile.TemporaryDirectory() as tmpdir:
            original_path = os.path.join(tmpdir, "document.md")
            with open(original_path, 'w') as f:
                f.write("content")
            
            backup_path = create_backup(original_path, "content")
            
            # Should match pattern: document_backup_YYYYMMDD_HHMMSS.md
            filename = os.path.basename(backup_path)
            assert filename.startswith("document_backup_")
            # Extract timestamp part
            timestamp_part = filename.replace("document_backup_", "").replace(".md", "")
            assert len(timestamp_part) == 15  # YYYYMMDD_HHMMSS


class TestGetContentHelper:
    """Tests for get_content helper function."""
    
    def test_get_content_from_file(self):
        """Test getting content from file path."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write("# Test Content")
            temp_path = f.name
        
        try:
            content, error = get_content(temp_path, None)
            assert error is None
            assert content == "# Test Content"
        finally:
            os.unlink(temp_path)
    
    def test_get_content_from_direct_input(self):
        """Test getting content from direct input."""
        content, error = get_content(None, "Direct content here")
        assert error is None
        assert content == "Direct content here"
    
    def test_get_content_file_not_found(self):
        """Test error when file not found."""
        content, error = get_content("/nonexistent/path.md", None)
        assert content is None
        assert "File not found" in error
    
    def test_get_content_no_input(self):
        """Test error when no input provided."""
        content, error = get_content(None, None)
        assert content is None
        assert "No content provided" in error


class TestMCPDocumentIntelligenceTools:
    """Tests for MCP document intelligence tools."""
    
    def test_handle_verify_links_with_urls(self):
        """Test link verification with direct URL list."""
        with patch('mcp_server.server.doc_intelligence') as mock_di:
            mock_di.verify_links_batch.return_value = [
                {'url': 'https://example.com', 'status': 'ok', 'status_code': 200}
            ]
            
            result = handle_verify_links(None, None, ['https://example.com'])
            
            assert "Link Verification Results" in result
            assert "✅" in result or "OK" in result
    
    def test_handle_verify_links_with_content(self):
        """Test link verification with document content."""
        content = "Check this [link](https://example.com)."
        
        with patch('mcp_server.server.verify_document_links') as mock_verify:
            mock_verify.return_value = {
                'total_urls': 1,
                'status_summary': {'ok': 1},
                'broken_links': [],
                'redirected_links': [],
            }
            
            result = handle_verify_links(None, content, None)
            
            assert "Link Verification Results" in result
    
    def test_handle_suggest_citations(self):
        """Test citation suggestions."""
        content = "Studies show that 50% of patients respond to treatment."
        
        result = handle_suggest_citations(None, content, False)
        
        assert "Citation Suggestions" in result
    
    def test_handle_check_compliance(self):
        """Test citation compliance check."""
        content = "This is a simple document with no claims."
        
        result = handle_check_compliance(None, content)
        
        assert "Citation Compliance Check" in result
        assert "Compliance Score" in result
    
    def test_handle_analyze_document(self):
        """Test comprehensive document analysis."""
        content = "# Test Document\n\nSimple content here."
        
        with patch('mcp_server.server.doc_intelligence') as mock_di:
            mock_di.analyze_document.return_value = {
                'timestamp': '2025-01-01T00:00:00',
                'document_length': 100,
                'line_count': 5,
                'overall_health_score': 95.0,
                'link_verification': {'total_urls': 0, 'broken_links': []},
                'citation_suggestions': {'count': 0},
                'citation_compliance': {'compliance_score': 100, 'total_issues': 0},
            }
            
            result = handle_analyze_document(None, content, True, True, True, False)
            
            assert "Document Analysis Report" in result
            assert "Health Score" in result
    
    def test_handle_extract_metadata_llm_missing_params(self):
        """Test LLM extraction with missing parameters."""
        result = handle_extract_metadata_llm(None, None)
        assert "Error" in result
        
        result = handle_extract_metadata_llm("https://example.com", None)
        assert "Error" in result


class TestMCPToolExecution:
    """Tests for MCP tool execution via call_tool."""
    
    @patch('mcp_server.server.handle_verify_links')
    def test_call_citation_verify_links(self, mock_handler):
        """Test calling citation_verify_links tool."""
        mock_handler.return_value = "# Link Verification\nAll OK"
        
        result = run_async(call_tool("citation_verify_links", {
            "urls": ["https://example.com"]
        }))
        
        assert len(result) == 1
        assert "Link Verification" in result[0].text
    
    @patch('mcp_server.server.handle_suggest_citations')
    def test_call_citation_suggest_citations(self, mock_handler):
        """Test calling citation_suggest_citations tool."""
        mock_handler.return_value = "# Citation Suggestions\n0 suggestions"
        
        result = run_async(call_tool("citation_suggest_citations", {
            "content": "Test content"
        }))
        
        assert len(result) == 1
        assert "Citation Suggestions" in result[0].text
    
    @patch('mcp_server.server.handle_check_compliance')
    def test_call_citation_check_compliance(self, mock_handler):
        """Test calling citation_check_compliance tool."""
        mock_handler.return_value = "# Compliance Check\nScore: 100"
        
        result = run_async(call_tool("citation_check_compliance", {
            "content": "Test content"
        }))
        
        assert len(result) == 1
        assert "Compliance" in result[0].text
    
    @patch('mcp_server.server.handle_analyze_document')
    def test_call_citation_analyze_document(self, mock_handler):
        """Test calling citation_analyze_document tool."""
        mock_handler.return_value = "# Analysis\nHealth: 95"
        
        result = run_async(call_tool("citation_analyze_document", {
            "content": "Test content"
        }))
        
        assert len(result) == 1
        assert "Analysis" in result[0].text


class MockLookupWithPubMed:
    """Mock CitationLookup with PubMed client for testing."""
    
    def __init__(self):
        self.style = "vancouver"
        self._pubmed_client = Mock()
        self._pubmed_client.search_by_title.return_value = []
    
    @property
    def pubmed_client(self):
        return self._pubmed_client
    
    def set_style(self, style):
        self.style = style


class TestHTTPDocumentIntelligenceEndpoints:
    """Integration tests for HTTP document intelligence endpoints."""
    
    @pytest.fixture(scope="class")
    def server_thread(self):
        """Start server in background for testing."""
        import socket
        from http.server import HTTPServer
        
        # Find available port
        sock = socket.socket()
        sock.bind(('', 0))
        port = sock.getsockname()[1]
        sock.close()
        
        # Set up handler with mocks
        CitationHTTPHandler.lookup = MockLookupWithPubMed()
        CitationHTTPHandler.document_intelligence = DocumentIntelligence()
        CitationHTTPHandler.type_detector = Mock()
        
        server = HTTPServer(('127.0.0.1', port), CitationHTTPHandler)
        
        thread = threading.Thread(target=server.serve_forever)
        thread.daemon = True
        thread.start()
        
        time.sleep(0.2)
        
        yield port
        
        server.shutdown()
    
    def test_verify_link_endpoint(self, server_thread):
        """Test GET /api/verify-link endpoint."""
        port = server_thread
        conn = HTTPConnection('127.0.0.1', port)
        
        # Test with invalid URL (should return quickly)
        conn.request('GET', '/api/verify-link?url=not-a-url')
        response = conn.getresponse()
        
        assert response.status == 200
        data = json.loads(response.read())
        assert 'status' in data
    
    def test_suggest_citations_endpoint(self, server_thread):
        """Test POST /api/suggest-citations endpoint."""
        port = server_thread
        conn = HTTPConnection('127.0.0.1', port)
        
        body = json.dumps({
            'content': 'Studies show that 50% of patients respond.'
        })
        headers = {'Content-Type': 'application/json'}
        conn.request('POST', '/api/suggest-citations', body, headers)
        response = conn.getresponse()
        
        assert response.status == 200
        data = json.loads(response.read())
        assert 'count' in data
        assert 'suggestions' in data
    
    def test_check_compliance_endpoint(self, server_thread):
        """Test POST /api/check-compliance endpoint."""
        port = server_thread
        conn = HTTPConnection('127.0.0.1', port)
        
        body = json.dumps({
            'content': 'This is a simple test document.'
        })
        headers = {'Content-Type': 'application/json'}
        conn.request('POST', '/api/check-compliance', body, headers)
        response = conn.getresponse()
        
        assert response.status == 200
        data = json.loads(response.read())
        assert 'compliance_score' in data
        assert 'total_issues' in data
    
    def test_analyze_document_endpoint(self, server_thread):
        """Test POST /api/analyze-document endpoint."""
        port = server_thread
        conn = HTTPConnection('127.0.0.1', port)
        
        body = json.dumps({
            'content': '# Test\n\nSimple content.',
            'verify_links': False,  # Skip link verification for speed
            'suggest_citations': True,
            'check_plagiarism': True,
        })
        headers = {'Content-Type': 'application/json'}
        conn.request('POST', '/api/analyze-document', body, headers)
        response = conn.getresponse()
        
        assert response.status == 200
        data = json.loads(response.read())
        assert 'overall_health_score' in data
        assert 'timestamp' in data
    
    def test_suggest_citations_missing_content(self, server_thread):
        """Test error when content is missing."""
        port = server_thread
        conn = HTTPConnection('127.0.0.1', port)
        
        body = json.dumps({})
        headers = {'Content-Type': 'application/json'}
        conn.request('POST', '/api/suggest-citations', body, headers)
        response = conn.getresponse()
        
        assert response.status == 400
        data = json.loads(response.read())
        assert 'error' in data


class TestHTTPBackupFunctionality:
    """Tests for HTTP server backup functionality."""
    
    def test_create_backup_method(self):
        """Test HTTP handler _create_backup method."""
        handler = CitationHTTPHandler.__new__(CitationHTTPHandler)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "test.md")
            content = "# Test Content"
            with open(file_path, 'w') as f:
                f.write(content)
            
            backup_path = handler._create_backup(file_path, content)
            
            assert os.path.exists(backup_path)
            assert "test_backup_" in backup_path


class TestMCPToolsList:
    """Tests for MCP tool listing including new tools."""
    
    def test_document_intelligence_tools_listed(self):
        """Test that all document intelligence tools are listed."""
        from mcp_server.server import list_tools
        
        tools = run_async(list_tools())
        tool_names = [t.name for t in tools]
        
        # Document intelligence tools
        assert "citation_verify_links" in tool_names
        assert "citation_suggest_citations" in tool_names
        assert "citation_check_compliance" in tool_names
        assert "citation_analyze_document" in tool_names
        assert "citation_extract_metadata_llm" in tool_names
    
    def test_document_intelligence_tools_have_schemas(self):
        """Test that document intelligence tools have proper schemas."""
        from mcp_server.server import list_tools
        
        tools = run_async(list_tools())
        di_tools = [t for t in tools if t.name.startswith('citation_') and 
                    any(x in t.name for x in ['verify', 'suggest', 'compliance', 'analyze', 'extract_metadata'])]
        
        for tool in di_tools:
            assert tool.description is not None
            assert len(tool.description) > 10
            assert tool.inputSchema is not None
            assert "properties" in tool.inputSchema

