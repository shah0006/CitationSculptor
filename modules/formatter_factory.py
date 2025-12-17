"""Formatter Factory - Returns the appropriate citation formatter by style."""

from typing import Dict, Type, List

from .base_formatter import BaseFormatter
from .vancouver_formatter import VancouverFormatter
from .apa_formatter import APAFormatter
from .mla_formatter import MLAFormatter
from .chicago_formatter import ChicagoFormatter
from .harvard_formatter import HarvardFormatter
from .ieee_formatter import IEEEFormatter


# Registry of available formatters
FORMATTERS: Dict[str, Type[BaseFormatter]] = {
    'vancouver': VancouverFormatter,
    'apa': APAFormatter,
    'mla': MLAFormatter,
    'chicago': ChicagoFormatter,
    'harvard': HarvardFormatter,
    'ieee': IEEEFormatter,
}

# Aliases for convenience
FORMATTER_ALIASES: Dict[str, str] = {
    'van': 'vancouver',
    'apa7': 'apa',
    'mla9': 'mla',
    'turabian': 'chicago',
    'harv': 'harvard',
}

DEFAULT_STYLE = 'vancouver'


def get_formatter(style: str = DEFAULT_STYLE, **kwargs) -> BaseFormatter:
    """
    Get a citation formatter instance for the specified style.
    
    Args:
        style: Citation style name (vancouver, apa, mla, chicago, harvard, ieee)
        **kwargs: Additional arguments passed to formatter constructor
    
    Returns:
        BaseFormatter instance for the specified style
    
    Raises:
        ValueError: If style is not recognized
    
    Examples:
        >>> formatter = get_formatter('apa')
        >>> formatter = get_formatter('vancouver', max_authors=5)
    """
    # Normalize style name
    style_lower = style.lower().strip()
    
    # Check aliases first
    if style_lower in FORMATTER_ALIASES:
        style_lower = FORMATTER_ALIASES[style_lower]
    
    # Get formatter class
    if style_lower not in FORMATTERS:
        available = ', '.join(sorted(FORMATTERS.keys()))
        raise ValueError(f"Unknown citation style: '{style}'. Available styles: {available}")
    
    formatter_class = FORMATTERS[style_lower]
    return formatter_class(**kwargs)


def get_available_styles() -> List[str]:
    """Get list of available citation styles."""
    return sorted(FORMATTERS.keys())


def get_style_info() -> Dict[str, str]:
    """Get information about available styles."""
    return {
        'vancouver': 'Vancouver (medical/scientific standard)',
        'apa': 'APA 7th Edition (social sciences)',
        'mla': 'MLA 9th Edition (humanities)',
        'chicago': 'Chicago/Turabian (notes-bibliography)',
        'harvard': 'Harvard (author-date)',
        'ieee': 'IEEE (engineering/computer science)',
    }


def is_valid_style(style: str) -> bool:
    """Check if a style name is valid."""
    style_lower = style.lower().strip()
    return style_lower in FORMATTERS or style_lower in FORMATTER_ALIASES

