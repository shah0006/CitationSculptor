"""
Learning Engine Module - Self-improving citation resolution system.

This module implements a learning system that:
1. Tracks failed lookups and their reasons
2. Stores successful resolution strategies
3. Learns URL/domain patterns for identifier extraction
4. Records user corrections to improve future lookups
5. Provides suggestions based on learned patterns

The learning database persists across sessions, allowing the tool
to improve over time as it encounters more cases.
"""

import sqlite3
import json
import re
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, asdict
from loguru import logger


@dataclass
class FailureRecord:
    """Record of a failed lookup attempt."""
    url: Optional[str]
    title: Optional[str]
    domain: Optional[str]
    failure_reason: str
    failure_type: str  # 'no_identifier', 'lookup_failed', 'network_error', 'parse_error'
    attempted_strategies: List[str]  # What was tried
    timestamp: str
    resolved: bool = False
    resolution_strategy: Optional[str] = None
    resolution_identifier: Optional[str] = None


@dataclass
class LearnedPattern:
    """A learned pattern for identifier extraction."""
    domain: str
    pattern_type: str  # 'doi_in_url', 'doi_in_meta', 'pmid_in_url', 'scrape_required'
    regex_pattern: Optional[str]
    meta_tag: Optional[str]
    success_count: int
    last_success: str
    notes: Optional[str] = None


@dataclass
class UserCorrection:
    """A user-provided correction to teach the system."""
    original_url: Optional[str]
    original_title: Optional[str]
    correct_identifier: str
    identifier_type: str  # 'pmid', 'doi', 'pmcid'
    correction_source: str  # 'manual', 'feedback', 'api'
    timestamp: str


class LearningEngine:
    """
    Self-learning system for improving citation resolution over time.
    
    The engine maintains a SQLite database with:
    - Failure records: What failed and why
    - Learned patterns: Domain-specific extraction rules
    - User corrections: Manual fixes that teach the system
    - Resolution strategies: What worked for previously failed cases
    """
    
    SCHEMA = """
    -- Failed lookup attempts
    CREATE TABLE IF NOT EXISTS failures (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        url TEXT,
        title TEXT,
        domain TEXT,
        failure_reason TEXT NOT NULL,
        failure_type TEXT NOT NULL,
        attempted_strategies TEXT,  -- JSON array
        timestamp TEXT NOT NULL,
        resolved INTEGER DEFAULT 0,
        resolution_strategy TEXT,
        resolution_identifier TEXT,
        resolution_timestamp TEXT
    );
    
    -- Learned patterns for domains
    CREATE TABLE IF NOT EXISTS patterns (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        domain TEXT NOT NULL UNIQUE,
        pattern_type TEXT NOT NULL,
        regex_pattern TEXT,
        meta_tag TEXT,
        success_count INTEGER DEFAULT 1,
        last_success TEXT NOT NULL,
        notes TEXT
    );
    
    -- User corrections
    CREATE TABLE IF NOT EXISTS corrections (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        original_url TEXT,
        original_title TEXT,
        correct_identifier TEXT NOT NULL,
        identifier_type TEXT NOT NULL,
        correction_source TEXT NOT NULL,
        timestamp TEXT NOT NULL
    );
    
    -- Resolution strategies that worked
    CREATE TABLE IF NOT EXISTS strategies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        domain TEXT,
        url_pattern TEXT,
        strategy_name TEXT NOT NULL,
        strategy_config TEXT,  -- JSON with strategy-specific config
        success_count INTEGER DEFAULT 1,
        failure_count INTEGER DEFAULT 0,
        last_used TEXT NOT NULL
    );
    
    -- Domain-specific metadata extraction rules
    CREATE TABLE IF NOT EXISTS domain_rules (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        domain TEXT NOT NULL UNIQUE,
        doi_url_pattern TEXT,
        doi_meta_tag TEXT,
        pmid_url_pattern TEXT,
        pmid_meta_tag TEXT,
        title_selector TEXT,
        author_selector TEXT,
        requires_scraping INTEGER DEFAULT 0,
        requires_javascript INTEGER DEFAULT 0,
        notes TEXT,
        last_updated TEXT NOT NULL
    );
    
    -- Indexes for performance
    CREATE INDEX IF NOT EXISTS idx_failures_domain ON failures(domain);
    CREATE INDEX IF NOT EXISTS idx_failures_resolved ON failures(resolved);
    CREATE INDEX IF NOT EXISTS idx_patterns_domain ON patterns(domain);
    CREATE INDEX IF NOT EXISTS idx_corrections_identifier ON corrections(correct_identifier);
    CREATE INDEX IF NOT EXISTS idx_strategies_domain ON strategies(domain);
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """Initialize the learning engine."""
        if db_path is None:
            cache_dir = Path(__file__).parent.parent / ".cache"
            cache_dir.mkdir(exist_ok=True)
            db_path = str(cache_dir / "learning.db")
        
        self.db_path = db_path
        self._init_db()
        self._load_builtin_patterns()
        logger.info(f"Learning engine initialized with database: {db_path}")
    
    def _init_db(self):
        """Initialize database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(self.SCHEMA)
            conn.commit()
    
    def _load_builtin_patterns(self):
        """Load built-in patterns for known domains."""
        builtin_rules = [
            {
                'domain': 'frontiersin.org',
                'doi_url_pattern': r'/articles/(10\.\d{4,}/[^/]+)',
                'requires_scraping': 0,
                'notes': 'DOI embedded in URL path after /articles/'
            },
            {
                'domain': 'pubmed.ncbi.nlm.nih.gov',
                'pmid_url_pattern': r'pubmed\.ncbi\.nlm\.nih\.gov/(\d+)',
                'requires_scraping': 0,
                'notes': 'PMID is the numeric path segment'
            },
            {
                'domain': 'pmc.ncbi.nlm.nih.gov',
                'pmid_meta_tag': 'citation_pmid',
                'requires_scraping': 1,
                'notes': 'PMID in meta tag, may need to scrape'
            },
            {
                'domain': 'doi.org',
                'doi_url_pattern': r'doi\.org/(10\.\d{4,}/[^\s\)\]]+)',
                'requires_scraping': 0,
                'notes': 'Direct DOI URL'
            },
            {
                'domain': 'nature.com',
                'doi_meta_tag': 'citation_doi',
                'requires_scraping': 1,
                'notes': 'DOI in meta tag'
            },
            {
                'domain': 'sciencedirect.com',
                'doi_meta_tag': 'citation_doi',
                'requires_scraping': 1,
                'notes': 'DOI in meta tag'
            },
            {
                'domain': 'ahajournals.org',
                'doi_url_pattern': r'/doi/(10\.\d{4,}/[^/\?]+)',
                'requires_scraping': 0,
                'notes': 'DOI in URL path'
            },
            {
                'domain': 'mdpi.com',
                'doi_url_pattern': r'mdpi\.com/\d+-\d+/\d+/\d+/(\d+)',
                'doi_meta_tag': 'citation_doi',
                'requires_scraping': 1,
                'notes': 'Article ID in URL, DOI in meta'
            },
            {
                'domain': 'ecrjournal.com',
                'doi_meta_tag': 'citation_doi',
                'requires_scraping': 1,
                'notes': 'European Cardiology Review - DOI in meta tag'
            },
            {
                'domain': 'dovepress.com',
                'doi_meta_tag': 'citation_doi',
                'requires_scraping': 1,
                'notes': 'Dove Medical Press - DOI in meta tag'
            },
        ]
        
        with sqlite3.connect(self.db_path) as conn:
            for rule in builtin_rules:
                # Only insert if doesn't exist
                existing = conn.execute(
                    "SELECT id FROM domain_rules WHERE domain = ?",
                    (rule['domain'],)
                ).fetchone()
                
                if not existing:
                    conn.execute("""
                        INSERT INTO domain_rules 
                        (domain, doi_url_pattern, doi_meta_tag, pmid_url_pattern, 
                         pmid_meta_tag, requires_scraping, notes, last_updated)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        rule['domain'],
                        rule.get('doi_url_pattern'),
                        rule.get('doi_meta_tag'),
                        rule.get('pmid_url_pattern'),
                        rule.get('pmid_meta_tag'),
                        rule.get('requires_scraping', 0),
                        rule.get('notes'),
                        datetime.now().isoformat()
                    ))
            conn.commit()
    
    def record_failure(self, 
                      url: Optional[str],
                      title: Optional[str],
                      failure_reason: str,
                      failure_type: str,
                      attempted_strategies: List[str]) -> int:
        """Record a failed lookup attempt for future learning."""
        domain = self._extract_domain(url) if url else None
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                INSERT INTO failures 
                (url, title, domain, failure_reason, failure_type, 
                 attempted_strategies, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                url, title, domain, failure_reason, failure_type,
                json.dumps(attempted_strategies),
                datetime.now().isoformat()
            ))
            conn.commit()
            failure_id = cursor.lastrowid
            
        logger.debug(f"Recorded failure #{failure_id} for domain {domain}: {failure_reason}")
        return failure_id
    
    def record_success(self,
                      url: Optional[str],
                      identifier: str,
                      identifier_type: str,
                      strategy_used: str,
                      strategy_config: Optional[Dict] = None):
        """Record a successful lookup to reinforce the strategy."""
        domain = self._extract_domain(url) if url else None
        
        with sqlite3.connect(self.db_path) as conn:
            # Update or insert strategy
            existing = conn.execute(
                "SELECT id, success_count FROM strategies WHERE domain = ? AND strategy_name = ?",
                (domain, strategy_used)
            ).fetchone()
            
            if existing:
                conn.execute("""
                    UPDATE strategies 
                    SET success_count = success_count + 1, last_used = ?
                    WHERE id = ?
                """, (datetime.now().isoformat(), existing[0]))
            else:
                conn.execute("""
                    INSERT INTO strategies 
                    (domain, strategy_name, strategy_config, last_used)
                    VALUES (?, ?, ?, ?)
                """, (
                    domain, strategy_used,
                    json.dumps(strategy_config) if strategy_config else None,
                    datetime.now().isoformat()
                ))
            
            # Also check if this resolves any previous failures
            if url:
                conn.execute("""
                    UPDATE failures 
                    SET resolved = 1, resolution_strategy = ?, 
                        resolution_identifier = ?, resolution_timestamp = ?
                    WHERE url = ? AND resolved = 0
                """, (
                    strategy_used, identifier,
                    datetime.now().isoformat(), url
                ))
            
            conn.commit()
        
        logger.debug(f"Recorded success for {domain} using {strategy_used}")
    
    def add_user_correction(self,
                           original_url: Optional[str],
                           original_title: Optional[str],
                           correct_identifier: str,
                           identifier_type: str,
                           source: str = 'manual'):
        """Add a user-provided correction to teach the system."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO corrections 
                (original_url, original_title, correct_identifier, 
                 identifier_type, correction_source, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                original_url, original_title, correct_identifier,
                identifier_type, source, datetime.now().isoformat()
            ))
            
            # Mark any matching failures as resolved
            if original_url:
                conn.execute("""
                    UPDATE failures 
                    SET resolved = 1, resolution_strategy = 'user_correction',
                        resolution_identifier = ?, resolution_timestamp = ?
                    WHERE url = ? AND resolved = 0
                """, (correct_identifier, datetime.now().isoformat(), original_url))
            
            conn.commit()
        
        logger.info(f"Added user correction: {identifier_type}={correct_identifier}")
    
    def get_domain_rules(self, url: str) -> Optional[Dict[str, Any]]:
        """Get learned extraction rules for a domain."""
        domain = self._extract_domain(url)
        if not domain:
            return None
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            result = conn.execute(
                "SELECT * FROM domain_rules WHERE domain = ?",
                (domain,)
            ).fetchone()
            
            if result:
                return dict(result)
        
        # Check for partial domain match (e.g., 'journals.plos.org' -> 'plos.org')
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            results = conn.execute("SELECT * FROM domain_rules").fetchall()
            
            for row in results:
                if row['domain'] in domain:
                    return dict(row)
        
        return None
    
    def get_best_strategy(self, url: str) -> Optional[Tuple[str, Dict]]:
        """Get the best known strategy for a URL based on past successes."""
        domain = self._extract_domain(url)
        if not domain:
            return None
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            result = conn.execute("""
                SELECT strategy_name, strategy_config, success_count, failure_count
                FROM strategies 
                WHERE domain = ?
                ORDER BY (success_count - failure_count) DESC, last_used DESC
                LIMIT 1
            """, (domain,)).fetchone()
            
            if result:
                config = json.loads(result['strategy_config']) if result['strategy_config'] else {}
                return (result['strategy_name'], config)
        
        return None
    
    def check_correction(self, url: Optional[str], title: Optional[str]) -> Optional[Dict]:
        """Check if we have a user correction for this reference."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            # Check by URL first
            if url:
                result = conn.execute(
                    "SELECT * FROM corrections WHERE original_url = ? ORDER BY timestamp DESC LIMIT 1",
                    (url,)
                ).fetchone()
                if result:
                    return dict(result)
            
            # Check by title (fuzzy match)
            if title:
                # Simple prefix match for now
                result = conn.execute(
                    "SELECT * FROM corrections WHERE original_title LIKE ? ORDER BY timestamp DESC LIMIT 1",
                    (title[:50] + '%',)
                ).fetchone()
                if result:
                    return dict(result)
        
        return None
    
    def get_failure_stats(self) -> Dict[str, Any]:
        """Get statistics about failures and learning progress."""
        with sqlite3.connect(self.db_path) as conn:
            total_failures = conn.execute("SELECT COUNT(*) FROM failures").fetchone()[0]
            resolved_failures = conn.execute("SELECT COUNT(*) FROM failures WHERE resolved = 1").fetchone()[0]
            
            # Top failure types
            failure_types = conn.execute("""
                SELECT failure_type, COUNT(*) as count 
                FROM failures 
                GROUP BY failure_type 
                ORDER BY count DESC
            """).fetchall()
            
            # Top problematic domains
            problem_domains = conn.execute("""
                SELECT domain, COUNT(*) as count 
                FROM failures 
                WHERE resolved = 0 AND domain IS NOT NULL
                GROUP BY domain 
                ORDER BY count DESC
                LIMIT 10
            """).fetchall()
            
            # Total corrections
            corrections = conn.execute("SELECT COUNT(*) FROM corrections").fetchone()[0]
            
            # Total learned patterns
            patterns = conn.execute("SELECT COUNT(*) FROM domain_rules").fetchone()[0]
            
            # Most successful strategies
            strategies = conn.execute("""
                SELECT strategy_name, SUM(success_count) as successes
                FROM strategies
                GROUP BY strategy_name
                ORDER BY successes DESC
                LIMIT 5
            """).fetchall()
        
        return {
            'total_failures': total_failures,
            'resolved_failures': resolved_failures,
            'resolution_rate': round(resolved_failures / total_failures * 100, 1) if total_failures > 0 else 0,
            'failure_types': dict(failure_types),
            'problem_domains': dict(problem_domains),
            'user_corrections': corrections,
            'learned_patterns': patterns,
            'top_strategies': dict(strategies),
        }
    
    def learn_from_url(self, url: str, identifier: str, identifier_type: str):
        """
        Learn a new extraction pattern from a successful resolution.
        
        This analyzes the URL to extract patterns that can be applied
        to similar URLs in the future.
        """
        domain = self._extract_domain(url)
        if not domain:
            return
        
        # Try to create a regex pattern for the identifier in the URL
        if identifier in url:
            # Create a pattern that captures this identifier
            escaped_id = re.escape(identifier)
            # Replace the identifier with a capture group
            pattern = url.replace(identifier, f'({escaped_id.replace(chr(92), "")}[^/\\s\\)\\]]*)')
            
            # Simplify to just the relevant path part
            from urllib.parse import urlparse
            parsed = urlparse(url)
            path_pattern = parsed.path.replace(identifier, f'({identifier_type}_pattern)')
            
            with sqlite3.connect(self.db_path) as conn:
                if identifier_type == 'doi':
                    conn.execute("""
                        INSERT OR REPLACE INTO domain_rules 
                        (domain, doi_url_pattern, last_updated, notes)
                        VALUES (?, ?, ?, ?)
                    """, (
                        domain,
                        f"/{identifier_type}/(10\\.\\d{{4,}}/[^/\\s]+)",
                        datetime.now().isoformat(),
                        f"Auto-learned from URL: {url[:100]}"
                    ))
                elif identifier_type == 'pmid':
                    conn.execute("""
                        INSERT OR REPLACE INTO domain_rules 
                        (domain, pmid_url_pattern, last_updated, notes)
                        VALUES (?, ?, ?, ?)
                    """, (
                        domain,
                        r"/(\d{7,})",
                        datetime.now().isoformat(),
                        f"Auto-learned from URL: {url[:100]}"
                    ))
                conn.commit()
            
            logger.info(f"Learned new pattern for {domain}: {identifier_type} extraction")
    
    def suggest_resolution(self, url: Optional[str], title: Optional[str]) -> List[Dict]:
        """
        Suggest resolution strategies based on learned patterns.
        
        Returns a list of suggestions ordered by likelihood of success.
        """
        suggestions = []
        
        # Check for user corrections first
        correction = self.check_correction(url, title)
        if correction:
            suggestions.append({
                'type': 'user_correction',
                'identifier': correction['correct_identifier'],
                'identifier_type': correction['identifier_type'],
                'confidence': 1.0,
                'source': 'User provided correction'
            })
        
        # Check domain rules
        if url:
            rules = self.get_domain_rules(url)
            if rules:
                if rules.get('doi_url_pattern'):
                    match = re.search(rules['doi_url_pattern'], url)
                    if match:
                        suggestions.append({
                            'type': 'url_pattern',
                            'identifier': match.group(1),
                            'identifier_type': 'doi',
                            'confidence': 0.9,
                            'source': f"Domain pattern for {rules['domain']}"
                        })
                
                if rules.get('requires_scraping'):
                    suggestions.append({
                        'type': 'scrape',
                        'meta_tag': rules.get('doi_meta_tag') or rules.get('pmid_meta_tag'),
                        'confidence': 0.7,
                        'source': f"Scraping required for {rules['domain']}"
                    })
            
            # Check best strategy
            strategy = self.get_best_strategy(url)
            if strategy:
                suggestions.append({
                    'type': 'learned_strategy',
                    'strategy': strategy[0],
                    'config': strategy[1],
                    'confidence': 0.8,
                    'source': 'Previously successful strategy'
                })
        
        return suggestions
    
    def _extract_domain(self, url: str) -> Optional[str]:
        """Extract domain from URL."""
        if not url:
            return None
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            # Remove www. prefix
            if domain.startswith('www.'):
                domain = domain[4:]
            return domain
        except:
            return None
    
    def export_learnings(self) -> Dict[str, Any]:
        """Export all learned data for backup or transfer."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            domain_rules = [dict(r) for r in conn.execute("SELECT * FROM domain_rules").fetchall()]
            corrections = [dict(r) for r in conn.execute("SELECT * FROM corrections").fetchall()]
            strategies = [dict(r) for r in conn.execute("SELECT * FROM strategies").fetchall()]
        
        return {
            'version': '1.0',
            'exported_at': datetime.now().isoformat(),
            'domain_rules': domain_rules,
            'corrections': corrections,
            'strategies': strategies,
        }
    
    def import_learnings(self, data: Dict[str, Any]):
        """Import learned data from another instance."""
        with sqlite3.connect(self.db_path) as conn:
            # Import domain rules
            for rule in data.get('domain_rules', []):
                conn.execute("""
                    INSERT OR REPLACE INTO domain_rules 
                    (domain, doi_url_pattern, doi_meta_tag, pmid_url_pattern,
                     pmid_meta_tag, requires_scraping, notes, last_updated)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    rule['domain'], rule.get('doi_url_pattern'),
                    rule.get('doi_meta_tag'), rule.get('pmid_url_pattern'),
                    rule.get('pmid_meta_tag'), rule.get('requires_scraping', 0),
                    rule.get('notes'), rule.get('last_updated', datetime.now().isoformat())
                ))
            
            # Import corrections
            for corr in data.get('corrections', []):
                conn.execute("""
                    INSERT INTO corrections 
                    (original_url, original_title, correct_identifier,
                     identifier_type, correction_source, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    corr.get('original_url'), corr.get('original_title'),
                    corr['correct_identifier'], corr['identifier_type'],
                    'imported', datetime.now().isoformat()
                ))
            
            conn.commit()
        
        logger.info(f"Imported {len(data.get('domain_rules', []))} domain rules, "
                   f"{len(data.get('corrections', []))} corrections")


# Singleton instance for easy access
_learning_engine: Optional[LearningEngine] = None

def get_learning_engine() -> LearningEngine:
    """Get or create the singleton learning engine instance."""
    global _learning_engine
    if _learning_engine is None:
        _learning_engine = LearningEngine()
    return _learning_engine

