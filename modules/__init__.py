"""CitationSculptor Modules"""

from .file_handler import FileHandler
from .reference_parser import ReferenceParser, ParsedReference, DocumentSection
from .type_detector import CitationTypeDetector, CitationType
from .pubmed_client import PubMedClient, ArticleMetadata, IdConversionResult, CrossRefMetadata
from .vancouver_formatter import VancouverFormatter, FormattedCitation
from .inline_replacer import InlineReplacer
from .output_generator import OutputGenerator, OutputDocument, ManualReviewItem, ReferenceMapping

__version__ = '0.3.0'

