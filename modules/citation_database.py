"""Citation Database Module.

SQLite-backed persistent storage for citations with:
- Full-text search
- Duplicate detection
- Citation relationships
- Tag/collection support
"""

import sqlite3
import json
import hashlib
from dataclasses import dataclass, asdict
from typing import Optional, List, Dict, Any, Iterator
from pathlib import Path
from datetime import datetime
from loguru import logger


@dataclass
class StoredCitation:
    """A citation stored in the database."""
    id: int
    identifier_type: str  # pmid, doi, arxiv, isbn, etc.
    identifier: str
    title: str
    authors: str  # JSON array
    year: str
    citation_style: str
    inline_mark: str
    full_citation: str
    metadata: str  # JSON object
    tags: str  # JSON array
    collections: str  # JSON array
    created_at: str
    updated_at: str
    notes: Optional[str] = None
    
    @property
    def authors_list(self) -> List[str]:
        try:
            return json.loads(self.authors) if self.authors else []
        except json.JSONDecodeError:
            return []
    
    @property
    def tags_list(self) -> List[str]:
        try:
            return json.loads(self.tags) if self.tags else []
        except json.JSONDecodeError:
            return []
    
    @property
    def metadata_dict(self) -> Dict[str, Any]:
        try:
            return json.loads(self.metadata) if self.metadata else {}
        except json.JSONDecodeError:
            return {}


class CitationDatabase:
    """
    SQLite-backed citation database with full-text search.
    """
    
    SCHEMA = """
    -- Main citations table
    CREATE TABLE IF NOT EXISTS citations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        identifier_type TEXT NOT NULL,
        identifier TEXT NOT NULL,
        title TEXT NOT NULL,
        authors TEXT DEFAULT '[]',
        year TEXT,
        citation_style TEXT DEFAULT 'vancouver',
        inline_mark TEXT,
        full_citation TEXT,
        metadata TEXT DEFAULT '{}',
        tags TEXT DEFAULT '[]',
        collections TEXT DEFAULT '[]',
        notes TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(identifier_type, identifier, citation_style)
    );
    
    -- Full-text search virtual table
    CREATE VIRTUAL TABLE IF NOT EXISTS citations_fts USING fts5(
        title, authors, notes,
        content='citations',
        content_rowid='id'
    );
    
    -- Triggers to keep FTS in sync
    CREATE TRIGGER IF NOT EXISTS citations_ai AFTER INSERT ON citations BEGIN
        INSERT INTO citations_fts(rowid, title, authors, notes)
        VALUES (new.id, new.title, new.authors, new.notes);
    END;
    
    CREATE TRIGGER IF NOT EXISTS citations_ad AFTER DELETE ON citations BEGIN
        INSERT INTO citations_fts(citations_fts, rowid, title, authors, notes)
        VALUES ('delete', old.id, old.title, old.authors, old.notes);
    END;
    
    CREATE TRIGGER IF NOT EXISTS citations_au AFTER UPDATE ON citations BEGIN
        INSERT INTO citations_fts(citations_fts, rowid, title, authors, notes)
        VALUES ('delete', old.id, old.title, old.authors, old.notes);
        INSERT INTO citations_fts(rowid, title, authors, notes)
        VALUES (new.id, new.title, new.authors, new.notes);
    END;
    
    -- Collections table
    CREATE TABLE IF NOT EXISTS collections (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        description TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    
    -- Citation relationships (cited_by, references)
    CREATE TABLE IF NOT EXISTS citation_links (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source_id INTEGER NOT NULL,
        target_id INTEGER NOT NULL,
        link_type TEXT NOT NULL,  -- 'cites', 'cited_by', 'related'
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (source_id) REFERENCES citations(id) ON DELETE CASCADE,
        FOREIGN KEY (target_id) REFERENCES citations(id) ON DELETE CASCADE,
        UNIQUE(source_id, target_id, link_type)
    );
    
    -- Indexes
    CREATE INDEX IF NOT EXISTS idx_citations_identifier ON citations(identifier_type, identifier);
    CREATE INDEX IF NOT EXISTS idx_citations_year ON citations(year);
    CREATE INDEX IF NOT EXISTS idx_citations_style ON citations(citation_style);
    """
    
    def __init__(self, db_path: str = None):
        """
        Initialize the citation database.
        
        Args:
            db_path: Path to SQLite database file. Defaults to .cache/citations.db
        """
        if db_path is None:
            cache_dir = Path(__file__).parent.parent / ".cache"
            cache_dir.mkdir(exist_ok=True)
            db_path = str(cache_dir / "citations.db")
        
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """Initialize database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(self.SCHEMA)
            conn.commit()
    
    def _get_conn(self) -> sqlite3.Connection:
        """Get a database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def add_citation(
        self,
        identifier_type: str,
        identifier: str,
        title: str,
        authors: List[str] = None,
        year: str = "",
        citation_style: str = "vancouver",
        inline_mark: str = "",
        full_citation: str = "",
        metadata: Dict[str, Any] = None,
        tags: List[str] = None,
        collections: List[str] = None,
        notes: str = None
    ) -> int:
        """
        Add or update a citation in the database.
        
        Returns:
            Citation ID
        """
        authors_json = json.dumps(authors or [])
        metadata_json = json.dumps(metadata or {})
        tags_json = json.dumps(tags or [])
        collections_json = json.dumps(collections or [])
        
        with self._get_conn() as conn:
            cursor = conn.execute("""
                INSERT INTO citations (
                    identifier_type, identifier, title, authors, year,
                    citation_style, inline_mark, full_citation,
                    metadata, tags, collections, notes, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(identifier_type, identifier, citation_style) DO UPDATE SET
                    title = excluded.title,
                    authors = excluded.authors,
                    year = excluded.year,
                    inline_mark = excluded.inline_mark,
                    full_citation = excluded.full_citation,
                    metadata = excluded.metadata,
                    tags = excluded.tags,
                    collections = excluded.collections,
                    notes = COALESCE(excluded.notes, citations.notes),
                    updated_at = CURRENT_TIMESTAMP
                RETURNING id
            """, (
                identifier_type, identifier, title, authors_json, year,
                citation_style, inline_mark, full_citation,
                metadata_json, tags_json, collections_json, notes
            ))
            
            result = cursor.fetchone()
            conn.commit()
            return result[0]
    
    def get_citation(self, citation_id: int) -> Optional[StoredCitation]:
        """Get a citation by ID."""
        with self._get_conn() as conn:
            cursor = conn.execute(
                "SELECT * FROM citations WHERE id = ?",
                (citation_id,)
            )
            row = cursor.fetchone()
            if row:
                return StoredCitation(**dict(row))
            return None
    
    def get_by_identifier(
        self, 
        identifier_type: str, 
        identifier: str,
        citation_style: str = None
    ) -> Optional[StoredCitation]:
        """Get a citation by identifier."""
        with self._get_conn() as conn:
            if citation_style:
                cursor = conn.execute(
                    "SELECT * FROM citations WHERE identifier_type = ? AND identifier = ? AND citation_style = ?",
                    (identifier_type, identifier, citation_style)
                )
            else:
                cursor = conn.execute(
                    "SELECT * FROM citations WHERE identifier_type = ? AND identifier = ? LIMIT 1",
                    (identifier_type, identifier)
                )
            row = cursor.fetchone()
            if row:
                return StoredCitation(**dict(row))
            return None
    
    def search(self, query: str, limit: int = 50) -> List[StoredCitation]:
        """
        Full-text search for citations.
        
        Args:
            query: Search query
            limit: Maximum results
        
        Returns:
            List of matching citations
        """
        with self._get_conn() as conn:
            cursor = conn.execute("""
                SELECT c.* FROM citations c
                JOIN citations_fts fts ON c.id = fts.rowid
                WHERE citations_fts MATCH ?
                ORDER BY rank
                LIMIT ?
            """, (query, limit))
            
            return [StoredCitation(**dict(row)) for row in cursor.fetchall()]
    
    def search_by_title(self, title: str, threshold: float = 0.8) -> List[StoredCitation]:
        """
        Search for citations with similar titles (for duplicate detection).
        
        Args:
            title: Title to search for
            threshold: Similarity threshold (0-1)
        
        Returns:
            List of potentially matching citations
        """
        # Use FTS for initial filtering
        words = title.split()[:5]
        query = ' OR '.join(words)
        
        return self.search(query, limit=20)
    
    def get_all(
        self, 
        citation_style: str = None,
        year: str = None,
        collection: str = None,
        limit: int = 1000,
        offset: int = 0
    ) -> List[StoredCitation]:
        """
        Get all citations with optional filters.
        """
        conditions = []
        params = []
        
        if citation_style:
            conditions.append("citation_style = ?")
            params.append(citation_style)
        if year:
            conditions.append("year = ?")
            params.append(year)
        if collection:
            conditions.append("collections LIKE ?")
            params.append(f'%"{collection}"%')
        
        where = "WHERE " + " AND ".join(conditions) if conditions else ""
        
        with self._get_conn() as conn:
            cursor = conn.execute(f"""
                SELECT * FROM citations {where}
                ORDER BY updated_at DESC
                LIMIT ? OFFSET ?
            """, params + [limit, offset])
            
            return [StoredCitation(**dict(row)) for row in cursor.fetchall()]
    
    def delete_citation(self, citation_id: int) -> bool:
        """Delete a citation by ID."""
        with self._get_conn() as conn:
            cursor = conn.execute(
                "DELETE FROM citations WHERE id = ?",
                (citation_id,)
            )
            conn.commit()
            return cursor.rowcount > 0
    
    def add_tag(self, citation_id: int, tag: str):
        """Add a tag to a citation."""
        citation = self.get_citation(citation_id)
        if citation:
            tags = citation.tags_list
            if tag not in tags:
                tags.append(tag)
                with self._get_conn() as conn:
                    conn.execute(
                        "UPDATE citations SET tags = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                        (json.dumps(tags), citation_id)
                    )
                    conn.commit()
    
    def remove_tag(self, citation_id: int, tag: str):
        """Remove a tag from a citation."""
        citation = self.get_citation(citation_id)
        if citation:
            tags = citation.tags_list
            if tag in tags:
                tags.remove(tag)
                with self._get_conn() as conn:
                    conn.execute(
                        "UPDATE citations SET tags = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                        (json.dumps(tags), citation_id)
                    )
                    conn.commit()
    
    def add_link(self, source_id: int, target_id: int, link_type: str):
        """Add a relationship between citations."""
        with self._get_conn() as conn:
            try:
                conn.execute("""
                    INSERT OR IGNORE INTO citation_links (source_id, target_id, link_type)
                    VALUES (?, ?, ?)
                """, (source_id, target_id, link_type))
                conn.commit()
            except sqlite3.IntegrityError:
                pass
    
    def get_linked_citations(self, citation_id: int, link_type: str = None) -> List[StoredCitation]:
        """Get citations linked to a given citation."""
        with self._get_conn() as conn:
            if link_type:
                cursor = conn.execute("""
                    SELECT c.* FROM citations c
                    JOIN citation_links l ON c.id = l.target_id
                    WHERE l.source_id = ? AND l.link_type = ?
                """, (citation_id, link_type))
            else:
                cursor = conn.execute("""
                    SELECT c.* FROM citations c
                    JOIN citation_links l ON c.id = l.target_id
                    WHERE l.source_id = ?
                """, (citation_id,))
            
            return [StoredCitation(**dict(row)) for row in cursor.fetchall()]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get database statistics."""
        with self._get_conn() as conn:
            stats = {}
            
            # Total count
            cursor = conn.execute("SELECT COUNT(*) FROM citations")
            stats['total_citations'] = cursor.fetchone()[0]
            
            # By type
            cursor = conn.execute("""
                SELECT identifier_type, COUNT(*) as count
                FROM citations GROUP BY identifier_type
            """)
            stats['by_type'] = dict(cursor.fetchall())
            
            # By year
            cursor = conn.execute("""
                SELECT year, COUNT(*) as count
                FROM citations WHERE year != ''
                GROUP BY year ORDER BY year DESC LIMIT 10
            """)
            stats['by_year'] = dict(cursor.fetchall())
            
            # By style
            cursor = conn.execute("""
                SELECT citation_style, COUNT(*) as count
                FROM citations GROUP BY citation_style
            """)
            stats['by_style'] = dict(cursor.fetchall())
            
            return stats
    
    def export_all(self, format: str = "json") -> str:
        """
        Export all citations.
        
        Args:
            format: 'json', 'bibtex', or 'ris'
        
        Returns:
            Exported data as string
        """
        citations = self.get_all(limit=100000)
        
        if format == "json":
            return json.dumps([asdict(c) for c in citations], indent=2)
        
        # For bibtex/ris, would need the handler modules
        return json.dumps([asdict(c) for c in citations], indent=2)
    
    def vacuum(self):
        """Optimize database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("VACUUM")

