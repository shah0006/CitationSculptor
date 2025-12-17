"""
Logging configuration for CitationSculptor.

Provides centralized logging setup with:
- Console output (always enabled)
- File logging with rotation (configurable)
- Structured log format with timestamps
- Separate error log for critical issues
"""

import sys
from pathlib import Path
from loguru import logger
from datetime import datetime

# Determine log directory
LOG_DIR = Path(__file__).parent.parent / '.data' / 'logs'

# Flag to track if logging is already configured
_logging_configured = False


def setup_logging(
    log_level: str = "INFO",
    enable_file_logging: bool = True,
    rotation_size_mb: int = 10,
    retention_count: int = 5,
    verbose: bool = False
):
    """
    Configure logging for CitationSculptor.
    
    Args:
        log_level: Minimum log level (DEBUG, INFO, WARNING, ERROR)
        enable_file_logging: Whether to write logs to files
        rotation_size_mb: Size in MB before rotating log file
        retention_count: Number of rotated log files to keep
        verbose: Enable verbose/debug output
    """
    global _logging_configured
    
    if _logging_configured:
        return
    
    # Remove default handler
    logger.remove()
    
    # Determine effective log level
    effective_level = "DEBUG" if verbose else log_level.upper()
    
    # Console handler - always enabled
    console_format = (
        "<green>{time:HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan> | "
        "<level>{message}</level>"
    )
    logger.add(
        sys.stderr,
        format=console_format,
        level=effective_level,
        colorize=True,
        backtrace=True,
        diagnose=True,
    )
    
    # File logging
    if enable_file_logging:
        # Ensure log directory exists
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        
        # Main application log
        file_format = (
            "{time:YYYY-MM-DD HH:mm:ss.SSS} | "
            "{level: <8} | "
            "{name}:{function}:{line} | "
            "{message}"
        )
        
        main_log = LOG_DIR / "citationsculptor.log"
        logger.add(
            str(main_log),
            format=file_format,
            level="DEBUG",  # Always capture DEBUG to file for troubleshooting
            rotation=f"{rotation_size_mb} MB",
            retention=retention_count,
            compression="zip",
            backtrace=True,
            diagnose=True,
            enqueue=True,  # Thread-safe
        )
        
        # Separate error log for critical issues
        error_log = LOG_DIR / "errors.log"
        logger.add(
            str(error_log),
            format=file_format,
            level="ERROR",
            rotation=f"{rotation_size_mb} MB",
            retention=retention_count,
            compression="zip",
            backtrace=True,
            diagnose=True,
            enqueue=True,
        )
        
        # Document processing log - detailed record of all document operations
        processing_log = LOG_DIR / "document_processing.log"
        logger.add(
            str(processing_log),
            format=file_format,
            level="INFO",
            rotation=f"{rotation_size_mb} MB",
            retention=retention_count,
            compression="zip",
            filter=lambda record: "document" in record["name"].lower() or 
                                  "process" in record["message"].lower() or
                                  "backup" in record["message"].lower() or
                                  "restore" in record["message"].lower() or
                                  "save" in record["message"].lower(),
            enqueue=True,
        )
        
        logger.info(f"File logging enabled. Log directory: {LOG_DIR}")
    
    _logging_configured = True
    logger.info(f"CitationSculptor logging initialized (level={effective_level})")


def get_log_directory() -> Path:
    """Return the log directory path."""
    return LOG_DIR


def get_recent_logs(max_lines: int = 100) -> str:
    """
    Read the most recent log entries.
    
    Args:
        max_lines: Maximum number of lines to return
        
    Returns:
        String containing recent log entries
    """
    main_log = LOG_DIR / "citationsculptor.log"
    if not main_log.exists():
        return "No log file found."
    
    try:
        with open(main_log, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            return ''.join(lines[-max_lines:])
    except Exception as e:
        return f"Error reading log file: {e}"


def log_document_operation(operation: str, file_path: str, details: dict = None):
    """
    Log a document operation with structured data.
    
    Args:
        operation: Type of operation (process, backup, restore, save)
        file_path: Path to the document
        details: Additional details as a dictionary
    """
    details = details or {}
    details['timestamp'] = datetime.now().isoformat()
    details['file_path'] = file_path
    details['operation'] = operation
    
    logger.bind(**details).info(
        f"Document {operation}: {file_path} | {details}"
    )


def log_reference_lookup(ref_number: int, identifier: str, result: str, details: dict = None):
    """
    Log a reference lookup operation.
    
    Args:
        ref_number: Original reference number
        identifier: The identifier being looked up
        result: Result status (success, failed, etc.)
        details: Additional details
    """
    details = details or {}
    logger.debug(
        f"Reference #{ref_number} lookup: {identifier} -> {result} | {details}"
    )


# Initialize logging with defaults if imported directly
def init_from_config():
    """Initialize logging from config settings."""
    try:
        from modules.config import config
        setup_logging(
            log_level=config.LOG_LEVEL,
            enable_file_logging=config.ENABLE_FILE_LOGGING,
            rotation_size_mb=config.LOG_ROTATION_SIZE_MB,
            retention_count=config.LOG_RETENTION_COUNT,
            verbose=config.VERBOSE,
        )
    except ImportError:
        # Config not available, use defaults
        setup_logging()


__all__ = [
    'setup_logging',
    'get_log_directory',
    'get_recent_logs',
    'log_document_operation',
    'log_reference_lookup',
    'init_from_config',
]

