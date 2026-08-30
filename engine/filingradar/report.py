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
    "accounts_overdue": "Accounts overdue",
    "accounts_due_soon": "Accounts due soon",
    "confirmation_overdue": "Confirmation statement overdue",
    "confirmation_due_soon": "Confirmation statement due soon",
    "idv_overdue": "ID verification overdue",
    "idv_pending": "ID not verified",
    "no_active_officers": "No serving officers",
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

    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<title>Filing Radar — {f_name}</title><style>{CSS}</style></head><body><div class="wrap">
<h1>Statutory risk: {f_name}</h1>
<p class="sub">{html.escape(report["firm"]["address"])} · report generated {report["generated"]}
· source: the public Companies House register</p>
<div class="tiles">
{tile(report["book_size"], "companies at this address")}
{tile(s["critical"], "critical findings", crit=s["critical"] > 0)}
{tile(s["idv_overdue"] + s["idv_pending"], "directors not yet verified")}
{tile("£" + f'{s["money_gbp"]:,}', "estimated penalties")}
</div>
<h2>Findings — {s["total"]} across {s["companies"]} companies</h2>
<div class="scroll"><table><thead><tr><th>Company</th><th>Risk</th><th>Detail</th><th>Due</th><th style="text-align:right">Penalty</th></tr></thead>
<tbody>{"".join(rows) if rows else '<tr><td colspan="5">No findings — everything at this address is in order.</td></tr>'}</tbody></table></div>
<h2>How this was produced, and what it does not cover</h2>
<div class="note">
<p><strong>Source.</strong> The public Companies House register only — the company record
and the officers page for each company. No private or purchased data. Every row links
back to the source so you can check it yourself.</p>
<p><strong>How the company list was built.</strong> These are companies whose registered
office address matches yours. If you provide a registered office service, this is your
client book. If other organisations share the address, some rows will not be yours —
say so and I will remove them.</p>
<p><strong>Penalty estimates</strong> use the Companies House late-filing scale for a
private company (£150 / £375 / £750 / £1,500 by lateness). The doubling that applies to a
second consecutive late filing is <em>not</em> included, so the figure understates rather
than overstates.</p>
<p><strong>Secretaries are excluded.</strong> Under ECCTA, company secretaries are not
required to verify their identity, and they are not listed here.</p>
<p><strong>What this is not.</strong> Not legal advice and not a compliance audit.
Verifying identity directly with Companies House is free; this report does not replace
that, it shows you who has not done it.</p>
</div>
<footer>Filing Radar · Companies House data under the Open Government Licence v3.0 ·
to receive no further reports, reply to the email with the word &ldquo;stop&rdquo;
</footer>
</div></body></html>"""


# ---------------------------------------------------------------------------
# Обезличивание и письмо
# ---------------------------------------------------------------------------

def anonymise(report: dict) -> dict:
    """Копия отчёта без названий фирмы и клиентов.

    Нужна для публичного образца: сам отчёт строится из открытого реестра, но
    публиковать под именем конкретной практики сводку её проблем — значит
    создавать ей репутационную экспозицию, о которой она не просила.
    """
    import copy
    r = copy.deepcopy(report)
    r["firm"] = {"name": "A UK accountancy practice", "address": "Sample — names removed"}
    seen: dict[str, str] = {}
    for f in r["findings"]:
        num = f["company_number"]
        seen.setdefault(num, f"Client company {len(seen) + 1}")
        f["company_name"] = seen[num]
        f["company_number"] = "—"
        # Имя директора стоит первым в detail, до разделителя. Разделитель
        # менялся (": " -> " — "), и привязка к одному варианту однажды уже
        # привела к утечке имён в публичный образец — поэтому ищем любой.
        for sep in (" — ", ": "):
            if sep in f["detail"]:
                f["detail"] = "A director" + f["detail"][f["detail"].index(sep):]
                break
    return r


EMAIL_CSS = ("font-family:-apple-system,Segoe UI,Helvetica,Arial,sans-serif;"
             "font-size:14px;line-height:1.5;color:#0b0c0c")
# Стили держим на <table>, а не на каждой ячейке: письмо становится вчетверо
# легче, а Gmail обрезает длинные письма и прячет концовку за «показать всё».
TABLE_OPEN = (f'<table cellpadding="6" cellspacing="0" border="0" '
              f'style="border-collapse:collapse;{EMAIL_CSS};width:100%;max-width:640px">')
TH = ('<tr style="text-align:left;font-size:12px;color:#505a5f">'
      '<th align="left">Company</th><th align="left">Risk</th><th align="left">Detail</th></tr>')


def to_email_html(report: dict, limit: int = 12, kinds: tuple[str, ...] | None = None) -> str:
    """Компактная таблица находок для тела письма.

    Инлайновые стили и никаких внешних ресурсов: почтовые клиенты вырезают
    <style> и блокируют загрузку по сети. Данные идут прямо в тело письма, а не
    ссылкой — так у получателя нет причины никуда переходить, чтобы увидеть суть.
    """
    items = [f for f in report["findings"] if kinds is None or f["kind"] in kinds]
    if not items:
        return ""
    rows = []
    for f in items[:limit]:
        colour = "#a4260a" if f["severity"] == CRITICAL else "#7a4a00"
        rows.append(
            f'<tr style="border-top:1px solid #e5e9ec">'
            f'<td valign="top"><a href="{CH}{f["company_number"]}" style="color:#0b4f6c">'
            f'{html.escape(f["company_name"] or "")}</a></td>'
            f'<td valign="top" style="color:{colour}">{KIND_LABEL.get(f["kind"], f["kind"])}</td>'
            f'<td valign="top">{html.escape(f["detail"])}</td></tr>')
    more = len(items) - limit
    tail = (f'<p style="{EMAIL_CSS};color:#505a5f">…and {more} more across the book.</p>'
            if more > 0 else "")
    return f'{TABLE_OPEN}<thead>{TH}</thead><tbody>{"".join(rows)}</tbody></table>{tail}'
