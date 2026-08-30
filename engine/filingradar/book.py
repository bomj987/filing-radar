"""Восстановление клиентской базы практики из публичного реестра.

Метод: компании, зарегистрированные по адресу практики. Работает только у
фирм, предоставляющих клиентам адрес регистрации — измерено 2026-08-30, это
меньшинство фирм, и отчёт обязан говорить об этом прямо.
"""
from __future__ import annotations

import csv
import io
import re

from .fetch import Fetcher
from .parse import parse_company, parse_officers


def normalise_address(addr: str) -> str:
    """Убирает 'United Kingdom' и схлопывает пробелы: строка идёт в поиск как есть."""
    return re.sub(r"\s+", " ", re.sub(r",?\s*United Kingdom", "", addr, flags=re.I)).strip()


def companies_at_address(fetcher: Fetcher, address: str) -> list[dict]:
    """Активные компании по адресу. Возвращает строки CSV реестра."""
    body = fetcher.get("/advanced-search/csv",
                       {"registeredOfficeAddress": normalise_address(address),
                        "status": "active"})
    if not body.lstrip().lower().startswith("company_name"):
        raise RuntimeError("реестр вернул не CSV — вероятно, изменился эндпоинт поиска")
    return list(csv.DictReader(io.StringIO(body)))


def load_company(fetcher: Fetcher, number: str):
    """Полная карточка компании: сроки подачи + действующие должностные лица."""
    c = parse_company(fetcher.get(f"/company/{number}"), number)
    c.officers = parse_officers(fetcher.get(f"/company/{number}/officers"))
    return c


def build_book(fetcher: Fetcher, address: str, exclude: set[str] | None = None,
               limit: int | None = None, progress=None):
    """Все компании по адресу, кроме самой практики (exclude)."""
    exclude = exclude or set()
    rows = [r for r in companies_at_address(fetcher, address)
            if r["company_number"] not in exclude]
    if limit:
        rows = rows[:limit]
    out = []
    for i, r in enumerate(rows, 1):
        try:
            out.append(load_company(fetcher, r["company_number"]))
        except Exception as e:
            if progress:
                progress(i, len(rows), f"ОШИБКА {r['company_number']}: {e}")
            continue
        if progress:
            progress(i, len(rows), out[-1].name or r["company_name"])
    return out
