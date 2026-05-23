"""
Embed the local corpus into a ChromaDB vector store.

Run build_rag_corpus.py first, then:
    python scripts/embed_corpus.py
    python scripts/embed_corpus.py --corpus ./corpus --db ./chroma_db

Uses the default all-MiniLM-L6-v2 model (downloaded ~90MB on first run).
Re-run after adding new corpus files — existing docs are upserted, not duplicated.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def main() -> None:
    parser = argparse.ArgumentParser(description="Embed PoE2 corpus into ChromaDB")
    parser.add_argument("--corpus", default="./corpus", help="Corpus directory (default: ./corpus)")
    parser.add_argument("--db", default="./chroma_db", help="ChromaDB directory (default: ./chroma_db)")
    parser.add_argument("--batch", type=int, default=50, help="Upsert batch size (default: 50)")
    args = parser.parse_args()

    corpus_dir = Path(args.corpus)
    db_dir = Path(args.db)

    if not corpus_dir.exists():
        print(f"Corpus not found at {corpus_dir}. Run build_rag_corpus.py first.")
        sys.exit(1)

    try:
        import chromadb
        from chromadb.utils.embedding_functions import DefaultEmbeddingFunction
    except ImportError:
        print("chromadb not installed. Run: pip install -e '.[rag]'")
        sys.exit(1)

    print(f"Loading corpus from {corpus_dir.resolve()}")
    print(f"Writing DB to    {db_dir.resolve()}")
    print("(First run downloads ~90MB embedding model)\n")

    docs, ids, metadatas = [], [], []
    for md_file in sorted(corpus_dir.rglob("*.md")):
        content = md_file.read_text(encoding="utf-8").strip()
        if not content:
            continue
        category = md_file.parent.name
        title = md_file.stem.replace("_", " ")
        doc_id = f"{category}/{md_file.stem}"
        docs.append(content)
        ids.append(doc_id)
        metadatas.append({"category": category, "title": title})

    print(f"Found {len(docs)} documents\n")

    client = chromadb.PersistentClient(path=str(db_dir))
    ef = DefaultEmbeddingFunction()
    collection = client.get_or_create_collection(
        name="poe2",
        embedding_function=ef,
        metadata={"hnsw:space": "cosine"},
    )

    for i in range(0, len(docs), args.batch):
        batch_end = min(i + args.batch, len(docs))
        collection.upsert(
            documents=docs[i:batch_end],
            ids=ids[i:batch_end],
            metadatas=metadatas[i:batch_end],
        )
        print(f"  embedded {batch_end}/{len(docs)}")

    print(f"\nDone. {collection.count()} documents in collection 'poe2'.")


if __name__ == "__main__":
    main()
