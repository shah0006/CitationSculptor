"""
Tests for MCP server (mcp_server/server.py).

Tests cover:
- Tool listing
- Tool execution for all citation tools
- Result formatting
- Error handling
"""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock
import asyncio

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp_server.server import (
    server,
    lookup,
    list_tools,
    call_tool,
    format_result,
)
from citation_lookup import LookupResult


def run_async(coro):
    """Helper to run async functions in sync tests."""
    return asyncio.get_event_loop().run_until_complete(coro)


class TestFormatResult:
    """Test cases for format_result function."""

    def test_format_successful_result(self):
        """Test formatting a successful lookup result."""
        result = LookupResult(
            success=True,
            identifier="32089132",
            identifier_type="pmid",
            inline_mark="[^KramerCM-2020-32089132]",
            endnote_citation="[^KramerCM-2020-32089132]: Kramer CM...",
            full_citation="[^KramerCM-2020-32089132]: Kramer CM...",
            metadata={
                "pmid": "32089132",
                "title": "Test Article",
                "authors": ["Smith J", "Jones M", "Brown K", "Wilson L"],
                "journal_abbreviation": "Test J",
                "year": "2024",
                "doi": "10.1234/test"
            },
            error=None
        )
        
        formatted = format_result(result)
        
        assert "**Inline Mark:**" in formatted
        assert "[^KramerCM-2020-32089132]" in formatted
        assert "**Full Citation:**" in formatted
        assert "**Metadata:**" in formatted
        assert "PMID: 32089132" in formatted

    def test_format_failed_result(self):
        """Test formatting a failed lookup result."""
        result = LookupResult(
            success=False,
            identifier="invalid",
            identifier_type="unknown",
            error="Article not found"
        )
        
        formatted = format_result(result)
        
        assert "Error:" in formatted
        assert "Article not found" in formatted

    def test_format_result_truncates_authors(self):
        """Test that authors are truncated if more than 3."""
        result = LookupResult(
            success=True,
            identifier="123",
            identifier_type="pmid",
            inline_mark="[^Test]",
            full_citation="Full",
            metadata={
                "authors": ["Author1", "Author2", "Author3", "Author4", "Author5"],
                "title": "Test"
            }
        )
        
        formatted = format_result(result)
        
        assert "Author1" in formatted
        assert "Author2" in formatted
        assert "Author3" in formatted
        assert "..." in formatted  # Truncation indicator


class TestListTools:
    """Test cases for tool listing."""

    def test_list_tools_returns_all_tools(self):
        """Test that list_tools returns all available tools."""
        tools = run_async(list_tools())
        
        tool_names = [t.name for t in tools]
        
        # Core lookup tools
        assert "citation_lookup_pmid" in tool_names
        assert "citation_lookup_doi" in tool_names
        assert "citation_lookup_pmcid" in tool_names
        assert "citation_lookup_title" in tool_names
        assert "citation_lookup_auto" in tool_names
        
        # Format tools
        assert "citation_get_inline_only" in tool_names
        assert "citation_get_endnote_only" in tool_names
        assert "citation_get_metadata" in tool_names
        assert "citation_get_abstract" in tool_names
        
        # Search and batch
        assert "citation_search_pubmed" in tool_names
        assert "citation_batch_lookup" in tool_names
        
        # Utility
        assert "citation_test_connection" in tool_names

    def test_tools_have_required_schema(self):
        """Test that all tools have required schema fields."""
        tools = run_async(list_tools())
        
        for tool in tools:
            assert tool.name is not None
            assert tool.description is not None
            assert tool.inputSchema is not None
            assert "type" in tool.inputSchema
            assert "properties" in tool.inputSchema


class TestCallTool:
    """Test cases for tool execution."""

    @patch('mcp_server.server.lookup')
    def test_call_citation_lookup_pmid(self, mock_lookup):
        """Test calling citation_lookup_pmid tool."""
        mock_result = LookupResult(
            success=True,
            identifier="32089132",
            identifier_type="pmid",
            inline_mark="[^Test-2024]",
            full_citation="Full citation",
            metadata={"pmid": "32089132"}
        )
        mock_lookup.lookup_pmid = Mock(return_value=mock_result)
        
        result = run_async(call_tool("citation_lookup_pmid", {"pmid": "32089132"}))
        
        assert len(result) == 1
        assert result[0].type == "text"
        assert "Test-2024" in result[0].text

    @patch('mcp_server.server.lookup')
    def test_call_citation_lookup_doi(self, mock_lookup):
        """Test calling citation_lookup_doi tool."""
        mock_result = LookupResult(
            success=True,
            identifier="10.1234/test",
            identifier_type="doi",
            inline_mark="[^DOI-Test]",
            full_citation="Full citation"
        )
        mock_lookup.lookup_doi = Mock(return_value=mock_result)
        
        result = run_async(call_tool("citation_lookup_doi", {"doi": "10.1234/test"}))
        
        assert len(result) == 1
        assert "DOI-Test" in result[0].text

    @patch('mcp_server.server.lookup')
    def test_call_citation_get_inline_only(self, mock_lookup):
        """Test calling citation_get_inline_only tool."""
        mock_result = LookupResult(
            success=True,
            identifier="123",
            identifier_type="pmid",
            inline_mark="[^TestInline-2024]",
            full_citation="Full"
        )
        mock_lookup.lookup_auto = Mock(return_value=mock_result)
        
        result = run_async(call_tool("citation_get_inline_only", {"identifier": "123"}))
        
        assert len(result) == 1
        assert result[0].text == "[^TestInline-2024]"

    @patch('mcp_server.server.lookup')
    def test_call_citation_get_metadata(self, mock_lookup):
        """Test calling citation_get_metadata tool."""
        mock_result = LookupResult(
            success=True,
            identifier="123",
            identifier_type="pmid",
            inline_mark="[^Test]",
            metadata={"title": "Test Title", "year": "2024"}
        )
        mock_lookup.lookup_auto = Mock(return_value=mock_result)
        
        result = run_async(call_tool("citation_get_metadata", {"identifier": "123"}))
        
        assert len(result) == 1
        parsed = json.loads(result[0].text)
        assert parsed["title"] == "Test Title"
        assert parsed["year"] == "2024"

    @patch('mcp_server.server.lookup')
    def test_call_citation_get_abstract(self, mock_lookup):
        """Test calling citation_get_abstract tool."""
        mock_result = LookupResult(
            success=True,
            identifier="123",
            identifier_type="pmid",
            inline_mark="[^Test]",
            metadata={"abstract": "This is the abstract text."}
        )
        mock_lookup.lookup_auto = Mock(return_value=mock_result)
        
        result = run_async(call_tool("citation_get_abstract", {"identifier": "123"}))
        
        assert len(result) == 1
        assert "This is the abstract text." in result[0].text

    @patch('mcp_server.server.lookup')
    def test_call_citation_search_pubmed(self, mock_lookup):
        """Test calling citation_search_pubmed tool."""
        mock_article = Mock()
        mock_article.title = "Test Article"
        mock_article.authors = ["Smith J"]
        mock_article.journal_abbreviation = "Test J"
        mock_article.journal = "Test Journal"
        mock_article.year = "2024"
        mock_article.pmid = "12345"
        mock_article.doi = "10.1234/test"
        
        mock_lookup.pubmed_client = Mock()
        mock_lookup.pubmed_client.search_by_title = Mock(return_value=[mock_article])
        
        result = run_async(call_tool("citation_search_pubmed", {"query": "test"}))
        
        assert len(result) == 1
        assert "Test Article" in result[0].text
        assert "12345" in result[0].text

    @patch('mcp_server.server.lookup')
    def test_call_citation_batch_lookup(self, mock_lookup):
        """Test calling citation_batch_lookup tool."""
        mock_results = [
            LookupResult(success=True, identifier="1", identifier_type="pmid", 
                        inline_mark="[^Test1]", full_citation="Citation 1"),
            LookupResult(success=True, identifier="2", identifier_type="pmid",
                        inline_mark="[^Test2]", full_citation="Citation 2"),
        ]
        mock_lookup.batch_lookup = Mock(return_value=mock_results)
        
        result = run_async(call_tool("citation_batch_lookup", {"identifiers": ["1", "2"]}))
        
        assert len(result) == 1
        assert "[^Test1]" in result[0].text
        assert "[^Test2]" in result[0].text

    def test_call_unknown_tool(self):
        """Test calling unknown tool returns error."""
        result = run_async(call_tool("unknown_tool", {}))
        
        assert len(result) == 1
        assert "Unknown tool" in result[0].text

    @patch('mcp_server.server.lookup')
    def test_call_tool_handles_exception(self, mock_lookup):
        """Test that tool errors are handled gracefully."""
        mock_lookup.lookup_pmid = Mock(side_effect=Exception("Test error"))
        
        result = run_async(call_tool("citation_lookup_pmid", {"pmid": "123"}))
        
        assert len(result) == 1
        assert "Error" in result[0].text


class TestConnectionTool:
    """Test cases for connection test tool."""

    @patch('mcp_server.server.lookup')
    def test_connection_test_success(self, mock_lookup):
        """Test successful connection test."""
        mock_lookup.test_connection = Mock(return_value=True)
        
        result = run_async(call_tool("citation_test_connection", {}))
        
        assert len(result) == 1
        assert "OK" in result[0].text

    @patch('mcp_server.server.lookup')
    def test_connection_test_failure(self, mock_lookup):
        """Test failed connection test."""
        mock_lookup.test_connection = Mock(return_value=False)
        
        result = run_async(call_tool("citation_test_connection", {}))
        
        assert len(result) == 1
        assert "FAILED" in result[0].text

