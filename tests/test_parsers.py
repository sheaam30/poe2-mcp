"""Unit tests for wikitext parsing and formatting — no network required."""
import pytest
from poe2_mcp.wiki import (
    parse_item_template,
    parse_monster_template,
    strip_markup,
    extract_prose,
    extract_monster_phases,
    format_gem,
    format_item,
    format_monster,
)

GEM_WIKITEXT = """\
{{Item
|rarity_id                               = normal
|name                                    = Fireball
|class_id                                = Active Skill Gem
|gem_tags                                = Spell, AoE, Fire, Projectile
|gem_description                         = Fires a projectile that explodes in fire.
|required_level                          = 1
|cast_time                               = 0.75
|active_skill_name                       = Fireball
|skill_id                                = Fireball
|static_cost_types                       = Mana
|static_mana_cost                        = 6
|static_stat1_id                         = base_is_projectile
|static_stat1_value                      = 1
|static_stat2_id                         = is_area_damage
|static_stat2_value                      = 1
}}
"""

CURRENCY_WIKITEXT = """\
{{Item
|rarity_id                               = normal
|name                                    = Chaos Orb
|class_id                                = StackableCurrency
|description                             = Reforges a rare item with new random modifiers
|stack_size                              = 20
|drop_level                              = 5
|release_version                         = 0.1.0
}}
"""

MAP_WIKITEXT = """\
{{Item
|rarity_id                               = normal
|name                                    = Waystone (Tier 5)
|class_id                                = Map
|map_tier                                = 5
|map_area_level                          = 69
|drop_level                              = 69
|release_version                         = 0.1.0
}}
"""

SUPPORT_GEM_WIKITEXT = """\
{{Item
|rarity_id                               = normal
|name                                    = Lifetap
|class_id                                = Support Skill Gem
|gem_tags                                = Support
|gem_description                         = Causes skills to spend life instead of mana.
|required_level                          = 8
}}
"""


class TestParseItemTemplate:
    def test_parses_gem_fields(self):
        data = parse_item_template(GEM_WIKITEXT)
        assert data["name"] == "Fireball"
        assert data["class_id"] == "Active Skill Gem"
        assert data["gem_tags"] == "Spell, AoE, Fire, Projectile"
        assert data["cast_time"] == "0.75"

    def test_parses_currency_fields(self):
        data = parse_item_template(CURRENCY_WIKITEXT)
        assert data["name"] == "Chaos Orb"
        assert data["class_id"] == "StackableCurrency"
        assert data["stack_size"] == "20"
        assert data["description"] == "Reforges a rare item with new random modifiers"

    def test_returns_empty_dict_for_no_template(self):
        assert parse_item_template("Just some prose text.") == {}

    def test_ignores_empty_values(self):
        wikitext = "{{Item\n|name = Test\n|empty_field =\n}}"
        data = parse_item_template(wikitext)
        assert "empty_field" not in data
        assert data["name"] == "Test"

    def test_support_gem_class_id(self):
        data = parse_item_template(SUPPORT_GEM_WIKITEXT)
        assert "Skill Gem" in data["class_id"]


class TestStripMarkup:
    def test_removes_color_template(self):
        assert strip_markup("{{c|gem|Fire}}") == "Fire"

    def test_removes_item_link(self):
        assert strip_markup("{{il|Chaos Orb}}") == "Chaos Orb"

    def test_removes_wiki_link_with_display(self):
        assert strip_markup("[[Rare|rare item]]") == "rare item"

    def test_removes_plain_wiki_link(self):
        assert strip_markup("[[Fireball]]") == "Fireball"

    def test_removes_bold(self):
        assert strip_markup("'''bold text'''") == "bold text"

    def test_removes_html_tags(self):
        assert strip_markup("<br>text</br>") == "text"

    def test_collapses_extra_spaces(self):
        result = strip_markup("{{c|color|word}}  next")
        assert "  " not in result

    def test_passes_through_plain_text(self):
        assert strip_markup("plain text") == "plain text"


class TestExtractProse:
    def test_extracts_opening_prose(self):
        wikitext = """\
{{SomeTemplate}}
==Section==
This is the actual prose description that should be extracted.
Another sentence here.
"""
        result = extract_prose(wikitext)
        assert "actual prose" in result
        assert "Another sentence" in result

    def test_skips_template_lines(self):
        wikitext = "{{Template|arg}}\nReal prose here with enough characters."
        result = extract_prose(wikitext)
        assert "{{" not in result
        assert "Real prose" in result

    def test_skips_table_markup(self):
        wikitext = "|-\n| cell\nReal prose line that is long enough."
        result = extract_prose(wikitext)
        assert "|-" not in result
        assert "| cell" not in result

    def test_respects_max_chars(self):
        long_prose = "\n".join(["Word " * 20] * 20)
        result = extract_prose(long_prose, max_chars=100)
        assert len(result) <= 200  # some slack for joining

    def test_returns_empty_for_all_markup(self):
        wikitext = "{{Template}}\n==Header==\n[[Category:Foo]]"
        result = extract_prose(wikitext)
        assert result == ""


class TestFormatGem:
    def test_formats_core_fields(self):
        data = parse_item_template(GEM_WIKITEXT)
        result = format_gem(data)
        assert "name: Fireball" in result
        assert "gem_tags: Spell, AoE, Fire, Projectile" in result
        assert "cast_time: 0.75" in result

    def test_formats_static_stats(self):
        data = parse_item_template(GEM_WIKITEXT)
        result = format_gem(data)
        assert "static_stats:" in result
        assert "base_is_projectile = 1" in result
        assert "is_area_damage = 1" in result

    def test_empty_data_returns_message(self):
        assert format_gem({}) == "No data found."


class TestFormatItem:
    def test_currency_shows_description_first(self):
        data = parse_item_template(CURRENCY_WIKITEXT)
        result = format_item(data)
        lines = result.splitlines()
        field_names = [l.split(":")[0] for l in lines]
        assert field_names.index("description") < field_names.index("drop_level")

    def test_map_shows_tier_first(self):
        data = parse_item_template(MAP_WIKITEXT)
        result = format_item(data)
        lines = result.splitlines()
        field_names = [l.split(":")[0] for l in lines]
        assert "map_tier" in field_names
        assert field_names.index("map_tier") < field_names.index("drop_level")

    def test_empty_data_returns_message(self):
        assert format_item({}) == "No data found."

    def test_excludes_recipe_fields(self):
        data = {"name": "Test", "class_id": "Weapon", "recipe_item": "something"}
        result = format_item(data)
        assert "recipe_item" not in result

    def test_excludes_metadata_fields(self):
        data = {"name": "Test", "class_id": "Weapon", "metadata_id": "Metadata/foo"}
        result = format_item(data)
        assert "metadata_id" not in result


MONSTER_WIKITEXT = """\
{{MonsterBox
|name                                    = The Lich King
|rarity                                  = Unique
|level                                   = 80
|location                                = Gehenna
|resistance                              = Fire, Cold
|weakness                                = Lightning
|damage                                  = Physical, Chaos
}}

==Phase 1==
Some lore text here.

{|
! Skill !! Description
|-
| Bone Nova | Fires bones in all directions
|-
| Death Grip | Pulls target toward boss
|}

==Phase 2==

{|
! Skill !! Description
|-
| Final Form | Unleashes full power
|}
"""

MECHANIC_WIKITEXT = """\
{{SomeTemplate}}
==Overview==
Critical Strike is a mechanic that deals bonus damage.
A critical strike deals increased damage based on your Critical Strike Multiplier.
The base critical strike chance is 5%.
WHERE items.crit LIKE "%crit%"
AND (more sql stuff here)
This line should appear after the SQL is filtered.
"""


class TestParseMonsterTemplate:
    def test_parses_basic_fields(self):
        data = parse_monster_template(MONSTER_WIKITEXT)
        assert data["name"] == "The Lich King"
        assert data["level"] == "80"
        assert data["rarity"] == "Unique"

    def test_parses_resistance_and_weakness(self):
        data = parse_monster_template(MONSTER_WIKITEXT)
        assert data["resistance"] == "Fire, Cold"
        assert data["weakness"] == "Lightning"

    def test_returns_empty_for_no_template(self):
        assert parse_monster_template("No monster here.") == {}

    def test_ignores_empty_values(self):
        wikitext = "{{MonsterBox\n|name = Boss\n|empty_field =\n}}"
        data = parse_monster_template(wikitext)
        assert "empty_field" not in data


class TestExtractMonsterPhases:
    def test_extracts_phase_headers(self):
        result = extract_monster_phases(MONSTER_WIKITEXT)
        assert "Phase 1" in result or "phase" in result.lower()

    def test_extracts_skill_table_rows(self):
        result = extract_monster_phases(MONSTER_WIKITEXT)
        assert "Bone Nova" in result or "Death Grip" in result

    def test_returns_empty_for_no_phases(self):
        result = extract_monster_phases("Just prose, no tables.")
        assert result == ""


class TestFormatMonster:
    def test_formats_known_fields(self):
        data = parse_monster_template(MONSTER_WIKITEXT)
        result = format_monster(data)
        assert "name: The Lich King" in result
        assert "level: 80" in result
        assert "resistance: Fire, Cold" in result

    def test_appends_phases_when_present(self):
        data = parse_monster_template(MONSTER_WIKITEXT)
        result = format_monster(data, phases="[Phase 1]\n  Bone Nova")
        assert "Encounter" in result
        assert "Bone Nova" in result

    def test_empty_data_returns_message(self):
        assert format_monster({}) == "No data found."


class TestExtractProseFiltering:
    def test_filters_sql_where_clauses(self):
        result = extract_prose(MECHANIC_WIKITEXT)
        assert "WHERE" not in result
        assert "LIKE" not in result
        assert "AND (" not in result

    def test_keeps_prose_after_sql_lines(self):
        result = extract_prose(MECHANIC_WIKITEXT)
        assert "This line should appear" in result

    def test_keeps_legitimate_prose(self):
        result = extract_prose(MECHANIC_WIKITEXT)
        assert "Critical Strike is a mechanic" in result
