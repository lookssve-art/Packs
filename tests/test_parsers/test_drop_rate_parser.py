"""Tests for drop rate parsers."""

import pytest

from src.parsers.drop_rate_parser import (
    _parse_percentage,
    parse_drop_rates_from_api,
    parse_drop_rates_from_scrape,
    parse_drop_rates_manual,
)


class TestParsePercentage:
    def test_percentage_string(self):
        assert _parse_percentage("2.00%") == pytest.approx(0.02)
        assert _parse_percentage("100%") == pytest.approx(1.0)
        assert _parse_percentage("0.5%") == pytest.approx(0.005)

    def test_decimal_string(self):
        assert _parse_percentage("0.02") == pytest.approx(0.02)
        assert _parse_percentage("1.0") == pytest.approx(1.0)

    def test_large_number_treated_as_percentage(self):
        assert _parse_percentage("60") == pytest.approx(0.60)


class TestParseDropRatesFromAPI:
    def test_structure_1_rates_dict(self):
        data = {"rates": {"holographic": 0.02, "gold": 0.08, "silver": 0.30, "gloss": 0.60}}
        snapshot = parse_drop_rates_from_api(data, "sapphire")
        assert snapshot is not None
        assert snapshot.rates["holographic"] == pytest.approx(0.02)
        assert sum(snapshot.rates.values()) == pytest.approx(1.0)

    def test_structure_2_tiers_list(self):
        data = {"tiers": [
            {"name": "Holographic", "rate": 0.02},
            {"name": "Gold", "rate": 0.08},
            {"name": "Silver", "rate": 0.30},
            {"name": "Gloss", "rate": 0.60},
        ]}
        snapshot = parse_drop_rates_from_api(data, "emerald")
        assert snapshot is not None
        assert snapshot.rates["holographic"] == pytest.approx(0.02)

    def test_structure_3_droprates_pct(self):
        data = {"dropRates": {
            "Holographic": "2%",
            "Gold": "8%",
            "Silver": "30%",
            "Gloss": "60%",
        }}
        snapshot = parse_drop_rates_from_api(data, "sapphire")
        assert snapshot is not None
        assert snapshot.rates["holographic"] == pytest.approx(0.02)

    def test_empty_data_returns_none(self):
        assert parse_drop_rates_from_api({}, "sapphire") is None


class TestParseDropRatesFromScrape:
    def test_valid_scraped_data(self):
        data = {"tiers": [
            {"name": "Holographic", "percentage": "2.00%", "value_range": "$500-$2000"},
            {"name": "Gold", "percentage": "8.00%", "value_range": "$100-$400"},
            {"name": "Silver", "percentage": "30.00%"},
            {"name": "Gloss", "percentage": "60.00%"},
        ]}
        snapshot = parse_drop_rates_from_scrape(data, "sapphire")
        assert snapshot is not None
        assert snapshot.rates["holographic"] == pytest.approx(0.02)
        assert snapshot.source == "scraper"


class TestParseDropRatesManual:
    def test_manual_entry(self):
        rates = {"holographic": 0.02, "gold": 0.08, "silver": 0.30, "gloss": 0.60}
        snapshot = parse_drop_rates_manual(rates, "sapphire")
        assert snapshot.source == "manual"
        assert snapshot.rates == rates
