"""
Build a RAG corpus from poe2wiki.net.

Crawls wiki categories and dumps each page as a markdown file in ./corpus/.
Use the resulting files with any vector DB (ChromaDB, Pinecone, pgvector, etc.)

Usage:
    python scripts/build_rag_corpus.py
    python scripts/build_rag_corpus.py --output ./my-corpus --delay 0.5

The script respects the wiki's rate limits by adding a small delay between
requests (default 0.3s). Restart to resume — already-written files are skipped.
"""
import argparse
import asyncio
import re
import sys
import time
from pathlib import Path

# Allow running from the repo root
sys.path.insert(0, str(Path(__file__).parent.parent))

from poe2_mcp import wiki

# Categories to crawl and their output subdirectory
CRAWL_PLAN = [
    # (category_name, subdirectory, max_pages)
    ("Ailments",                        "mechanics",    50),
    ("Attributes",                      "mechanics",    20),
    ("Ascendancy classes",              "ascendancy",   30),
    ("Ascendancy passive skills",       "ascendancy",  200),
    ("Atlas passive skills",            "atlas",       100),
    ("Keystone passive skills",         "passives",     50),
    ("Act 1 unique monsters",           "monsters",     30),
    ("Act 2 unique monsters",           "monsters",     30),
    ("Act 3 unique monsters",           "monsters",     30),
    ("Act 4 unique monsters",           "monsters",     30),
    ("Acts",                            "acts",         20),
    ("Areas",                           "areas",        50),
]

# Standalone pages to always include (mechanics without a clean category)
STANDALONE_PAGES = [
    ("Critical strike",     "mechanics"),
    ("Evasion",             "mechanics"),
    ("Block",               "mechanics"),
    ("Armour",              "mechanics"),
    ("Energy shield",       "mechanics"),
    ("Leech",               "mechanics"),
    ("Stun",                "mechanics"),
    ("Mana",                "mechanics"),
    ("Life",                "mechanics"),
    ("Ailment",             "mechanics"),
    ("Damage",              "mechanics"),
    ("Penetration",         "mechanics"),
    ("Resistance",          "mechanics"),
    ("Accuracy",            "mechanics"),
    ("Cast speed",          "mechanics"),
    ("Attack speed",        "mechanics"),
    ("Movement speed",      "mechanics"),
    ("Area of effect",      "mechanics"),
    ("Projectile",          "mechanics"),
    ("Boss",                "mechanics"),
    ("Waystone",            "endgame"),
    ("Atlas",               "endgame"),
    ("Breach",              "endgame"),
    ("Delirium",            "endgame"),
    ("Ritual",              "endgame"),
]


def slugify(title: str) -> str:
    return re.sub(r"[^\w\-]", "_", title).strip("_")


def page_to_markdown(title: str, wikitext: str) -> str:
    """Convert a wiki page to a clean markdown string for embedding."""
    data = wiki.parse_monster_template(wikitext)
    if data:
        # Boss/monster page
        lines = [f"# {title}", ""]
        for field in wiki.MONSTER_FIELDS:
            if field in data:
                val = wiki.strip_markup(re.sub(r"<br\s*/?>", " / ", data[field]))
                lines.append(f"**{field}**: {val}")
        phases = wiki.extract_monster_phases(wikitext)
        if phases:
            lines += ["", "## Encounter", phases]
        prose = wiki.extract_prose(wikitext, max_chars=1500)
        if prose:
            lines += ["", "## Description", prose]
        return "\n".join(lines)

    item_data = wiki.parse_item_template(wikitext)
    if item_data:
        # Item/gem/currency page — use formatted output
        lines = [f"# {title}", ""]
        class_id = item_data.get("class_id", "")
        if "Skill Gem" in class_id:
            lines.append(wiki.format_gem(item_data))
        else:
            lines.append(wiki.format_item(item_data))
        return "\n".join(lines)

    # Prose page (mechanics, passives, ascendancy)
    prose = wiki.extract_prose(wikitext, max_chars=3000)
    if not prose:
        return ""
    return f"# {title}\n\n{prose}"


async def crawl(output_dir: Path, delay: float) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    written = 0
    skipped = 0

    async def process_page(title: str, subdir: str) -> None:
        nonlocal written, skipped
        dest = output_dir / subdir / f"{slugify(title)}.md"
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            skipped += 1
            return
        wikitext = await wiki.fetch_wikitext(title)
        if not wikitext:
            return
        content = page_to_markdown(title, wikitext)
        if content.strip():
            dest.write_text(content, encoding="utf-8")
            written += 1
            print(f"  wrote: {dest.relative_to(output_dir)}")
        await asyncio.sleep(delay)

    # Category crawls
    for category, subdir, max_pages in CRAWL_PLAN:
        print(f"\n[category] {category} → {subdir}/")
        titles = await wiki.list_category(category, limit=max_pages)
        for title in titles:
            await process_page(title, subdir)

    # Standalone pages
    print("\n[standalone pages]")
    for title, subdir in STANDALONE_PAGES:
        await process_page(title, subdir)

    print(f"\nDone. {written} pages written, {skipped} already existed.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build PoE2 RAG corpus from poe2wiki.net")
    parser.add_argument("--output", default="./corpus", help="Output directory (default: ./corpus)")
    parser.add_argument("--delay", type=float, default=0.3, help="Delay between requests in seconds (default: 0.3)")
    args = parser.parse_args()

    output_dir = Path(args.output)
    print(f"Building corpus in {output_dir.resolve()}")
    print(f"Request delay: {args.delay}s\n")

    asyncio.run(crawl(output_dir, args.delay))


if __name__ == "__main__":
    main()
