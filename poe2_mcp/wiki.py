import asyncio
import re
import time
import httpx

WIKI_API = "https://www.poe2wiki.net/api.php"
USER_AGENT = "poe2-mcp/0.1 (local MCP server; poe2 game data lookups)"
# Wiki data rarely changes — cache aggressively (24 hours default)
CACHE_TTL = 86_400

_cache: dict[str, tuple[float, object]] = {}
_client: httpx.AsyncClient | None = None
# Limit concurrent wiki requests to avoid timeouts
_sem = asyncio.Semaphore(3)


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(
            headers={"User-Agent": USER_AGENT},
            timeout=20.0,
        )
    return _client


async def _api(params: dict) -> dict:
    key = str(sorted(params.items()))
    if key in _cache:
        ts, data = _cache[key]
        if time.time() - ts < CACHE_TTL:
            return data  # type: ignore[return-value]

    async with _sem:
        resp = await _get_client().get(WIKI_API, params=params)
    resp.raise_for_status()
    data = resp.json()
    _cache[key] = (time.time(), data)
    return data


def _chunks(lst: list, n: int):
    for i in range(0, len(lst), n):
        yield lst[i : i + n]


async def search_pages(query: str, limit: int = 10) -> list[str]:
    data = await _api({
        "action": "opensearch",
        "format": "json",
        "search": query,
        "namespace": 0,
        "limit": limit,
    })
    return data[1] if len(data) > 1 else []


async def list_category(category: str, limit: int = 100) -> list[str]:
    data = await _api({
        "action": "query",
        "format": "json",
        "list": "categorymembers",
        "cmtitle": f"Category:{category}",
        "cmlimit": min(limit, 500),
        "cmtype": "page",
    })
    return [m["title"] for m in data.get("query", {}).get("categorymembers", [])]


async def fetch_wikitexts_batch(titles: list[str]) -> dict[str, str]:
    """Fetch wikitext for multiple pages in as few requests as possible (50 per call)."""
    if not titles:
        return {}
    results: dict[str, str] = {}
    for chunk in _chunks(list(titles), 50):
        async with _sem:
            resp = await _get_client().get(WIKI_API, params={
                "action": "query",
                "format": "json",
                "titles": "|".join(chunk),
                "prop": "revisions",
                "rvprop": "content",
                "rvslots": "main",
            })
        resp.raise_for_status()
        data = resp.json()
        for page in data.get("query", {}).get("pages", {}).values():
            revs = page.get("revisions", [])
            if revs:
                content = revs[0].get("slots", {}).get("main", {}).get("*", "")
                results[page["title"]] = content
    return results


async def fetch_wikitext(page: str) -> str:
    data = await _api({
        "action": "parse",
        "format": "json",
        "page": page,
        "prop": "wikitext",
        "redirects": 1,
    })
    if "parse" in data:
        return data["parse"]["wikitext"]["*"]
    return ""


def _parse_template(wikitext: str, name: str) -> dict[str, str]:
    """Extract key-value pairs from any {{TemplateName|...}} block."""
    match = re.search(rf"\{{\{{{name}\s*\n(.*?)\n\}}\}}", wikitext, re.DOTALL)
    if not match:
        return {}
    result = {}
    for line in match.group(1).splitlines():
        line = line.strip()
        if line.startswith("|") and "=" in line:
            key, _, value = line[1:].partition("=")
            key, value = key.strip(), value.strip()
            if value:
                result[key] = value
    return result


def parse_item_template(wikitext: str) -> dict[str, str]:
    """Extract key-value pairs from the {{Item|...}} template block."""
    return _parse_template(wikitext, "Item")


def parse_monster_template(wikitext: str) -> dict[str, str]:
    """Extract key-value pairs from the {{MonsterBox|...}} template block."""
    return _parse_template(wikitext, "MonsterBox")


def strip_markup(text: str) -> str:
    """Remove common wiki markup from prose text."""
    # {{c|color|text}} → text  (colored text)
    text = re.sub(r"\{\{c\|[^|]+\|([^}]+)\}\}", r"\1", text)
    # {{il|name}}, {{ml|name}}, {{sl|name}} → name  (item/mod/skill links)
    text = re.sub(r"\{\{(?:il|ml|sl|gem)\|([^|}]+)[^}]*\}\}", r"\1", text)
    # {{passive skill link|Name}} → Name
    text = re.sub(r"\{\{passive skill link\|([^|}]+)[^}]*\}\}", r"\1", text)
    # remaining {{template|...}} → empty
    text = re.sub(r"\{\{[^}]*\}\}", "", text)
    # [[link|display]] → display
    text = re.sub(r"\[\[[^\]]*\|([^\]]+)\]\]", r"\1", text)
    # [[link]] → link
    text = re.sub(r"\[\[([^\]]+)\]\]", r"\1", text)
    # '''bold''' and ''italic''
    text = re.sub(r"'{2,3}", "", text)
    # HTML tags
    text = re.sub(r"<[^>]+>", "", text)
    # collapse multiple spaces left by removed templates
    text = re.sub(r"  +", " ", text)
    return text.strip()


_SQL_RE = re.compile(r"\b(WHERE|LIKE\s+['\"]%|AND\s*\(|SELECT\s+\w|FROM\s+\w+\s+WHERE)\b", re.IGNORECASE)


def extract_prose(wikitext: str, max_chars: int = 800) -> str:
    """Return the first meaningful prose block from a wiki page."""
    lines = []
    for line in wikitext.splitlines():
        stripped = line.strip()
        # Skip template lines, headers, table markup, category links, SQL fragments
        if (
            stripped.startswith("{{")
            or stripped.startswith("|")
            or stripped.startswith("!")
            or stripped.startswith("==")
            or stripped.startswith("[[Category")
            or stripped.startswith("{|")
            or stripped.startswith("|-")
            or not stripped
            or _SQL_RE.search(stripped)
        ):
            continue
        cleaned = strip_markup(stripped)
        if len(cleaned) > 20:
            lines.append(cleaned)
        if sum(len(line) for line in lines) >= max_chars:
            break
    return "\n\n".join(lines)


GEM_FIELDS = [
    "name", "class_id", "gem_tags", "gem_description",
    "required_level", "cast_time", "critical_strike_chance",
    "active_skill_name", "skill_id",
    "static_cost_types", "static_mana_cost", "static_life_cost",
    "static_critical_strike_chance", "static_damage_multiplier",
    "quality_type1_stat_text",
]

ITEM_FIELDS = [
    "name", "class_id", "drop_level", "required_level",
    "required_strength", "required_dexterity", "required_intelligence",
    "physical_damage_min", "physical_damage_max",
    "critical_strike_chance", "attack_speed", "weapon_range",
    "armour", "evasion", "energy_shield",
    "block", "ward",
    "tags",
]

CURRENCY_FIELDS = [
    "name", "class_id", "description", "stack_size", "drop_level",
]

MAP_FIELDS = [
    "name", "class_id", "map_tier", "map_area_level", "drop_level",
    "drop_rarities_ids", "tags",
]

RUNE_FIELDS = [
    "name", "class_id", "description", "drop_level", "tags",
]

MONSTER_FIELDS = [
    "name", "rarity", "level", "location",
    "resistance", "weakness", "damage", "modifier",
]

STAT_ID_RE = re.compile(r"^static_stat(\d+)_id$")


def extract_monster_phases(wikitext: str) -> str:
    """Extract phase headers and skill tables from a boss encounter page."""
    lines = wikitext.splitlines()
    output: list[str] = []
    in_table = False

    for line in lines:
        stripped = line.strip()
        # Phase/section headers
        if re.match(r"^===?.+===?$", stripped):
            header = re.sub(r"=+", "", stripped).strip()
            if any(w in header.lower() for w in ["phase", "encounter", "form"]):
                output.append(f"\n[{header}]")
                in_table = False
            continue
        # Table start
        if stripped.startswith("{|"):
            in_table = True
            continue
        # Table end
        if stripped == "|}":
            in_table = False
            continue
        if not in_table:
            continue
        # Header row — extract column names
        if stripped.startswith("!"):
            cols = [c.strip() for c in stripped.lstrip("!").split("!!")]
            if "Skill" in cols:
                output.append("  " + " | ".join(cols))
            continue
        # Row separator
        if stripped == "|-":
            continue
        # Cell content
        if stripped.startswith("|"):
            cell = strip_markup(stripped.lstrip("|").strip())
            if cell and len(cell) > 2:
                output.append(f"  {cell}")

    return "\n".join(output).strip()


def format_monster(data: dict[str, str], phases: str = "") -> str:
    if not data:
        return "No data found."
    lines = []
    for f in MONSTER_FIELDS:
        if f in data:
            val = strip_markup(re.sub(r"<br\s*/?>", " / ", data[f]))
            lines.append(f"{f}: {val}")
    if phases:
        lines.append("\n--- Encounter ---")
        lines.append(phases)
    return "\n".join(lines)


def format_gem(data: dict[str, str]) -> str:
    if not data:
        return "No data found."
    lines = []
    for f in GEM_FIELDS:
        if f in data:
            lines.append(f"{f}: {data[f]}")
    # Collect static stats as id→value pairs
    stats: dict[str, str] = {}
    for key, value in data.items():
        m = STAT_ID_RE.match(key)
        if m:
            n = m.group(1)
            val_key = f"static_stat{n}_value"
            stat_val = data.get(val_key, "?")
            stats[value] = stat_val
    if stats:
        lines.append("static_stats:")
        for stat_id, val in stats.items():
            lines.append(f"  {stat_id} = {val}")
    return "\n".join(lines)


def _format_with_fields(data: dict[str, str], priority_fields: list[str]) -> str:
    lines = []
    shown: set[str] = set()
    for f in priority_fields:
        if f in data:
            lines.append(f"{f}: {data[f]}")
            shown.add(f)
    for key, value in data.items():
        if key not in shown and not key.startswith("recipe") and not key.startswith("metadata"):
            lines.append(f"{key}: {value}")
    return "\n".join(lines)


def format_item(data: dict[str, str]) -> str:
    if not data:
        return "No data found."
    class_id = data.get("class_id", "")
    if class_id == "StackableCurrency":
        return _format_with_fields(data, CURRENCY_FIELDS)
    if class_id == "Map":
        return _format_with_fields(data, MAP_FIELDS)
    if class_id == "SoulCore":
        return _format_with_fields(data, RUNE_FIELDS)
    return _format_with_fields(data, ITEM_FIELDS)
