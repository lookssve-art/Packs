"""Tests for pull parsers."""

import datetime
import pytest

from src.parsers.pull_parser import (
    parse_me_activity,
    parse_packs_api_pull,
    parse_scraped_pull,
)


class TestParseMEActivity:
    def test_basic_parsing(self):
        activity = {
            "signature": "abc123",
            "tokenMint": "mint456",
            "blockTime": 1700000000,
            "price": 150.0,
            "name": "Pokemon Gold Card",
            "image": "https://example.com/card.png",
            "collectionSymbol": "collector_crypt",
        }
        pull = parse_me_activity(activity, pack_type="sapphire")
        assert pull is not None
        assert pull.pull_id == "me_activity:abc123:mint456"
        assert pull.pack_type == "sapphire"
        assert pull.rarity == "gold"  # Inferred from name
        assert pull.estimated_value == 150.0

    def test_missing_signature_returns_none(self):
        activity = {"tokenMint": "mint456"}
        assert parse_me_activity(activity) is None

    def test_missing_mint_returns_none(self):
        activity = {"signature": "abc123"}
        assert parse_me_activity(activity) is None

    def test_rarity_inference_from_price(self):
        # High price → holographic
        pull = parse_me_activity({
            "signature": "s1", "tokenMint": "m1", "price": 1000.0
        })
        assert pull.rarity == "holographic"

        # Medium → gold
        pull = parse_me_activity({
            "signature": "s2", "tokenMint": "m2", "price": 150.0
        })
        assert pull.rarity == "gold"

        # Low → silver
        pull = parse_me_activity({
            "signature": "s3", "tokenMint": "m3", "price": 50.0
        })
        assert pull.rarity == "silver"


class TestParsePacksAPIPull:
    def test_basic_parsing(self):
        data = {
            "id": "pull_001",
            "timestamp": "2024-01-15T12:00:00Z",
            "packType": "sapphire",
            "rarity": "Gold",
            "cardName": "Pikachu VMAX",
            "value": 150.0,
            "payoutValue": 127.5,
            "imageUrl": "https://example.com/pikachu.png",
        }
        pull = parse_packs_api_pull(data)
        assert pull is not None
        assert pull.pull_id == "pull_001"
        assert pull.pack_type == "sapphire"
        assert pull.rarity == "gold"  # Lowercased
        assert pull.estimated_value == 150.0
        assert pull.payout_value == 127.5

    def test_generates_id_when_missing(self):
        data = {
            "timestamp": "2024-01-15T12:00:00Z",
            "packType": "sapphire",
            "rarity": "Silver",
        }
        pull = parse_packs_api_pull(data)
        assert pull is not None
        assert pull.pull_id.startswith("packs:")


class TestParseScrapedPull:
    def test_basic_parsing(self):
        data = {
            "pull_id": "scrape_001",
            "timestamp": "2024-01-15T12:00:00Z",
            "pack_type": "Emerald",
            "rarity": "Holographic",
            "card_name": "Charizard Base Set",
            "value": 2000.0,
        }
        pull = parse_scraped_pull(data)
        assert pull is not None
        assert pull.pack_type == "emerald"
        assert pull.rarity == "holographic"
        assert pull.estimated_value == 2000.0
