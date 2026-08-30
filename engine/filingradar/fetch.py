"""HTTP-доступ к публичным страницам Companies House.

Вежливый по умолчанию: кэш на диске, задержка между запросами, повторы.
Реестр — государственный сервис; кэш существует, чтобы не ходить туда дважды
за одним и тем же.
"""
from __future__ import annotations

import hashlib
import time
import urllib.parse
import urllib.request
from pathlib import Path

BASE = "https://find-and-update.company-information.service.gov.uk"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) filing-radar/0.1"
DEFAULT_DELAY = 0.6


class Fetcher:
    def __init__(self, cache_dir: str | Path = ".cache", delay: float = DEFAULT_DELAY,
                 retries: int = 2, timeout: int = 45):
        self.cache = Path(cache_dir)
        self.cache.mkdir(parents=True, exist_ok=True)
        self.delay = delay
        self.retries = retries
        self.timeout = timeout
        self._last = 0.0

    def _key(self, url: str) -> Path:
        return self.cache / (hashlib.sha256(url.encode()).hexdigest()[:32] + ".html")

    def get(self, path: str, params: dict | None = None, use_cache: bool = True) -> str:
        url = BASE + path
        if params:
            url += "?" + urllib.parse.urlencode(params)
        key = self._key(url)
        if use_cache and key.exists():
            return key.read_text(encoding="utf-8")

        last_err: Exception | None = None
        for attempt in range(self.retries + 1):
            wait = self.delay - (time.monotonic() - self._last)
            if wait > 0:
                time.sleep(wait)
            try:
                req = urllib.request.Request(url, headers={"User-Agent": UA})
                with urllib.request.urlopen(req, timeout=self.timeout) as r:
                    body = r.read().decode("utf-8", "replace")
                self._last = time.monotonic()
                key.write_text(body, encoding="utf-8")
                return body
            except Exception as e:  # сеть/таймаут/5xx — повторяем с отступом
                last_err = e
                self._last = time.monotonic()
                time.sleep(1.5 * (attempt + 1))
        raise RuntimeError(f"не удалось загрузить {url}: {last_err}")
