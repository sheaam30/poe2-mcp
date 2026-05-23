# poe2-mcp

A locally-hosted MCP server that gives Claude access to Path of Exile 2 game data via [poe2wiki.net](https://www.poe2wiki.net).

## Tools

- **`search_wiki`** — keyword search across the wiki, returns matching page titles
- **`get_item`** — full stats for any item (base types, uniques): damage, requirements, implicits
- **`get_gem`** — skill gem details: description, tags, cast time, mana cost, static stats
- **`search_gems`** — search gems by name fragment + optional tag filter (Fire, AoE, Support, Melee…)
- **`get_passive`** — description of any passive tree node, keystone, or notable

## Requirements

- Python 3.10+ (3.13 recommended)
- No API keys needed — all data is public

## Setup

```bash
git clone <repo>
cd poe2-mcp

# Create venv and install
python3 -m venv .venv
.venv/bin/pip install -e .

# Register with Claude Code
claude mcp add poe2 /path/to/poe2-mcp/.venv/bin/poe2-mcp
```

Then restart Claude Code — `claude mcp list` should show `poe2: ✓ Connected`.

## Usage examples

Once registered, just ask Claude naturally:

- "What are the stats on a Vaal Axe?"
- "Show me all lightning support gems"
- "What does Resolute Technique do?"
- "Find me unique items related to bleed"
- "What's the Fireball gem description and tags?"

## Data & caching

Data is fetched from [poe2wiki.net](https://www.poe2wiki.net)'s MediaWiki API. Responses are cached in-memory for 24 hours — wiki data only changes on game patches, so this avoids hammering the wiki. Restart the server to clear the cache.

Concurrent requests to the wiki are capped at 3 to prevent timeouts on bulk searches.

## Limitations

- No structured affix/modifier data (wiki's Cargo API is unavailable — use `search_wiki` then read individual pages)
- Gem level scaling tables are not yet parsed — only static stats returned
- Passive data is prose-only (no numeric stats in structured form)
- Wiki coverage is incomplete for some early access content — pages may not exist yet for newer skills
