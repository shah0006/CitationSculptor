"""
Settings Manager for CitationSculptor

Handles persistent user settings stored in a JSON file.
These settings can be modified via the Web UI without editing .env files.

Settings are stored in .data/settings.json and take precedence over
environment variables for supported options.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional
from dataclasses import dataclass, field, asdict
from datetime import datetime
from loguru import logger


# Default settings file location
SETTINGS_DIR = Path(__file__).parent.parent / '.data'
SETTINGS_FILE = SETTINGS_DIR / 'settings.json'


@dataclass
class UserSettings:
    """
    User-configurable settings that can be modified via the Web UI.
    
    These settings are persisted to settings.json and loaded on startup.
    """
    
    # Obsidian vault path for relative path resolution
    obsidian_vault_path: str = ""
    
    # Default citation style
    default_citation_style: str = "vancouver"
    
    # Safety features
    create_backup_on_process: bool = True
    
    # Document intelligence defaults
    verify_links_by_default: bool = True
    suggest_citations_by_default: bool = True
    check_compliance_by_default: bool = True
    
    # Display preferences
    max_search_results: int = 10
    
    # LLM settings
    ollama_model: str = "llama3:8b"
    enable_llm_extraction: bool = True
    
    # Last modified timestamp
    last_modified: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'UserSettings':
        """Create from dictionary."""
        # Filter out unknown keys for forward compatibility
        known_keys = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in known_keys}
        return cls(**filtered)


class SettingsManager:
    """
    Manages user settings persistence and access.
    
    Settings are stored in .data/settings.json and can be modified
    via the Web UI or programmatically.
    """
    
    def __init__(self, settings_file: Path = None):
        self.settings_file = settings_file or SETTINGS_FILE
        self._settings: Optional[UserSettings] = None
        self._ensure_directory()
        self.load()
    
    def _ensure_directory(self) -> None:
        """Ensure the settings directory exists."""
        self.settings_file.parent.mkdir(parents=True, exist_ok=True)
    
    def load(self) -> UserSettings:
        """Load settings from file, creating defaults if not exists."""
        if self.settings_file.exists():
            try:
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self._settings = UserSettings.from_dict(data)
                logger.debug(f"Loaded settings from {self.settings_file}")
            except (json.JSONDecodeError, Exception) as e:
                logger.warning(f"Failed to load settings: {e}. Using defaults.")
                self._settings = UserSettings()
        else:
            logger.info("No settings file found. Creating with defaults.")
            self._settings = UserSettings()
            self.save()
        
        return self._settings
    
    def save(self) -> bool:
        """Save current settings to file."""
        try:
            self._settings.last_modified = datetime.now().isoformat()
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(self._settings.to_dict(), f, indent=2)
            logger.info(f"Settings saved to {self.settings_file}")
            return True
        except Exception as e:
            logger.error(f"Failed to save settings: {e}")
            return False
    
    @property
    def settings(self) -> UserSettings:
        """Get current settings."""
        if self._settings is None:
            self.load()
        return self._settings
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a specific setting value."""
        return getattr(self.settings, key, default)
    
    def set(self, key: str, value: Any) -> bool:
        """Set a specific setting value and save."""
        if hasattr(self.settings, key):
            setattr(self._settings, key, value)
            return self.save()
        logger.warning(f"Unknown setting key: {key}")
        return False
    
    def update(self, updates: Dict[str, Any]) -> bool:
        """Update multiple settings at once."""
        for key, value in updates.items():
            if hasattr(self._settings, key):
                setattr(self._settings, key, value)
            else:
                logger.warning(f"Skipping unknown setting: {key}")
        return self.save()
    
    def reset_to_defaults(self) -> bool:
        """Reset all settings to defaults."""
        self._settings = UserSettings()
        return self.save()
    
    def get_all(self) -> Dict[str, Any]:
        """Get all settings as a dictionary."""
        return self.settings.to_dict()
    
    def get_obsidian_vault_path(self) -> str:
        """
        Get the Obsidian vault path.
        
        Checks settings first, then falls back to environment variable.
        """
        # Settings take precedence
        if self.settings.obsidian_vault_path:
            return self.settings.obsidian_vault_path
        
        # Fall back to environment variable
        return os.environ.get('OBSIDIAN_VAULT_PATH', '')


# Global settings manager instance
settings_manager = SettingsManager()


def get_settings() -> UserSettings:
    """Get current user settings."""
    return settings_manager.settings


def update_settings(updates: Dict[str, Any]) -> bool:
    """Update user settings."""
    return settings_manager.update(updates)


def get_setting(key: str, default: Any = None) -> Any:
    """Get a specific setting."""
    return settings_manager.get(key, default)


__all__ = [
    'SettingsManager',
    'UserSettings', 
    'settings_manager',
    'get_settings',
    'update_settings',
    'get_setting',
]

