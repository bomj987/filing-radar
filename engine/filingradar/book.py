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

# Почтовый индекс Великобритании. Он — единственный надёжный различитель:
# поиск реестра по адресу работает как частичное совпадение, поэтому
# адрес вида "Unit A" матчит тысячи чужих компаний (наблюдалось 2026-08-30).
POSTCODE_RE = re.compile(r"\b([A-Z]{1,2}\d[A-Z\d]?)\s*(\d[A-Z]{2})\b", re.I)

# Столько компаний по одному адресу означает не клиентскую базу, а
# сервисный офис или ошибку сопоставления. Отчёт по такому адресу бессмыслен.
OVERMATCH_LIMIT = 600


class AddressTooBroad(RuntimeError):
    """Адрес не позволяет однозначно выделить клиентскую базу."""


def postcode_of(addr: str) -> str | None:
    m = POSTCODE_RE.search(addr)
    return f"{m.group(1)} {m.group(2)}".upper() if m else None


def normalise_address(addr: str) -> str:
    """Убирает 'United Kingdom' и схлопывает пробелы: строка идёт в поиск как есть."""
    return re.sub(r"\s+", " ", re.sub(r",?\s*United Kingdom", "", addr, flags=re.I)).strip()


def companies_at_address(fetcher: Fetcher, address: str) -> list[dict]:
    """Активные компании по адресу, отфильтрованные по почтовому индексу.

    Поиск реестра сопоставляет адрес частично, поэтому его результат
    обязательно сужается: оставляем только строки, у которых индекс совпадает
    с индексом практики. Без индекса в адресе работать нельзя — результат
    будет включать чужие компании, а отчёт с чужими компаниями хуже, чем
    отсутствие отчёта.
    """
    pc = postcode_of(address)
    if not pc:
        raise AddressTooBroad(f"в адресе нет почтового индекса: {address!r}")

    body = fetcher.get("/advanced-search/csv",
                       {"registeredOfficeAddress": normalise_address(address),
                        "status": "active"})
    if not body.lstrip().lower().startswith("company_name"):
        raise RuntimeError("реестр вернул не CSV — вероятно, изменился эндпоинт поиска")

    rows = list(csv.DictReader(io.StringIO(body)))
    matched = [r for r in rows
               if postcode_of(r.get("registered_office_address", "") or "") == pc]
    if len(matched) > OVERMATCH_LIMIT:
        raise AddressTooBroad(
            f"по адресу {address!r} найдено {len(matched)} компаний — это сервисный "
            f"офис или слишком общий адрес, а не клиентская база")
    return matched


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
