"""Журнал событий воронки.

Продукт доставляется письмом, а не веб-приложением, поэтому события пишутся
там, где они реально происходят: при генерации отчёта, отправке, ответе и
оплате. Формат — JSON Lines: дописывается атомарно, читается чем угодно,
не ломается при параллельной записи.

Событие — факт, а не намерение. `email_sent` пишется ПОСЛЕ подтверждения
отправки почтовым сервером, иначе журнал начнёт лгать в приятную сторону.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

# Воронка: от «работа сделана» до «заплатили и вернулись».
KINDS = (
    "report_generated",   # отчёт по фирме построен
    "email_sent",         # письмо принято почтовым сервером
    "email_bounced",      # доставка не удалась
    "reply_received",     # содержательный ответ
    "opt_out",            # ответ «stop»
    "call_booked",        # разговор назначен
    "pilot_agreed",       # согласие на платный пилот
    "payment_received",   # оплата
    "weekly_delivered",   # очередной недельный отчёт доставлен
    "churned",            # отказ от подписки
    "error",              # сбой в прогоне
)

DEFAULT_PATH = Path(__file__).resolve().parents[2] / "marketing" / "events.jsonl"


class UnknownEvent(ValueError):
    """Незнакомый тип события: опечатка не должна тихо попадать в воронку."""


def record(kind: str, firm: str, path: Path | str = DEFAULT_PATH, **fields) -> dict:
    if kind not in KINDS:
        raise UnknownEvent(f"{kind!r} не входит в воронку: {', '.join(KINDS)}")
    event = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
             "kind": kind, "firm": firm, **fields}
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, ensure_ascii=False) + "\n")
        fh.flush()
        os.fsync(fh.fileno())
    return event


def read(path: Path | str = DEFAULT_PATH) -> list[dict]:
    p = Path(path)
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


def funnel(path: Path | str = DEFAULT_PATH) -> dict:
    """Числитель и знаменатель на каждом шаге — как требует мандат.

    Проценты считаются от предыдущего РЕАЛЬНОГО шага, а не от начала воронки:
    доля ответов от доставленных — управляемая величина, доля ответов от
    сгенерированных отчётов — самообман.
    """
    ev = read(path)
    n = {k: sum(1 for e in ev if e["kind"] == k) for k in KINDS}
    delivered = n["email_sent"] - n["email_bounced"]

    def pct(num, den):
        return round(100 * num / den, 1) if den else None

    return {
        "reports_generated": n["report_generated"],
        "emails_sent": n["email_sent"],
        "bounced": n["email_bounced"],
        "delivered": delivered,
        "replies": n["reply_received"],
        "opt_outs": n["opt_out"],
        "calls": n["call_booked"],
        "pilots": n["pilot_agreed"],
        "payments": n["payment_received"],
        "reply_rate_pct": pct(n["reply_received"], delivered),
        "pilot_rate_pct": pct(n["pilot_agreed"], n["reply_received"]),
        "payment_rate_pct": pct(n["payment_received"], n["pilot_agreed"]),
        "firms_touched": len({e["firm"] for e in ev if e["kind"] == "email_sent"}),
    }
