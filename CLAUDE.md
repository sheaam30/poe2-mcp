# poe2-mcp

Local MCP server for Path of Exile 2 game data, backed by poe2wiki.net.

## Running the server

```bash
.venv/bin/poe2-mcp
```

The server speaks MCP over stdio. It's registered in `~/.claude.json` and starts automatically when Claude Code is opened in this project.

## Development

Python 3.13 via Homebrew. Always use the venv:

```bash
.venv/bin/python3.13   # interpreter
.venv/bin/pip          # package manager
.venv/bin/poe2-mcp     # entry point (installed editable via pip install -e .)
```

Re-install after editing `pyproject.toml`:
```bash
.venv/bin/pip install -e .
```

## Project layout

```
poe2_mcp/
  wiki.py    — poe2wiki.net API client + wikitext parser + formatters
  server.py  — FastMCP server, all tool definitions
  rag.py     — ChromaDB wrapper for local semantic search
scripts/
  build_rag_corpus.py  — crawl wiki categories → corpus/ markdown files
  embed_corpus.py      — embed corpus/ into chroma_db/ vector store
corpus/      — generated wiki markdown (gitignored, run build_rag_corpus.py)
chroma_db/   — ChromaDB vector index (gitignored, run embed_corpus.py)
pyproject.toml
```

## Data source

All data comes from **poe2wiki.net** (the dedicated PoE2 wiki) via two MediaWiki API actions:
- `opensearch` — keyword search returning page titles
- `parse&prop=wikitext` — full wikitext for a named page

The Cargo API (structured SQL-like queries) returns errors for all table names — use the parse API instead.

Responses are cached in-memory for **24 hours** (`CACHE_TTL` in `wiki.py`). Wiki data only changes on patches, so this is intentional. Restart the server to bust the cache.

Concurrent requests are capped at 3 via a semaphore (`_sem`) to prevent timeouts.

## Tools

| Tool | Description |
|---|---|
| `search_wiki(query, limit)` | Keyword search — returns page titles |
| `get_item(name)` | Parse `{{Item}}` template for base types and uniques |
| `get_gem(name)` | Parse gem data — tags, description, cast time, stats |
| `search_gems(name, gem_tag)` | Search + filter gems by tag (Fire, AoE, Support, etc.) |
| `get_passive(name)` | Extract prose description for passive nodes |
| `get_monster(name)` | Parse `{{MonsterBox}}` template + phase/skill tables |
| `get_mechanic(name)` | Extract prose for mechanics pages (crit, ailments, etc.) |
| `search_items(query, item_class)` | Search non-gem items, filter by class |
| `search_corpus(query, category, n_results)` | Semantic search over local ChromaDB index |

## RAG corpus

`scripts/build_rag_corpus.py` crawls 14 wiki categories + 25 standalone pages → `corpus/` markdown files.
`scripts/embed_corpus.py` embeds those files into `chroma_db/` using `all-MiniLM-L6-v2` via ChromaDB.

Install RAG deps: `.venv/bin/pip install "chromadb>=0.5.0"` (not in default install — optional `[rag]` group).

`search_corpus` gracefully returns an error message if `chroma_db/` doesn't exist, so the server still starts without it.

## Wikitext parsing notes

Items and gems use a `{{Item|key = value}}` template — `parse_item_template()` extracts this into a dict.

Passive pages use prose with `{{Passive skill box|Name}}` — no structured template, so `extract_prose()` strips markup and returns the first meaningful paragraphs.

`strip_markup()` handles common wiki templates:
- `{{il|name}}` / `{{ml|name}}` / `{{sl|name}}` → display name
- `{{c|color|text}}` → text
- `[[link|display]]` → display, `[[link]]` → link

## Known gaps

- **Affixes/mods**: No structured affix data — the Cargo API is unavailable. Workaround: `search_wiki("bleed")` then read individual pages.
- **Runes**: Covered as items via `get_item`.
- **Ascendancy passives**: Covered via `get_passive` for any named node.
- **Level scaling**: Gem level tables are in the wikitext but not yet parsed — only static stats are returned.
- **Ascendancy passive skills / Atlas passive skills**: Wiki category pages return no members — not yet populated for early access content.
- **Cargo SQL leakage**: Some mechanic pages (e.g. Freeze) embed Cargo SQL in wikitext; `extract_prose` filters these via `_SQL_RE` in `wiki.py`.
