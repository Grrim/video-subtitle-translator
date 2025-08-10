"""
System logowania dla aplikacji
"""

import logging
import sys
from pathlib import Path
from typing import Optional

def get_logger(name: str, level: str = "INFO") -> logging.Logger:
    """
    Pobierz skonfigurowany logger
    
    Args:
        name: Nazwa loggera (zazwyczaj __name__)
        level: Poziom logowania (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    
    Returns:
        Skonfigurowany logger
    """
    logger = logging.getLogger(name)
    
    # Sprawdź czy logger już ma handlery (unikaj duplikowania)
    if logger.handlers:
        return logger
    
    # Ustaw poziom logowania
    logger.setLevel(getattr(logging, level.upper()))
    
    # Stwórz formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Handler dla konsoli
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # Handler dla pliku (opcjonalnie)
    log_dir = Path("logs")
    if log_dir.exists() or _create_log_dir(log_dir):
        file_handler = logging.FileHandler(log_dir / "app.log", encoding='utf-8')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger

def _create_log_dir(log_dir: Path) -> bool:
    """Stwórz katalog dla logów"""
    try:
        log_dir.mkdir(exist_ok=True)
        return True
    except Exception:
        return False