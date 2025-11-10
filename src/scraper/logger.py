from __future__ import annotations

import logging
import sys
from typing import Optional

def get_logger(name: Optional[str] = None) -> logging.Logger:
    logger = logging.getLogger(name if name else "cloudflare_scraper")
    if logger.handlers:
        return logger  # already configured

    logger.setLevel(logging.INFO)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(logging.INFO)
    stream_format = logging.Formatter(
        "[%(asctime)s] %(levelname)s %(name)s - %(message)s", "%Y-%m-%d %H:%M:%S"
    )
    stream_handler.setFormatter(stream_format)

    logger.addHandler(stream_handler)
    logger.propagate = False
    return logger