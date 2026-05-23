"""Integration tests — hit the live poe2wiki.net API.

Skipped automatically when the network is unavailable or SKIP_INTEGRATION=1 is set.
Run manually with: pytest tests/test_integration.py -v
"""
import os
import asyncio
import pytest
from poe2_mcp import wiki

pytestmark = pytest.mark.skipif(
    os.environ.get("SKIP_INTEGRATION") == "1",
    reason="SKIP_INTEGRATION=1",
)


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


class TestSearchPages:
    def test_finds_known_gem(self):
        results = run(wiki.search_pages("Rolling Magma", limit=5))
        assert "Rolling Magma" in results

    def test_finds_poe2_only_gem(self):
        results = run(wiki.search_pages("Galvanic Shard", limit=5))
        assert any("Galvanic" in r for r in results)

    def test_returns_empty_for_nonsense(self):
        results = run(wiki.search_pages("xyzzy_notarealpage_12345", limit=5))
        assert results == []


class TestFetchWikitext:
    def test_fetches_gem_page(self):
        wikitext = run(wiki.fetch_wikitext("Fireball"))
        assert "{{Item" in wikitext
        assert "Active Skill Gem" in wikitext

    def test_returns_empty_for_missing_page(self):
        wikitext = run(wiki.fetch_wikitext("Xyzzy_NotARealPage_99999"))
        assert wikitext == ""


class TestFetchWikitextsBatch:
    def test_fetches_multiple_pages(self):
        results = run(wiki.fetch_wikitexts_batch(["Fireball", "Rolling Magma"]))
        assert "Fireball" in results
        assert "Rolling Magma" in results
        assert "{{Item" in results["Fireball"]

    def test_handles_missing_pages(self):
        results = run(wiki.fetch_wikitexts_batch(["Fireball", "Xyzzy_NotARealPage_99999"]))
        assert "Fireball" in results
        assert "Xyzzy_NotARealPage_99999" not in results

    def test_returns_empty_dict_for_empty_input(self):
        results = run(wiki.fetch_wikitexts_batch([]))
        assert results == {}


class TestListCategory:
    def test_lists_fire_gems(self):
        members = run(wiki.list_category("Fire skill gems"))
        assert len(members) > 5
        assert "Fireball" in members

    def test_returns_empty_for_nonexistent_category(self):
        members = run(wiki.list_category("Xyzzy_NotACategory_99999"))
        assert members == []


class TestEndToEnd:
    def test_parse_fireball_gem(self):
        wikitext = run(wiki.fetch_wikitext("Fireball"))
        data = wiki.parse_item_template(wikitext)
        assert data["name"] == "Fireball"
        assert "Fire" in data.get("gem_tags", "")
        result = wiki.format_gem(data)
        assert "cast_time" in result

    def test_parse_exalted_orb_currency(self):
        wikitext = run(wiki.fetch_wikitext("Exalted Orb"))
        data = wiki.parse_item_template(wikitext)
        assert data["class_id"] == "StackableCurrency"
        result = wiki.format_item(data)
        assert "description:" in result
        assert result.index("description:") < result.index("drop_level:")
