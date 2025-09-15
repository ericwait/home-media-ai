"""
Logging utilities for Home Media AI.

This module provides centralized logging configuration for the entire toolkit,
with support for different log levels, formatters, and output destinations.

Functions:
    setup_logging: Configure logging for the application
    get_logger: Get a logger instance for a specific module
    
Example:
    >>> from home_media_ai.utils import setup_logging
    >>> setup_logging('INFO')
    >>> import logging
    >>> logger = logging.getLogger(__name__)
    >>> logger.info("Processing started")
"""

import logging
import sys
from pathlib import Path
from typing import Optional, Union


def setup_logging(
    level: Union[str, int] = logging.INFO,
    log_file: Optional[Union[str, Path]] = None,
    format_string: Optional[str] = None,
    include_timestamp: bool = True
) -> None:
    """Set up logging configuration for the application.
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional path to log file (logs to console if None)
        format_string: Custom format string for log messages
        include_timestamp: Whether to include timestamp in log messages
        
    Example:
        >>> setup_logging('DEBUG', 'processing.log')
        >>> setup_logging(logging.WARNING)  # Numeric level
    """
    # Convert string level to numeric if needed
    if isinstance(level, str):
        level = getattr(logging, level.upper())
    
    # Default format string
    if format_string is None:
        if include_timestamp:
            format_string = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        else:
            format_string = '%(name)s - %(levelname)s - %(message)s'
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    # Remove existing handlers to avoid duplicates
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Create formatter
    formatter = logging.Formatter(format_string)
    
    # Console handler (always present)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # File handler (optional)
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.FileHandler(log_path)
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    
    # Set level for third-party libraries to reduce noise
    logging.getLogger('PIL').setLevel(logging.WARNING)
    logging.getLogger('matplotlib').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance for a specific module.
    
    Args:
        name: Name for the logger (typically __name__)
        
    Returns:
        Logger instance
        
    Example:
        >>> logger = get_logger(__name__)
        >>> logger.info("Module loaded successfully")
    """
    return logging.getLogger(name)