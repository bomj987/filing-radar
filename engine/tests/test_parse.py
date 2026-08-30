"""Тесты парсера закреплены на реально сохранённых страницах Companies House.

Если разметка государственного сайта изменится — эти тесты упадут, и это их
назначение. Сеть в тестах не используется, зависимостей нет: запуск
`python3 -m unittest discover -s tests -v` из каталога mvp/.
"""
import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from filingradar.parse import parse_company, parse_officers, parse_date, text_of  # noqa: E402

FIX = Path(__file__).resolve().parents[1] / "fixtures"


def read(name):
    return (FIX / name).read_text(encoding="utf-8", errors="replace")


class TestHelpers(unittest.TestCase):
    def test_parse_date_handles_gov_uk_format(self):
        self.assertEqual(parse_date("due by 31 October 2022"), date(2022, 10, 31))

    def test_parse_date_returns_none_when_absent(self):
        self.assertIsNone(parse_date("никакой даты здесь нет"))

    def test_text_of_separates_adjacent_fields(self):
        self.assertIn("|", text_of("<dt>Role</dt><dd>Director</dd>"))


class TestCompanyPage(unittest.TestCase):
    def test_company_with_overdue_filings(self):
        c = parse_company(read("company_active.html"), "11787047")
        self.assertEqual(c.name, "SHL CONSULTANCY LTD")
        self.assertEqual(c.status, "Active")
        self.assertEqual(c.incorporated, date(2019, 1, 24))
        self.assertTrue(c.accounts_overdue)
        self.assertTrue(c.confirmation_overdue)
        self.assertEqual(c.accounts_next_due, date(2022, 10, 31))
        self.assertEqual(c.confirmation_next_due, date(2022, 1, 17))
        self.assertTrue(c.sic.startswith("69201"))

    def test_company_in_good_standing(self):
        c = parse_company(read("company_ok.html"), "00445790")
        self.assertEqual(c.name, "TESCO PLC")
        self.assertFalse(c.accounts_overdue)
        self.assertFalse(c.confirmation_overdue)
        self.assertEqual(c.accounts_next_due, date(2027, 8, 26))

    def test_dissolved_company_has_no_future_deadlines(self):
        c = parse_company(read("company_overdue.html"), "12345678")
        self.assertEqual(c.status, "Dissolved")
        self.assertIsNone(c.accounts_next_due)
        self.assertIsNone(c.confirmation_next_due)


class TestOfficersPage(unittest.TestCase):
    def test_unverified_officer_exposes_personal_deadline(self):
        officers = parse_officers(read("officers_unverified.html"))
        self.assertEqual(len(officers), 1)
        o = officers[0]
        self.assertEqual(o.name, "HOWARD, Siobhan")
        self.assertEqual(o.role, "Director")
        self.assertFalse(o.resigned)
        self.assertFalse(o.identity_verified)
        self.assertEqual(o.verification_due, date(2025, 11, 18))

    def test_secretary_is_not_required_to_verify(self):
        """Регрессия: 2026-08-30 движок помечал секретарей как непроверенных.

        По ECCTA верификацию проходят директора, PSC и участники LLP, но не
        секретари. Companies House это различает: у необязанного лица на
        странице нет ни поля 'due', ни поля 'status'.
        """
        officers = parse_officers(read("officers_mixed_secretary.html"))
        by_role = {(o.name, o.role): o for o in officers}
        secretary = by_role[("ATHERTON, Wendy Elizabeth", "Secretary")]
        director = by_role[("ATHERTON, Robert James", "Director")]
        self.assertFalse(secretary.verification_required)
        self.assertTrue(director.verification_required)
        self.assertTrue(director.identity_verified)

    def test_secretary_excluded_from_unverified_list(self):
        c = parse_company(read("company_ok.html"), "07085010")
        c.officers = parse_officers(read("officers_mixed_secretary.html"))
        self.assertEqual(len(c.active_officers), 3)
        self.assertEqual(c.unverified_officers, [])

    def test_verified_officer_detected(self):
        o = parse_officers(read("officers_verified.html"))[0]
        self.assertEqual(o.name, "SMITH, Kevin Daryl")
        self.assertTrue(o.identity_verified)
        self.assertIsNone(o.verification_due)

    def test_company_helpers_split_active_and_unverified(self):
        c = parse_company(read("company_active.html"), "11787047")
        c.officers = parse_officers(read("officers_unverified.html"))
        self.assertEqual(len(c.active_officers), 1)
        self.assertEqual(len(c.unverified_officers), 1)


if __name__ == "__main__":
    unittest.main()
