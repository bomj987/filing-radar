"""Правила риска по данным реестра.

Функции чистые: на вход — разобранная компания и «сегодня», на выход — список
находок. Никакой сети, поэтому правила тестируются полностью детерминированно.

Суммы штрафов — установленная Companies House шкала для частной компании
(наблюдалась 2026-08-30): до 1 мес. £150, 1–3 мес. £375, 3–6 мес. £750,
более 6 мес. £1 500; удваивается, если просрочка второй год подряд.
Мы не знаем, второй ли это год, поэтому удвоение НЕ применяем — оценка
намеренно консервативная.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import date

# Предельный срок верификации личности действующих директоров по ECCTA.
IDV_DEADLINE = date(2026, 11, 18)

CRITICAL, WARNING = "critical", "warning"

LATE_FILING_SCALE = ((30, 150), (90, 375), (180, 750))
LATE_FILING_MAX = 1500


def late_filing_penalty(days_late: int) -> int:
    """Штраф частной компании за просрочку отчётности по числу дней."""
    if days_late <= 0:
        return 0
    for limit, amount in LATE_FILING_SCALE:
        if days_late <= limit:
            return amount
    return LATE_FILING_MAX


@dataclass
class Finding:
    company_number: str
    company_name: str | None
    kind: str
    severity: str
    detail: str
    due: date | None = None
    days: int | None = None
    money_gbp: int = 0

    def to_dict(self) -> dict:
        d = asdict(self)
        d["due"] = self.due.isoformat() if self.due else None
        return d


def assess(company, today: date, soon_days: int = 30) -> list[Finding]:
    """Все находки по одной компании. Отсортированы: критичные и дорогие выше."""
    out: list[Finding] = []
    if (company.status or "").lower() != "active":
        return out  # растворённые и ликвидируемые компании — не работа практики

    def add(**kw):
        out.append(Finding(company_number=company.number, company_name=company.name, **kw))

    if company.accounts_overdue and company.accounts_next_due:
        late = (today - company.accounts_next_due).days
        add(kind="accounts_overdue", severity=CRITICAL,
            detail=f"Accounts overdue by {late} days (were due {company.accounts_next_due})",
            due=company.accounts_next_due, days=-late,
            money_gbp=late_filing_penalty(late))
    elif company.accounts_next_due:
        left = (company.accounts_next_due - today).days
        if 0 <= left <= soon_days:
            add(kind="accounts_due_soon", severity=WARNING,
                detail=f"Accounts due in {left} days",
                due=company.accounts_next_due, days=left, money_gbp=150)

    if company.confirmation_overdue and company.confirmation_next_due:
        late = (today - company.confirmation_next_due).days
        add(kind="confirmation_overdue", severity=CRITICAL,
            detail=f"Confirmation statement overdue by {late} days — grounds for strike-off",
            due=company.confirmation_next_due, days=-late)
    elif company.confirmation_next_due:
        left = (company.confirmation_next_due - today).days
        if 0 <= left <= soon_days:
            add(kind="confirmation_due_soon", severity=WARNING,
                detail=f"Confirmation statement due in {left} days",
                due=company.confirmation_next_due, days=left)

    for o in company.unverified_officers:
        personal = o.verification_due or IDV_DEADLINE
        left = (personal - today).days
        if left < 0:
            add(kind="idv_overdue", severity=CRITICAL,
                detail=f"{o.name}: Companies House shows a verification due date of {personal}, "
                       f"which passed {abs(left)} days ago — the company cannot file its "
                       f"confirmation statement until this director supplies a personal code",
                due=personal, days=left)
        else:
            add(kind="idv_pending", severity=WARNING if left > 30 else CRITICAL,
                detail=f"{o.name}: identity not verified, {left} days left",
                due=personal, days=left)

    if not company.active_officers:
        add(kind="no_active_officers", severity=CRITICAL,
            detail="Active company with no serving officers on the register")

    out.sort(key=lambda f: (f.severity != CRITICAL, -f.money_gbp, f.days if f.days is not None else 0))
    return out


def summarise(findings: list[Finding]) -> dict:
    return {
        "total": len(findings),
        "critical": sum(1 for f in findings if f.severity == CRITICAL),
        "warning": sum(1 for f in findings if f.severity == WARNING),
        "idv_overdue": sum(1 for f in findings if f.kind == "idv_overdue"),
        "idv_pending": sum(1 for f in findings if f.kind == "idv_pending"),
        "accounts_overdue": sum(1 for f in findings if f.kind == "accounts_overdue"),
        "confirmation_overdue": sum(1 for f in findings if f.kind == "confirmation_overdue"),
        "money_gbp": sum(f.money_gbp for f in findings),
        "companies": len({f.company_number for f in findings}),
    }
