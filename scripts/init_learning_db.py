#!/usr/bin/env python3
"""
Initialize the Learning Database with Comprehensive Knowledge

This script pre-populates the learning database with:
1. Domain rules for academic publishers and websites
2. URL patterns for identifier extraction
3. Known resolution strategies
4. Common failure patterns to avoid

Run this once to bootstrap the learning engine with knowledge.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from modules.learning_engine import LearningEngine
import sqlite3
from datetime import datetime

def init_comprehensive_domain_rules(engine: LearningEngine):
    """Add comprehensive domain rules for academic publishers."""
    
    domain_rules = [
        # === Major Academic Publishers ===
        {
            'domain': 'pubmed.ncbi.nlm.nih.gov',
            'pmid_url_pattern': r'/(\d{7,8})/?$',
            'requires_scraping': 0,
            'notes': 'PubMed - PMID is the numeric path segment'
        },
        {
            'domain': 'pmc.ncbi.nlm.nih.gov',
            'pmid_meta_tag': 'citation_pmid',
            'doi_meta_tag': 'citation_doi',
            'requires_scraping': 1,
            'notes': 'PubMed Central - PMCID in URL, PMID/DOI in meta'
        },
        {
            'domain': 'doi.org',
            'doi_url_pattern': r'doi\.org/(10\.\d{4,}/[^\s\)\]]+)',
            'requires_scraping': 0,
            'notes': 'Direct DOI resolver'
        },
        {
            'domain': 'dx.doi.org',
            'doi_url_pattern': r'dx\.doi\.org/(10\.\d{4,}/[^\s\)\]]+)',
            'requires_scraping': 0,
            'notes': 'Legacy DOI resolver'
        },
        
        # === Frontiers ===
        {
            'domain': 'frontiersin.org',
            'doi_url_pattern': r'/articles/(10\.\d{4,}/[^/]+)',
            'doi_meta_tag': 'citation_doi',
            'requires_scraping': 0,
            'notes': 'Frontiers - DOI embedded in URL path after /articles/'
        },
        
        # === Nature Publishing Group ===
        {
            'domain': 'nature.com',
            'doi_meta_tag': 'citation_doi',
            'pmid_meta_tag': 'citation_pmid',
            'requires_scraping': 1,
            'notes': 'Nature - DOI and PMID in meta tags'
        },
        {
            'domain': 'springer.com',
            'doi_url_pattern': r'/article/(10\.\d{4,}/[^/]+)',
            'doi_meta_tag': 'citation_doi',
            'requires_scraping': 1,
            'notes': 'Springer - DOI in URL or meta'
        },
        {
            'domain': 'link.springer.com',
            'doi_url_pattern': r'/article/(10\.\d{4,}/[^/]+)',
            'doi_meta_tag': 'citation_doi',
            'requires_scraping': 1,
            'notes': 'Springer Link - DOI in URL or meta'
        },
        {
            'domain': 'biomedcentral.com',
            'doi_url_pattern': r'/articles/(10\.\d{4,}/[^/]+)',
            'doi_meta_tag': 'citation_doi',
            'requires_scraping': 1,
            'notes': 'BMC - DOI in URL or meta'
        },
        
        # === Elsevier ===
        {
            'domain': 'sciencedirect.com',
            'doi_meta_tag': 'citation_doi',
            'requires_scraping': 1,
            'notes': 'ScienceDirect/Elsevier - DOI in meta'
        },
        {
            'domain': 'cell.com',
            'doi_meta_tag': 'citation_doi',
            'requires_scraping': 1,
            'notes': 'Cell Press - DOI in meta'
        },
        {
            'domain': 'thelancet.com',
            'doi_meta_tag': 'citation_doi',
            'requires_scraping': 1,
            'notes': 'The Lancet - DOI in meta'
        },
        
        # === Wiley ===
        {
            'domain': 'wiley.com',
            'doi_url_pattern': r'/doi/(10\.\d{4,}/[^/]+)',
            'doi_meta_tag': 'citation_doi',
            'requires_scraping': 1,
            'notes': 'Wiley - DOI in URL or meta'
        },
        {
            'domain': 'onlinelibrary.wiley.com',
            'doi_url_pattern': r'/doi/(?:abs|full|pdf)?/?(10\.\d{4,}/[^/]+)',
            'doi_meta_tag': 'citation_doi',
            'requires_scraping': 1,
            'notes': 'Wiley Online Library - DOI in URL or meta'
        },
        
        # === Oxford University Press ===
        {
            'domain': 'academic.oup.com',
            'doi_url_pattern': r'/doi/(10\.\d{4,}/[^/]+)',
            'doi_meta_tag': 'citation_doi',
            'requires_scraping': 1,
            'notes': 'OUP Academic - DOI in URL or meta, watch for trailing page numbers'
        },
        
        # === American Heart Association ===
        {
            'domain': 'ahajournals.org',
            'doi_url_pattern': r'/doi/(10\.\d{4,}/[^/\?]+)',
            'doi_meta_tag': 'citation_doi',
            'pmid_meta_tag': 'citation_pmid',
            'requires_scraping': 1,
            'notes': 'AHA Journals (Circulation, etc.) - DOI in URL'
        },
        
        # === MDPI ===
        {
            'domain': 'mdpi.com',
            'doi_meta_tag': 'citation_doi',
            'requires_scraping': 1,
            'notes': 'MDPI Open Access - DOI in meta'
        },
        
        # === PLOS ===
        {
            'domain': 'plos.org',
            'doi_url_pattern': r'article\?id=(10\.\d{4,}/[^&]+)',
            'doi_meta_tag': 'citation_doi',
            'requires_scraping': 1,
            'notes': 'PLOS - DOI in URL query or meta'
        },
        {
            'domain': 'journals.plos.org',
            'doi_url_pattern': r'article\?id=(10\.\d{4,}/[^&]+)',
            'doi_meta_tag': 'citation_doi',
            'requires_scraping': 1,
            'notes': 'PLOS Journals - DOI in URL query or meta'
        },
        
        # === JAMA Network ===
        {
            'domain': 'jamanetwork.com',
            'doi_meta_tag': 'citation_doi',
            'pmid_meta_tag': 'citation_pmid',
            'requires_scraping': 1,
            'notes': 'JAMA Network - DOI and PMID in meta'
        },
        
        # === NEJM ===
        {
            'domain': 'nejm.org',
            'doi_meta_tag': 'citation_doi',
            'pmid_meta_tag': 'citation_pmid',
            'requires_scraping': 1,
            'notes': 'New England Journal of Medicine - DOI/PMID in meta'
        },
        
        # === BMJ ===
        {
            'domain': 'bmj.com',
            'doi_meta_tag': 'citation_doi',
            'pmid_meta_tag': 'citation_pmid',
            'requires_scraping': 1,
            'notes': 'BMJ - DOI and PMID in meta'
        },
        
        # === Cardiology Specific ===
        {
            'domain': 'jacc.org',
            'doi_meta_tag': 'citation_doi',
            'requires_scraping': 1,
            'notes': 'JACC - Journal of the American College of Cardiology'
        },
        {
            'domain': 'acc.org',
            'doi_meta_tag': 'citation_doi',
            'requires_scraping': 1,
            'notes': 'American College of Cardiology - educational content'
        },
        {
            'domain': 'ecrjournal.com',
            'doi_meta_tag': 'citation_doi',
            'requires_scraping': 1,
            'notes': 'European Cardiology Review'
        },
        {
            'domain': 'escardio.org',
            'doi_meta_tag': 'citation_doi',
            'requires_scraping': 1,
            'notes': 'European Society of Cardiology'
        },
        
        # === Preprint Servers ===
        {
            'domain': 'arxiv.org',
            'doi_url_pattern': r'arxiv\.org/abs/(\d+\.\d+)',
            'requires_scraping': 0,
            'notes': 'arXiv preprint server - arXiv ID in URL'
        },
        {
            'domain': 'biorxiv.org',
            'doi_url_pattern': r'biorxiv\.org/content/(10\.\d{4,}/[^/\.]+)',
            'doi_meta_tag': 'citation_doi',
            'requires_scraping': 1,
            'notes': 'bioRxiv preprints'
        },
        {
            'domain': 'medrxiv.org',
            'doi_url_pattern': r'medrxiv\.org/content/(10\.\d{4,}/[^/\.]+)',
            'doi_meta_tag': 'citation_doi',
            'requires_scraping': 1,
            'notes': 'medRxiv preprints'
        },
        {
            'domain': 'researchgate.net',
            'doi_meta_tag': 'citation_doi',
            'requires_scraping': 1,
            'notes': 'ResearchGate - may have DOI if paper is published'
        },
        
        # === Japanese Academic ===
        {
            'domain': 'jstage.jst.go.jp',
            'doi_meta_tag': 'citation_doi',
            'requires_scraping': 1,
            'notes': 'J-STAGE Japanese academic platform'
        },
        
        # === Diabetes/Endocrinology ===
        {
            'domain': 'diabetesjournals.org',
            'doi_meta_tag': 'citation_doi',
            'pmid_meta_tag': 'citation_pmid',
            'requires_scraping': 1,
            'notes': 'ADA Diabetes journals'
        },
        
        # === Aging Research ===
        {
            'domain': 'aging-us.com',
            'doi_meta_tag': 'citation_doi',
            'requires_scraping': 1,
            'notes': 'Aging journal'
        },
        
        # === Other Academic Publishers ===
        {
            'domain': 'dovepress.com',
            'doi_meta_tag': 'citation_doi',
            'requires_scraping': 1,
            'notes': 'Dove Medical Press'
        },
        {
            'domain': 'imrpress.com',
            'doi_meta_tag': 'citation_doi',
            'requires_scraping': 1,
            'notes': 'IMR Press'
        },
        {
            'domain': 'jci.org',
            'doi_meta_tag': 'citation_doi',
            'pmid_meta_tag': 'citation_pmid',
            'requires_scraping': 1,
            'notes': 'Journal of Clinical Investigation'
        },
        {
            'domain': 'karger.com',
            'doi_meta_tag': 'citation_doi',
            'requires_scraping': 1,
            'notes': 'Karger Publishers'
        },
        {
            'domain': 'tandfonline.com',
            'doi_url_pattern': r'/doi/(?:abs|full)?/(10\.\d{4,}/[^/]+)',
            'doi_meta_tag': 'citation_doi',
            'requires_scraping': 1,
            'notes': 'Taylor & Francis Online'
        },
        {
            'domain': 'sagepub.com',
            'doi_meta_tag': 'citation_doi',
            'requires_scraping': 1,
            'notes': 'SAGE Publications'
        },
        {
            'domain': 'journals.sagepub.com',
            'doi_url_pattern': r'/doi/(10\.\d{4,}/[^/]+)',
            'doi_meta_tag': 'citation_doi',
            'requires_scraping': 1,
            'notes': 'SAGE Journals'
        },
        
        # === Clinical Trials ===
        {
            'domain': 'clinicaltrials.gov',
            'requires_scraping': 0,
            'notes': 'ClinicalTrials.gov - NCT number in URL'
        },
    ]
    
    with sqlite3.connect(engine.db_path) as conn:
        for rule in domain_rules:
            # Check if exists
            existing = conn.execute(
                "SELECT id FROM domain_rules WHERE domain = ?",
                (rule['domain'],)
            ).fetchone()
            
            if existing:
                # Update existing
                conn.execute("""
                    UPDATE domain_rules SET
                        doi_url_pattern = COALESCE(?, doi_url_pattern),
                        doi_meta_tag = COALESCE(?, doi_meta_tag),
                        pmid_url_pattern = COALESCE(?, pmid_url_pattern),
                        pmid_meta_tag = COALESCE(?, pmid_meta_tag),
                        requires_scraping = ?,
                        notes = ?,
                        last_updated = ?
                    WHERE domain = ?
                """, (
                    rule.get('doi_url_pattern'),
                    rule.get('doi_meta_tag'),
                    rule.get('pmid_url_pattern'),
                    rule.get('pmid_meta_tag'),
                    rule.get('requires_scraping', 0),
                    rule.get('notes'),
                    datetime.now().isoformat(),
                    rule['domain']
                ))
            else:
                # Insert new
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
    
    print(f"✓ Added/updated {len(domain_rules)} domain rules")


def init_resolution_strategies(engine: LearningEngine):
    """Add known successful resolution strategies."""
    
    strategies = [
        # URL-based extraction strategies
        ('pubmed.ncbi.nlm.nih.gov', 'url_extraction', {'pattern': 'pmid_in_path'}, 100),
        ('pmc.ncbi.nlm.nih.gov', 'url_extraction', {'pattern': 'pmcid_in_path'}, 100),
        ('doi.org', 'url_extraction', {'pattern': 'doi_in_path'}, 100),
        ('frontiersin.org', 'url_extraction', {'pattern': 'doi_in_articles_path'}, 50),
        ('ahajournals.org', 'url_extraction', {'pattern': 'doi_in_doi_path'}, 50),
        
        # Meta tag scraping strategies
        ('nature.com', 'webpage_scraping', {'meta_tag': 'citation_doi'}, 80),
        ('sciencedirect.com', 'webpage_scraping', {'meta_tag': 'citation_doi'}, 80),
        ('mdpi.com', 'webpage_scraping', {'meta_tag': 'citation_doi'}, 80),
        ('wiley.com', 'webpage_scraping', {'meta_tag': 'citation_doi'}, 70),
        ('springer.com', 'webpage_scraping', {'meta_tag': 'citation_doi'}, 70),
        
        # Metadata extraction from reference text
        (None, 'metadata_doi', {'source': 'reference_text'}, 90),
        
        # Title search
        (None, 'title_search', {'database': 'pubmed'}, 30),
        
        # Fallback
        (None, 'fallback_citation', {'type': 'webpage'}, 100),
    ]
    
    with sqlite3.connect(engine.db_path) as conn:
        import json
        
        for domain, strategy, config, success_count in strategies:
            # Check if exists
            existing = conn.execute(
                "SELECT id, success_count FROM strategies WHERE domain IS ? AND strategy_name = ?",
                (domain, strategy)
            ).fetchone()
            
            if existing:
                # Update success count to be at least the baseline
                conn.execute("""
                    UPDATE strategies SET
                        success_count = MAX(success_count, ?),
                        strategy_config = ?,
                        last_used = ?
                    WHERE id = ?
                """, (success_count, json.dumps(config), datetime.now().isoformat(), existing[0]))
            else:
                conn.execute("""
                    INSERT INTO strategies (domain, strategy_name, strategy_config, success_count, last_used)
                    VALUES (?, ?, ?, ?, ?)
                """, (domain, strategy, json.dumps(config), success_count, datetime.now().isoformat()))
        
        conn.commit()
    
    print(f"✓ Added/updated {len(strategies)} resolution strategies")


def init_known_patterns(engine: LearningEngine):
    """Add learned patterns from known working cases."""
    
    patterns = [
        # Frontiers pattern
        ('frontiersin.org', 'doi_in_url', r'/articles/(10\.\d{4,}/[^/]+)', None, 50),
        
        # AHA Journals pattern
        ('ahajournals.org', 'doi_in_url', r'/doi/(10\.\d{4,}/[^/\?]+)', None, 30),
        
        # Springer pattern
        ('springer.com', 'doi_in_url', r'/article/(10\.\d{4,}/[^/]+)', None, 30),
        
        # Wiley pattern
        ('onlinelibrary.wiley.com', 'doi_in_url', r'/doi/(?:abs|full)?/?(10\.\d{4,}/[^/]+)', None, 30),
        
        # PLOS pattern
        ('journals.plos.org', 'doi_in_url', r'article\?id=(10\.\d{4,}/[^&]+)', None, 20),
    ]
    
    with sqlite3.connect(engine.db_path) as conn:
        for domain, pattern_type, regex, meta_tag, success_count in patterns:
            existing = conn.execute(
                "SELECT id FROM patterns WHERE domain = ?",
                (domain,)
            ).fetchone()
            
            if not existing:
                conn.execute("""
                    INSERT INTO patterns (domain, pattern_type, regex_pattern, meta_tag, success_count, last_success)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (domain, pattern_type, regex, meta_tag, success_count, datetime.now().isoformat()))
        
        conn.commit()
    
    print(f"✓ Added {len(patterns)} learned patterns")


def print_stats(engine: LearningEngine):
    """Print database statistics."""
    
    with sqlite3.connect(engine.db_path) as conn:
        domain_count = conn.execute("SELECT COUNT(*) FROM domain_rules").fetchone()[0]
        strategy_count = conn.execute("SELECT COUNT(*) FROM strategies").fetchone()[0]
        pattern_count = conn.execute("SELECT COUNT(*) FROM patterns").fetchone()[0]
        correction_count = conn.execute("SELECT COUNT(*) FROM corrections").fetchone()[0]
        failure_count = conn.execute("SELECT COUNT(*) FROM failures").fetchone()[0]
    
    print("\n" + "="*50)
    print("📚 Learning Database Statistics")
    print("="*50)
    print(f"  Domain Rules:      {domain_count}")
    print(f"  Strategies:        {strategy_count}")
    print(f"  Learned Patterns:  {pattern_count}")
    print(f"  User Corrections:  {correction_count}")
    print(f"  Recorded Failures: {failure_count}")
    print("="*50)


def main():
    print("🧠 Initializing Learning Database with Comprehensive Knowledge\n")
    
    # Create/connect to learning engine
    engine = LearningEngine()
    
    # Initialize all knowledge
    init_comprehensive_domain_rules(engine)
    init_resolution_strategies(engine)
    init_known_patterns(engine)
    
    # Print stats
    print_stats(engine)
    
    print("\n✅ Learning database initialized successfully!")
    print(f"   Database location: {engine.db_path}")


if __name__ == "__main__":
    main()

