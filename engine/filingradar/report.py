"""Генерация отчёта: JSON, CSV и самодостаточный HTML без внешних зависимостей.

HTML пишется одним файлом намеренно: его открывают из письма, часто без сети
для сторонних ресурсов, и он должен печататься на бумагу как есть.
"""
from __future__ import annotations

import html
import json
from datetime import date

from .risk import CRITICAL, assess, summarise

KIND_LABEL = {
    "accounts_overdue": "Отчётность просрочена",
    "accounts_due_soon": "Отчётность скоро",
    "confirmation_overdue": "Confirmation statement просрочен",
    "confirmation_due_soon": "Confirmation statement скоро",
    "idv_overdue": "Верификация личности просрочена",
    "idv_pending": "Личность не верифицирована",
    "no_active_officers": "Нет действующих директоров",
}
CH = "https://find-and-update.company-information.service.gov.uk/company/"


def build(companies, today: date, firm_name: str, firm_address: str) -> dict:
    findings = [f for c in companies for f in assess(c, today)]
    findings.sort(key=lambda f: (f.severity != CRITICAL, -f.money_gbp,
                                 f.days if f.days is not None else 9999))
    return {
        "firm": {"name": firm_name, "address": firm_address},
        "generated": today.isoformat(),
        "book_size": len(companies),
        "summary": summarise(findings),
        "findings": [f.to_dict() for f in findings],
    }


def to_json(report: dict) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2)


def to_csv(report: dict) -> str:
    rows = ["company_number,company_name,kind,severity,due,days,money_gbp,detail"]
    for f in report["findings"]:
        detail = f['detail'].replace('"', "'")
        rows.append(f'{f["company_number"]},"{f["company_name"] or ""}",{f["kind"]},'
                    f'{f["severity"]},{f["due"] or ""},{f["days"] if f["days"] is not None else ""},'
                    f'{f["money_gbp"]},"{detail}"')
    return "\n".join(rows) + "\n"


CSS = """
:root{--bg:#fff;--fg:#0b0c0c;--muted:#505a5f;--line:#d6dbde;--card:#f8f9fa;
--crit:#a4260a;--critbg:#fdf1ee;--warn:#7a4a00;--warnbg:#fdf6e9;--accent:#0b4f6c}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#12161a;--fg:#e9eef2;
--muted:#9aa7b0;--line:#2a333b;--card:#181e24;--crit:#ff8f75;--critbg:#2a1512;
--warn:#f0c07a;--warnbg:#2a2113;--accent:#7ec8e3}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);
font:16px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif}
.wrap{max-width:960px;margin:0 auto;padding:32px 20px 72px}
h1{font-size:28px;line-height:1.2;margin:0 0 4px}
h2{font-size:19px;margin:36px 0 12px;padding-top:20px;border-top:1px solid var(--line)}
.sub{color:var(--muted);margin:0 0 28px}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin:0 0 8px}
.tile{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:14px 16px}
.tile .n{font-size:30px;font-weight:650;letter-spacing:-.02em;line-height:1.1}
.tile .l{color:var(--muted);font-size:13px;margin-top:2px}
.tile.crit .n{color:var(--crit)}
.scroll{overflow-x:auto;-webkit-overflow-scrolling:touch}
table{border-collapse:collapse;width:100%;min-width:640px;font-size:14.5px}
th,td{text-align:left;padding:9px 10px;border-bottom:1px solid var(--line);vertical-align:top}
th{font-size:12.5px;text-transform:uppercase;letter-spacing:.04em;color:var(--muted);font-weight:600}
tr.crit td:first-child{box-shadow:inset 3px 0 0 var(--crit)}
.badge{display:inline-block;font-size:12px;font-weight:600;padding:2px 8px;border-radius:999px;white-space:nowrap}
.badge.crit{background:var(--critbg);color:var(--crit)}
.badge.warn{background:var(--warnbg);color:var(--warn)}
a{color:var(--accent)}
.note{background:var(--card);border:1px solid var(--line);border-left:3px solid var(--accent);
border-radius:0 8px 8px 0;padding:14px 16px;margin:16px 0}
.note p{margin:0 0 8px}.note p:last-child{margin:0}
footer{margin-top:40px;padding-top:18px;border-top:1px solid var(--line);color:var(--muted);font-size:13.5px}
"""


def to_html(report: dict) -> str:
    s, f_name = report["summary"], html.escape(report["firm"]["name"])
    rows = []
    for f in report["findings"]:
        crit = f["severity"] == CRITICAL
        rows.append(
            f'<tr class="{"crit" if crit else ""}">'
            f'<td><a href="{CH}{f["company_number"]}" rel="noopener">{html.escape(f["company_name"] or f["company_number"])}</a>'
            f'<br><span style="color:var(--muted);font-size:12.5px">{f["company_number"]}</span></td>'
            f'<td><span class="badge {"crit" if crit else "warn"}">{KIND_LABEL.get(f["kind"], f["kind"])}</span></td>'
            f'<td>{html.escape(f["detail"])}</td>'
            f'<td style="white-space:nowrap">{f["due"] or "—"}</td>'
            f'<td style="text-align:right">{("£" + str(f["money_gbp"])) if f["money_gbp"] else "—"}</td></tr>')

    def tile(n, label, crit=False):
        return f'<div class="tile{" crit" if crit else ""}"><div class="n">{n}</div><div class="l">{label}</div></div>'

    return f"""<!doctype html><html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<title>Filing Radar — {f_name}</title><style>{CSS}</style></head><body><div class="wrap">
<h1>Статутарные риски: {f_name}</h1>
<p class="sub">{html.escape(report["firm"]["address"])} · отчёт составлен {report["generated"]}
· источник: публичный реестр Companies House</p>
<div class="tiles">
{tile(report["book_size"], "компаний по адресу")}
{tile(s["critical"], "критических находок", crit=s["critical"] > 0)}
{tile(s["idv_overdue"] + s["idv_pending"], "директоров без верификации")}
{tile("£" + f'{s["money_gbp"]:,}'.replace(",", " "), "оценка штрафов")}
</div>
<h2>Находки — {s["total"]} по {s["companies"]} компаниям</h2>
<div class="scroll"><table><thead><tr><th>Компания</th><th>Риск</th><th>Детали</th><th>Срок</th><th style="text-align:right">Штраф</th></tr></thead>
<tbody>{"".join(rows) if rows else '<tr><td colspan="5">Находок нет — по этому адресу всё в порядке.</td></tr>'}</tbody></table></div>
<h2>Как это посчитано и чего здесь нет</h2>
<div class="note">
<p><strong>Источник.</strong> Только публичный реестр Companies House: карточка компании
и страница должностных лиц. Никаких закрытых или купленных данных. Каждую строку
можно проверить по ссылке в первой колонке.</p>
<p><strong>Как определён список компаний.</strong> Это компании, у которых адрес
регистрации совпадает с вашим. Если вы предоставляете клиентам адрес регистрации —
это ваша клиентская база. Если по адресу сидят и другие организации, в списке
будут лишние: скажите, и я их уберу.</p>
<p><strong>Оценка штрафов</strong> — установленная шкала Companies House для частной
компании (£150 / £375 / £750 / £1 500 по глубине просрочки). Удвоение за вторую
просрочку подряд НЕ учтено, поэтому цифра занижена, а не завышена.</p>
<p><strong>Чего здесь нет.</strong> Это не юридическая консультация и не полный
compliance-аудит. Верификация личности напрямую в Companies House — бесплатна;
этот отчёт не заменяет её, а показывает, у кого она ещё не пройдена.</p>
</div>
<footer>Filing Radar · данные Companies House под Open Government Licence v3.0 ·
чтобы больше не получать такие отчёты, ответьте на письмо словом «stop»</footer>
</div></body></html>"""
