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


async def search_pages(query: str, limit: int = 10) -> list[str]:
    data = await _api({
        "action": "opensearch",
        "format": "json",
        "search": query,
        "namespace": 0,
        "limit": limit,
    })
    return data[1] if len(data) > 1 else []


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


def parse_item_template(wikitext: str) -> dict[str, str]:
    """Extract key-value pairs from the {{Item|...}} template block."""
    match = re.search(r"\{\{Item\s*\n(.*?)\n\}\}", wikitext, re.DOTALL)
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


def extract_prose(wikitext: str, max_chars: int = 800) -> str:
    """Return the first meaningful prose block from a wiki page."""
    lines = []
    for line in wikitext.splitlines():
        stripped = line.strip()
        # Skip template lines, headers, table markup, category links
        if (
            stripped.startswith("{{")
            or stripped.startswith("|")
            or stripped.startswith("!")
            or stripped.startswith("==")
            or stripped.startswith("[[Category")
            or stripped.startswith("{|")
            or stripped.startswith("|-")
            or not stripped
        ):
            continue
        cleaned = strip_markup(stripped)
        if len(cleaned) > 20:
            lines.append(cleaned)
        if sum(len(l) for l in lines) >= max_chars:
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

STAT_ID_RE = re.compile(r"^static_stat(\d+)_id$")


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


def format_item(data: dict[str, str]) -> str:
    if not data:
        return "No data found."
    lines = []
    shown: set[str] = set()
    for f in ITEM_FIELDS:
        if f in data:
            lines.append(f"{f}: {data[f]}")
            shown.add(f)
    # Include implicits and remaining non-recipe fields
    for key, value in data.items():
        if key not in shown and not key.startswith("recipe") and not key.startswith("metadata"):
            lines.append(f"{key}: {value}")
    return "\n".join(lines)
