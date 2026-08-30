"""Тесты правил риска. Полностью детерминированы: сеть не используется,
«сегодня» передаётся явно."""
import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from filingradar.parse import Company, Officer  # noqa: E402
from filingradar.risk import assess, late_filing_penalty, summarise, IDV_DEADLINE  # noqa: E402

TODAY = date(2026, 8, 30)


def company(**kw):
    base = dict(number="00000001", name="TEST LTD", status="Active")
    base.update(kw)
    return Company(**base)


class TestPenaltyScale(unittest.TestCase):
    def test_scale_matches_companies_house_bands(self):
        self.assertEqual(late_filing_penalty(0), 0)
        self.assertEqual(late_filing_penalty(1), 150)
        self.assertEqual(late_filing_penalty(30), 150)
        self.assertEqual(late_filing_penalty(31), 375)
        self.assertEqual(late_filing_penalty(90), 375)
        self.assertEqual(late_filing_penalty(91), 750)
        self.assertEqual(late_filing_penalty(181), 1500)


class TestAssess(unittest.TestCase):
    def test_dissolved_company_produces_nothing(self):
        c = company(status="Dissolved", accounts_overdue=True,
                    accounts_next_due=date(2020, 1, 1))
        self.assertEqual(assess(c, TODAY), [])

    def test_overdue_accounts_carry_money(self):
        c = company(accounts_overdue=True, accounts_next_due=date(2026, 1, 1))
        f = [x for x in assess(c, TODAY) if x.kind == "accounts_overdue"][0]
        self.assertEqual(f.severity, "critical")
        self.assertEqual(f.money_gbp, 1500)  # просрочка больше 180 дней

    def test_accounts_due_soon_is_warning_not_critical(self):
        c = company(accounts_next_due=date(2026, 9, 20))
        f = [x for x in assess(c, TODAY) if x.kind == "accounts_due_soon"][0]
        self.assertEqual(f.severity, "warning")
        self.assertEqual(f.days, 21)

    def test_distant_deadline_is_not_reported(self):
        # Директор нужен: без него сработает отдельное правило no_active_officers,
        # и тест перестанет проверять именно дальний срок.
        c = company(accounts_next_due=date(2027, 6, 1),
                    officers=[Officer(name="X", identity_verified=True, verification_required=True)])
        self.assertEqual(assess(c, TODAY), [])

    def test_unverified_officer_past_personal_deadline_is_critical(self):
        c = company(officers=[Officer(name="X", identity_verified=False, verification_required=True,
                                      verification_due=date(2025, 11, 18))])
        f = [x for x in assess(c, TODAY) if x.kind == "idv_overdue"][0]
        self.assertEqual(f.severity, "critical")
        self.assertIn("истёк", f.detail)

    def test_unverified_officer_without_date_falls_back_to_statutory_deadline(self):
        c = company(officers=[Officer(name="X", identity_verified=False, verification_required=True)])
        f = [x for x in assess(c, TODAY) if x.kind == "idv_pending"][0]
        self.assertEqual(f.due, IDV_DEADLINE)
        self.assertEqual(f.days, 80)

    def test_verified_officer_produces_no_finding(self):
        c = company(officers=[Officer(name="X", identity_verified=True, verification_required=True)])
        self.assertEqual([x for x in assess(c, TODAY) if x.kind.startswith("idv")], [])

    def test_resigned_officer_is_ignored(self):
        c = company(officers=[Officer(name="X", identity_verified=False, verification_required=True, resigned=True)])
        kinds = {x.kind for x in assess(c, TODAY)}
        self.assertNotIn("idv_pending", kinds)
        self.assertIn("no_active_officers", kinds)

    def test_critical_findings_sort_before_warnings(self):
        c = company(accounts_overdue=True, accounts_next_due=date(2026, 1, 1),
                    confirmation_next_due=date(2026, 9, 10))
        sev = [f.severity for f in assess(c, TODAY)]
        self.assertEqual(sev, sorted(sev, key=lambda s: s != "critical"))


class TestSecretaryRegression(unittest.TestCase):
    """Секретарь без обязанности верифицироваться не должен попадать в находки."""

    def test_secretary_not_flagged(self):
        c = company(officers=[
            Officer(name="SEC", role="Secretary", verification_required=False),
            Officer(name="DIR", role="Director", verification_required=True,
                    identity_verified=True),
        ])
        self.assertEqual([f for f in assess(c, TODAY) if f.kind.startswith("idv")], [])


class TestSummarise(unittest.TestCase):
    def test_summary_counts_and_money(self):
        c = company(accounts_overdue=True, accounts_next_due=date(2026, 1, 1),
                    officers=[Officer(name="X", identity_verified=False, verification_required=True)])
        s = summarise(assess(c, TODAY))
        self.assertEqual(s["critical"], 1)
        self.assertEqual(s["idv_pending"], 1)
        self.assertEqual(s["money_gbp"], 1500)
        self.assertEqual(s["companies"], 1)


if __name__ == "__main__":
    unittest.main()
