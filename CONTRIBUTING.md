# Contributing

## Setup

```bash
git clone https://github.com/sheaam30/poe2-mcp
cd poe2-mcp
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

Register the server with Claude Code:

```bash
claude mcp add poe2 /path/to/poe2-mcp/.venv/bin/poe2-mcp
```

Restart Claude Code after registering. Run `claude mcp list` to confirm `poe2: ✓ Connected`.

## Project layout

```
poe2_mcp/
  wiki.py    — poe2wiki.net API client, wikitext parser, formatters
  server.py  — FastMCP server and all tool definitions
```

New tools go in `server.py`. Parsing or formatting logic goes in `wiki.py`.

## Running locally

```bash
.venv/bin/poe2-mcp          # starts the stdio server (Claude Code manages this)
```

To test a tool without Claude Code, use the Python API directly:

```python
import asyncio
from poe2_mcp import wiki

async def test():
    titles = await wiki.search_pages("Galvanic Shards")
    wikitext = await wiki.fetch_wikitext(titles[0])
    data = wiki.parse_item_template(wikitext)
    print(wiki.format_gem(data))

asyncio.run(test())
```

## Linting

```bash
.venv/bin/ruff check poe2_mcp/
```

CI runs this on every PR. Fix all errors before opening a PR.

## Adding a new tool

1. Add any new parsing/formatting helpers to `wiki.py`.
2. Add the `@mcp.tool()` decorated function to `server.py`.
3. Update the tools table in `README.md`.
4. Test it live: restart Claude Code and ask Claude to use the tool.
5. Paste example output in the PR description.

## Data source

All data comes from [poe2wiki.net](https://www.poe2wiki.net) via its MediaWiki API (`/api.php`). The wiki uses the `{{Item}}` template for structured data (items, gems, currency, waystones, runes). Prose pages (passives, bosses, mechanics) are extracted via `extract_prose()`.

Responses are cached in-memory for 24 hours. Restart the server to bust the cache.

## PR guidelines

- One logical change per PR — don't bundle a new tool with unrelated refactors.
- Include live tool output in the PR description.
- Keep tool docstrings concise — Claude uses them to decide when to call the tool.
- Don't break existing tools. Run all tools you touched before submitting.
