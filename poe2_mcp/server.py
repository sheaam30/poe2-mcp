import asyncio
from mcp.server.fastmcp import FastMCP
from poe2_mcp import wiki

mcp = FastMCP(
    "poe2",
    instructions="Path of Exile 2 game data — items, gems, and passives via poe2wiki.net",
)


@mcp.tool()
async def search_wiki(query: str, limit: int = 10) -> str:
    """Search the PoE wiki for pages matching a query. Returns up to `limit` page titles.
    Use this to discover item names, gem names, passive names, or any other game concept
    before fetching detailed data with get_item, get_gem, or get_passive."""
    titles = await wiki.search_pages(query, limit=min(limit, 20))
    if not titles:
        return f"No wiki pages found for '{query}'."
    return "\n".join(f"- {t}" for t in titles)


@mcp.tool()
async def get_item(name: str) -> str:
    """Get detailed stats for a PoE item — base types (weapons, armour, flasks) or unique items.
    Returns structured data including damage ranges, requirements, implicits, and tags.
    Use search_wiki first if you're unsure of the exact page name."""
    wikitext = await wiki.fetch_wikitext(name)
    if not wikitext:
        return f"Page '{name}' not found."
    data = wiki.parse_item_template(wikitext)
    if not data:
        return f"No item template found on '{name}'. Try search_wiki to find the correct page name."
    return wiki.format_item(data)


@mcp.tool()
async def get_gem(name: str) -> str:
    """Get details for a skill gem or support gem — description, tags, cast time, required level,
    mana cost, and static stats. Use search_wiki first if unsure of the exact name."""
    wikitext = await wiki.fetch_wikitext(name)
    if not wikitext:
        return f"Page '{name}' not found."
    data = wiki.parse_item_template(wikitext)
    if not data:
        return f"No gem data found on '{name}'. Try search_wiki to find the correct page name."
    class_id = data.get("class_id", "")
    if "Skill Gem" not in class_id:
        return f"'{name}' does not appear to be a skill gem (class_id: {class_id}). Try get_item instead."
    return wiki.format_gem(data)


@mcp.tool()
async def search_gems(name: str, gem_tag: str = "") -> str:
    """Search for skill gems by name fragment, optionally filtered by a gem tag (e.g. 'Fire',
    'AoE', 'Support', 'Cold', 'Lightning', 'Projectile', 'Melee', 'Spell', 'Minion').
    When gem_tag is provided, uses wiki category listings for complete coverage.
    Returns matching gem names and their tags."""
    if gem_tag:
        # Category listing gives complete, accurate tag coverage
        categories = [f"{gem_tag} skill gems", f"{gem_tag} support gems", f"{gem_tag} meta gems"]
        cat_results = await asyncio.gather(*[wiki.list_category(c) for c in categories])
        titles = [t for group in cat_results for t in group]
        if name:
            name_lower = name.lower()
            titles = [t for t in titles if name_lower in t.lower()]
        if not titles:
            return f"No gems found with tag '{gem_tag}'" + (f" matching '{name}'" if name else "") + "."
    else:
        titles = await wiki.search_pages(name, limit=15)
        if not titles:
            return f"No results for '{name}'."

    wikitexts = await wiki.fetch_wikitexts_batch(titles)

    results = []
    for title in titles:
        data = wiki.parse_item_template(wikitexts.get(title, ""))
        if "Skill Gem" not in data.get("class_id", ""):
            continue
        tags = data.get("gem_tags", "")
        gem_name = data.get("name", title)
        desc = data.get("gem_description", "")
        line = f"- {gem_name}"
        if tags:
            line += f"  [{tags}]"
        if desc:
            line += f"\n  {wiki.strip_markup(desc)}"
        results.append(line)

    if not results:
        msg = f"No gems found matching '{name}'"
        if gem_tag:
            msg += f" with tag '{gem_tag}'"
        return msg + "."
    return "\n".join(results)


@mcp.tool()
async def search_items(query: str, item_class: str = "") -> str:
    """Search for non-gem items by name fragment, optionally filtered by item class.
    Common item_class values: 'StackableCurrency', 'Map', 'SoulCore' (runes),
    'Body Armour', 'Helmet', 'Gloves', 'Boots', 'Weapon', 'Shield', 'Flask'.
    Unique items have rarity_id = 'unique'. Returns matching item names and classes."""
    titles = await wiki.search_pages(query, limit=15)
    if not titles:
        return f"No results for '{query}'."

    wikitexts = await wiki.fetch_wikitexts_batch(titles)

    results = []
    for title in titles:
        data = wiki.parse_item_template(wikitexts.get(title, ""))
        if not data:
            continue
        class_id = data.get("class_id", "")
        # Exclude gems — use search_gems for those
        if "Skill Gem" in class_id:
            continue
        if item_class and item_class.lower() not in class_id.lower():
            continue
        item_name = data.get("name", title)
        rarity = data.get("rarity_id", "")
        line = f"- {item_name}  [{class_id}]"
        if rarity and rarity != "normal":
            line += f"  ({rarity})"
        desc = data.get("description", "") or data.get("help_text", "")
        if desc:
            line += f"\n  {wiki.strip_markup(desc)}"
        results.append(line)

    if not results:
        msg = f"No items found matching '{query}'"
        if item_class:
            msg += f" with class '{item_class}'"
        return msg + "."
    return "\n".join(results)


@mcp.tool()
async def get_monster(name: str) -> str:
    """Get stats and encounter guide for a boss or unique monster.
    Returns resistances, weaknesses, damage types, level, and phase-by-phase
    skill breakdown where available. Use search_wiki to find the exact page name."""
    wikitext = await wiki.fetch_wikitext(name)
    if not wikitext:
        return f"Page '{name}' not found."
    data = wiki.parse_monster_template(wikitext)
    if not data:
        return f"No monster data found for '{name}'. Try search_wiki to find the correct page name."
    phases = wiki.extract_monster_phases(wikitext)
    return wiki.format_monster(data, phases)


@mcp.tool()
async def get_mechanic(name: str) -> str:
    """Get a detailed explanation of a game mechanic or keyword — e.g. 'Critical strike',
    'Ailment', 'Freeze', 'Bleed', 'Stun', 'Leech', 'Evasion', 'Block', 'Mana'.
    Returns the wiki prose description with mechanics and formulas.
    Use search_wiki to discover the exact page name."""
    wikitext = await wiki.fetch_wikitext(name)
    if not wikitext:
        return f"Page '{name}' not found."
    prose = wiki.extract_prose(wikitext, max_chars=2000)
    if not prose:
        return f"No description found for '{name}'."
    return f"=== {name} ===\n{prose}"


@mcp.tool()
async def get_passive(name: str) -> str:
    """Get the description and effects of a passive skill tree node (including keystones
    and notables). Returns prose description extracted from the wiki page."""
    wikitext = await wiki.fetch_wikitext(name)
    if not wikitext:
        return f"Page '{name}' not found."
    prose = wiki.extract_prose(wikitext)
    if not prose:
        return f"No description found for passive '{name}'."
    return f"=== {name} ===\n{prose}"


@mcp.tool()
async def search_corpus(query: str, category: str = "", n_results: int = 5) -> str:
    """Semantic search over the local PoE2 knowledge corpus (mechanics, monsters, ascendancies,
    passives, endgame content). Returns the most relevant passages ranked by similarity.
    Optional category filter: mechanics, monsters, ascendancy, passives, endgame, areas, acts.
    Requires running scripts/embed_corpus.py first to build the local index."""
    from poe2_mcp import rag

    if not rag.is_available():
        return (
            "Corpus index not found. Build it first:\n"
            "  python scripts/build_rag_corpus.py\n"
            "  python scripts/embed_corpus.py"
        )

    results = rag.query(query, n_results=min(n_results, 10), category=category)
    if not results:
        return f"No results found for '{query}'" + (f" in category '{category}'" if category else "") + "."

    lines = []
    for r in results:
        lines.append(f"[{r['category']}] {r['title']}  (relevance: {r['score']})")
        lines.append(r["content"][:600])
        lines.append("")
    return "\n".join(lines).strip()


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
