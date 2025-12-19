"""
Configuration module for CitationSculptor.

Centralizes all configuration settings, environment variables, and defaults.
Settings can be overridden via environment variables or .env file.

Usage:
    from modules.config import config
    
    # Access settings
    server_url = config.PUBMED_MCP_URL
    max_authors = config.MAX_AUTHORS
    
    # Check if feature is enabled
    if config.ENABLE_WEBPAGE_SCRAPING:
        ...
"""

import os
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field

# Try to load .env file if python-dotenv is available
try:
    from dotenv import load_dotenv
    # Load from project root .env file
    env_path = Path(__file__).parent.parent / '.env'
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass  # python-dotenv not installed, use environment variables directly


def _get_env(key: str, default: str = "") -> str:
    """Get environment variable with default."""
    return os.environ.get(key, default)


def _get_env_bool(key: str, default: bool = False) -> bool:
    """Get boolean environment variable."""
    val = os.environ.get(key, "").lower()
    if val in ("true", "1", "yes", "on"):
        return True
    if val in ("false", "0", "no", "off"):
        return False
    return default


def _get_env_int(key: str, default: int = 0) -> int:
    """Get integer environment variable."""
    val = os.environ.get(key, "")
    try:
        return int(val) if val else default
    except ValueError:
        return default


def _get_env_float(key: str, default: float = 0.0) -> float:
    """Get float environment variable."""
    val = os.environ.get(key, "")
    try:
        return float(val) if val else default
    except ValueError:
        return default


@dataclass
class Config:
    """
    CitationSculptor configuration settings.
    
    All settings can be overridden via environment variables.
    """
    
    # ==========================================================================
    # PubMed MCP Server Settings
    # ==========================================================================
    
    # URL for the PubMed MCP server
    PUBMED_MCP_URL: str = field(default_factory=lambda: _get_env(
        "PUBMED_MCP_URL", "http://127.0.0.1:3017/mcp"
    ))
    
    # Rate limiting (requests per second)
    # NCBI allows 3/sec without API key, 10/sec with key
    # We use conservative defaults to avoid rate limiting
    REQUESTS_PER_SECOND: float = field(default_factory=lambda: _get_env_float(
        "REQUESTS_PER_SECOND", 2.5
    ))
    
    # Maximum retry attempts for failed requests
    MAX_RETRIES: int = field(default_factory=lambda: _get_env_int(
        "MAX_RETRIES", 4
    ))
    
    # Request timeout in seconds
    REQUEST_TIMEOUT: int = field(default_factory=lambda: _get_env_int(
        "REQUEST_TIMEOUT", 30
    ))
    
    # ==========================================================================
    # Citation Formatting Settings
    # ==========================================================================
    
    # Maximum authors to list before "et al."
    MAX_AUTHORS: int = field(default_factory=lambda: _get_env_int(
        "MAX_AUTHORS", 3
    ))
    
    # Maximum editors to list before "et al."
    MAX_EDITORS: int = field(default_factory=lambda: _get_env_int(
        "MAX_EDITORS", 3
    ))
    
    # ==========================================================================
    # Webpage Scraping Settings
    # ==========================================================================
    
    # Enable webpage metadata scraping
    ENABLE_WEBPAGE_SCRAPING: bool = field(default_factory=lambda: _get_env_bool(
        "ENABLE_WEBPAGE_SCRAPING", True
    ))
    
    # Timeout for webpage scraping requests (seconds)
    SCRAPING_TIMEOUT: int = field(default_factory=lambda: _get_env_int(
        "SCRAPING_TIMEOUT", 10
    ))
    
    # User agent string for scraping
    USER_AGENT: str = field(default_factory=lambda: _get_env(
        "USER_AGENT",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    ))
    
    # ==========================================================================
    # Ollama/LLM Settings (for MCP server)
    # ==========================================================================
    
    # Ollama API URL
    OLLAMA_URL: str = field(default_factory=lambda: _get_env(
        "OLLAMA_URL", "http://localhost:11434"
    ))
    
    # Default model for Ollama
    OLLAMA_MODEL: str = field(default_factory=lambda: _get_env(
        "OLLAMA_MODEL", "deepseek-r1:32b-qwen-distill-q4_K_M"
    ))
    
    # ==========================================================================
    # Logging Settings
    # ==========================================================================
    
    # Log level: DEBUG, INFO, WARNING, ERROR
    LOG_LEVEL: str = field(default_factory=lambda: _get_env(
        "LOG_LEVEL", "INFO"
    ))
    
    # Enable verbose logging
    VERBOSE: bool = field(default_factory=lambda: _get_env_bool(
        "VERBOSE", False
    ))
    
    # Enable file logging
    ENABLE_FILE_LOGGING: bool = field(default_factory=lambda: _get_env_bool(
        "ENABLE_FILE_LOGGING", True
    ))
    
    # Log file rotation size (MB)
    LOG_ROTATION_SIZE_MB: int = field(default_factory=lambda: _get_env_int(
        "LOG_ROTATION_SIZE_MB", 10
    ))
    
    # Number of log files to retain
    LOG_RETENTION_COUNT: int = field(default_factory=lambda: _get_env_int(
        "LOG_RETENTION_COUNT", 5
    ))
    
    # ==========================================================================
    # Cache Settings
    # ==========================================================================
    
    # Maximum cache size for PMID lookups
    PMID_CACHE_SIZE: int = field(default_factory=lambda: _get_env_int(
        "PMID_CACHE_SIZE", 500
    ))
    
    # Maximum cache size for ID conversions
    CONVERSION_CACHE_SIZE: int = field(default_factory=lambda: _get_env_int(
        "CONVERSION_CACHE_SIZE", 500
    ))
    
    # Maximum cache size for CrossRef lookups
    CROSSREF_CACHE_SIZE: int = field(default_factory=lambda: _get_env_int(
        "CROSSREF_CACHE_SIZE", 200
    ))
    
    # ==========================================================================
    # Obsidian Vault Settings
    # ==========================================================================
    
    # Path to your Obsidian vault (for relative path resolution)
    # Set via environment variable OBSIDIAN_VAULT_PATH or in .env file
    OBSIDIAN_VAULT_PATH: str = field(default_factory=lambda: _get_env(
        "OBSIDIAN_VAULT_PATH", ""
    ))
    
    # ==========================================================================
    # Output Settings
    # ==========================================================================
    
    # Create backup files before processing
    CREATE_BACKUP: bool = field(default_factory=lambda: _get_env_bool(
        "CREATE_BACKUP", True
    ))
    
    # Generate mapping JSON files
    GENERATE_MAPPING: bool = field(default_factory=lambda: _get_env_bool(
        "GENERATE_MAPPING", True
    ))
    
    # ==========================================================================
    # Feature Flags
    # ==========================================================================
    
    # Enable multi-section document processing
    ENABLE_MULTI_SECTION: bool = field(default_factory=lambda: _get_env_bool(
        "ENABLE_MULTI_SECTION", True
    ))
    
    # Enable CrossRef fallback for non-PubMed articles
    ENABLE_CROSSREF_FALLBACK: bool = field(default_factory=lambda: _get_env_bool(
        "ENABLE_CROSSREF_FALLBACK", True
    ))
    
    # Enable URL-based metadata extraction for blocked sites
    ENABLE_URL_EXTRACTION: bool = field(default_factory=lambda: _get_env_bool(
        "ENABLE_URL_EXTRACTION", True
    ))
    
    # ==========================================================================
    # Known Domain Mappings
    # ==========================================================================
    
    # Organization abbreviations (can be extended via config)
    ORG_ABBREVIATIONS: dict = field(default_factory=lambda: {
        'american medical association': 'AMA',
        'american hospital association': 'AHA',
        'association of american medical colleges': 'AAMC',
        'center on budget and policy priorities': 'CBPP',
        'centers for disease control': 'CDC',
        'centers for medicare': 'CMS',
        'florida department of health': 'FLDOH',
        'food and drug administration': 'FDA',
        'national institutes of health': 'NIH',
        'world health organization': 'WHO',
        'kaiser family foundation': 'KFF',
        'commonwealth fund': 'CWF',
    })
    
    # Known news/media domains for organization extraction
    KNOWN_DOMAINS: dict = field(default_factory=lambda: {
        'politico.com': 'Politico',
        'nytimes.com': 'The New York Times',
        'washingtonpost.com': 'The Washington Post',
        'wsj.com': 'The Wall Street Journal',
        'reuters.com': 'Reuters',
        'bbc.com': 'BBC',
        'cnn.com': 'CNN',
        'fiercehealthcare.com': 'FierceHealthcare',
        'healthaffairs.org': 'Health Affairs',
        'kff.org': 'Kaiser Family Foundation (KFF)',
        'cbpp.org': 'Center on Budget and Policy Priorities (CBPP)',
        'mckinsey.com': 'McKinsey & Company',
    })
    
    def __post_init__(self) -> None:
        """Validate configuration after initialization."""
        # Validate log level
        valid_levels = {'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'}
        if self.LOG_LEVEL.upper() not in valid_levels:
            self.LOG_LEVEL = 'INFO'
        
        # Ensure positive values
        if self.MAX_AUTHORS < 1:
            self.MAX_AUTHORS = 3
        if self.MAX_RETRIES < 1:
            self.MAX_RETRIES = 4
        if self.REQUESTS_PER_SECOND <= 0:
            self.REQUESTS_PER_SECOND = 2.5
    
    def to_dict(self) -> dict:
        """Convert config to dictionary for logging/debugging."""
        return {
            'PUBMED_MCP_URL': self.PUBMED_MCP_URL,
            'REQUESTS_PER_SECOND': self.REQUESTS_PER_SECOND,
            'MAX_AUTHORS': self.MAX_AUTHORS,
            'LOG_LEVEL': self.LOG_LEVEL,
            'ENABLE_WEBPAGE_SCRAPING': self.ENABLE_WEBPAGE_SCRAPING,
            'ENABLE_CROSSREF_FALLBACK': self.ENABLE_CROSSREF_FALLBACK,
        }


# Global config instance
config = Config()


# ==========================================================================
# Version Information
# ==========================================================================

VERSION = "2.3.0"
VERSION_DATE = "2025-12"


# ==========================================================================
# Path Resolution Helper
# ==========================================================================

def resolve_vault_path(file_path: str) -> str:
    """
    Resolve a file path, supporting both absolute and relative paths.
    
    Checks settings manager first, then falls back to environment variable.
    If vault path is set and the path is relative, the vault path is prepended.
    
    Args:
        file_path: Path to resolve (can be absolute or relative to vault)
        
    Returns:
        Resolved absolute path
    """
    if not file_path:
        return file_path
    
    # Expand ~ to home directory
    file_path = os.path.expanduser(file_path)
    
    # If already absolute, return as-is
    if os.path.isabs(file_path):
        return file_path
    
    # Try to get vault path from settings manager first, then env var
    vault_path = ""
    try:
        from modules.settings_manager import settings_manager
        vault_path = settings_manager.get_obsidian_vault_path()
    except ImportError:
        pass
    
    # Fall back to config if settings manager doesn't have it
    if not vault_path:
        vault_path = config.OBSIDIAN_VAULT_PATH
    
    if vault_path:
        vault_path = os.path.expanduser(vault_path)
        resolved = os.path.join(vault_path, file_path)
        return resolved
    
    # No vault configured, return as-is (will likely fail)
    return file_path


__all__ = ['config', 'Config', 'VERSION', 'VERSION_DATE', 'resolve_vault_path']

