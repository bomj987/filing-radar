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

    def test_anonymiser_survives_a_change_of_detail_separator(self):
        """Регрессия 2026-08-30: разделитель в detail поменялся с ': ' на ' — ',
        обезличиватель был привязан к старому и перестал вырезать имена."""
        r = sample()
        for f in r["findings"]:
            f["detail"] = f["detail"].replace(" — ", ": ", 1)
        self.assertNotIn("SMITH, John", str(anonymise(r)))

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


class TestEmailSections(unittest.TestCase):
    """Тема письма обещает конкретный тип находок — таблица обязана начинаться с него."""

    def test_kinds_filter_selects_only_requested(self):
        from filingradar.report import to_email_html
        c = Company(number="1", name="X", status="Active",
                    accounts_overdue=True, accounts_next_due=date(2026, 1, 1),
                    officers=[Officer(name="A", role="Director",
                                      verification_required=True, identity_verified=False)])
        r = build([c], TODAY, "F", "1 Street L1 1AA")
        idv = to_email_html(r, kinds=("idv_pending", "idv_overdue"))
        self.assertIn("ID not verified", idv)
        self.assertNotIn("Accounts overdue", idv)

    def test_empty_filter_returns_empty_string_not_empty_table(self):
        from filingradar.report import to_email_html
        c = Company(number="1", name="X", status="Active",
                    officers=[Officer(name="A", role="Director",
                                      verification_required=True, identity_verified=True)])
        r = build([c], TODAY, "F", "1 Street L1 1AA")
        self.assertEqual(to_email_html(r, kinds=("idv_pending",)), "")


class TestShortAddress(unittest.TestCase):
    def test_drops_country_and_keeps_whole_words(self):
        import sys as _s
        _s.path.insert(0, str(Path(__file__).resolve().parents[1]))
        from compose import short_address
        got = short_address("Carter House G2 Wyvern Court Derby England DE21 6BF")
        self.assertIn("Wyvern Court", got)
        self.assertNotIn("England", got)
        self.assertIn("DE21 6BF", got)
