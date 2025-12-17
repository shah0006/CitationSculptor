"""
Safety tests for the save_to_file feature in document processing.
These tests verify that the auto-save functionality works correctly and safely.
All tests use HTTP calls to the running server for accurate integration testing.
"""
import os
import sys
import tempfile
import shutil
import glob
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Check if server is running
def server_available():
    """Check if the CitationSculptor server is running."""
    try:
        import requests
        health = requests.get("http://127.0.0.1:3019/health", timeout=2)
        return health.status_code == 200
    except:
        return False


@pytest.fixture
def test_file():
    """Create a temporary test file."""
    temp_dir = tempfile.mkdtemp()
    test_path = os.path.join(temp_dir, "test_document.md")
    original_content = """# Test Document

This is a test document with some content.

## References
Some medical claim here [^1].

[^1]: https://pubmed.ncbi.nlm.nih.gov/12345678/
"""
    with open(test_path, 'w', encoding='utf-8') as f:
        f.write(original_content)
    
    yield {
        'dir': temp_dir,
        'path': test_path,
        'content': original_content
    }
    
    # Cleanup
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)


@pytest.fixture
def simple_test_file():
    """Create a simple test file without references."""
    temp_dir = tempfile.mkdtemp()
    test_path = os.path.join(temp_dir, "simple_test.md")
    original_content = """# Simple Test

No references here, just text.
"""
    with open(test_path, 'w', encoding='utf-8') as f:
        f.write(original_content)
    
    yield {
        'dir': temp_dir,
        'path': test_path,
        'content': original_content
    }
    
    # Cleanup
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)


@pytest.mark.skipif(not server_available(), reason="Server not running")
class TestSaveToFileSafety:
    """Test suite for save_to_file functionality with full safety verification."""
    
    def test_save_to_file_false_does_not_modify_original(self, test_file):
        """Verify save_to_file=false leaves original file unchanged."""
        import requests
        
        # Get original modification time and content
        original_mtime = os.path.getmtime(test_file['path'])
        
        # Process without saving
        response = requests.post(
            "http://127.0.0.1:3019/api/process-document",
            json={
                "file_path": test_file['path'],
                "style": "vancouver",
                "save_to_file": False,
                "create_backup": False
            },
            timeout=30
        )
        
        data = response.json()
        assert data.get('success'), f"Processing should succeed: {data}"
        
        # Verify original was NOT modified
        new_mtime = os.path.getmtime(test_file['path'])
        assert original_mtime == new_mtime, "File should not be modified when save_to_file=false"
        
        with open(test_file['path'], 'r') as f:
            assert f.read() == test_file['content'], "Content should be unchanged"
    
    def test_save_to_file_true_creates_backup_first(self, simple_test_file):
        """Verify save_to_file=true ALWAYS creates backup before modifying."""
        import requests
        
        # Count existing backups
        backup_pattern = os.path.join(simple_test_file['dir'], "*_backup_*.md")
        initial_backups = glob.glob(backup_pattern)
        assert len(initial_backups) == 0, "Should start with no backups"
        
        # Process WITH saving
        response = requests.post(
            "http://127.0.0.1:3019/api/process-document",
            json={
                "file_path": simple_test_file['path'],
                "style": "vancouver",
                "save_to_file": True
            },
            timeout=30
        )
        
        data = response.json()
        assert data.get('success'), f"Processing should succeed: {data}"
        
        # Verify backup was created
        assert "backup_path" in data, "Response should include backup_path"
        assert os.path.exists(data["backup_path"]), f"Backup file should exist at {data['backup_path']}"
        
        # Verify backup count increased
        final_backups = glob.glob(backup_pattern)
        assert len(final_backups) == 1, "Exactly one backup should be created"
    
    def test_save_to_file_true_writes_processed_content(self, simple_test_file):
        """Verify save_to_file=true writes processed content to file."""
        import requests
        
        # Process WITH saving
        response = requests.post(
            "http://127.0.0.1:3019/api/process-document",
            json={
                "file_path": simple_test_file['path'],
                "style": "vancouver",
                "save_to_file": True
            },
            timeout=30
        )
        
        data = response.json()
        assert data.get('success'), f"Processing should succeed: {data}"
        assert data.get('saved_to_file') == True, "saved_to_file should be True"
        assert "saved_path" in data, "Response should include saved_path"
        
        # Verify file content matches processed_content
        with open(simple_test_file['path'], 'r', encoding='utf-8') as f:
            file_content = f.read()
        assert file_content == data["processed_content"], "File should contain processed content"
    
    def test_response_includes_all_safety_info(self, simple_test_file):
        """Verify API response includes all safety-related information."""
        import requests
        
        response = requests.post(
            "http://127.0.0.1:3019/api/process-document",
            json={
                "file_path": simple_test_file['path'],
                "style": "vancouver",
                "save_to_file": True
            },
            timeout=30
        )
        
        data = response.json()
        assert data.get('success'), f"Processing should succeed: {data}"
        
        # Verify safety-related fields
        assert "backup_path" in data, "Should include backup_path"
        assert "saved_to_file" in data, "Should include saved_to_file status"
        assert "saved_path" in data, "Should include saved_path"
        
        # Verify paths are absolute and valid
        assert os.path.isabs(data["backup_path"]), "backup_path should be absolute"
        assert os.path.isabs(data["saved_path"]), "saved_path should be absolute"
    
    def test_backup_preserves_original_content(self, simple_test_file):
        """Verify backup contains the original content before modification."""
        import requests
        
        original_content = simple_test_file['content']
        
        # Process WITH saving
        response = requests.post(
            "http://127.0.0.1:3019/api/process-document",
            json={
                "file_path": simple_test_file['path'],
                "style": "vancouver",
                "save_to_file": True
            },
            timeout=30
        )
        
        data = response.json()
        assert data.get('success'), f"Processing should succeed: {data}"
        
        # Read backup content
        with open(data["backup_path"], 'r', encoding='utf-8') as f:
            backup_content = f.read()
        
        # Verify backup has original content
        assert backup_content == original_content, "Backup should contain original content"
    
    def test_backup_filename_has_timestamp(self, simple_test_file):
        """Verify backup filename includes timestamp for uniqueness."""
        import requests
        
        response = requests.post(
            "http://127.0.0.1:3019/api/process-document",
            json={
                "file_path": simple_test_file['path'],
                "style": "vancouver",
                "save_to_file": True
            },
            timeout=30
        )
        
        data = response.json()
        assert data.get('success'), f"Processing should succeed: {data}"
        
        # Verify timestamp pattern in filename
        backup_filename = os.path.basename(data["backup_path"])
        assert "_backup_" in backup_filename, "Backup filename should contain '_backup_'"
        assert backup_filename.endswith(".md"), "Backup should preserve file extension"
        
        # Extract and validate timestamp (format: YYYYMMDD_HHMMSS)
        parts = backup_filename.split("_backup_")
        assert len(parts) == 2, "Filename should have exactly one _backup_ segment"
        timestamp_part = parts[1].replace(".md", "")
        assert len(timestamp_part) == 15, f"Timestamp should be 15 chars (YYYYMMDD_HHMMSS), got {len(timestamp_part)}"
    
    def test_backup_in_same_directory_as_original(self, simple_test_file):
        """Verify backup is created in same directory as original file."""
        import requests
        
        response = requests.post(
            "http://127.0.0.1:3019/api/process-document",
            json={
                "file_path": simple_test_file['path'],
                "style": "vancouver",
                "save_to_file": True
            },
            timeout=30
        )
        
        data = response.json()
        assert data.get('success'), f"Processing should succeed: {data}"
        
        original_dir = os.path.dirname(simple_test_file['path'])
        backup_dir = os.path.dirname(data["backup_path"])
        
        assert original_dir == backup_dir, "Backup should be in same directory as original"


@pytest.mark.skipif(not server_available(), reason="Server not running")
class TestBackupRecovery:
    """Tests for backup recovery scenarios."""
    
    def test_can_restore_original_from_backup(self, simple_test_file):
        """Verify we can restore original content from backup after processing."""
        import requests
        
        original_content = simple_test_file['content']
        
        # Process WITH saving (modifies file)
        response = requests.post(
            "http://127.0.0.1:3019/api/process-document",
            json={
                "file_path": simple_test_file['path'],
                "style": "vancouver",
                "save_to_file": True
            },
            timeout=30
        )
        
        data = response.json()
        assert data.get('success'), f"Processing should succeed: {data}"
        
        # Verify file was modified (should match processed content)
        with open(simple_test_file['path'], 'r') as f:
            modified_content = f.read()
        assert modified_content == data["processed_content"], "File should have processed content"
        
        # Now restore from backup
        backup_path = data["backup_path"]
        with open(backup_path, 'r', encoding='utf-8') as f:
            backup_content = f.read()
        with open(simple_test_file['path'], 'w', encoding='utf-8') as f:
            f.write(backup_content)
        
        # Verify restoration
        with open(simple_test_file['path'], 'r') as f:
            restored_content = f.read()
        assert restored_content == original_content, "Original content should be restored"
    
    def test_backup_survives_original_file_deletion(self, simple_test_file):
        """Verify backup persists even if original file is deleted."""
        import requests
        
        # Process WITH saving
        response = requests.post(
            "http://127.0.0.1:3019/api/process-document",
            json={
                "file_path": simple_test_file['path'],
                "style": "vancouver",
                "save_to_file": True
            },
            timeout=30
        )
        
        data = response.json()
        assert data.get('success'), f"Processing should succeed: {data}"
        backup_path = data["backup_path"]
        
        # Delete the original file
        os.remove(simple_test_file['path'])
        assert not os.path.exists(simple_test_file['path']), "Original should be deleted"
        
        # Backup should still exist
        assert os.path.exists(backup_path), "Backup should survive original deletion"
        
        # Can read backup content
        with open(backup_path, 'r') as f:
            backup_content = f.read()
        assert backup_content == simple_test_file['content'], "Backup should have original content"
    
    def test_utf8_content_preserved_in_backup(self, simple_test_file):
        """Verify UTF-8 special characters are preserved in backup."""
        import requests
        
        # Write special content
        special_content = "UTF-8 test: émoji 🔬 unicode → symbol © ™ ® β α γ\n日本語テスト"
        with open(simple_test_file['path'], 'w', encoding='utf-8') as f:
            f.write(special_content)
        
        # Process WITH saving
        response = requests.post(
            "http://127.0.0.1:3019/api/process-document",
            json={
                "file_path": simple_test_file['path'],
                "style": "vancouver",
                "save_to_file": True
            },
            timeout=30
        )
        
        data = response.json()
        assert data.get('success'), f"Processing should succeed: {data}"
        
        # Verify backup preserves special characters
        with open(data["backup_path"], 'r', encoding='utf-8') as f:
            backup_content = f.read()
        assert backup_content == special_content, "Backup should preserve UTF-8 content"


@pytest.mark.skipif(not server_available(), reason="Server not running")
class TestEdgeCases:
    """Test edge cases and error handling."""
    
    def test_save_without_file_path_returns_error(self):
        """Verify save_to_file without file_path is handled gracefully."""
        import requests
        
        # Process with content but no file path - save_to_file should be ignored
        response = requests.post(
            "http://127.0.0.1:3019/api/process-document",
            json={
                "content": "# Test\n\nSome content",
                "style": "vancouver",
                "save_to_file": True  # This should be ignored since no file_path
            },
            timeout=30
        )
        
        data = response.json()
        assert data.get('success'), "Processing should succeed even with save_to_file but no path"
        # saved_to_file should NOT be True since there was no file
        assert data.get('saved_to_file') != True, "Should not save when no file_path provided"
    
    def test_nonexistent_file_returns_error(self):
        """Verify processing nonexistent file returns proper error."""
        import requests
        
        response = requests.post(
            "http://127.0.0.1:3019/api/process-document",
            json={
                "file_path": "/nonexistent/path/to/file.md",
                "style": "vancouver",
                "save_to_file": True
            },
            timeout=30
        )
        
        # Should return 404 or error
        assert response.status_code == 404 or "error" in response.json()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
