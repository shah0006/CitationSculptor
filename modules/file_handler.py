"""File Handler Module - Handles file I/O operations."""

import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional
from loguru import logger


class FileHandler:
    """Handles all file operations for CitationSculptor."""

    def __init__(self, input_path: str):
        self.input_path = Path(input_path).resolve()
        self.original_content: Optional[str] = None
        if not self.input_path.exists():
            raise FileNotFoundError(f"File not found: {self.input_path}")

    def read_file(self) -> str:
        """Read the input markdown file."""
        logger.info(f"Reading: {self.input_path}")
        with open(self.input_path, 'r', encoding='utf-8') as f:
            self.original_content = f.read()
        logger.info(f"Read {len(self.original_content)} characters")
        return self.original_content

    def create_backup(self) -> Path:
        """Create a timestamped backup."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{self.input_path.stem}_backup_{timestamp}{self.input_path.suffix}"
        backup_path = self.input_path.parent / backup_name
        shutil.copy2(self.input_path, backup_path)
        logger.info(f"Backup created: {backup_path}")
        return backup_path

    def get_output_path(self, output_path: Optional[str] = None) -> Path:
        """Determine the output file path."""
        if output_path:
            return Path(output_path).resolve()
        return self.input_path.parent / f"{self.input_path.stem}_formatted{self.input_path.suffix}"

    def write_output(self, content: str, output_path: Optional[str] = None) -> Path:
        """Write formatted content to output file."""
        out_path = self.get_output_path(output_path)
        logger.info(f"Writing to: {out_path}")
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(content)
        logger.info(f"Wrote {len(content)} characters")
        return out_path

    def get_file_info(self) -> dict:
        """Get input file metadata."""
        stat = self.input_path.stat()
        return {
            'path': str(self.input_path),
            'name': self.input_path.name,
            'size_bytes': stat.st_size,
            'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
        }

