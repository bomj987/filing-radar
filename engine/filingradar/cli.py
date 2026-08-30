"""CLI: собрать отчёт по адресу практики.

  python3 -m filingradar.cli --address "43a St Mary's Road Market Harborough LE16 7DS" \
      --firm "HARMAN & HUNTER" --out ../site/r/harman-hunter
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from .book import build_book
from .fetch import Fetcher
from .report import build, to_csv, to_html, to_json


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="filingradar", description=__doc__)
    p.add_argument("--address", required=True, help="адрес регистрации практики")
    p.add_argument("--firm", required=True, help="название практики для заголовка")
    p.add_argument("--out", required=True, help="каталог для index.html / report.json / report.csv")
    p.add_argument("--exclude", default="", help="номера компаний через запятую (обычно сама практика)")
    p.add_argument("--limit", type=int, default=None, help="ограничить число компаний")
    p.add_argument("--cache", default=".cache")
    p.add_argument("--today", default=None, help="YYYY-MM-DD, для воспроизводимых прогонов")
    a = p.parse_args(argv)

    today = date.fromisoformat(a.today) if a.today else date.today()
    fetcher = Fetcher(cache_dir=a.cache)
    exclude = {x.strip() for x in a.exclude.split(",") if x.strip()}

    def progress(i, n, label):
        print(f"  [{i}/{n}] {label}", file=sys.stderr, flush=True)

    companies = build_book(fetcher, a.address, exclude=exclude, limit=a.limit, progress=progress)
    if not companies:
        print("По этому адресу не найдено активных компаний.", file=sys.stderr)
        return 2

    report = build(companies, today, a.firm, a.address)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "index.html").write_text(to_html(report), encoding="utf-8")
    (out / "report.json").write_text(to_json(report), encoding="utf-8")
    (out / "report.csv").write_text(to_csv(report), encoding="utf-8")

    s = report["summary"]
    print(f"\n{a.firm}: {report['book_size']} компаний, {s['total']} находок "
          f"({s['critical']} критических), директоров без верификации "
          f"{s['idv_overdue'] + s['idv_pending']}, оценка штрафов £{s['money_gbp']}")
    print(f"-> {out/'index.html'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
