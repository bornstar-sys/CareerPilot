"""Embed document chunks and one question. No Groq calls or database writes."""

import argparse
import json
import math

from careerpilot.documents import TextDocument, chunk_document
from careerpilot.embeddings import DIMENSIONS, MODEL_NAME, LocalEmbedder


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-download", action="store_true",
                        help="Permit fetching model files if the cache is incomplete.")
    parser.add_argument("--cache-dir", help="Override the default model cache directory.")
    args = parser.parse_args()
    document = TextDocument(
        document_id="demo-android-role",
        source_name="example_android_role.txt",
        text=(
            "Illustrative Android role, not a live job listing.\n"
            "Required skills: Kotlin, Jetpack Compose, Room, and REST APIs.\n"
            "Practice: build an offline notes app and synchronize notes with a server.\n"
            "Use Git to track changes and write tests for the data layer.\n"
        ),
    )
    chunks = chunk_document(document, chunk_size=120, overlap=25)
    embedder = LocalEmbedder(cache_dir=args.cache_dir, local_files_only=not args.allow_download)
    embedded = embedder.embed_chunks(chunks)
    query = embedder.embed_query("How can I practice offline data storage on Android?")
    assert len(embedded) == 3
    for item in embedded:
        assert len(item.embedding.values) == DIMENSIONS
        assert math.isclose(math.hypot(*item.embedding.values), 1.0, abs_tol=1e-6)
    assert len(query.values) == DIMENSIONS
    print(json.dumps({
        "check": "PASS", "model": MODEL_NAME, "provider": "CPU",
        "chunk_count": len(embedded), "dimensions": DIMENSIONS,
        "query_dimensions": len(query.values),
        "chunks": [
            {"chunk_id": item.chunk.chunk_id, "source": item.chunk.source_name,
             "start_char": item.chunk.start_char, "end_char": item.chunk.end_char,
             "vector_norm": round(math.hypot(*item.embedding.values), 6)}
            for item in embedded
        ],
    }, indent=2))


if __name__ == "__main__":
    main()
