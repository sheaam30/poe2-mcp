# poe2-mcp

A locally-hosted MCP server that gives Agents access to Path of Exile 2 game data via [poe2wiki.net](https://www.poe2wiki.net).

## Tools

| Tool | Description |
|---|---|
| `search_wiki` | Keyword search — returns matching page titles |
| `get_item` | Full stats for any item (base types, uniques, currency, waystones, runes) |
| `get_gem` | Skill gem details: description, tags, cast time, mana cost, static stats |
| `search_gems` | Search gems by name + optional tag filter (Fire, AoE, Support, Melee…) |
| `search_items` | Search non-gem items by name + optional class filter (Currency, Map, SoulCore…) |
| `get_monster` | Boss/unique monster stats: resistances, weaknesses, damage types, phase guide |
| `get_mechanic` | Game mechanic explanations: Critical Strike, Ailments, Freeze, Leech, Evasion… |
| `get_passive` | Description of any passive tree node, keystone, or notable |
| `search_corpus` | Semantic search over local knowledge base (mechanics, monsters, ascendancies, passives, endgame) |

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

**Items & gear**
- "What are the stats on a Vaal Axe?"
- "Show me the Kingsguard unique body armour"
- "What does an Exalted Orb do and how does it stack?"
- "Find me all Tier 5 waystone details"

**Gems**
- "Show me all lightning support gems"
- "What's the Galvanic Shards gem description and tags?"
- "Find me AoE fire spell gems"

**Passives & builds**
- "What does Resolute Technique do?"
- "Explain the Acrobatics keystone"

**Currency & endgame**
- "What does a Chaos Orb do?"
- "Find all rune types"
- "Search the wiki for Breach mechanics"

## Local RAG corpus (semantic search)

`search_corpus` provides semantic similarity search over a local ChromaDB index — useful for open-ended questions like "what counters fire damage?" or "how does ascendancy X work?".

**First-time setup:**

```bash
# Install RAG dependencies
.venv/bin/pip install "chromadb>=0.5.0"

# Crawl the wiki and build markdown files (~207 pages)
.venv/bin/python scripts/build_rag_corpus.py

# Embed into ChromaDB (downloads ~80MB model on first run)
.venv/bin/python scripts/embed_corpus.py
```

The corpus and vector DB are local-only (gitignored). Re-run both scripts after game patches to pick up wiki updates.

**Covered categories:** mechanics, ailments, ascendancy classes, keystone passives, act bosses, areas, endgame (Atlas, Breach, Delirium, Ritual, Waystone)

## Data & caching

Data is fetched from [poe2wiki.net](https://www.poe2wiki.net)'s MediaWiki API. Responses are cached in-memory for 24 hours — wiki data only changes on game patches, so this avoids hammering the wiki. Restart the server to clear the cache.

Concurrent requests to the wiki are capped at 3 to prevent timeouts on bulk searches.

## Limitations

- No structured affix/modifier data (wiki's Cargo API is unavailable — use `search_wiki` then read individual pages)
- Gem level scaling tables are not yet parsed — only static stats returned
- Passive data is prose-only (no numeric stats in structured form)
- Wiki coverage is incomplete for some early access content — pages may not exist yet for newer skills
