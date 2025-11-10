from __future__ import annotations

from itertools import cycle
from typing import Iterable, Optional

class ProxyManager:
    """
    Simple round-robin proxy provider.
    Accepts Playwright-style proxy strings, e.g.:
      http://user:pass@host:port
      socks5://host:1080
    """

    def __init__(self, proxies: Optional[Iterable[str]] = None) -> None:
        proxies = list(proxies or [])
        self._has_proxies = len(proxies) > 0
        self._cycler = cycle(proxies) if self._has_proxies else None

    def next(self) -> Optional[str]:
        if not self._has_proxies:
            return None
        return next(self._cycler)