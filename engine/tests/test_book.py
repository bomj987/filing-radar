"""Тесты сужения адреса. Сеть не используется."""
import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from filingradar.book import postcode_of, normalise_address  # noqa: E402


class TestPostcode(unittest.TestCase):
    def test_extracts_uk_postcode_in_various_shapes(self):
        self.assertEqual(postcode_of("2 Stamford Square London SW15 2BF"), "SW15 2BF")
        self.assertEqual(postcode_of("202 Merlin Park Ormskirk L408JY"), "L40 8JY")
        self.assertEqual(postcode_of("4a Smithdown Road Liverpool England L7 4JG"), "L7 4JG")

    def test_returns_none_for_address_without_postcode(self):
        # Реальный случай из реестра 2026-08-30: адрес практики буквально "Unit A".
        self.assertIsNone(postcode_of("Unit A"))

    def test_normalise_strips_country(self):
        self.assertEqual(normalise_address("4a Smithdown Road Liverpool, United Kingdom L7 4JG"),
                         "4a Smithdown Road Liverpool L7 4JG")
