"""Тесты обезличивания и письма."""
import sys, unittest
from datetime import date
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from filingradar.parse import Company, Officer  # noqa: E402
from filingradar.report import build, anonymise, to_email_html, to_csv  # noqa: E402

TODAY = date(2026, 8, 30)


def sample():
    c = Company(number="01234567", name="ACME TRADING LTD", status="Active",
                accounts_overdue=True, accounts_next_due=date(2026, 1, 1),
                officers=[Officer(name="SMITH, John", role="Director",
                                  verification_required=True, identity_verified=False)])
    return build([c], TODAY, "REAL FIRM LTD", "1 Real Street L1 1AA")


class TestAnonymise(unittest.TestCase):
    def test_removes_firm_and_client_identity(self):
        a = anonymise(sample())
        blob = str(a)
        self.assertNotIn("REAL FIRM LTD", blob)
        self.assertNotIn("ACME TRADING LTD", blob)
        self.assertNotIn("01234567", blob)
        self.assertNotIn("SMITH, John", blob)
        self.assertIn("Client company 1", blob)

    def test_original_report_is_not_mutated(self):
        r = sample()
        anonymise(r)
        self.assertEqual(r["firm"]["name"], "REAL FIRM LTD")
        self.assertIn("ACME TRADING LTD", str(r))

    def test_findings_count_preserved(self):
        r = sample()
        self.assertEqual(len(anonymise(r)["findings"]), len(r["findings"]))


class TestEmailHtml(unittest.TestCase):
    def test_contains_no_external_resources(self):
        h = to_email_html(sample())
        self.assertNotIn("<style", h)
        self.assertNotIn("<script", h)
        self.assertNotIn('src=', h)

    def test_links_back_to_companies_house(self):
        self.assertIn("company-information.service.gov.uk/company/01234567", to_email_html(sample()))

    def test_truncation_is_announced(self):
        r = sample()
        r["findings"] = r["findings"] * 20
        self.assertIn("and 28 more", to_email_html(r, limit=12))


class TestCsv(unittest.TestCase):
    def test_header_and_row_count(self):
        r = sample()
        lines = to_csv(r).strip().split("\n")
        self.assertTrue(lines[0].startswith("company_number,"))
        self.assertEqual(len(lines) - 1, len(r["findings"]))
