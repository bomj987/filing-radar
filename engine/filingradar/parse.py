"""Разбор публичных страниц Companies House в структуры.

Все регулярные выражения выведены из реально сохранённых страниц в fixtures/,
а не из предположений о разметке. Разметка GOV.UK стабильна, но это HTML
государственного сайта, а не контракт API: поэтому парсер возвращает None
вместо того, чтобы догадываться, а тесты закреплены на живых страницах.
"""
from __future__ import annotations

import html as _html
import re
from dataclasses import asdict, dataclass, field
from datetime import date, datetime

TAG_RE = re.compile(r"<[^>]+>")
WS_RE = re.compile(r"\s+")
MONTHS = ("January February March April May June July August September "
          "October November December").split()
DATE_RE = re.compile(r"(\d{1,2}) (" + "|".join(MONTHS) + r") (\d{4})")


def text_of(fragment: str) -> str:
    """HTML -> плоский текст, где каждый тег становится '|'.

    Разделитель нужен, чтобы соседние поля определения (<dt>/<dd>) не
    склеивались в одну строку и их можно было различить регулярным выражением.
    """
    t = _html.unescape(TAG_RE.sub("|", fragment))
    t = re.sub(r"\|+", "|", t)
    return WS_RE.sub(" ", t).strip()


def parse_date(s: str) -> date | None:
    m = DATE_RE.search(s)
    if not m:
        return None
    try:
        return datetime.strptime(" ".join(m.groups()), "%d %B %Y").date()
    except ValueError:
        return None


@dataclass
class Officer:
    name: str
    role: str | None = None
    resigned: bool = False
    identity_verified: bool = False
    verification_due: date | None = None
    # Верификацию личности по ECCTA проходят директора, PSC и участники LLP,
    # но НЕ секретари и не корпоративные должностные лица. Companies House сам
    # различает их: у обязанного лица на странице есть поле «Identity
    # verification due» или «status», у необязанного — ни одного.
    # Проверено на живых данных 2026-08-30 (07085010, 07046890, 04831820).
    verification_required: bool = False

    def to_dict(self) -> dict:
        d = asdict(self)
        d["verification_due"] = self.verification_due.isoformat() if self.verification_due else None
        return d


@dataclass
class Company:
    number: str
    name: str | None = None
    status: str | None = None
    incorporated: date | None = None
    sic: str | None = None
    accounts_next_due: date | None = None
    accounts_overdue: bool = False
    confirmation_next_due: date | None = None
    confirmation_overdue: bool = False
    officers: list[Officer] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        for k in ("incorporated", "accounts_next_due", "confirmation_next_due"):
            v = getattr(self, k)
            d[k] = v.isoformat() if v else None
        d["officers"] = [o.to_dict() for o in self.officers]
        return d

    @property
    def active_officers(self) -> list[Officer]:
        return [o for o in self.officers if not o.resigned]

    @property
    def unverified_officers(self) -> list[Officer]:
        """Только те, кто обязан верифицироваться и ещё не сделал этого.

        Секретарь без обязанности сюда не попадает — иначе отчёт назовёт
        нарушителем человека, которому верификация вообще не нужна.
        """
        return [o for o in self.active_officers
                if o.verification_required and not o.identity_verified]


def parse_company(html_doc: str, number: str) -> Company:
    t = text_of(html_doc)
    c = Company(number=number)

    m = re.search(r"\|\s*([^|]{2,120}?)\s*\|[\s|]*Company number\s*\|", t)
    if m:
        c.name = m.group(1).strip()
    m = re.search(r"Company status\s*\|[\s|]*([A-Za-z][A-Za-z\- ]{2,40}?)\s*\|", t)
    if m:
        c.status = m.group(1).strip()
    m = re.search(r"Incorporated on\s*\|[\s|]*([^|]+)\|", t)
    if m:
        c.incorporated = parse_date(m.group(1))
    m = re.search(r"Nature of business \(SIC\)\s*\|[\s|]*([^|]+?)\s*\|", t)
    if m:
        c.sic = m.group(1).strip()

    # Просрочка помечена блоком Warning непосредственно перед секцией.
    c.accounts_overdue = "Accounts overdue" in t
    c.confirmation_overdue = "Confirmation statement overdue" in t

    m = re.search(r"Next accounts made up to\s*\|[^|]*\|[\s|]*due by\s*\|([^|]+)\|", t)
    if m:
        c.accounts_next_due = parse_date(m.group(1))
    m = re.search(r"Next statement date\s*\|[^|]*\|[\s|]*due by\s*\|([^|]+)\|", t)
    if m:
        c.confirmation_next_due = parse_date(m.group(1))
    return c


# Карточка каждого должностного лица обёрнута в <div class="appointment-N">.
APPOINTMENT_SPLIT = re.compile(r'class="appointment-\d+"')
ROLE_RE = re.compile(r"Role\s*\|\s*(?:Active|Resigned)\s*\|[\s|]*([A-Za-z][A-Za-z\- ]{2,40}?)\s*\|")
# Имя лежит в <span id="officer-name-N"> внутри ссылки; из плоского текста
# его брать нельзя — блок начинается с обрезка тега.
NAME_RE = re.compile(r'id="officer-name-\d+"(.{0,600}?)</span>', re.S)


def parse_officers(html_doc: str) -> list[Officer]:
    out: list[Officer] = []
    for block in APPOINTMENT_SPLIT.split(html_doc)[1:]:
        t = text_of(block[:8000])
        nm = NAME_RE.search(block[:8000])
        name = text_of(nm.group(1)).strip(">| \t") if nm else ""
        if not name:
            continue
        role_m = ROLE_RE.search(t)
        # Проверено на живых данных 2026-08-30: прошедшие верификацию имеют
        # поле "Identity verification status: Verified"; не прошедшие — поле
        # "Identity verification due" с персональной датой.
        has_status = "Identity verification status" in t
        has_due = "Identity verification due" in t
        verified = has_status and "Verified" in t
        due = None
        m = re.search(r"Identity verification due\s*\|[\s|]*([^|]+)\|", t)
        if m:
            due = parse_date(m.group(1))
        out.append(Officer(
            name=name,
            role=role_m.group(1).strip() if role_m else None,
            resigned="Resigned on" in t,
            identity_verified=verified,
            verification_due=due,
            verification_required=has_status or has_due,
        ))
    return out
