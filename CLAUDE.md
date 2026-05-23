# poe2-mcp

Local MCP server for Path of Exile 2 game data, backed by poewiki.net.

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
  wiki.py    — poewiki.net API client + wikitext parser + formatters
  server.py  — FastMCP server, all tool definitions
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
